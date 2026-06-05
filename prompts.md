# Key AI Prompts

1. Asked ChatGPT to outline a BAX-423 Option B architecture for a job matching app covering ingestion, deduplication, embedding retrieval, ranking, feedback learning, and resume generation; adapted the output into a FastAPI + static frontend design.
2. Asked ChatGPT to generate starter FastAPI endpoints for resume upload, job search, feedback, resume generation, health checks, and benchmark reporting; modified the code to use local CSV data plus optional Adzuna enrichment.
3. Asked ChatGPT to suggest skill extraction rules for analytics, ML, data engineering, and business analysis roles; reviewed and corrected regex patterns, especially standalone R matching.
4. Asked ChatGPT to design a multi-stage ranking pipeline with candidate retrieval, hard filters, scoring, and re-ranking; adjusted filters to match the four assignment personas.
5. Asked ChatGPT to draft resume tailoring prompts that use only candidate-provided resume content; kept the fallback template generator for offline demo reliability.
6. Asked ChatGPT to identify demo risks in the Kaggle data snapshot; updated handling for missing salary, location, visa, and company-size metadata and documented the limitation.
