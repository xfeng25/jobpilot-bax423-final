FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV KAGGLE_CSV=data/jobs.csv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}
