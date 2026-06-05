"""
BAX-423 Technique #1 — Lecture 5: TF-IDF + SVD (LSA) Embeddings + Cosine Similarity
BAX-423 Technique #2 — Lecture 7: Multi-Stage Ranking Pipeline
  Stage 1: Embedding-based candidate retrieval
  Stage 2: Hard filters (dealbreakers, salary, visa)
  Stage 3: Feature-weighted scoring
  Stage 4: Diversity re-ranking (MMR)
Evaluation metric: NDCG@10
"""
from __future__ import annotations
import math
import re
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize


US_LOCATION_HINTS = [
    "united states", "remote", "bay area", "san francisco", "new york", "nyc",
    "california", "texas", "washington", "massachusetts", "illinois", "georgia",
    "florida", "palo alto", "sunnyvale", "manhattan", "charlotte", "atlanta",
]

# ── Lecture 5: Dense Semantic Embeddings ─────────────────────────────────────

class EmbeddingIndex:
    """
    TF-IDF → TruncatedSVD (150d LSA) → L2-normalize → cosine similarity.
    Conceptually identical to Sentence-BERT + FAISS from Lecture 5.
    """
    def __init__(self):
        self.vectorizer = None
        self.svd = None
        self.matrix = None
        self.job_ids = []

    def build(self, jobs: list[dict]):
        texts = [_job_text(j) for j in jobs]
        self.job_ids = [j["job_id"] for j in jobs]
        self.vectorizer = TfidfVectorizer(max_features=20000, ngram_range=(1, 2), sublinear_tf=True, min_df=2)
        tfidf = self.vectorizer.fit_transform(texts)
        n_comp = min(150, tfidf.shape[0] - 1, tfidf.shape[1] - 1)
        self.svd = TruncatedSVD(n_components=max(1, n_comp), random_state=42)
        dense = self.svd.fit_transform(tfidf).astype(np.float32)
        self.matrix = normalize(dense)
        var = self.svd.explained_variance_ratio_.sum()
        print(f"[Embedding] Built index: {len(jobs)} jobs, {n_comp}d, {var:.1%} variance explained")

    def search(self, query: str, top_k: int = 500) -> list[tuple[str, float]]:
        if self.matrix is None or not self.job_ids:
            return []
        q_tfidf = self.vectorizer.transform([query])
        q_dense = self.svd.transform(q_tfidf).astype(np.float32)
        q_norm = normalize(q_dense)
        scores = (self.matrix @ q_norm.T).flatten()
        top_k = min(top_k, len(self.job_ids))
        indices = np.argsort(scores)[::-1][:top_k]
        return [(self.job_ids[i], float(scores[i])) for i in indices]


def _job_text(job: dict) -> str:
    skills = " ".join(job.get("skills_extracted", []))
    title = (job.get("title", "") + " ") * 3  # weight title heavily
    return f"{title}{skills} {job.get('industry', '')} {job.get('description', '')[:300]}"


def _profile_query(profile: dict, criteria: dict) -> str:
    target_role = criteria.get("target_role", "")
    parts = [
        (target_role + " ") * 5,  # repeat target role 5x for strong signal
        " ".join(criteria.get("skills", [])),
        " ".join(profile.get("skills", [])),
        " ".join([f"{e.get('title','')} {e.get('description','')}" for e in profile.get("experience", [])]),
    ]
    return " ".join(p for p in parts if p)


# ── Lecture 7: Multi-Stage Ranking Pipeline ───────────────────────────────────

