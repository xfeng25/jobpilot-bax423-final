"""
BAX-423 Lecture 6: Recommendation Systems — Implicit Feedback Learning
Accept (+1) / Skip (0) / Reject (-1) signals update feature weights,
improving ranking quality over multiple rounds. Tracks NDCG improvement.
"""
from __future__ import annotations
import json
from pathlib import Path

REWARD = {"accept": 1.0, "skip": 0.0, "reject": -1.0}


class FeedbackLearner:
    def __init__(self):
        self.events: list[dict] = []
        self.weights: dict[str, dict[str, float]] = {}
        self.ndcg_history: list[float] = []
        self.ndcg_baseline: float | None = None

    def record(self, profile_id: str, job_id: str, action: str, job: dict):
        profile_id = profile_id or "default"
        reward = REWARD.get(action.lower(), 0.0)
        event = {"profile_id": profile_id, "job_id": job_id, "action": action, "reward": reward}
        self.events.append(event)
        lr = 0.25
        profile_weights = self.weights.setdefault(profile_id, {})
        # Boost/penalize specific job_id directly
        self._add_weight(profile_weights, f"job:{job_id}", lr * reward * 1.2, limit=0.6)
        # Update weights for skills, location, industry
        for skill in job.get("skills_extracted", []):
            key = f"skill:{skill.lower()}"
            self._add_weight(profile_weights, key, lr * reward * 0.35, limit=0.35)
        for key in [f"location:{job.get('location','').lower()}", f"industry:{job.get('industry','').lower()}"]:
            self._add_weight(profile_weights, key, lr * reward * 0.2, limit=0.25)

    def get_weights(self, profile_id: str = None) -> dict[str, float]:
        return dict(self.weights.get(profile_id or "default", {}))

    def relevance_labels(self, profile_id: str = None) -> dict[str, float]:
        labels = {}
        for event in self.events:
            if profile_id and event["profile_id"] != profile_id:
                continue
            action = event["action"].lower()
            if action == "accept":
                labels[event["job_id"]] = 3.0
            elif action == "skip":
                labels[event["job_id"]] = 1.0
            elif action == "reject":
                labels[event["job_id"]] = 0.0
        return labels

    def track_ndcg(self, val: float):
        if val is not None:
            val = round(val, 4)
            if self.ndcg_baseline is None:
                self.ndcg_baseline = val
            self.ndcg_history.append(val)

    def learned_preferences(self, profile_id: str = None) -> list[dict]:
        weights = self.weights.get(profile_id or "default", {})
        top = sorted(weights.items(), key=lambda x: abs(x[1]), reverse=True)[:8]
        return [{"signal": k, "weight": round(v, 3)} for k, v in top if abs(v) > 0.01]

    def summary(self, profile_id: str = None) -> dict:
        events = [e for e in self.events if not profile_id or e["profile_id"] == profile_id]
        accepts = sum(1 for e in events if e["action"] == "accept")
        rejects = sum(1 for e in events if e["action"] == "reject")
        skips = sum(1 for e in events if e["action"] == "skip")
        improvement = 0.0
        if self.ndcg_baseline is not None and self.ndcg_history:
            improvement = round((self.ndcg_history[-1] - self.ndcg_baseline) / max(self.ndcg_baseline, 0.01) * 100, 1)
        return {
            "total_feedback": len(events),
            "accepts": accepts, "rejects": rejects, "skips": skips,
            "ndcg_history": self.ndcg_history,
            "ndcg_baseline": self.ndcg_baseline,
            "improvement_pct": improvement,
        }

    @staticmethod
    def _add_weight(weights: dict[str, float], key: str, delta: float, limit: float):
        current = weights.get(key, 0.0) + delta
        weights[key] = max(-limit, min(limit, current))
