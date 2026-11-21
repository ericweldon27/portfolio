"""Judgments that need reading, not keyword matching: fit by meaning, searcher intent, funnel stage,
review aspects and claim defensibility.

A run queues each item it can't answer in output/judgments/queue.json. Claude reads the queue in the
session and writes answers to output/judgments/answers.json, keyed by the same id. Answers are reused
on every later run, so each item is judged once. Items without an answer fall back to the heuristic.

Answer shapes, by kind:
  fit      {"fit": 0..1, "reason": str}                    keyword vs. our differentiators
  intent   {"intent": business|consumer|mixed|research|jobs, "reason": str}   from the top results
  funnel   {"stage": awareness|consideration|decision, "reason": str}
  review   {"aspects": [{"aspect": str, "sentiment": like|dislike, "quote": str}], "summary": str}
  claim    {"verdict": defensible|risky|unsupported, "reason": str, "safer_wording": str}
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

REVIEW_ASPECTS = ["billing and pricing", "missed or late pickups", "service and responsiveness", "contract terms",
                  "technology and data", "savings delivered", "sustainability and reporting", "setup and onboarding"]


class Judgments:
    def __init__(self, folder: Path):
        self.folder = folder
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / "answers.json"
        self.answers: dict = json.loads(path.read_text()) if path.exists() else {}
        self.queue: dict = {}

    @staticmethod
    def item_id(kind: str, payload: dict) -> str:
        key = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return f"{kind}:{hashlib.sha1(key.encode()).hexdigest()[:12]}"

    def ask(self, kind: str, payload: dict, stable: str | None = None) -> dict | None:
        """The answer if Claude has judged this item; otherwise queue it and return None.
        With `stable` (e.g. a claim's text, or "draft"), the latest answer saved under kind~stable is used
        when the evidence has shifted, so small changes between runs don't discard a finished judgment."""
        iid = self.item_id(kind, payload)
        if iid in self.answers:
            return self.answers[iid]
        if stable and f"{kind}~{stable}" in self.answers:
            return self.answers[f"{kind}~{stable}"]
        self.queue[iid] = {"kind": kind, **payload}
        return None

    def save_queue(self) -> int:
        (self.folder / "queue.json").write_text(json.dumps(self.queue, indent=1, ensure_ascii=False))
        return len(self.queue)


class NoJudgments(Judgments):
    """Stand-in when judgments are off: never answers, never queues."""

    def __init__(self):
        self.answers, self.queue, self.folder = {}, {}, None

    def ask(self, kind, payload, stable=None):
        return None

    def save_queue(self) -> int:
        return 0