def run_pipeline(jobs: list[dict], profile: dict, criteria: dict,
                 index: EmbeddingIndex, feedback_weights: dict,
                 limit: int = 10, rejected_ids: set = None,
                 feedback_labels: dict[str, float] = None) -> dict:
    """
    4-stage pipeline (Lecture 7):
    Stage 1: Embedding retrieval
    Stage 2: Hard filters (role fit, dealbreakers, visa/location constraints)
    Stage 3: Feature-weighted scoring
    Stage 4: MMR diversity re-ranking
    """
    rejected_ids = rejected_ids or set()

    # Stage 1: Embedding retrieval
    query = _profile_query(profile, criteria)
    retrieved = index.search(query, top_k=1000)
    emb_score_map = {jid: score for jid, score in retrieved}
    retrieved_ids = set(emb_score_map.keys())
    candidates = [j for j in jobs if j["job_id"] in retrieved_ids and j["job_id"] not in rejected_ids]
    # Fallback: if retrieval returns too few, use all jobs
    if len(candidates) < 20:
        candidates = [j for j in jobs if j["job_id"] not in rejected_ids]
    n_retrieved = len(candidates)

    # Stage 2: Hard filters
    passed, excluded = [], []
    for job in candidates:
        reason = _hard_filter(job, criteria, profile)
        if reason:
            excluded.append({**job, "filter_reason": reason})
        else:
            passed.append(job)

    if len(passed) < limit:
        candidate_ids = {j["job_id"] for j in candidates}
        for job in jobs:
            if job["job_id"] in candidate_ids or job["job_id"] in rejected_ids:
                continue
            reason = _hard_filter(job, criteria, profile)
            if reason:
                if len(excluded) < 20:
                    excluded.append({**job, "filter_reason": reason})
            else:
                passed.append(job)
            if len(passed) >= max(limit * 3, 30):
                break
    n_filtered = len(passed)

    # Stage 3: Scoring
    profile_skills = _profile_skill_set(profile, criteria)
    scored = []
    for job in passed:
        emb = emb_score_map.get(job["job_id"], 0.0)
        s = _score(job, profile, criteria, profile_skills, emb, feedback_weights)
        scored.append({**job, **s})
    scored.sort(key=lambda x: x["match_score"], reverse=True)

    # Stage 4: Diversity re-ranking
    reranked = _diversity_rerank(scored, criteria, limit)

    results = reranked[:limit]
    feedback_ndcg = _feedback_ndcg_at_k(reranked, feedback_labels or {}, k=10)

    return {
        "results": results,
        "excluded": excluded[:20],
        "benchmark": feedback_ndcg,
        "pipeline_counts": {
            "retrieved": n_retrieved,
            "after_hard_filters": n_filtered,
            "returned": len(results),
        },
    }


def _hard_filter(job: dict, criteria: dict, profile: dict) -> str:
    """Returns reason string if job should be excluded, else empty string.
    Missing salary is not a hard filter because the Kaggle snapshot often omits it.
    Missing/unknown metadata is penalized in scoring and surfaced in explanations."""
    dealbreakers = criteria.get("dealbreakers", [])
    title = (job.get("title", "") or "").lower()
    description = (job.get("description", "") or "").lower()
    employment = (job.get("employment_type", "") or "").lower()
    text = f"{title} {employment} {description}"
    role_line = _role_context_text(job)

    role_reason = _role_filter_reason(job, criteria)
    if role_reason:
        return role_reason

    salary_min_req = int(criteria.get("salary_min", 0) or 0)
    salary_max = int(job.get("salary_max", 0) or 0)
    if salary_min_req and salary_max and salary_max < salary_min_req:
        return "Below minimum salary preference"

    if "No Defense Companies" in dealbreakers:
        defense_text = " ".join([
            job.get("title", "") or "",
            job.get("company", "") or "",
            job.get("industry", "") or "",
            job.get("description", "") or "",
        ]).lower()
        defense_terms = [
            "defense", "defence", "military", "lockheed", "raytheon", "northrop",
            "general dynamics", "general atomics", "boeing defense", "bae systems",
            "l3harris", "anduril", "dod", "department of defense", "national security",
            "intelligence community", "security clearance", "top secret", "secret clearance",
            "air force", "army", "navy", "naval", "marine corps",
        ]
        if any(w in defense_text for w in defense_terms):
            return "Defense company (dealbreaker)"

    if "No Contract Roles" in dealbreakers:
        contract_text = any(p in text for p in [
            "contract role", "contract position", "contract job", "contract-to-hire",
            "contract to hire", "temporary role", "temporary position", "months contract",
            "month contract", "duration:", "c2c", "w2 contract", "corp-to-corp",
        ])
        if any(w in f"{title} {employment}" for w in ["contract", "contractor", "freelance", "self-employed", "1099"]) or contract_text:
            return "Contract role (dealbreaker)"

    if "No Temp Roles" in dealbreakers:
        if any(w in text for w in ["temp", "temporary", "seasonal"]):
            return "Temp role (dealbreaker)"

    if "No Unpaid Roles" in dealbreakers:
        if any(w in text for w in ["unpaid", "volunteer", "no compensation", "commission only", "commission-only"]):
            return "Unpaid role (dealbreaker)"

    if "No Senior Roles" in dealbreakers:
        if _has_senior_signal(title) or _has_senior_signal(role_line):
            return "Senior role (dealbreaker)"

    if "No Staff Roles" in dealbreakers:
        if "staff" in title or "staff" in role_line:
            return "Staff role (dealbreaker)"

    if "No Junior Roles" in dealbreakers:
        if any(w in title for w in ["junior", "jr.", "trainee", "intern", "entry level", "entry-level"]):
            return "Junior role (dealbreaker)"

    if "No Startups" in dealbreakers:
        size = int(job.get("company_size", 0) or 0)
        if 0 < size < 100:
            return "Startup (dealbreaker)"

    if "No 3+ Years Required" in dealbreakers:
        required_years = max(int(job.get("required_years", 0) or 0), _extract_required_years(text))
        if required_years >= 3:
            return "3+ years required (dealbreaker)"
        if _has_senior_signal(title) or _has_senior_signal(role_line):
            return "3+ years likely required (dealbreaker)"

    if "No 5+ Years ML Required" in dealbreakers:
        required = max(int(job.get("required_years", 0) or 0), _extract_required_years(text))
        if required >= 5 and any(w in text for w in ["machine learning", " ml ", "pytorch", "tensorflow"]):
            return "5+ years ML required (dealbreaker)"

    # Visa — only exclude if explicitly says no sponsorship
    visa_req = (criteria.get("visa_sponsorship", "") or "").lower()
    if "Sponsorship Required" in dealbreakers or "h-1b" in visa_req or "required" in visa_req:
        visa_text = (job.get("visa", "") or "").lower()
        if any(w in visa_text for w in ["no sponsorship", "us citizen only", "citizens only", "no visa"]):
            return "No visa sponsorship available"
        if any(w in text for w in [
            "us citizen only", "u.s. citizen only", "must be us citizen",
            "must be a us citizen", "must be a u.s. citizen", "clearance required",
            "no sponsorship", "unable to sponsor", "cannot sponsor",
        ]):
            return "No visa sponsorship available"

    location_pref = (criteria.get("location", "") or "").lower()
    if "us only" in location_pref or location_pref.strip() == "us":
        loc = (job.get("location", "") or "").lower()
        if loc and not any(h in loc for h in US_LOCATION_HINTS):
            return "Outside US preference"

    return ""


