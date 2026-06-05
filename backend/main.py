"""
JobPilot — BAX-423 Final Project Option B
FastAPI backend serving frontend + ML pipeline
"""
from __future__ import annotations
import os, uuid
from pathlib import Path
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
UPLOAD_DIR = ROOT / "backend" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Load .env
env_path = ROOT / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
KAGGLE_CSV = os.getenv("KAGGLE_CSV", str(ROOT / "data" / "jobs.csv"))
ADZUNA_APP_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_APP_KEY = os.getenv("ADZUNA_APP_KEY", "")

# ── Load pipeline ─────────────────────────────────────────────────────────────
from backend.pipeline.ingestion import load_all_jobs, market_insights
from backend.pipeline.matching import EmbeddingIndex, TFIDFBaseline, run_pipeline
from backend.pipeline.feedback import FeedbackLearner
from backend.pipeline.resume_parser import parse_pdf
from backend.pipeline.resume_generator import generate as gen_resume

print("[Startup] Loading jobs...")
job_data = load_all_jobs(KAGGLE_CSV, ADZUNA_APP_ID, ADZUNA_APP_KEY)
JOBS = job_data["jobs"]
INGESTION_STATS = job_data

print("[Startup] Building embedding index...")
INDEX = EmbeddingIndex()
INDEX.build(JOBS)

TFIDF_INDEX = TFIDFBaseline()
TFIDF_INDEX.build(JOBS)

LEARNER = FeedbackLearner()
JOB_MAP = {j["job_id"]: j for j in JOBS}
INSIGHTS = market_insights(JOBS)

print(f"[Startup] Ready — {len(JOBS)} jobs loaded")

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(title="JobPilot", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")


@app.get("/")
def index():
    return FileResponse(str(FRONTEND / "index.html"))


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "jobs_loaded": len(JOBS),
        "ingestion": {
            "total_ingested": INGESTION_STATS["total_ingested"],
            "duplicates_removed": INGESTION_STATS["duplicates_removed"],
            "kaggle_count": INGESTION_STATS["kaggle_count"],
            "adzuna_count": INGESTION_STATS["adzuna_count"],
        },
        "lectures": ["Lecture 3: streaming ingestion", "Lecture 5: TF-IDF+SVD embeddings", "Lecture 6: implicit feedback learning", "Lecture 7: multi-stage ranking pipeline"],
    }


# ── Profile ───────────────────────────────────────────────────────────────────
@app.post("/api/profile/extract")
async def extract_profile(file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files supported")
    dest = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    dest.write_bytes(await file.read())
    result = parse_pdf(dest, api_key=ANTHROPIC_API_KEY)
    # Include raw text for View Original feature
    from backend.pipeline.resume_parser import extract_text
    raw_text = extract_text(dest)
    result["raw_text"] = raw_text[:3000]  # limit size
    return result


@app.post("/api/profile/save")
def save_profile(profile: dict):
    # Store profile in memory (stateless for demo)
    return {"status": "saved", "profile_id": profile.get("id", "default")}


# ── Jobs ──────────────────────────────────────────────────────────────────────
class SearchRequest(BaseModel):
    profile: dict
    criteria: dict


@app.post("/api/jobs/search")
def search_jobs(req: SearchRequest):
    profile_id = req.profile.get("id", "default")
    weights = LEARNER.get_weights(profile_id)
    labels = LEARNER.relevance_labels(profile_id)
    rejected_ids = set(req.criteria.get("rejected_ids", []))
    result = run_pipeline(
        jobs=JOBS,
        profile=req.profile,
        criteria=req.criteria,
        index=INDEX,
        feedback_weights=weights,
        limit=int(req.criteria.get("limit", 10)),
        rejected_ids=rejected_ids,
        feedback_labels=labels,
    )
    ndcg = result["benchmark"].get("ndcg_at_10")
    LEARNER.track_ndcg(ndcg)

    # Compute market insights from search results if available, else full dataset
    result_jobs = result.get("results", [])
    insights = market_insights(result_jobs) if len(result_jobs) >= 5 else INSIGHTS

    return {
        **result,
        "market_insights": insights,
        "learned_preferences": LEARNER.learned_preferences(),
        "ingestion_stats": {
            "total_ingested": INGESTION_STATS["total_ingested"],
            "duplicates_removed": INGESTION_STATS["duplicates_removed"],
            "jobs_indexed": len(JOBS),
        },
    }


# ── Feedback ──────────────────────────────────────────────────────────────────
class FeedbackRequest(BaseModel):
    profile_id: str
    job_id: str
    action: str  # accept | reject | skip


@app.post("/api/feedback")
def record_feedback(req: FeedbackRequest):
    if req.action.lower() not in ("accept", "reject", "skip"):
        raise HTTPException(400, "action must be accept, reject, or skip")
    job = JOB_MAP.get(req.job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    LEARNER.record(req.profile_id, req.job_id, req.action, job)
    return {
        "status": "recorded",
        "learned_preferences": LEARNER.learned_preferences(),
        "feedback_summary": LEARNER.summary(),
    }


# ── Resume ────────────────────────────────────────────────────────────────────
class ResumeRequest(BaseModel):
    profile: dict
    job: dict


@app.post("/api/resume/generate")
def generate_resume(req: ResumeRequest):
    result = gen_resume(req.profile, req.job, api_key=ANTHROPIC_API_KEY)
    resume_id = uuid.uuid4().hex[:12]
    return {
        "id": resume_id,
        "name": f"Resume_{req.job.get('title','').replace(' ','_')}_{req.job.get('company','').replace(' ','_')}",
        "job_title": req.job.get("title", ""),
        "company": req.job.get("company", ""),
        **result,
    }


# ── Benchmark ─────────────────────────────────────────────────────────────────
@app.get("/api/benchmark")
def benchmark():
    """Compare LSA embedding vs TF-IDF baseline — required by rubric."""
    import time
    test_queries = [
        "machine learning engineer python pytorch remote",
        "data analyst sql tableau business intelligence",
        "research scientist nlp computer vision",
        "mlops platform engineer kubernetes kafka",
    ]
    emb_times, tfidf_times = [], []
    for q in test_queries:
        t0 = time.time(); INDEX.search(q, top_k=20); emb_times.append((time.time()-t0)*1000)
        t0 = time.time(); TFIDF_INDEX.search(q, top_k=20); tfidf_times.append((time.time()-t0)*1000)

    import numpy as np
    return {
        "embedding_lsa": {"avg_latency_ms": round(float(np.mean(emb_times)), 2), "description": "TF-IDF + SVD (150d) + cosine — semantic matching (Lecture 5)"},
        "tfidf_baseline": {"avg_latency_ms": round(float(np.mean(tfidf_times)), 2), "description": "Sparse TF-IDF — keyword matching (baseline)"},
        "advantage": "LSA captures semantic similarity (e.g. 'ML Engineer' ≈ 'Applied Scientist') while TF-IDF only matches exact keywords",
        "feedback_summary": LEARNER.summary(),
    }
