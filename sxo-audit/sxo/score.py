"""Roll check scores up into section scores, gaps and a fix-first list."""
from __future__ import annotations

SECTIONS = ("UX", "SEO", "AEO")


def section_scores(checks: list[dict]) -> dict:
    out = {}
    for section in SECTIONS:
        scored = [c for c in checks if c["section"] == section and c["score"] is not None]
        total = sum(c["weight"] for c in scored)
        out[section] = round(100 * sum(c["score"] * c["weight"] for c in scored) / total) if total else None
    valid = [v for v in out.values() if v is not None]
    out["overall"] = round(sum(valid) / len(valid)) if valid else None
    return out


def gaps(ours: list[dict], theirs: dict[str, list[dict]], threshold: float = 0.2) -> list[dict]:
    """Checks where a competitor beats us by at least `threshold`."""
    by_id = {c["id"]: c for c in ours}
    out = []
    for name, checks in theirs.items():
        for c in checks:
            mine = by_id.get(c["id"])
            if not mine or mine["score"] is None or c["score"] is None:
                continue
            diff = c["score"] - mine["score"]
            if diff >= threshold:
                out.append({"competitor": name, "id": c["id"], "section": c["section"], "name": c["name"],
                            "ours": mine["summary"], "theirs": c["summary"], "diff": round(diff, 3),
                            "impact": round(diff * c["weight"], 3)})
    return sorted(out, key=lambda g: -g["impact"])


def fix_first(ours: list[dict], limit: int = 12) -> list[dict]:
    """Our weakest checks, weighted by importance."""
    todo = [c for c in ours if c["score"] is not None and c["score"] < 0.8 and c["recommendation"]]
    todo.sort(key=lambda c: -(1 - c["score"]) * c["weight"])
    return [{"id": c["id"], "section": c["section"], "name": c["name"], "status": c["status"],
             "summary": c["summary"], "recommendation": c["recommendation"],
             "priority": round((1 - c["score"]) * c["weight"], 2)} for c in todo[:limit]]