def _role_context_text(job: dict) -> str:
    text = " ".join([
        job.get("title", "") or "",
        (job.get("description", "") or "")[:300],
    ]).lower()
    markers = ["job title:", "title:", "position:", "role:"]
    for marker in markers:
        if marker in text:
            start = text.find(marker)
            return text[start:start + 160]
    return text[:180]


def _has_senior_signal(text: str) -> bool:
    text = (text or "").lower()
    return bool(re.search(r"\b(senior|sr\.?|lead|principal|director|manager)\b", text))


def _extract_required_years(text: str) -> int:
    text = (text or "").lower()
    patterns = [
        r"(?:minimum|min\.?|at least|required|requires?)\s*:?\s*(\d{1,2})\+?\s*(?:years|yrs)",
        r"(\d{1,2})\+?\s*(?:years|yrs)\s+(?:of\s+)?(?:experience|exp|required)",
        r"(?:experience|exp)\s*:?\s*(\d{1,2})\+?\s*(?:years|yrs)",
    ]
    values = []
    for pattern in patterns:
        values.extend(int(m.group(1)) for m in re.finditer(pattern, text))
    return max(values) if values else 0


def _score(job: dict, profile: dict, criteria: dict,
           profile_skills: set, emb_score: float, feedback_weights: dict) -> dict:
    job_skill_map = _normalized_job_skills(job.get("skills_extracted", []))
    job_skill_map.update(_description_requirement_skills(job))
    job_skill_keys = set(job_skill_map)
    matched_skills = {k for k in job_skill_keys if _skill_covered(k, profile_skills)}
    missing_keys = [k for k in sorted(job_skill_keys) if not _skill_covered(k, profile_skills)]
    missing_skills = [job_skill_map[k] for k in missing_keys][:5]

    skill_match = len(matched_skills) / max(len(job_skill_keys), 1) if job_skill_keys else 0.5
    location_match = _location_score(criteria.get("location", "") or profile.get("current_location", ""), job.get("location", ""))
    salary_match = _salary_score(criteria.get("salary_min", 0) or 0, job.get("salary_min", 0) or 0, job.get("salary_max", 0) or 0)
    exp_match = _exp_score(profile, job.get("required_years", 0) or 0)
    seniority_match = _seniority_score(profile, job)
    feedback_boost = _feedback_score(job, feedback_weights)
    role_match = _role_score(job, criteria)
    preference_match = _preference_score(job, criteria)
    metadata_score = _metadata_score(job)

    total = (
        emb_score * 18 +
        skill_match * 18 +
        role_match * 24 +
        preference_match * 10 +
        location_match * 12 +
        salary_match * 8 +
        exp_match * 6 +
        seniority_match * 4 +
        metadata_score * 4 +
        min(feedback_boost * 15, 20)
    )
    if seniority_match < 0.5:
        total -= 12
    match_score = round(max(1, min(99, total)), 1)

    return {
        "match_score": match_score,
        "missing_skills": missing_skills,
        "why_ranked_here": {
            "skill_match": round(skill_match * 100, 1),
            "location_match": round(location_match * 100, 1),
            "salary_match": round(salary_match * 100, 1),
            "experience_match": round(exp_match * 100, 1),
            "seniority_match": round(seniority_match * 100, 1),
            "embedding_similarity": round(emb_score * 100, 1),
            "role_match": round(role_match * 100, 1),
            "preference_match": round(preference_match * 100, 1),
            "metadata_completeness": round(metadata_score * 100, 1),
            "dealbreaker_check": "Passed",
        },
    }


