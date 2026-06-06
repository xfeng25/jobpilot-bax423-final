# JobPilot — Smart Job Matcher & Resume Builder
**BAX-423 Big Data · Option B · Spring 2026 · UC Davis GSM**

## Run Locally

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Optional: set up environment variables for live API enrichment
cp .env.example .env
# Add ANTHROPIC_API_KEY and ADZUNA_APP_ID / ADZUNA_APP_KEY if available

# 3. Run with one command
bash run_local.sh

# Open http://localhost:8000
```

The app also runs without API keys using the offline `data/jobs.csv` snapshot.
This snapshot contains 30,000 postings streamed from the original Kaggle Techmap
JSONL file without modifying the raw source. When Adzuna keys are present,
startup enriches the offline Kaggle snapshot with current postings for demo-time
salary, location, and apply-link metadata.

## BAX-423 Techniques

| Technique | Lecture | Implementation |
|-----------|---------|----------------|
| Streaming Ingestion + Dedup | Lecture 3 | Kaggle CSV + Adzuna API, hash-based dedup |
| Dense Embeddings (LSA) | Lecture 5 | TF-IDF → TruncatedSVD (150d) → cosine search |
| Recommendation + Adaptive Learning | Lecture 6 | Accept/Reject/Skip → feature weight updates |
| Multi-Stage Ranking Pipeline | Lecture 7 | Retrieve → Filter → Score → Diversity Rerank |

## Submission Files

```
Feng_Xia_BAX423_Final/
├── code/
│   ├── backend/          # FastAPI + ML pipeline
│   ├── frontend/         # HTML + CSS + JS
│   ├── requirements.txt
│   ├── Dockerfile        # Cloud Run deployment config
│   ├── render.yaml       # Render deployment config
│   ├── run_local.sh      # One-command local runner
│   └── README.md
├── data/
│   └── jobs.csv          # 30,000-posting offline snapshot
├── brief.pdf             # Technical brief
└── prompts.md            # AI prompts used
```

## Data Notes

The Kaggle snapshot provides scale for retrieval, but many rows omit reliable
salary, visa sponsorship, company size, and required-years metadata. JobPilot
marks those fields as `Not listed` / `Unknown`, penalizes missing metadata in
ranking, and prefers API-enriched postings when available. Persona constraints
are enforced when structured evidence is present; ambiguous metadata is surfaced
as a limitation in the technical brief.
