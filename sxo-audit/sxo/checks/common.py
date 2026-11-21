"""The Check result shared by the UX, SEO and AEO modules, plus small helpers."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Optional

STOPWORDS = set("""a an and are as at be by can do does for from how i if in is it my of on or our so
that the their them this to we what when where which who why will with you your""".split())


@dataclass
class Check:
    id: str
    section: str  # "UX" | "SEO" | "AEO"
    name: str
    score: Optional[float]  # 0..1, or None when the check is informational / not available
    summary: str
    weight: float = 1.0
    recommendation: str = ""
    details: list = field(default_factory=list)  # rows (dicts) or plain strings

    @property
    def status(self) -> str:
        if self.score is None:
            return "info"
        if self.score >= 0.8:
            return "pass"
        if self.score >= 0.5:
            return "warn"
        return "fail"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status
        d["score"] = None if self.score is None else round(self.score, 3)
        d["details"] = self.details[:250]
        return d


def share(hits: int, total: int) -> Optional[float]:
    return None if total == 0 else hits / total


def pct(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{round(x * 100)}%"


def stem(word: str) -> str:
    w = word.lower()
    for suffix in ("ing", "ers", "ies", "es", "ed", "er", "s"):
        if w.endswith(suffix) and len(w) - len(suffix) >= 4:
            return w[: -len(suffix)]
    return w


def tokens(text: str) -> set[str]:
    return {stem(w) for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOPWORDS and len(w) > 2}


def syllables(word: str) -> int:
    w = word.lower().strip("'’")
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups) - (1 if w.endswith("e") and len(groups) > 1 else 0)
    return max(1, n)


def flesch(text: str) -> Optional[float]:
    sentences = [s for s in re.split(r"[.!?]+\s", text) if s.strip()]
    ws = re.findall(r"[A-Za-z]+", text)
    if len(ws) < 30 or not sentences:
        return None
    syl = sum(syllables(w) for w in ws)
    return 206.835 - 1.015 * (len(ws) / len(sentences)) - 84.6 * (syl / len(ws))