def _location_score(preferred: str, job_loc: str) -> float:
    p, j = (preferred or "").lower(), (job_loc or "").lower()
    if not p: return 0.75
    if not j or j in ("nan", "unknown"):
        return 0.15
    if "any us" in p and any(h in j for h in US_LOCATION_HINTS): return 0.95
    if ("us only" in p or p.strip() == "us") and any(h in j for h in US_LOCATION_HINTS): return 1.0
    if "remote" in p and "remote" in j: return 1.0
    if "remote" in j: return 0.8
    cities = [c.strip() for c in p.replace(",", " ").split() if len(c) > 2]
    for city in cities:
        if city in j: return 1.0
    return 0.4


def _salary_score(min_req: int, job_min: int, job_max: int) -> float:
    if not min_req: return 0.8
    if job_max == 0: return 0.25
    if job_max >= min_req * 1.1: return 1.0
    if job_max >= min_req: return 0.85
    return max(0.1, job_max / min_req)


def _exp_score(profile: dict, required: int) -> float:
    yoe = max(1, len(profile.get("experience", [])) * 2)
    if yoe >= required: return 1.0
    return max(0.3, yoe / max(required, 1))


def _seniority_score(profile: dict, job: dict) -> float:
    title = (job.get("title", "") or "").lower()
    role_line = _role_context_text(job)
    if not (_has_senior_signal(title) or _has_senior_signal(role_line)):
        return 1.0
    profile_text = " ".join([
        " ".join(e.get("title", "") for e in profile.get("experience", [])),
        " ".join(e.get("description", "") for e in profile.get("experience", [])),
        " ".join(f"{e.get('degree','')} {e.get('major','')}" for e in profile.get("education", [])),
    ]).lower()
    exp_count = len(profile.get("experience", []))
    student_or_new_grad = any(term in profile_text for term in ["student", "graduate researcher", "intern", "msba", "master"]) and exp_count <= 2
    if student_or_new_grad:
        return 0.35
    return 0.8


def _visa_score(auth: str, need: str, job_visa: str) -> float:
    auth_l = auth.lower()
    if "citizen" in auth_l or "permanent" in auth_l or "green card" in auth_l: return 1.0
    job_l = job_visa.lower()
    if any(w in job_l for w in ["h-1b", "h1b", "sponsor", "opt", "friendly"]): return 1.0
    if "required" in (need or "").lower(): return 0.3
    return 0.75


def _metadata_score(job: dict) -> float:
    checks = [
        bool(job.get("location")),
        bool(job.get("salary_max")),
        bool(job.get("link")),
        bool(job.get("skills_extracted")),
    ]
    return sum(checks) / len(checks)


