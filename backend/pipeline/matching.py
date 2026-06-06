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
    "united states", "bay area", "san francisco", "new york", "nyc",
    "california", "texas", "washington", "massachusetts", "illinois", "georgia",
    "florida", "palo alto", "sunnyvale", "manhattan", "charlotte", "atlanta",
    "seattle", "boston", "austin", "chicago", "st. louis", "creve coeur",
    "ladue", "duluth", "minneapolis", "bellevue", "redmond", "norfolk",
    "raleigh", "centennial", "highland park",
]

BAY_AREA_HINTS = [
    "bay area", "san francisco", "sf", "san jose", "palo alto", "mountain view",
    "sunnyvale", "santa clara", "cupertino", "menlo park", "redwood city",
    "oakland", "berkeley", "fremont", "san mateo", "milpitas", "pleasanton",
    "sfo", "south san francisco", "emeryville",
]

US_STATE_HINTS = [
    " al", " ak", " az", " ar", " ca", " co", " ct", " de", " fl", " ga",
    " hi", " ia", " id", " il", " in", " ks", " ky", " la", " ma", " md",
    " me", " mi", " mn", " mo", " ms", " mt", " nc", " nd", " ne", " nh",
    " nj", " nm", " nv", " ny", " oh", " ok", " or", " pa", " ri", " sc",
    " sd", " tn", " tx", " ut", " va", " vt", " wa", " wi", " wv", " wy",
]

