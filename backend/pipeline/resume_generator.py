"""Generate tailored resume using Claude API."""
from __future__ import annotations
import json, os, re, urllib.request


def generate(profile: dict, job: dict, api_key: str = "") -> dict:
    key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
    if key:
        try:
            return _claude_generate(profile, job, key)
        except Exception as e:
            print(f"[Resume] Claude failed: {e}")
    return _template_generate(profile, job)


def _claude_generate(profile: dict, job: dict, api_key: str) -> dict:
    exp_text = "\n".join([f"- {e.get('title')} at {e.get('company')}: {e.get('description','')}" for e in profile.get("experience", [])])
    edu_text = "\n".join([f"- {e.get('degree')} in {e.get('major')} from {e.get('school')}" for e in profile.get("education", [])])
    proj_text = "\n".join([f"- {p.get('name')}: {p.get('description')}" for p in profile.get("projects", [])])

    prompt = f"""You are a professional resume writer. Write a tailored resume for this candidate applying to this job.

RULES:
- Use ONLY information from the candidate profile below
- Do NOT invent experience, companies, or achievements
- Reorder and reword to match the job requirements
- Always include an Education section if education is provided
- For students, recent graduates, or internship-heavy candidates, emphasize education before work experience
- Use job requirements as target keywords, not as completed candidate achievements
- Do NOT claim production deployment, model serving, leadership, publications, full-time work, or domain experience unless the candidate profile explicitly supports it
- If a requirement is not directly supported, frame related profile evidence as coursework, exposure, prototypes, research, or development interest
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
  "projects": "relevant projects formatted nicely",
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
    result["ai_changes"] = result.get("ai_changes", ["Tailored summary to job", "Highlighted relevant skills", "Reordered experience"])
    return result


def _template_generate(profile: dict, job: dict) -> dict:
    job_skills = set(job.get("skills_extracted", []))
    profile_skills = profile.get("skills", [])
    relevant = [s for s in profile_skills if s.lower() in {x.lower() for x in job_skills}]
    name = profile.get("name", "Candidate")
    exp_list = profile.get("experience", [])
    exp_text = "\n\n".join([f"{e.get('title','Role')} at {e.get('company','Company')} ({e.get('start','')}-{e.get('end','')})\n{e.get('description','')}" for e in exp_list])
    proj_text = "\n\n".join([f"{p.get('name','')}: {p.get('description','')}" for p in profile.get("projects", [])])
    edu_text = _education_text(profile)
    return {
        "summary": f"{name} is targeting {job.get('title','')} roles at {job.get('company','')}, with strengths in {', '.join((relevant or profile_skills)[:4])}.",
        "education": edu_text,
        "skills": ", ".join(relevant or profile_skills),
        "experience": exp_text or "No experience added to profile yet.",
        "projects": proj_text or "No projects added to profile yet.",
        "ai_changes": ["Highlighted skills matching job requirements", "Tailored summary to target role", "Profile information used as-is"],
    }


def _education_text(profile: dict) -> str:
    rows = []
    for item in profile.get("education", []) or []:
        degree = " ".join([item.get("degree", ""), item.get("major", "")]).strip()
        school = item.get("school", "")
        dates = "-".join([x for x in [item.get("start", ""), item.get("end", "")] if x])
        line = " | ".join([x for x in [school, degree, dates] if x])
        if line:
            rows.append(line)
    return "\n".join(rows)