SKILL_ALIASES = {
    "pytorch": ["pytorch", "basic pytorch", "torch"],
    "tensorflow": ["tensorflow", "tf"],
    "sklearn": ["scikit-learn", "scikit learn", "sklearn", "scikit"],
    "python": ["python"],
    "sql": ["sql"],
    "pandas": ["pandas"],
    "numpy": ["numpy"],
    "r": ["r"],
    "tableau": ["tableau"],
    "power_bi": ["power bi", "powerbi"],
    "spark": ["spark", "pyspark"],
    "pyspark": ["pyspark"],
    "kafka": ["kafka"],
    "kubernetes": ["kubernetes", "k8s"],
    "aws": ["aws", "amazon web services"],
    "java": ["java"],
    "cpp": ["c++", "cpp"],
    "nlp": ["nlp", "natural language processing"],
    "computer_vision": ["computer vision", "cv"],
    "deep_learning": ["deep learning"],
    "production_ml": ["production ml", "production machine learning", "model deployment", "model serving", "mlops"],
    "machine_learning": ["machine learning", "ml"],
    "analytics": ["analytics", "data analysis", "data analytics", "business analytics"],
    "statistics": ["statistics", "statistical"],
    "forecasting": ["forecasting", "forecast"],
    "segmentation": ["segmentation", "customer segmentation"],
}


SKILL_LABELS = {
    "sklearn": "scikit-learn",
    "power_bi": "Power BI",
    "cpp": "C++",
    "nlp": "NLP",
    "computer_vision": "computer vision",
    "deep_learning": "deep learning",
    "machine_learning": "machine learning",
    "production_ml": "production ML",
}


def _profile_skill_set(profile: dict, criteria: dict) -> set[str]:
    skills = set()
    explicit = list(profile.get("skills", [])) + list(criteria.get("skills", []))
    for skill in explicit:
        skills.add(_normalize_skill(skill))

    profile_text = " ".join([
        " ".join(f"{e.get('title','')} {e.get('description','')}" for e in profile.get("experience", [])),
        " ".join(f"{p.get('name','')} {p.get('description','')} {p.get('tech','')}" for p in profile.get("projects", [])),
    ]).lower()
    title_text = " ".join(e.get("title", "") for e in profile.get("experience", [])).lower()

    if any(term in title_text for term in ["data analyst", "analytics analyst", "business analyst"]):
        skills.add("analytics")
    if any(term in profile_text for term in ["forecast", "forecasting"]):
        skills.add("forecasting")
    if "segmentation" in profile_text:
        skills.add("segmentation")
    if any(term in profile_text for term in ["machine learning", "scikit", "pytorch", "tensorflow", " ml "]):
        skills.add("ml_basics")
    return {s for s in skills if s}


def _normalized_job_skills(raw_skills: list[str]) -> dict[str, str]:
    normalized = {}
    for raw in raw_skills or []:
        key = _normalize_skill(raw)
        if key:
            normalized.setdefault(key, SKILL_LABELS.get(key, str(raw)))
    return normalized


def _description_requirement_skills(job: dict) -> dict[str, str]:
    text = _job_signal_text(job)
    signals = {
        "production_ml": ["production ml", "production machine learning", "production inference", "model deployment", "model serving", "deployed model", "ml pipeline", "ml pipelines"],
        "tensorflow": ["tensorflow"],
        "statistics": ["statistics", "statistical"],
        "spark": ["spark"],
        "pyspark": ["pyspark"],
        "kafka": ["kafka"],
        "kubernetes": ["kubernetes", "k8s"],
        "aws": ["aws", "amazon web services"],
        "nlp": ["nlp", "natural language processing"],
        "computer_vision": ["computer vision"],
        "deep_learning": ["deep learning"],
        "power_bi": ["power bi", "powerbi"],
        "tableau": ["tableau"],
    }
    found = {}
    for key, terms in signals.items():
        if any(term in text for term in terms):
            found[key] = SKILL_LABELS.get(key, key.replace("_", " "))
    if any(term in text for term in ["ci/cd", "cicd", "continuous integration", "continuous deployment"]):
        found["ci_cd"] = "CI/CD"
    return found


def _normalize_skill(skill: str) -> str:
    text = f" {str(skill or '').strip().lower()} "
    if not text.strip():
        return ""
    for key, aliases in SKILL_ALIASES.items():
        if any(_alias_matches(text, alias) for alias in aliases):
            return key
    return text.strip().replace(" ", "_").replace("-", "_")


def _alias_matches(padded_text: str, alias: str) -> bool:
    alias_text = str(alias or "").strip().lower()
    if not alias_text:
        return False
    return f" {alias_text} " in padded_text


def _skill_covered(job_skill: str, profile_skills: set[str]) -> bool:
    if job_skill in profile_skills:
        return True
    if job_skill == "pyspark" and "spark" in profile_skills:
        return True
    if job_skill == "machine_learning" and ("ml_basics" in profile_skills or "sklearn" in profile_skills or "pytorch" in profile_skills):
        return True
    if job_skill == "analytics" and "analytics" in profile_skills:
        return True
    return False


