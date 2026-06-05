"""Resume PDF parser — uses Claude API for accurate extraction."""
from __future__ import annotations
import json, os, re
from pathlib import Path

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?(?:\(?\d{3}\)?[\s.-]?)\d{3}[\s.-]?\d{4}")
LINKEDIN_RE = re.compile(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+")


def extract_text(path: Path) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            return "\n".join(p.extract_text() or "" for p in pdf.pages)
    except Exception:
        return path.read_text(encoding="utf-8", errors="ignore")


def parse_pdf(path: Path, api_key: str = "") -> dict:
    text = extract_text(path)
    if not text.strip():
        return _empty()
    key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    if key:
        try:
            return _claude_parse(text, key)
        except Exception as e:
            print(f"[Parser] Claude failed: {e}, falling back to regex")
    return _regex_parse(text)


def _claude_parse(text: str, api_key: str) -> dict:
    import urllib.request
    prompt = f"""Extract resume information and return ONLY valid JSON (no markdown):
{{
  "name": "full name",
  "email": "email",
  "phone": "phone",
  "linkedin": "linkedin url or empty",
  "current_location": "City, State or empty",
  "work_authorization": "one of: U.S. Citizen, Permanent Resident, F-1 (STEM OPT), F-1 (OPT), H-1B, Needs Sponsorship, or empty",
  "education": [{{"school":"","degree":"","major":"","start":"YYYY-MM or empty","end":"YYYY-MM or empty"}}],
  "experience": [{{"company":"","title":"","start":"YYYY-MM or empty","end":"YYYY-MM or Present","current":false,"description":""}}],
  "skills": ["skill1","skill2"],
  "projects": [{{"name":"","description":"","tech_stack":""}}],
  "certifications": [{{"name":"","issuer":"","date":""}}]
}}

Resume:
{text[:4000]}"""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=payload,
        headers={"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    raw = data["content"][0]["text"].strip()
    raw = re.sub(r"^```[a-z]*\n?", "", raw); raw = re.sub(r"\n?```$", "", raw)
    return json.loads(raw)


def _regex_parse(text: str) -> dict:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    email = _first(EMAIL_RE, text)
    phone = _first(PHONE_RE, text)
    linkedin = _first(LINKEDIN_RE, text)
    name = next((l for l in lines[:8] if 1 <= len(l.split()) <= 5 and l[0].isupper()
                 and not any(x in l.lower() for x in ["@", "http", "resume", "phone"])), "")
    skills = _extract_skills(text)
    edu_block = _section(text, ["education", "academic"], ["experience", "work", "skills", "projects", "certifications"])
    exp_block = _section(text, ["experience", "work experience", "professional experience", "employment"], ["education", "skills", "projects", "certifications"])
    proj_block = _section(text, ["projects", "academic projects", "selected projects"], ["education", "experience", "work", "skills", "certifications"])
    cert_block = _section(text, ["certifications", "certificates", "licenses"], ["education", "experience", "work", "skills", "projects"])
    inline_certs = _inline_prefixed(lines, "certifications")
    return {
        "name": name, "email": email, "phone": phone, "linkedin": linkedin,
        "current_location": "", "work_authorization": "",
        "education": _parse_edu(edu_block),
        "experience": _parse_exp(exp_block),
        "skills": skills,
        "projects": _parse_proj(proj_block),
        "certifications": _parse_cert(cert_block or inline_certs),
    }

SKILL_BANK = ["Python","SQL","Excel","Tableau","Power BI","R","Machine Learning","NLP",
    "PyTorch","TensorFlow","Spark","PySpark","Statistics","Data Analysis","A/B Testing",
    "Java","C++","JavaScript","AWS","GCP","Azure","Docker","Kubernetes","dbt","Airflow",
    "Kafka","Snowflake","BigQuery","pandas","NumPy","scikit-learn","Deep Learning","LLM"]

def _extract_skills(text: str) -> list[str]:
    lower = text.lower()
    return [s for s in SKILL_BANK if s.lower() in lower]

def _first(pat, text):
    m = pat.search(text); return m.group(0) if m else ""

DATE_RE = re.compile(r"(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+)?(?:20|19)\d{2}|Present", re.I)


def _norm_heading(line: str) -> str:
    return re.sub(r"[^a-z ]+", "", line.lower()).strip()


def _heading_matches(line: str, needles: list[str]) -> bool:
    h = _norm_heading(line)
    compact = h.replace(" ", "")
    return any(s in h or s.replace(" ", "") in compact for s in needles)


def _section(text, starts, stops):
    lines = text.splitlines()
    si = None
    for i, l in enumerate(lines):
        h = _norm_heading(l)
        if _heading_matches(l, starts) and len(h) <= 50:
            si = i + 1; break
    if si is None: return ""
    ei = len(lines)
    for i in range(si, len(lines)):
        h = _norm_heading(lines[i])
        if _heading_matches(lines[i], stops) and len(h) <= 50:
            ei = i; break
    return "\n".join(lines[si:ei])


def _inline_prefixed(lines: list[str], label: str) -> str:
    out = []
    for line in lines:
        if line.lower().startswith(label.lower() + ":"):
            out.append(line.split(":", 1)[1].strip())
    return "\n".join(out)

def _parse_edu(block):
    if not block: return []
    lines = [l.strip() for l in block.splitlines() if l.strip()]
    school = next((l for l in lines if any(w in l.lower() for w in ["university","college","institute","school","uc davis","stanford","rutgers"])), "")
    degree = next((l for l in lines if any(w in l.lower() for w in ["master","bachelor","phd","mba","msba","b.s","bachelor","m.s","ms ","bs "])), "")
    major = next((l for l in lines if any(w in l.lower() for w in ["analytics","computer","data","business","statistics","science","engineering"])), "")
    dates = DATE_RE.findall(block)
    if not school and not degree: return []
    return [{"school": school, "degree": degree, "major": major, "start": dates[0] if dates else "", "end": dates[-1] if dates else ""}]

def _parse_exp(block):
    if not block: return []
    lines = [l.strip() for l in block.splitlines() if l.strip()]
    if not lines: return []
    role_words = ["analyst","engineer","scientist","manager","developer","intern","researcher","consultant","associate","owner","lead"]
    starts = [i for i, l in enumerate(lines) if any(w in l.lower() for w in role_words) and len(l) < 120]
    if not starts:
        starts = [0]
    rows = []
    for pos, start_i in enumerate(starts[:4]):
        end_i = starts[pos + 1] if pos + 1 < len(starts) else min(len(lines), start_i + 6)
        chunk = lines[start_i:end_i]
        title = chunk[0]
        company = ""
        if start_i > 0 and len(lines[start_i - 1]) < 100 and not DATE_RE.search(lines[start_i - 1]):
            company = lines[start_i - 1]
        elif len(chunk) > 1 and len(chunk[1]) < 100 and not chunk[1].startswith(("•", "-", "*")):
            company = chunk[1]
        dates = DATE_RE.findall(" ".join(chunk))
        desc_lines = [l for l in chunk[1:] if l != company]
        rows.append({
            "company": company,
            "title": title,
            "start": dates[0] if dates else "",
            "end": dates[-1] if dates else "",
            "current": bool(dates and dates[-1].lower() == "present"),
            "description": " ".join(desc_lines[:4]),
        })
    return rows

def _parse_proj(block):
    if not block: return []
    lines = [l.strip() for l in block.splitlines() if l.strip()]
    if not lines: return []
    return [{"name": lines[0], "description": " ".join(lines[1:3]), "tech_stack": ""}]


def _parse_cert(block):
    if not block: return []
    lines = [l.strip(" -•\t") for l in block.splitlines() if l.strip(" -•\t")]
    certs = []
    for line in lines[:6]:
        date = ""
        m = DATE_RE.search(line)
        if m:
            date = m.group(0)
        issuer = ""
        if " - " in line:
            name, issuer = [x.strip() for x in line.split(" - ", 1)]
        elif "," in line:
            name, issuer = [x.strip() for x in line.split(",", 1)]
        else:
            name = line
        certs.append({"name": name, "issuer": issuer, "date": date})
    return certs

def _empty():
    return {"name":"","email":"","phone":"","linkedin":"","current_location":"","work_authorization":"",
            "education":[],"experience":[],"skills":[],"projects":[],"certifications":[]}