NON_US_LOCATION_HINTS = [
    "australia", "victoria", "sydney", "melbourne", "taiwan", "taipei",
    "new zealand", "wellington", "auckland", "germany", "berlin", "leipzig",
    "china", "jiangsu", "shanghai", "beijing", "canada", "toronto", "vancouver",
    "india", "singapore", "united kingdom", "uk", "london", "ireland",
    "netherlands", "france", "spain", "portugal", "lisboa", "lisbon",
    "austria", "wien", "vienna", "japan", "korea", "hong kong",
    "deutschland", "milton keynes", "buckinghamshire", "england", "scotland",
    "wales", "europe", "european",
    "münchen", "munich", "hamburg",
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

    if len(passed) < max(30, limit):
        candidate_ids = {j["job_id"] for j in candidates}
        fallback_jobs = _targeted_fallback_jobs(jobs, criteria)
        for job in fallback_jobs:
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
    min_visible = min(limit, 30)
    qualified = [row for row in scored if row["match_score"] >= 40]
    if len(qualified) < min_visible:
        qualified_ids = {row["job_id"] for row in qualified}
        qualified.extend(row for row in scored if row["job_id"] not in qualified_ids)
    scored = qualified[:max(limit, min_visible)]

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

    content_reason = _non_job_filter_reason(job)
    if content_reason:
        return content_reason

    us_only_reason = _us_only_filter_reason(job, criteria)
    if us_only_reason:
        return us_only_reason

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
        if any(w in text for w in ["temp", "temporary", "seasonal", "intern", "internship"]):
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
        if required >= 5 and _has_ml_requirement_signal(text):
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

    return ""


def _targeted_fallback_jobs(jobs: list[dict], criteria: dict) -> list[dict]:
    target = (criteria.get("target_role", "") or "").lower()
    prefs = _normalized_preferences(criteria.get("preferences", []))
    if _requires_ml_evidence(criteria):
        return [job for job in jobs if _has_ml_related_evidence(job)]
    if "ml infrastructure" in prefs or any(term in target for term in ["ml platform", "mlops"]):
        return [job for job in jobs if _specialized_role_relevance(job, criteria) >= 0.35]
    if "research labs" in prefs or any(term in target for term in ["research scientist", "applied scientist", "ai engineer"]):
        return [job for job in jobs if _specialized_role_relevance(job, criteria) >= 0.35]
    return jobs


def _non_job_filter_reason(job: dict) -> str:
    title = (job.get("title", "") or "").lower()
    text = _job_signal_text(job)
    if any(term in title for term in [
        "online course", "training course", "learning pathway", "certification course",
        "free course", "course curriculum",
    ]):
        return "Non-job content"

    strong_course_signals = [
        "course objectives", "learning pathway", "course curriculum", "no-cost curriculum",
        "hours of learning", "online course", "introduced to the skills",
        "this pathway", "course modules", "training curriculum",
    ]
    if sum(1 for term in strong_course_signals if term in text) >= 2:
        return "Non-job content"
    return ""


def _location_filter_reason(job: dict, criteria: dict) -> str:
    pref = (criteria.get("location", "") or "").lower().strip()
    if not pref:
        return ""
    loc = (job.get("location", "") or "").lower()
    desc = (job.get("description", "") or "").lower()
    location_text = f" {loc} {desc[:600]} "
    if "any" in pref and "us" not in pref and "u.s" not in pref:
        return ""

    constraint = _parse_location_constraint(pref)
    if constraint["us_scope"]:
        loc_value = loc.strip()
        if loc_value and loc_value not in ("nan", "unknown", "not specified"):
            if not _is_remote(loc_value) and not _is_us_location(loc_value):
                return "Outside location preference"
        if _looks_non_us_location(loc) and not _has_explicit_us_remote(location_text):
            return "Outside location preference"
        if _has_non_us_location(location_text) and not _has_explicit_us_remote(location_text):
            return "Outside location preference"

    if constraint["specific"]:
        return ""

    if constraint["us_scope"]:
        return ""

    terms = [t.strip() for t in re.split(r"[,/]| or ", pref) if len(t.strip()) > 2]
    if terms and not any(t in location_text for t in terms):
        return "Outside location preference"
    return ""


def _us_only_filter_reason(job: dict, criteria: dict) -> str:
    pref = (criteria.get("location", "") or "").lower().strip()
    if "us only" not in pref and "u.s. only" not in pref:
        return ""
    loc = (job.get("location", "") or "").lower()
    desc = (job.get("description", "") or "").lower()
    location_text = f" {loc} {desc[:600]} "
    loc_value = loc.strip()
    if loc_value and loc_value not in ("nan", "unknown", "not specified"):
        if not _is_remote(loc_value) and not _is_us_location(loc_value):
            return "Outside US requirement"
    if _looks_non_us_location(loc) and not _has_explicit_us_remote(location_text):
        return "Outside US requirement"
    if _has_non_us_location(location_text) and not _has_explicit_us_remote(location_text):
        return "Outside US requirement"
    return ""


def _parse_location_constraint(pref: str) -> dict:
    return {
        "remote": "remote" in pref,
        "bay": "bay area" in pref or any(h in pref for h in BAY_AREA_HINTS),
        "nyc": "nyc" in pref or "new york" in pref,
        "us_scope": (
            "us only" in pref or "u.s. only" in pref or "any us" in pref
            or pref == "us" or "united states" in pref
            or "remote" in pref or "bay area" in pref or "nyc" in pref or "new york" in pref
        ),
        "specific": (
            "remote" in pref or "bay area" in pref or any(h in pref for h in BAY_AREA_HINTS)
            or "nyc" in pref or "new york" in pref
        ),
    }


def _matches_location_constraint(text: str, constraint: dict) -> bool:
    if constraint["remote"] and _is_remote(text):
        return True
    if constraint["bay"] and _is_bay_area_location(text):
        return True
    if constraint["nyc"] and _is_nyc_location(text):
        return True
    return False


def _employment_filter_reason(job: dict, criteria: dict) -> str:
    pref = (criteria.get("employment_type", "") or "").lower().strip()
    if pref != "full-time":
        return ""
    title = (job.get("title", "") or "").lower()
    employment = (job.get("employment_type", "") or "").lower()
    desc = (job.get("description", "") or "").lower()
    text = f" {title} {employment} {desc} "
    if _has_contract_signal(text) or _has_temp_signal(text) or _has_unpaid_signal(text):
        return "Not a full-time role"
    return ""


def _has_contract_signal(text: str) -> bool:
    return any(p in text for p in [
        " contract ", "contract role", "contract position", "contract job",
        "contract-to-hire", "contract to hire", "months contract", "month contract",
        "duration:", "c2c", "w2 contract", "corp-to-corp", "contractor",
        "freelance", "self-employed", "1099",
    ])


def _has_temp_signal(text: str) -> bool:
    return any(p in text for p in [
        " temp ", "temporary", "seasonal", "intern", "internship",
    ])


def _has_unpaid_signal(text: str) -> bool:
    return any(p in text for p in ["unpaid", "volunteer", "no compensation", "commission only", "commission-only"])


def _is_remote(text: str) -> bool:
    padded = f" {text.lower()} "
    if any(p in padded for p in [
        " not remote ", " not a remote ", " not currently remote ",
        " this is not a remote ", " not a remote role ", " not a remote position ",
    ]):
        return False
    return any(p in padded for p in [" remote ", "work from home", " wfh ", "telecommute"])


def _has_explicit_us_remote(text: str) -> bool:
    return _is_remote(text) and any(p in text for p in ["united states", " u.s.", " us ", " usa", "within the us", "within the u.s."])


def _has_non_us_location(text: str) -> bool:
    return any(h in text for h in NON_US_LOCATION_HINTS)


def _looks_non_us_location(text: str) -> bool:
    if not text:
        return False
    padded = f" {text.lower()} "
    if _has_non_us_location(padded):
        return True
    return _has_non_ascii(padded) and not _is_us_location(padded)


def _has_non_ascii(text: str) -> bool:
    return any(ord(ch) > 127 for ch in text or "")


def _is_us_location(text: str) -> bool:
    raw = f" {text.lower()} "
    if any(h in raw for h in US_LOCATION_HINTS):
        return True
    return bool(re.search(
        r",\s*(al|ak|az|ar|ca|co|ct|de|fl|ga|hi|ia|id|il|in|ks|ky|la|ma|md|me|mi|mn|mo|ms|mt|nc|nd|ne|nh|nj|nm|nv|ny|oh|ok|or|pa|ri|sc|sd|tn|tx|ut|va|vt|wa|wi|wv|wy)\b",
        raw,
    ))


def _is_bay_area_location(text: str) -> bool:
    raw = f" {text.lower()} "
    return any(h in raw for h in BAY_AREA_HINTS)


def _is_nyc_location(text: str) -> bool:
    raw = f" {text.lower()} "
    return any(h in raw for h in [
        "new york", "nyc", "manhattan", "brooklyn", "queens", "bronx",
        "staten island", "grand central",
    ])


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
        r"\+(\d{1,2})\s*(?:years|yrs)",
        r"(?:experience|exp)\s*:?\s*(\d{1,2})\+?\s*(?:years|yrs)",
    ]
    values = []
    for pattern in patterns:
        values.extend(int(m.group(1)) for m in re.finditer(pattern, text))
    return max(values) if values else 0