def _preference_score(job: dict, criteria: dict) -> float:
    prefs = [p.lower() for p in criteria.get("preferences", []) if p]
    if not prefs:
        return 0.0
    text = _job_signal_text(job)
    aliases = {
        "tech": ["technology", "software", "saas", "cloud", "platform", "engineering", "developer"],
        "healthcare": ["healthcare", "health care", "hospital", "clinic", "medical", "biotech", "pharma", "clinical"],
        "large tech": ["google", "amazon", "microsoft", "meta", "apple", "nvidia", "oracle", "salesforce", "adobe", "netflix", "uber"],
        "research labs": ["research lab", "laboratory", "university", "institute", "research scientist", "research", "publication"],
        "known h-1b sponsors": ["h-1b", "h1b", "sponsor", "opt", "google", "amazon", "microsoft", "meta", "apple", "nvidia", "oracle", "salesforce", "adobe", "research"],
        "ml infrastructure": ["mlops", "ml platform", "machine learning platform", "model serving", "model deployment", "kubernetes", "kafka", "spark", "infrastructure"],
        "ml-focused": _evidence_terms("ml"),
        "non-defense": [],
        "large companies": ["enterprise", "global", "fortune", "large company", "large-scale", "scale"],
    }
    total = 0.0
    for pref in prefs:
        terms = aliases.get(pref, [pref])
        if pref == "large companies":
            size = int(job.get("company_size", 0) or 0)
            if size >= 100:
                total += 1.0
                continue
        total += _evidence_score(text, terms)
    return min(1.0, total / max(len(prefs), 1))


def _role_filter_reason(job: dict, criteria: dict) -> str:
    target = (criteria.get("target_role", "") or "").lower().strip()
    if not target:
        return ""
    score = _role_score(job, criteria)
    if score >= 0.30:
        return ""
    return "Insufficient target-role fit"


def _role_score(job: dict, criteria: dict) -> float:
    target = (criteria.get("target_role", "") or "").lower().strip()
    if not target:
        return 0.75
    targets = [t.strip() for t in target.split(",") if t.strip()]
    if len(targets) > 1:
        return max(_single_role_score(job, t, criteria) for t in targets)
    return _single_role_score(job, target, criteria)


def _single_role_score(job: dict, target: str, criteria: dict = None) -> float:
    title = (job.get("title", "") or "").lower()
    text = _job_signal_text(job)
    target = (target or "").lower()
    prefs = [p.lower() for p in (criteria or {}).get("preferences", []) if p]

    if "data analyst" in target or "bi analyst" in target:
        title_terms = ["data analyst", "bi analyst", "business intelligence analyst", "analytics engineer", "junior data scientist"]
        evidence_terms = _evidence_terms("analytics")
    elif "platform" in target or "mlops" in target:
        title_terms = ["ml platform", "machine learning platform", "mlops", "machine learning ops", "platform engineer", "ml infrastructure"]
        evidence_terms = _evidence_terms("ml_infra")
    elif "research scientist" in target:
        title_terms = ["research scientist", "applied scientist", "ai scientist", "machine learning scientist"]
        evidence_terms = _evidence_terms("research")
    elif "applied scientist" in target:
        title_terms = ["applied scientist", "machine learning scientist", "ai scientist", "research scientist"]
        evidence_terms = _evidence_terms("research") + _evidence_terms("ml")
    elif "data scientist" in target:
        title_terms = ["data scientist", "machine learning scientist"]
        evidence_terms = _evidence_terms("data_science")
        if "ml-focused" in prefs:
            evidence_terms = _evidence_terms("ml")
    elif "ml" in target or "machine learning" in target or "ai engineer" in target:
        title_terms = ["ml engineer", "machine learning engineer", "ai engineer"]
        evidence_terms = _evidence_terms("ml")
    else:
        words = [w for w in target.split() if len(w) > 2]
        if not words:
            return 0.75
        return sum(1 for w in words if w in title) / len(words)

    title_fit = 1.0 if any(term in title for term in title_terms) else 0.0
    if not title_fit and any(term in text for term in title_terms):
        title_fit = 0.65

    evidence_fit = _evidence_score(text, evidence_terms)
    if "platform" in target or "mlops" in target:
        ml_fit = _evidence_score(text, _evidence_terms("ml"))
        infra_fit = _evidence_score(text, _evidence_terms("ml_infra"))
        evidence_fit = min(ml_fit, infra_fit)
        if infra_fit > 0 and ml_fit == 0:
            evidence_fit = 0.2
    if "research scientist" in target and any(pref in prefs for pref in ["research labs", "known h-1b sponsors"]):
        evidence_fit = min(1.0, evidence_fit + 0.15)
    generic_role_fit = 0.25 if any(w in title for w in ["engineer", "scientist", "analyst"]) else 0.0
    score = max(generic_role_fit, title_fit * 0.65 + evidence_fit * 0.35)

    if "data scientist" in target and "ml-focused" in prefs and title_fit:
        score = min(1.0, title_fit * 0.45 + evidence_fit * 0.55)
    return min(1.0, score)


