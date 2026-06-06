"""Generate tailored resume and cover letter using Claude API."""
from __future__ import annotations
from datetime import date
import json, os, re, urllib.request


def generate(profile: dict, job: dict, api_key: str = "") -> dict:
    key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    if key:
        try:
            return _claude_generate(profile, job, key)
        except Exception as e:
            print(f"[Resume] Claude failed: {e}")
    return _template_generate(profile, job)


def generate_cover_letter(profile: dict, job: dict, api_key: str = "") -> dict:
    key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    if key:
        try:
            return _clean_cover_letter_result(_claude_cover_letter(profile, job, key), profile, job)
        except Exception as e:
            print(f"[CoverLetter] Claude failed: {e}")
    return _clean_cover_letter_result(_template_cover_letter(profile, job), profile, job)


def _claude_generate(profile: dict, job: dict, api_key: str) -> dict:
    exp_text = "\n".join([f"- {e.get('title')} at {e.get('company')}: {e.get('description','')}" for e in profile.get("experience", [])])
    edu_text = _education_text(profile)
    proj_text = "\n".join([f"- {p.get('name')}: {p.get('description')}" for p in profile.get("projects", [])])

    prompt = f"""You are a professional resume writer. Write a tailored resume for this candidate applying to this job.

RULES:
- Use ONLY information from the candidate profile below
- Do NOT invent experience, companies, or achievements
- Reorder and reword to match the job requirements
- Always include an Education section if education is provided
- Omit sections that have no candidate-provided content; do not write placeholder text for empty sections
- Use education exactly as provided and formatted below
- Do NOT expand MSBA as Master of Business Administration
- Do NOT describe a degree as currently pursuing, expected graduation, or recent graduate unless those words are explicitly provided in the candidate profile
- For students, recent graduates, or internship-heavy candidates, emphasize education before work experience
- For candidates with full-time work experience, emphasize experience before education
- Use job requirements as target keywords, not as completed candidate achievements
- Do NOT claim production deployment, model serving, leadership, publications, full-time work, or domain experience unless the candidate profile explicitly supports it
- Do NOT claim end-to-end ML pipelines, production ML pipelines, production inference, or production deployment unless those exact capabilities are explicitly supported by the candidate profile
- For career-pivot candidates, avoid overstating expertise; prefer hands-on analytics experience, ML fundamentals, coursework exposure, or applied project experience when the profile uses basic or exposure language
- If a requirement is not directly supported, frame related profile evidence as coursework, exposure, prototypes, research, or development interest
- If the candidate profile explicitly mentions published research, conference papers, or authored papers, lead the summary and experience with that publication/research evidence before generic technical skills
- Use only this target company name when naming the target employer: {job.get('company','')}
- Return JSON only (no markdown)

CANDIDATE PROFILE:
Name: {profile.get('name','')}
Email: {profile.get('email','')}
Phone: {profile.get('phone','')}
Location: {profile.get('current_location','')}
Skills: {', '.join(profile.get('skills', []))}
Education:
{edu_text}
Experience:
{exp_text}
Projects:
{proj_text}

TARGET JOB:
Title: {job.get('title','')}
Company: {job.get('company','')}
Description: {job.get('description','')[:500]}
Required Skills: {', '.join(job.get('skills_extracted', []))}

Return this JSON:
{{
  "summary": "2-3 sentence professional summary tailored to the job",
  "education": "education section formatted nicely",
  "skills": "comma-separated relevant skills",
  "experience": "formatted work experience, one role per paragraph",
  "projects": "relevant projects formatted nicely, or empty string if no projects are provided",
  "ai_changes": ["change 1", "change 2", "change 3"]
}}"""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1500,
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
    result = json.loads(raw)
    result["education"] = result.get("education") or _education_text(profile)
    result = _clean_resume_result(result)
    result["ai_changes"] = result.get("ai_changes", ["Tailored summary to job", "Highlighted relevant skills", "Reordered experience"])
    return result


