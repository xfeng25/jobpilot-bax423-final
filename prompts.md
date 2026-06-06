# JobPilot — AI Prompt Log
**BAX-423 Big Data · Option B · Spring 2026**

Key prompts used during development, showing iteration from weak to production-aware. AI tools used: Claude (architecture, review, resume generation), Cursor (implementation).

---

## 1. System Architecture

**v1 — Weak:**
```
Design a job matching app in Python.
```

**v2 — Specific:**
```
Design a BAX-423 Option B job matching application with:
- Kaggle job data ingestion and deduplication
- Embedding-based retrieval using TF-IDF and SVD
- Multi-stage ranking pipeline with hard filters and weighted scoring
- Accept/reject/skip feedback learning
- Tailored resume generation using Claude API
```

**v3 — Production-aware:**
```
Design the app so it runs fully offline using a bundled CSV snapshot,
and optionally enriches results from the Adzuna live API when credentials
are provided. Separate concerns into ingestion, matching, feedback,
and generation modules. Deploy on Google Cloud Run with Docker.
The app must work without API keys so graders can run it without setup.
```

**Output used:** FastAPI backend, static frontend, modular pipeline under `backend/pipeline/`, offline-first data loading with optional API enrichment.

---

## 2. Data Ingestion and Deduplication

**v1 — Weak:**
```
Load job postings from a CSV file.
```

**v2 — Specific:**
```
Design a streaming-style ingestion pipeline that loads 30,000 Kaggle
job records, normalizes salary and employment type fields, extracts
skills from descriptions, and deduplicates by job identity.
```

**v3 — Production-aware:**
```
Do not modify the original Kaggle source file. Stream records from the
source dump and write a clean 30,000-row sample to data/jobs.csv.
Merge live Adzuna API records at startup when API keys are present.
Deduplicate across both sources using a hash of title + company + location.
Handle missing salary, required_years, and visa fields conservatively
rather than assuming or imputing values.
```

**Output used:** `backend/pipeline/ingestion.py` with structured field normalization, 60+ regex skill patterns, and hash-based deduplication across Kaggle and Adzuna sources.

---

## 3. Skill Extraction

**v1 — Weak:**
```
Extract skills from job descriptions.
```

**v2 — Specific:**
```
Write regex patterns to extract Python, SQL, R, Tableau, PySpark, PyTorch,
TensorFlow, Kafka, Spark, AWS, MLOps, and business analysis skills
from job description text.
```

**v3 — Production-aware:**
```
Fix standalone R matching so the extractor does not mark every word
containing the letter "r" as the R programming language. Use word
boundaries and context patterns such as "programming in R", "using R",
or "R and Python" to confirm R as a programming language match.
Apply the same pattern to avoid false positives on short ambiguous tokens.
```

**Output used:** `SKILL_PATTERNS` and `R_PATTERN` in `ingestion.py` with special-cased R detection and 60+ skill patterns covering analytics, ML, data engineering, cloud, and business analysis roles.

---

## 4. Embedding-Based Retrieval

**v1 — Weak:**
```
Implement job search using TF-IDF similarity.
```

**v2 — Specific:**
```
Build an embedding retrieval layer using TF-IDF vectorization,
TruncatedSVD to reduce to 150 dimensions, L2 normalization,
and cosine similarity search. Jobs and profiles should both be
represented as dense vectors for semantic matching.
```

**v3 — Production-aware:**
```
Do not call .toarray() on the TF-IDF matrix because converting a
30,000-row sparse matrix to dense uses over 1GB of RAM and will cause
an OOM crash on Cloud Run free tier. Keep the TF-IDF matrix and query
sparse, and only convert the final score vector to an array after
matrix multiplication. Build a separate TFIDFBaseline class using
sparse matrices for benchmarking latency against the LSA embedding
index.
```

**Output used:** `EmbeddingIndex` (TF-IDF + SVD, dense LSA matrix) and `TFIDFBaseline` (sparse TF-IDF baseline) in `matching.py`. Benchmark endpoint at `/api/benchmark` compares both.

---

## 5. Multi-Stage Ranking Pipeline

**v1 — Weak:**
```
Rank jobs by relevance to a user profile.
```

**v2 — Specific:**
```
Design a 4-stage ranking pipeline: candidate retrieval by cosine
similarity, hard filters for dealbreakers, weighted scoring combining
embedding similarity, role match, skill match, location, salary,
experience, and seniority, and a final rerank step.
```

**v3 — Production-aware:**
```
Remove the separate title boost and fold title evidence into role_match
to avoid double-counting. Role scoring should use title fit × 0.65 +
domain evidence fit × 0.35. Always sort results by final match_score
descending. Do not force target-role coverage after scoring because
enforcing coverage conflicts with score ordering and produces misleading
rankings. The final stage should only deduplicate by job_id and sort
by score.
```

**Output used:** `run_pipeline()` in `matching.py` with 4 stages: retrieve → hard filter → score → sort+dedup. Role match uses title fit plus domain evidence without separate title boost.

---

## 6. Persona Hard Filters