def _job_signal_text(job: dict) -> str:
    return " ".join([
        job.get("title", "") or "",
        job.get("company", "") or "",
        job.get("industry", "") or "",
        job.get("source", "") or "",
        " ".join(job.get("skills_extracted", []) or []),
        job.get("description", "") or "",
    ]).lower()


def _evidence_terms(category: str) -> list[str]:
    groups = {
        "ml": [
            "machine learning", " ml ", "pytorch", "tensorflow", "scikit", "deep learning",
            "nlp", "computer vision", "model training", "classification", "forecasting",
            "predictive model", "neural network", "recommendation", "model development",
        ],
        "data_science": [
            "statistics", "statistical", "modeling", "modelling", "prediction", "forecasting",
            "experiment", "python", "sql", "analytics", "data mining", "regression",
        ],
        "analytics": [
            "sql", "tableau", "dashboard", "business intelligence", "bi ", "reporting",
            "analytics", "excel", "power bi", "data warehouse", "metrics", "kpi",
        ],
        "ml_infra": [
            "mlops", "machine learning ops", "machine learning platform", "ml platform", "model serving",
            "model deployment", "kubernetes", "kafka", "spark", "aws", "microservices",
            "pipeline", "infrastructure", "devops", "production ml",
        ],
        "research": [
            "research", "publication", "paper", "laboratory", "lab", "experiment",
            "deep learning", "nlp", "computer vision", "pytorch", "conference",
        ],
    }
    return groups.get(category, [])


def _evidence_score(text: str, terms: list[str]) -> float:
    if not terms:
        return 0.0
    hits = sum(1 for term in terms if term in text)
    if hits >= 4:
        return 1.0
    if hits == 3:
        return 0.85
    if hits == 2:
        return 0.65
    if hits == 1:
        return 0.35
    return 0.0


def _feedback_score(job: dict, weights: dict) -> float:
    job_id = job.get("job_id", "")
    # Direct job boost (from accept/reject on this specific job)
    direct = weights.get(f"job:{job_id}", 0.0) * 2
    # Skill/location/industry boost
    labels = [f"skill:{s}" for s in job.get("skills_extracted", [])]
    labels += [f"location:{job.get('location','').lower()}", f"industry:{job.get('industry','').lower()}"]
    indirect = sum(weights.get(l.lower(), 0.0) for l in labels)
    return direct + indirect


def _diversity_rerank(rows: list[dict], criteria: dict = None, limit: int = 10) -> list[dict]:
    """Avoid duplicate job IDs and one role bucket dominating multi-role searches."""
    selected = []
    selected_ids: set[str] = set()
    role_count: dict[str, int] = {}
    deferred = []
    target_role = (criteria or {}).get("target_role", "")
    targets = [t.strip() for t in target_role.split(",") if t.strip()]
    use_role_cap = len(targets) > 1
    role_cap = max(1, math.ceil(min(limit, 10) * 0.5))

    if use_role_cap:
        for target in targets:
            desired = _target_role_buckets(target)
            for item in rows:
                if item.get("job_id", "") in selected_ids:
                    continue
                if _role_bucket(item) in desired:
                    selected.append(item)
                    selected_ids.add(item.get("job_id", ""))
                    role_bucket = _role_bucket(item)
                    role_count[role_bucket] = role_count.get(role_bucket, 0) + 1
                    break
    
    for item in rows:
        if item.get("job_id", "") in selected_ids:
            continue
        role_bucket = _role_bucket(item)
        role_ok = (not use_role_cap) or role_count.get(role_bucket, 0) < role_cap
        if role_ok:
            selected.append(item)
            selected_ids.add(item.get("job_id", ""))
            role_count[role_bucket] = role_count.get(role_bucket, 0) + 1
        else:
            deferred.append(item)
    
    selected.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    # Add deferred items at end (still in score order)
    selected.extend(deferred)
    return selected