def _has_ml_requirement_signal(text: str) -> bool:
    raw = f" {(text or '').lower()} "
    signals = [
        "machine learning", " ml ", "neural network", "model training",
        "model deployment", "pytorch", "tensorflow", "scikit-learn",
        "scikit learn", "deep learning", "nlp", "computer vision",
        "predictive model", "ml pipeline", "data science", "data scientist",
    ]
    return any(signal in raw for signal in signals)


def _score(job: dict, profile: dict, criteria: dict,
           profile_skills: set, emb_score: float, feedback_weights: dict) -> dict:
    job_skill_map = _normalized_job_skills(job.get("skills_extracted", []))
    job_skill_map.update(_description_requirement_skills(job))
    job_skill_keys = set(job_skill_map)
    matched_skills = {k for k in job_skill_keys if _skill_covered(k, profile_skills)}
    missing_keys = [k for k in sorted(job_skill_keys) if not _skill_covered(k, profile_skills)]
    missing_skills = [job_skill_map[k] for k in missing_keys][:5]

    skill_match = len(matched_skills) / max(len(job_skill_keys), 1) if job_skill_keys else 0.5
    location_match = _location_score(criteria.get("location", "") or profile.get("current_location", ""), job.get("location", ""), job)
    job_salary_min, job_salary_max = _job_salary_bounds(job)
    salary_match = _salary_score(criteria.get("salary_min", 0) or 0, job_salary_min, job_salary_max)
    exp_match = _exp_score(profile, job.get("required_years", 0) or 0)
    seniority_match = _seniority_score(profile, job)
    feedback_boost = _feedback_score(job, feedback_weights)
    role_match = _role_score(job, criteria)
    preference_match = _preference_score(job, criteria)
    metadata_score = _metadata_score(job)

    total = (
        emb_score * 18 +
        skill_match * 18 +
        role_match * 22 +
        preference_match * 14 +
        location_match * 12 +
        salary_match * 8 +
        exp_match * 6 +
        seniority_match * 4 +
        metadata_score * 4 +
        max(-8, min(feedback_boost * 8, 8))
    )
    if seniority_match < 0.5:
        total -= 12
    match_score = round(max(1, min(99, total)), 1)

    return {
        "match_score": match_score,
        "missing_skills": missing_skills,
        "why_ranked_here": {
            "skill_match": round(skill_match * 100, 1),
            "skill_signal_count": len(job_skill_keys),
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


def _location_score(preferred: str, job_loc: str, job: dict | None = None) -> float:
    p, j = (preferred or "").lower(), (job_loc or "").lower()
    if not p: return 0.75
    desc = ((job or {}).get("description", "") or "").lower()
    location_text = f" {j} {desc[:600]} "
    if not j or j in ("nan", "unknown"):
        return 0.15
    constraint = _parse_location_constraint(p)
    if constraint["specific"]:
        return 1.0 if _matches_location_constraint(location_text, constraint) else 0.1
    if "any us" in p and any(h in j for h in US_LOCATION_HINTS): return 0.95
    if ("us only" in p or p.strip() == "us") and any(h in j for h in US_LOCATION_HINTS): return 1.0
    if "remote" in p and "remote" in j: return 1.0
    if "remote" in j: return 0.8
    cities = [c.strip() for c in p.replace(",", " ").split() if len(c) > 2]
    for city in cities:
        if city in j: return 1.0
    return 0.4


def _specific_location_miss(preferred: str, job: dict) -> bool:
    pref = (preferred or "").lower().strip()
    if not pref:
        return False
    constraint = _parse_location_constraint(pref)
    if not constraint["specific"]:
        return False
    loc = (job.get("location", "") or "").lower()
    desc = (job.get("description", "") or "").lower()
    location_text = f" {loc} {desc[:600]} "
    return not _matches_location_constraint(location_text, constraint)


def _salary_score(min_req: int, job_min: int, job_max: int) -> float:
    if not min_req: return 0.8
    if job_max == 0: return 1.0
    if job_max >= min_req * 1.1: return 1.0
    if job_max >= min_req: return 0.85
    return max(0.1, job_max / min_req)


def _job_salary_bounds(job: dict) -> tuple[int, int]:
    lo = int(job.get("salary_min", 0) or 0)
    hi = int(job.get("salary_max", 0) or 0)
    structured_values = [v for v in [lo, hi] if v]
    if structured_values:
        return min(structured_values), max(structured_values)
    desc_lo, desc_hi = _extract_salary_bounds(job.get("description", "") or "")
    values = [v for v in [desc_lo, desc_hi] if v]
    if not values:
        return 0, 0
    return min(values), max(values)


def _extract_salary_bounds(text: str) -> tuple[int, int]:
    values = []
    for match in re.finditer(r"\$?\s*(\d{2,3})(?:,\d{3})?\s*[kK]\b|\$?\s*(\d{2,3}),(\d{3})", text or ""):
        if match.group(1):
            values.append(int(match.group(1)) * 1000)
        elif match.group(2) and match.group(3):
            values.append(int(f"{match.group(2)}{match.group(3)}"))
    values = [v for v in values if 30000 <= v <= 500000]
    if not values:
        return 0, 0
    return min(values), max(values)


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
    "mlops": ["mlops"],
    "analytics": ["analytics", "data analysis", "data analytics", "business analytics"],
    "statistics": ["statistics", "statistical"],
    "forecasting": ["forecasting", "forecast"],
    "segmentation": ["segmentation", "customer segmentation"],
    "llm": ["llm", "large language model", "large language models"],
    "rag": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
    "hadoop": ["hadoop"],
    "azure": ["azure"],
    "gcp": ["gcp", "google cloud"],
    "docker": ["docker"],
    "ci_cd": ["ci/cd", "cicd", "continuous integration", "continuous deployment"],
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
    "mlops": "MLOps",
    "llm": "LLM",
    "rag": "RAG",
    "ci_cd": "CI/CD",
    "gcp": "GCP",
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
        "production_ml": [
            "production ml", "production machine learning", "production inference",
            "production-grade", "production ready", "production-ready",
            "productionizing machine learning", "productionize machine learning",
            "model deployment", "model serving", "deployed model", "deploy models",
            "deploying models", "deploy machine learning", "deployed machine learning",
            "ml pipeline", "ml pipelines", "machine learning pipeline",
            "machine learning pipelines", "end-to-end ml", "end to end ml",
            "production inference", "inference at scale",
        ],
        "machine_learning": [
            "machine learning", "predictive model", "predictive models",
            "model training", "train models", "training models",
            "classification", "regression", "recommendation model",
            "recommendation models", "recommender", "semantic search",
        ],
        "tensorflow": ["tensorflow"],
        "sklearn": ["scikit-learn", "scikit learn", "sklearn"],
        "statistics": ["statistics", "statistical"],
        "spark": ["spark"],
        "pyspark": ["pyspark"],
        "kafka": ["kafka"],
        "kubernetes": ["kubernetes", "k8s"],
        "aws": ["aws", "amazon web services"],
        "azure": ["azure"],
        "gcp": ["gcp", "google cloud"],
        "docker": ["docker"],
        "hadoop": ["hadoop"],
        "nlp": ["nlp", "natural language processing"],
        "computer_vision": ["computer vision"],
        "deep_learning": ["deep learning"],
        "llm": ["llm", "large language model", "large language models"],
        "rag": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
        "mlops": ["mlops", "machine learning operations"],
        "power_bi": ["power bi", "powerbi"],
        "tableau": ["tableau"],
        "analytics": ["analytics", "data analysis", "data analytics", "business intelligence"],
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
    related_groups = [
        {"machine_learning", "ml_basics", "sklearn", "pytorch", "tensorflow", "llm", "rag", "deep_learning", "computer_vision", "nlp"},
        {"analytics", "statistics", "forecasting", "segmentation", "python", "sql", "pandas", "tableau", "power_bi"},
        {"spark", "pyspark", "hadoop", "python"},
        {"mlops", "production_ml", "aws", "azure", "gcp", "kubernetes", "docker", "ci_cd"},
    ]
    strict_skills = {"production_ml", "mlops"}
    if job_skill not in strict_skills:
        for group in related_groups:
            if job_skill in group and profile_skills & group:
                return True
    if job_skill == "pyspark" and "spark" in profile_skills:
        return True
    if job_skill == "machine_learning" and ("ml_basics" in profile_skills or "sklearn" in profile_skills or "pytorch" in profile_skills):
        return True
    if job_skill == "analytics" and "analytics" in profile_skills:
        return True
    return False


def _preference_score(job: dict, criteria: dict) -> float:
    prefs = _normalized_preferences(criteria.get("preferences", []))
    if not prefs:
        return 0.0
    text = _job_signal_text(job)
    aliases = {
        "tech": [
            "technology", "software", "saas", "cloud", "platform", "engineering",
            "developer", "data engineering", "data platform", "ai", "machine learning",
            "it jobs", "analytics engineer", "digital product",
        ],
        "healthcare": [
            "healthcare", "health care", "hospital", "clinic", "medical", "biotech",
            "pharma", "clinical", "patient", "health system", "life sciences",
        ],
        "large tech": [
            "google", "amazon", "microsoft", "meta", "apple", "nvidia", "oracle",
            "salesforce", "adobe", "netflix", "uber", "walmart global tech",
            "thomson reuters", "indeed",
        ],
        "research labs": [
            "research lab", "laboratory", "university", "institute", "research scientist",
            "research", "publication", "published", "conference", "foundation model",
            "applied science", "applied scientist",
        ],
        "known h-1b sponsors": [
            "h-1b", "h1b", "sponsor", "opt", "google", "amazon", "microsoft",
            "meta", "apple", "nvidia", "oracle", "salesforce", "adobe", "research",
            "walmart", "thomson reuters", "indeed", "general motors",
        ],
        "ml infrastructure": [
            "mlops", "ml platform", "machine learning platform", "model serving",
            "model deployment", "kubernetes", "kafka", "spark", "infrastructure",
            "feature pipeline", "feature pipelines", "production ml", "microservices",
            "distributed systems", "aws", "cloud",
        ],
        "ml-focused": _evidence_terms("ml") + [
            "ml pipeline", "ml pipelines", "machine learning pipeline",
            "machine learning pipelines", "production inference", "model deployment",
            "model serving", "pytorch", "tensorflow", "scikit-learn",
        ],
        "non-defense": [],
        "large companies": [
            "enterprise", "global", "fortune", "large company", "large-scale",
            "at scale", "scale", "1000 employees", "thousands of employees",
        ],
    }
    weights = {
        "ml-focused": 1.4,
        "ml infrastructure": 1.5,
        "research labs": 1.5,
        "tech": 1.2,
        "healthcare": 1.2,
        "large tech": 1.0,
        "known h-1b sponsors": 0.9,
        "large companies": 0.8,
    }
    total = 0.0
    denom = 0.0
    for pref in prefs:
        pref_weight = weights.get(pref, 1.0)
        denom += pref_weight
        terms = aliases.get(pref, [pref])
        if pref == "large companies":
            size = int(job.get("company_size", 0) or 0)
            if size >= 100:
                total += pref_weight
                continue
        total += _evidence_score(text, terms) * pref_weight
    return min(1.0, total / max(denom, 1.0))


def _normalized_preferences(raw_preferences: list[str]) -> list[str]:
    prefs: list[str] = []
    for raw in raw_preferences or []:
        text = str(raw or "").strip().lower()
        if not text:
            continue
        if "tech" in text and "health" in text:
            prefs.extend(["tech", "healthcare"])
            continue
        if "large" in text and "company" in text:
            prefs.append("large companies")
            continue
        prefs.append(text)
    return prefs


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
    description = (job.get("description", "") or "").lower()
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
    if not title_fit and any(term in description for term in title_terms):
        title_fit = 0.65
    elif not title_fit and any(term in text for term in title_terms):
        title_fit = 0.5

    evidence_fit = _evidence_score(text, evidence_terms)
    if evidence_fit >= 0.65 and title_fit == 0:
        title_fit = 0.45
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


def _specialized_role_relevance(job: dict, criteria: dict) -> float:
    target = (criteria.get("target_role", "") or "").lower()
    prefs = _normalized_preferences(criteria.get("preferences", []))
    text = _job_signal_text(job)
    title = (job.get("title", "") or "").lower()

    needs_ml_focus = "ml-focused" in prefs or any(term in target for term in [
        "ml engineer", "machine learning engineer",
    ])
    if needs_ml_focus:
        strong_ml_title = any(term in title for term in [
            "machine learning", "ml engineer", "ai engineer", "research scientist",
        ])
        related_science_title = any(term in title for term in [
            "applied scientist", "data scientist",
        ])
        if _is_unrelated_professional_family(title):
            return 0.0
        ml_score = _evidence_score(text, _evidence_terms("ml"))
        data_science_score = _evidence_score(text, _evidence_terms("ml_related_data_science"))
        if strong_ml_title:
            return max(0.45, min(1.0, 0.35 + max(ml_score, data_science_score) * 0.65))
        if related_science_title and max(ml_score, data_science_score) >= 0.25:
            return min(1.0, 0.2 + max(ml_score, data_science_score) * 0.8)
        return max(ml_score, data_science_score * 0.5)

    needs_ml_infra = any(term in target for term in [
        "ml platform", "mlops", "senior ml engineer", "machine learning engineer",
    ]) or "ml infrastructure" in prefs
    if needs_ml_infra:
        explicit_title = any(term in title for term in [
            "mlops", "ml platform", "machine learning engineer", "ml engineer",
            "ai engineer", "machine learning ops",
        ])
        ml_score = _evidence_score(text, _evidence_terms("ml"))
        infra_score = _evidence_score(text, _evidence_terms("ml_infra"))
        if explicit_title:
            return max(0.55, min(1.0, 0.45 + (ml_score + infra_score) / 2))
        return min(ml_score, infra_score)

    needs_research = any(term in target for term in ["research scientist", "applied scientist"]) or "research labs" in prefs
    if needs_research:
        explicit_title = any(term in title for term in [
            "research scientist", "applied scientist", "scientist",
        ])
        research_score = _evidence_score(text, _evidence_terms("research"))
        ml_score = _evidence_score(text, _evidence_terms("ml"))
        if explicit_title:
            return max(0.55, min(1.0, 0.45 + max(research_score, ml_score)))
        return max(research_score, ml_score)

    return 1.0


def _is_unrelated_professional_family(title: str) -> bool:
    return any(term in title for term in [
        "attorney", "lawyer", "legal counsel", "paralegal", "litigation",
        "immigration", "matrimonial", "family law", "financial analyst",
        "finance analyst", "accounting", "accountant", "controller",
        "fp&a", "revenue requirements analyst",
    ])


def _requires_ml_evidence(criteria: dict) -> bool:
    target = (criteria.get("target_role", "") or "").lower()
    prefs = _normalized_preferences(criteria.get("preferences", []))
    return (
        "ml-focused" in prefs
        or any(term in target for term in [
            "ml engineer", "machine learning engineer", "data scientist",
            "applied scientist", "ai engineer", "data science",
        ])
    )


def _has_ml_related_evidence(job: dict) -> bool:
    title = (job.get("title", "") or "").lower()
    description = (job.get("description", "") or "").lower()
    title_signals = [
        "machine learning", " ml ", "data scientist", "applied scientist",
        "ai engineer", "nlp", "deep learning", "computer vision", "mlops",
        "data science",
    ]
    description_signals = [
        "machine learning", "neural network", "model training", "model deployment",
        "pytorch", "tensorflow", "scikit-learn", "scikit learn", "deep learning",
        "nlp", "computer vision", "predictive model", "ml pipeline",
    ]
    padded_title = f" {title} "
    return (
        any(signal in padded_title for signal in title_signals)
        or any(signal in description for signal in description_signals)
    )


def _requires_specialized_relevance(criteria: dict) -> bool:
    target = (criteria.get("target_role", "") or "").lower()
    prefs = _normalized_preferences(criteria.get("preferences", []))
    return (
        "ml-focused" in prefs
        or "ml infrastructure" in prefs
        or "research labs" in prefs
        or any(term in target for term in [
            "ml engineer", "machine learning engineer", "ml platform", "mlops",
            "applied scientist", "research scientist", "ai engineer",
        ])
    )


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
        "ml_related_data_science": [
            "model", "modeling", "modelling", "predictive", "prediction", "forecasting",
            "classification", "regression", "recommendation", "personalization",
            "ranking", "optimization", "experiment", "experimentation", "causal",
            "feature engineering", "model training", "model evaluation", "algorithm",
            "statistical model", "statistical modeling", "python", "scikit", "pytorch",
            "tensorflow",
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
    direct = weights.get(f"job:{job_id}", 0.0)
    # Skill/location/industry boost
    labels = [f"skill:{s}" for s in job.get("skills_extracted", [])]
    labels += [f"location:{job.get('location','').lower()}", f"industry:{job.get('industry','').lower()}"]
    indirect = sum(weights.get(l.lower(), 0.0) for l in labels)
    indirect = max(-0.35, min(indirect, 0.35))
    return direct + indirect


def _diversity_rerank(rows: list[dict], criteria: dict = None, limit: int = 10) -> list[dict]:
    """Keep score order while removing duplicate job IDs."""
    selected = []
    selected_ids: set[str] = set()
    for item in rows:
        job_id = item.get("job_id", "")
        if job_id in selected_ids:
            continue
        selected.append(item)
        selected_ids.add(job_id)
    return selected


def _target_role_buckets(target: str) -> set[str]:
    t = (target or "").lower()
    if "applied scientist" in t:
        return {"applied_scientist"}
    if "research scientist" in t:
        return {"research_scientist"}
    if "mlops" in t:
        return {"mlops"}
    if "platform" in t:
        return {"ml_platform"}
    if "ml engineer" in t or "machine learning engineer" in t or "ai engineer" in t:
        return {"ml_engineer"}
    if "data scientist" in t:
        return {"data_scientist"}
    if "analytics engineer" in t:
        return {"analytics_engineer"}
    if "bi analyst" in t:
        return {"bi_analyst"}
    if "data analyst" in t:
        return {"data_analyst"}
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