**v1 — Weak:**
```
Filter jobs based on user preferences.
```

**v2 — Specific:**
```
Implement hard filters for the four BAX-423 test personas:
- Aisha: no Senior/Staff roles, no defense companies, no 5+ years ML required
- Marcus: no 3+ years required, no contract/unpaid roles
- Priya: no Junior roles, no tiny startups, US-only
- Kenji: no contract/temp roles, visa sponsorship compatible
```

**v3 — Production-aware:**
```
Hard filters must use explicit evidence only. Do not filter a job based
on missing metadata — only filter when the title, description, or
structured fields clearly violate a dealbreaker. For years-of-experience
filters, extract required years from both the structured field and
description text patterns such as "minimum 3 years", "3+ years exp",
"min. 4 years". For defense filtering, check title, company name,
industry, and description for signals like "defense", "military",
"DoD", "national security", and known defense contractor names.
Do not add constraints the persona did not state — Priya does not
have a contract filter; do not add one.
```

**Output used:** `_hard_filter()` in `matching.py` with pattern-based detection for seniority, defense, contract, experience years, visa, and non-job content.

---

## 7. Adaptive Feedback Learning

**v1 — Weak:**
```
Learn from user feedback to improve recommendations.
```

**v2 — Specific:**
```
Implement an implicit feedback learner where accept, reject, and skip
actions update profile-specific feature weights for job IDs, skills,
location, and industry. Apply these weights as a score boost on the
next search.
```

**v3 — Production-aware:**
```
Scope all feedback by profile_id so one persona's accept/reject actions
do not affect another persona's results. Limit the total feedback boost
to ±8 points so a single accept cannot dominate the ranking. Apply
bounded feedback updates: direct job_id signal up to ±0.60, skill
signals up to ±0.35, and location/industry signals up to ±0.25. Track
feedback-based NDCG@10 using accept=3, skip=1, reject=0 as relevance
labels, and only report it after at least 3 labeled results exist.
```

**Output used:** `FeedbackLearner` in `feedback.py` with profile-scoped weights, bounded boost, and NDCG tracking. Applied in `_feedback_score()` inside the scoring function.

---

## 8. Tailored Resume Generation

**v1 — Weak:**
```
Generate a resume for this job application.
```

**v2 — Specific:**
```
Write a tailored resume for this candidate applying to this job.
Use only information from the candidate profile. Reorder and reword
content to match job requirements. Include an Education section.
Return JSON with summary, education, skills, experience, and projects.
```

**v3 — Production-aware:**
```
Do not invent experience, achievements, or certifications not in
the profile. Do not claim production deployment, model serving,
end-to-end ML pipelines, or leadership unless the profile explicitly
supports it. For career-pivot candidates, frame related evidence as
coursework, exposure, or applied project experience rather than
production capability. Do not expand MSBA as Master of Business
Administration — render it as Master of Science in Business Analytics.
For profiles with published research or conference papers, lead the
summary and experience with publication evidence before generic skills.
For student or new-grad profiles, place Education before Experience.
If a section has no candidate-provided content, omit it entirely —
do not write placeholder text.
```

**Output used:** `_claude_generate()` in `resume_generator.py` with rule-enforced prompt and `_clean_empty_section_text()` to remove placeholder output.

---

## 9. Cover Letter Generation

**v1 — Weak:**
```
Write a cover letter for this job.
```

**v2 — Specific:**
```
Write a concise 3-4 paragraph cover letter tailored to this job.
Use only information from the candidate profile. Use professional
letter format. Return JSON with the letter text.
```

**v3 — Production-aware:**
```
Remove all bracket placeholders such as [Your Address], [Date],
and [Company Address] from the output. Only include contact, date,
company, and location information that is explicitly provided in the
profile and job fields. Do not invent publications, certifications,
or achievements. Use only this exact company name in the letter:
{company}. Include a deterministic fallback so the cover letter
feature works even when the Claude API is unavailable.
```

**Output used:** `_claude_cover_letter()` and `_template_cover_letter()` in `resume_generator.py`, with `_remove_placeholders()` post-processing and `_cover_letter_header()` using only real profile data.

---

## 10. Deployment

**v1 — Weak:**
```
Deploy the app online.
```

**v2 — Specific:**
```
Prepare the app for deployment on Google Cloud Run using Docker.
The service should run FastAPI with uvicorn on the port provided
by the platform and read API keys from environment variables.
```

**v3 — Production-aware:**
```
The app must start successfully even when ANTHROPIC_API_KEY,
ADZUNA_APP_ID, and ADZUNA_APP_KEY are not set — resume generation
and live enrichment should degrade gracefully. Set KAGGLE_CSV to
data/jobs.csv by default so graders can run the app with one command
without any environment setup. Use a lightweight Dockerfile based on
python:3.11-slim to keep the image size reasonable. Confirm the
/api/health endpoint returns the loaded job count so deployment status
is verifiable.
```

**Output used:** `Dockerfile`, `render.yaml`, Cloud Run service configuration, `.env.example`, default `KAGGLE_CSV` handling in `main.py`, and graceful API key handling throughout the pipeline.