def _target_role_buckets(target: str) -> set[str]:
    t = (target or "").lower()
    if "applied scientist" in t:
        return {"applied_scientist", "research_scientist", "scientist"}
    if "research scientist" in t:
        return {"research_scientist", "applied_scientist", "scientist"}
    if "mlops" in t:
        return {"mlops", "ml_platform", "engineer"}
    if "platform" in t:
        return {"ml_platform", "mlops", "engineer"}
    if "ml" in t or "machine learning" in t or "ai engineer" in t:
        return {"ml_engineer", "engineer"}
    if "data scientist" in t:
        return {"data_scientist", "scientist"}
    if "analytics engineer" in t:
        return {"analytics_engineer", "engineer"}
    if "bi analyst" in t:
        return {"bi_analyst", "analyst"}
    if "data analyst" in t:
        return {"data_analyst", "analyst"}
    return {"other"}


def _role_bucket(job: dict) -> str:
    title = (job.get("title", "") or "").lower()
    text = f"{title} {job.get('description','')}".lower()
    if "applied scientist" in title:
        return "applied_scientist"
    if "research scientist" in title:
        return "research_scientist"
    if "mlops" in title or "machine learning ops" in title:
        return "mlops"
    if "platform" in title and any(w in text for w in ["ml", "machine learning", "ai"]):
        return "ml_platform"
    if any(w in title for w in ["ml engineer", "machine learning engineer", "ai engineer"]):
        return "ml_engineer"
    if "data scientist" in title:
        return "data_scientist"
    if "analytics engineer" in title:
        return "analytics_engineer"
    if "business intelligence" in title or "bi analyst" in title:
        return "bi_analyst"
    if "data analyst" in title:
        return "data_analyst"
    if "engineer" in title:
        return "engineer"
    if "scientist" in title:
        return "scientist"
    if "analyst" in title:
        return "analyst"
    return "other"


def _ndcg_at_k(gains: list[float], k: int = 10) -> float:
    gains = gains[:k]
    if not gains: return 0.0
    dcg = sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(gains))
    ideal = sorted(gains, reverse=True)
    idcg = sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def _feedback_ndcg_at_k(rows: list[dict], labels: dict[str, float], k: int = 10) -> dict:
    labeled_rows = [row for row in rows if row.get("job_id") in labels]
    if len(labeled_rows) < 3:
        return {
            "metric": "feedback_ndcg_at_10",
            "available": False,
            "ndcg_at_10": None,
            "labeled_ranked_jobs": len(labeled_rows),
            "required_labeled_jobs": 3,
            "message": "Needs at least 3 ranked feedback signals",
        }
    gains = [labels.get(row.get("job_id"), 0.0) for row in rows[:k]]
    ideal_gains = sorted((labels[row.get("job_id")] for row in labeled_rows), reverse=True)[:k]
    return {
        "metric": "feedback_ndcg_at_10",
        "available": True,
        "ndcg_at_10": round(_ndcg_from_gains(gains, ideal_gains), 4),
        "labeled_ranked_jobs": len(labeled_rows),
        "required_labeled_jobs": 3,
        "message": "Computed from accept/skip/reject feedback",
    }


def _ndcg_from_gains(gains: list[float], ideal_gains: list[float]) -> float:
    dcg = sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(gains))
    idcg = sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(ideal_gains))
    return dcg / idcg if idcg else 0.0


# ── TF-IDF baseline for benchmarking ─────────────────────────────────────────

class TFIDFBaseline:
    """Sparse TF-IDF baseline for comparison with LSA embeddings."""
    def __init__(self):
        self.vectorizer = None
        self.matrix = None
        self.job_ids = []

    def build(self, jobs: list[dict]):
        texts = [_job_text(j) for j in jobs]
        self.job_ids = [j["job_id"] for j in jobs]
        self.vectorizer = TfidfVectorizer(max_features=10000, ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = normalize(self.vectorizer.fit_transform(texts))

    def search(self, query: str, top_k: int = 20) -> list[tuple[str, float]]:
        if self.matrix is None: return []
        q = normalize(self.vectorizer.transform([query]))
        scores = (self.matrix @ q.T).toarray().flatten()
        indices = np.argsort(scores)[::-1][:top_k]
        return [(self.job_ids[i], float(scores[i])) for i in indices]