def _template_generate(profile: dict, job: dict) -> dict:
    job_skills = set(job.get("skills_extracted", []))
    profile_skills = profile.get("skills", [])
    relevant = [s for s in profile_skills if s.lower() in {x.lower() for x in job_skills}]
    name = profile.get("name", "Candidate")
    exp_list = profile.get("experience", [])
    exp_text = "\n\n".join([f"{e.get('title','Role')} at {e.get('company','Company')} ({e.get('start','')}-{e.get('end','')})\n{_safe_resume_claims(e.get('description',''))}" for e in exp_list])
    proj_text = "\n\n".join([f"{p.get('name','')}: {p.get('description','')}" for p in profile.get("projects", [])])
    edu_text = _education_text(profile)
    summary = f"{name} is targeting {job.get('title','')} roles at {job.get('company','')}, with strengths in {', '.join((relevant or profile_skills)[:4])}."
    if _has_publication_evidence(profile):
        summary = f"{name} is a published machine learning researcher targeting {job.get('title','')} roles at {job.get('company','')}, with strengths in {', '.join((relevant or profile_skills)[:4])}."
    return {
        "summary": summary,
        "education": edu_text,
        "skills": ", ".join(relevant or profile_skills),
        "experience": exp_text,
        "projects": proj_text,
        "ai_changes": ["Highlighted skills matching job requirements", "Tailored summary to target role", "Profile information used as-is"],
    }


def _clean_resume_result(result: dict) -> dict:
    cleaned = dict(result or {})
    for key in ["summary", "education", "experience", "skills", "projects"]:
        cleaned[key] = _clean_empty_section_text(cleaned.get(key, ""))
    return cleaned


def _clean_empty_section_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    lowered = re.sub(r"\s+", " ", text.lower()).strip(" .")
    placeholder_bits = [
        "no projects", "projects provided", "projects added", "not provided",
        "no experience", "experience added", "no certifications",
    ]
    if any(bit in lowered for bit in placeholder_bits):
        return ""
    return text


def _has_publication_evidence(profile: dict) -> bool:
    text = " ".join([
        " ".join(str(s) for s in profile.get("skills", []) or []),
        " ".join(f"{e.get('title','')} {e.get('description','')}" for e in profile.get("experience", []) or []),
        " ".join(f"{p.get('name','')} {p.get('description','')} {p.get('tech','')}" for p in profile.get("projects", []) or []),
    ]).lower()
    return any(term in text for term in ["published research", "conference paper", "authored", "publication"])


def _safe_resume_claims(text: str) -> str:
    cleaned = str(text or "")
    replacements = {
        "end-to-end ML pipeline development": "ML model development workflows",
        "end-to-end ML pipelines": "ML model development workflows",
        "production ML pipelines": "ML model development workflows",
        "production inference": "model evaluation and applied ML workflows",
        "production deployment": "model development and evaluation",
        "model serving": "model development and evaluation",
    }
    for source, target in replacements.items():
        cleaned = re.sub(re.escape(source), target, cleaned, flags=re.IGNORECASE)
    return cleaned


def _education_text(profile: dict) -> str:
    rows = []
    for item in profile.get("education", []) or []:
        school = _clean(item.get("school", ""))
        degree = _format_degree(item.get("degree", ""), item.get("major", ""))
        dates = "-".join([x for x in [_clean(item.get("start", "")), _clean(item.get("end", ""))] if x])
        line = " | ".join([x for x in [school, degree, dates] if x])
        if line:
            rows.append(line)
    return "\n".join(rows)


def _clean(value: object) -> str:
    text = str(value or "").strip()
    if text.lower() in ("", "nan", "none", "null", "not provided", "[not provided]"):
        return ""
    return text


def _format_degree(degree: object, major: object) -> str:
    deg = _clean(degree)
    maj = _clean(major)
    dl = deg.lower()
    ml = maj.lower()
    if dl in ("master", "masters", "ms", "m.s.", "m.s"):
        if "business analytics" in ml:
            return "Master of Science in Business Analytics"
        if maj:
            return f"Master of Science in {maj}"
        return "Master"
    if dl in ("bachelor", "bachelors", "bs", "b.s.", "ba", "b.a."):
        if maj:
            return f"Bachelor of Science in {maj}"
        return "Bachelor"
    if dl in ("phd", "ph.d.", "doctorate"):
        if maj:
            return f"PhD in {maj}"
        return "PhD"
    if deg and maj:
        return f"{deg} in {maj}"
    return deg or maj


