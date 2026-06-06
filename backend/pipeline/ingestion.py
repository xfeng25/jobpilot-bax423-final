"""
Capability 1: Job Data Ingestion & Streaming
BAX-423 Lecture 3: Kafka-style streaming pipeline simulation
"""
from __future__ import annotations
import hashlib, json, os, re
from html import unescape
import requests
import pandas as pd
from pathlib import Path

# Use word-boundary matching to avoid "r" matching every word with 'r'
SKILL_PATTERNS = [
    (r'\bpython\b', 'python'),
    (r'\bsql\b', 'sql'),
    (r'\bexcel\b', 'excel'),
    (r'\btableau\b', 'tableau'),
    (r'\bpower\s*bi\b', 'power bi'),
    (r'(?:programming\s+in|using|with|knowledge\s+of)\s+[Rr](?![a-zA-Z])|\b[Rr]\b(?=\s*,|\s*and\s*python|\s*&)|\bR\s+programming\b', 'R'),
    (r'\bmachine\s*learning\b', 'machine learning'),
    (r'\bnlp\b|\bnatural\s*language\s*processing\b', 'nlp'),
    (r'\bpytorch\b', 'pytorch'),
    (r'\btensorflow\b', 'tensorflow'),
    (r'\bspark\b', 'spark'),
    (r'\bpyspark\b', 'pyspark'),
    (r'\bstatistics\b|\bstatistical\b', 'statistics'),
    (r'\bdata\s*analysis\b|\bdata\s*analytics\b', 'data analysis'),
    (r'\ba/b\s*test', 'a/b testing'),
    (r'\bcomputer\s*vision\b', 'computer vision'),
    (r'\bjava\b', 'java'),
    (r'\bc\+\+\b', 'c++'),
    (r'\bjavascript\b', 'javascript'),
    (r'\baws\b', 'aws'),
    (r'\bgcp\b|\bgoogle\s*cloud\b', 'gcp'),
    (r'\bazure\b', 'azure'),
    (r'\bdocker\b', 'docker'),
    (r'\bkubernetes\b', 'kubernetes'),
    (r'\bdbt\b', 'dbt'),
    (r'\bairflow\b', 'airflow'),
    (r'\bkafka\b', 'kafka'),
    (r'\bsnowflake\b', 'snowflake'),
    (r'\bbigquery\b', 'bigquery'),
    (r'\bpandas\b', 'pandas'),
    (r'\bscikit[\s-]*learn\b', 'scikit-learn'),
    (r'\bdeep\s*learning\b', 'deep learning'),
    (r'\bllm\b|\blarge\s*language\s*model\b', 'llm'),
    (r'\bproduct\s*management\b|\bproduct\s*manager\b', 'product management'),
    (r'\blooker\b', 'looker'),
    (r'\bsalesforce\b', 'salesforce'),
    # Business Analyst skills
    (r'\bbusiness\s*analysis\b|\bbusiness\s*analyst\b', 'business analysis'),
    (r'\brequirements\s*(elicitation|gathering|analysis)\b', 'requirements analysis'),
    (r'\bprocess\s*(mapping|improvement|optimization)\b', 'process mapping'),
    (r'\bjira\b', 'jira'),
    (r'\bconfluence\b', 'confluence'),
    (r'\bagile\b', 'agile'),
    (r'\bscrum\b', 'scrum'),
    (r'\bvisio\b', 'visio'),
    (r'\bstakeholder\b', 'stakeholder management'),
    (r'\bsap\b', 'sap'),
    (r'\bpower\s*apps\b', 'power apps'),
    (r'\bpower\s*automate\b', 'power automate'),
    (r'\bsharepoint\b', 'sharepoint'),
    (r'\bvba\b', 'vba'),
    (r'\bqlik\b', 'qlik'),
    (r'\bmicrosoft\s*office\b|\bms\s*office\b', 'microsoft office'),
    # Data Engineering
    (r'\bmlops\b', 'mlops'),
    (r'\bteradata\b', 'teradata'),
    (r'\bhadoop\b', 'hadoop'),
    (r'\bredshift\b', 'redshift'),
    (r'\belasticsearch\b', 'elasticsearch'),
    (r'\bnumpy\b', 'numpy'),
    (r'\bmatplotlib\b', 'matplotlib'),
    (r'\bseaborn\b', 'seaborn'),
]

COMPILED_PATTERNS = [(re.compile(p, re.IGNORECASE), name) for p, name in SKILL_PATTERNS]
# Fix R pattern - only match standalone R as a programming language
R_PATTERN = re.compile(r'(?<![a-zA-Z])[Rr](?![a-zA-Z])\s+(?:programming|language|software|package|script|studio|markdown|shiny|ggplot|tidyverse|dplyr|cran)|(?:programming\s+in|using|with|knowledge\s+of)\s+[Rr](?![a-zA-Z])|\b[Rr]\b(?=\s*,|\s*and\s*python|\s*&)', re.IGNORECASE)


def extract_skills(description: str) -> list[str]:
    text = description or ""
    found = []
    for pattern, name in COMPILED_PATTERNS:
        if name == 'R':
            # Special handling for R to avoid false positives
            if R_PATTERN.search(text):
                found.append('R')
        elif pattern.search(text):
            found.append(name)
    return found


def _clean_text(value, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    if text.lower() in ("", "nan", "none", "null"):
        return default
    return text


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    text = unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _safe_int(value, default: int = 0) -> int:
    try:
        if value is None:
            return default
        text = str(value).replace(",", "").replace("$", "").strip()
        if text.lower() in ("", "nan", "none", "null"):
            return default
        return int(float(text))
    except Exception:
        return default


SALARY_RE = re.compile(r'\$?\s*(\d{2,3})(?:,\d{3})?\s*[kK]\b|\$?\s*(\d{2,3}),(\d{3})')
YEARS_RE = re.compile(r'(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:professional\s+)?experience', re.IGNORECASE)
LOCATION_RE = re.compile(r'\b(?:location|based in)\s*:?\s*([A-Z][A-Za-z .,-]{2,60})', re.IGNORECASE)


def _infer_salary(description: str) -> tuple[int, int]:
    values = []
    for m in SALARY_RE.finditer(description or ""):
        if m.group(1):
            values.append(int(m.group(1)) * 1000)
        elif m.group(2) and m.group(3):
            values.append(int(f"{m.group(2)}{m.group(3)}"))
    values = [v for v in values if 30000 <= v <= 400000]
    if not values:
        return 0, 0
    return min(values), max(values)


def _infer_required_years(description: str) -> int:
    years = [_safe_int(m.group(1)) for m in YEARS_RE.finditer(description or "")]
    return min(years) if years else 0


def _infer_location(raw_location: str, description: str) -> str:
    if raw_location:
        return raw_location
    m = LOCATION_RE.search(description or "")
    if m:
        loc = m.group(1).strip(" .,-")
        if len(loc) <= 60:
            return loc
    return ""


def _infer_employment_type(raw_type: str, title: str, description: str) -> str:
    raw = (raw_type or "").lower()
    title_l = (title or "").lower()
    desc = (description or "").lower()
    explicit_contract = any(p in desc for p in [
        "contract role", "contract position", "contract job", "contract-to-hire",
        "contract to hire", "temporary role", "temporary position",
    ])
    if any(w in f"{title_l} {raw}" for w in ["contract", "contractor", "temporary", " temp ", "freelance", "self-employed"]) or explicit_contract:
        return "Contract"
    if "part time" in f"{title_l} {raw}" or "part-time" in f"{title_l} {raw}":
        return "Part-time"
    if raw_type and raw_type.lower() not in ("other", "nan"):
        return raw_type
    return "Full-time"


def _nested(obj: dict, path: list[str], default=""):
    cur = obj
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
    return cur if cur is not None else default


def job_id(title: str, employer: str, location: str) -> str:
    key = f"{title}|{employer}|{location}".lower().strip()
    return hashlib.md5(key.encode()).hexdigest()[:16]


def load_kaggle_jobs(csv_path: str, limit: int = 30000) -> list[dict]:
    path = Path(csv_path)
    if not path.exists():
        print(f"[Ingestion] Kaggle CSV not found: {csv_path}")
        return []
    if path.suffix.lower() == ".json":
        return load_techmap_jsonl_jobs(csv_path, limit=limit)
    try:
        df = pd.read_csv(path, nrows=limit)
        df.columns = [c.lower().strip().replace(" ", "_") for c in df.columns]
        col_map = {
            "name": "title", "job_title": "title", "position": "title",
            "company": "employer", "organization": "employer",
            "contract_time": "employment_type", "job_type": "employment_type",
            "redirect_url": "link", "url": "link", "job_url": "link",
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
        jobs = []
        for _, row in df.iterrows():
            title = _clean_text(row.get("title", ""))
            employer = _clean_text(row.get("employer", ""), "Unknown employer")
            raw_location = _clean_text(row.get("location", ""))
            if not title:
                continue
            description = _clean_text(row.get("description", ""))
            link = _clean_text(row.get("link", ""))
            location = _infer_location(raw_location, description)
            skills = extract_skills(description)
            emp_type = _infer_employment_type(_clean_text(row.get("employment_type", "")), title, description)
            sal_min = _safe_int(row.get("salary_min", 0))
            sal_max = _safe_int(row.get("salary_max", 0))
            if sal_max == 0:
                sal_min, sal_max = _infer_salary(description)
            required_years = _safe_int(row.get("required_years", 0)) or _infer_required_years(description)
            company_size = _safe_int(row.get("company_size", 0))
            jobs.append({
                "job_id": job_id(title, employer, location),
                "title": title,
                "company": employer,
                "location": location,
                "employment_type": emp_type,
                "salary_min": sal_min,
                "salary_max": sal_max,
                "salary_display": f"${sal_min:,}–${sal_max:,}" if sal_max > 0 else "Not listed",
                "industry": _clean_text(row.get("industry", "General"), "General"),
                "visa": _clean_text(row.get("visa", "Unknown"), "Unknown"),
                "required_years": required_years,
                "company_size": company_size,
                "description": description,
                "skills_extracted": skills,
                "link": link,
                "source": _clean_text(row.get("source", ""), "kaggle"),
            })
        print(f"[Ingestion] Loaded {len(jobs)} jobs from Kaggle CSV")
        return jobs
    except Exception as e:
        print(f"[Ingestion] Error loading CSV: {e}")
        return []


def load_techmap_jsonl_jobs(json_path: str, limit: int = 30000) -> list[dict]:
    """Stream the original Techmap/Kaggle JSONL file without modifying it."""
    path = Path(json_path)
    jobs = []
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            for line_no, line in enumerate(f, start=1):
                if len(jobs) >= limit:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue

                title = _clean_text(row.get("name")) or _clean_text(_nested(row, ["position", "name"]))
                if not title:
                    continue
                description = _clean_text(row.get("text")) or _strip_html(_clean_text(_nested(row, ["json", "schemaOrg", "description"])))
                if not description:
                    continue

                company = (
                    _clean_text(_nested(row, ["orgCompany", "name"]))
                    or _clean_text(_nested(row, ["orgCompany", "nameOrg"]))
                    or _clean_text(_nested(row, ["json", "schemaOrg", "hiringOrganization", "name"]))
                    or "Unknown employer"
                )
                address = row.get("orgAddress") if isinstance(row.get("orgAddress"), dict) else {}
                city = _clean_text(address.get("city"))
                state = _clean_text(address.get("state"))
                country = _clean_text(address.get("country")) or _clean_text(address.get("countryCode")) or _clean_text(row.get("sourceCC"))
                formatted = _clean_text(address.get("formatted")) or _clean_text(address.get("addressLine"))
                location = formatted or ", ".join([x for x in [city, state, country.upper() if len(country) == 2 else country] if x])

                raw_type = (
                    _clean_text(_nested(row, ["position", "workType"]))
                    or _clean_text(_nested(row, ["json", "schemaOrg", "employmentType"]))
                )
                emp_type = _infer_employment_type(raw_type, title, description)
                sal_min, sal_max = _infer_salary(description)
                source = _clean_text(row.get("source"), "kaggle_json")
                link = _clean_text(row.get("url")) or _clean_text(_nested(row, ["json", "schemaOrg", "url"]))
                required_years = _infer_required_years(description)

                jobs.append({
                    "job_id": job_id(title, company, location or str(row.get("idInSource", line_no))),
                    "title": title,
                    "company": company,
                    "location": location,
                    "employment_type": emp_type,
                    "salary_min": sal_min,
                    "salary_max": sal_max,
                    "salary_display": f"${sal_min:,}–${sal_max:,}" if sal_max > 0 else "Not listed",
                    "industry": "General",
                    "visa": "Unknown",
                    "required_years": required_years,
                    "company_size": 0,
                    "description": description,
                    "skills_extracted": extract_skills(description),
                    "link": link,
                    "source": source,
                })
        print(f"[Ingestion] Streamed {len(jobs)} jobs from original Kaggle JSONL")
        return jobs
    except Exception as e:
        print(f"[Ingestion] Error loading JSONL: {e}")
        return []


def fetch_adzuna_jobs(app_id: str, app_key: str, query: str = "data analyst", country: str = "us", pages: int = 3) -> list[dict]:
    jobs = []
    for page in range(1, pages + 1):
        try:
            url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
            params = {"app_id": app_id, "app_key": app_key, "results_per_page": 50, "what": query}
            resp = requests.get(url, params=params, timeout=10)
            if not resp.ok:
                print(f"[Adzuna] Query '{query}' page {page} returned HTTP {resp.status_code}")
                break
            for item in resp.json().get("results", []):
                title = item.get("title", "").strip()
                employer = item.get("company", {}).get("display_name", "").strip()
                location = item.get("location", {}).get("display_name", "").strip()
                if not title:
                    continue
                description = item.get("description", "")
                sal_min = int(item.get("salary_min", 0) or 0)
                sal_max = int(item.get("salary_max", 0) or 0)
                jobs.append({
                    "job_id": job_id(title, employer, location),
                    "title": title, "company": employer, "location": location,
                    "employment_type": "Full-time",
                    "salary_min": sal_min, "salary_max": sal_max,
                    "salary_display": f"${sal_min:,}–${sal_max:,}" if sal_max > 0 else "Competitive",
                    "industry": item.get("category", {}).get("label", "General"),
                    "visa": "Not specified", "required_years": 0, "company_size": 0,
                    "description": description,
                    "skills_extracted": extract_skills(description),
                    "link": item.get("redirect_url", ""), "source": "adzuna",
                })
        except Exception as e:
            print(f"[Adzuna] Query '{query}' page {page} failed: {type(e).__name__}")
            break
    print(f"[Ingestion] Fetched {len(jobs)} jobs from Adzuna")
    return jobs


def deduplicate(jobs: list[dict]) -> list[dict]:
    seen = set()
    result = []
    for job in jobs:
        jid = job["job_id"]
        if jid not in seen:
            seen.add(jid)
            result.append(job)
    print(f"[Dedup] {len(jobs)} → {len(result)} unique jobs ({len(jobs)-len(result)} duplicates removed)")
    return result


def load_all_jobs(kaggle_csv: str, adzuna_app_id: str = "", adzuna_app_key: str = "") -> dict:
    kaggle = load_kaggle_jobs(kaggle_csv)
    adzuna = []
    if adzuna_app_id and adzuna_app_key:
        queries = os.getenv(
            "ADZUNA_QUERIES",
            "data analyst,machine learning engineer,data scientist,mlops engineer,applied scientist,research scientist,analytics engineer,business intelligence analyst",
        )
        pages = int(os.getenv("ADZUNA_PAGES", "3") or 3)
        for query in [q.strip() for q in queries.split(",") if q.strip()]:
            adzuna += fetch_adzuna_jobs(adzuna_app_id, adzuna_app_key, query=query, pages=pages)
    all_jobs = kaggle + adzuna
    deduped = deduplicate(all_jobs)
    return {
        "jobs": deduped,
        "total_ingested": len(all_jobs),
        "duplicates_removed": len(all_jobs) - len(deduped),
        "kaggle_count": len(kaggle),
        "adzuna_count": len(adzuna),
    }


def market_insights(jobs: list[dict]) -> dict:
    if not jobs:
        return {}

    # Skills: count mentions, take top 8, normalize to 100%
    skill_counts: dict[str, int] = {}
    for job in jobs:
        seen = set()
        for skill in job.get("skills_extracted", []):
            if skill and skill not in seen:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1
                seen.add(skill)
    top_skills_raw = sorted(skill_counts.items(), key=lambda x: -x[1])[:8]
    total_skill = sum(c for _, c in top_skills_raw) or 1
    top_skills_pct = [[s, round(c / total_skill * 100, 1)] for s, c in top_skills_raw]

    # Roles: take top 6, normalize to 100%
    role_counts: dict[str, int] = {}
    for job in jobs:
        t = (job.get("title", "") or "").strip()
        if t:
            role_counts[t] = role_counts.get(t, 0) + 1
    top_roles_raw = sorted(role_counts.items(), key=lambda x: -x[1])[:6]
    total_roles = sum(c for _, c in top_roles_raw) or 1
    top_roles_pct = [[r, round(c / total_roles * 100, 1)] for r, c in top_roles_raw]

    location_counts: dict[str, int] = {}
    for job in jobs:
        loc = (job.get("location", "") or "").strip()
        if loc and loc.lower() not in ("nan", "unknown"):
            location_counts[loc] = location_counts.get(loc, 0) + 1
    top_locations_raw = sorted(location_counts.items(), key=lambda x: -x[1])[:8]
    total_locations = sum(c for _, c in top_locations_raw) or 1
    top_locations_pct = [[loc, round(c / total_locations * 100, 1)] for loc, c in top_locations_raw]

    # Salary distribution — include competitive bucket
    salary_buckets = {"Not Listed": 0, "<80K": 0, "80K-100K": 0, "100K-130K": 0, "130K-160K": 0, "160K+": 0}
    for job in jobs:
        lo, hi = job.get("salary_min", 0), job.get("salary_max", 0)
        if lo == 0 and hi == 0:
            salary_buckets["Not Listed"] += 1
            continue
        mid = (lo + hi) / 2
        if mid < 80000: salary_buckets["<80K"] += 1
        elif mid < 100000: salary_buckets["80K-100K"] += 1
        elif mid < 130000: salary_buckets["100K-130K"] += 1
        elif mid < 160000: salary_buckets["130K-160K"] += 1
        else: salary_buckets["160K+"] += 1
    total_sal = sum(salary_buckets.values()) or 1
    salary_pct = [[k, round(v / total_sal * 100, 1)] for k, v in salary_buckets.items() if v > 0]

    return {
        "top_skills": top_skills_pct,
        "in_demand_roles": top_roles_pct,
        "top_locations": top_locations_pct,
        "salary_distribution": salary_pct,
        "total_jobs": len(jobs),
    }