def _claude_cover_letter(profile: dict, job: dict, api_key: str) -> dict:
    exp_text = "\n".join([f"- {e.get('title')} at {e.get('company')}: {e.get('description','')}" for e in profile.get("experience", [])])
    edu_text = _education_text(profile)
    proj_text = "\n".join([f"- {p.get('name')}: {p.get('description')}" for p in profile.get("projects", [])])
    prompt = f"""You are a professional cover letter writer. Write a concise tailored cover letter for this candidate.

RULES:
- Use ONLY information from the candidate profile below
- Do NOT invent experience, companies, achievements, publications, education, or certifications
- Do NOT claim the candidate has completed job requirements unless the profile supports it
- Keep it to 3-4 short paragraphs
- Use a professional letter format
- Do NOT include bracket placeholders such as [Your Address], [Date], or [Company Address]
- Include only real contact, date, company, and location information provided below
- If company address is not provided, omit it
- Use only this target company name: {job.get('company','')}
- Return JSON only

CANDIDATE PROFILE:
Name: {profile.get('name','')}
Email: {profile.get('email','')}
Phone: {profile.get('phone','')}
Location: {profile.get('current_location','')}
Skills: {', '.join(profile.get('skills', []))}
Education:
{edu_text}
Experience:
{exp_text}
Projects:
{proj_text}

TARGET JOB:
Title: {job.get('title','')}
Company: {job.get('company','')}
Location: {job.get('location','')}
Description: {job.get('description','')[:700]}
Required Skills: {', '.join(job.get('skills_extracted', []))}

Return this JSON:
{{
  "letter": "full cover letter text",
  "ai_changes": ["change 1", "change 2", "change 3"]
}}"""
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 1200,
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
    result = json.loads(raw)
    result["ai_changes"] = result.get("ai_changes", ["Tailored opening to target role", "Highlighted relevant profile evidence", "Added concise closing paragraph"])
    return result


def _template_cover_letter(profile: dict, job: dict) -> dict:
    name = profile.get("name") or "Candidate"
    company = job.get("company") or "your team"
    title = job.get("title") or "this role"
    skills = ", ".join((profile.get("skills") or [])[:5])
    experience = profile.get("experience") or []
    lead = ""
    if experience:
        e = experience[0]
        lead = f"My background as {e.get('title','a professional')} at {e.get('company','my organization')} has given me relevant experience with {skills}."
    else:
        lead = f"My profile includes relevant experience with {skills}."
    letter = "\n\n".join([
        _cover_letter_header(profile, job),
        f"Dear {company} Hiring Team,",
        f"I am excited to apply for the {title} position at {company}. {lead}",
        f"I am especially interested in this opportunity because it aligns with my target role and the skills highlighted in my profile. I would bring a focused, analytical approach and a strong commitment to learning the role quickly.",
        "Thank you for your time and consideration. I would welcome the opportunity to discuss how my background can contribute to your team.",
        f"Sincerely,\n{name}",
    ])
    return {
        "letter": letter,
        "ai_changes": ["Tailored opening to target role", "Highlighted relevant profile evidence", "Added concise closing paragraph"],
    }


def _cover_letter_header(profile: dict, job: dict) -> str:
    name = _clean(profile.get("name", ""))
    contact = " | ".join([x for x in [
        _clean(profile.get("email", "")),
        _clean(profile.get("phone", "")),
        _clean(profile.get("current_location", "")),
        _clean(profile.get("linkedin", "")),
    ] if x])
    company = _clean(job.get("company", ""))
    location = _clean(job.get("location", ""))
    parts = [name, contact, date.today().strftime("%B %-d, %Y"), company, location]
    return "\n".join([p for p in parts if p])


def _clean_cover_letter_result(result: dict, profile: dict, job: dict) -> dict:
    letter = result.get("letter", "")
    letter = _remove_placeholders(letter)
    header = _cover_letter_header(profile, job)
    if header and header.split("\n")[0] not in letter[:200]:
        letter = f"{header}\n\n{letter}".strip()
    result["letter"] = letter
    result["ai_changes"] = result.get("ai_changes", ["Tailored opening to target role", "Highlighted relevant profile evidence", "Added concise closing paragraph"])
    return result


def _remove_placeholders(text: str) -> str:
    lines = []
    placeholder_re = re.compile(r"^\s*\[[^\]]*(address|date|company address|your address)[^\]]*\]\s*$", re.IGNORECASE)
    for line in (text or "").splitlines():
        if placeholder_re.match(line):
            continue
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned
