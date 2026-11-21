"""The research brief: what to research, filled in on the setup page. Merged over config.json."""
from __future__ import annotations

import json
from pathlib import Path

PRIORITY_WEIGHT = {"high": 1.0, "medium": 0.8, "low": 0.6}


def _unique(items) -> list:
    out, seen = [], set()
    for x in items:
        k = x.strip().lower()
        if k and k not in seen:
            seen.add(k)
            out.append(x.strip())
    return out


def apply_brief(cfg: dict, brief: dict) -> dict:
    """config.json keeps the tool's defaults; the brief decides what this run researches."""
    out = dict(cfg)
    topics = [t for t in brief.get("topics", []) if t.get("name")]
    if brief.get("our_site", {}).get("url"):
        out["our_site"] = brief["our_site"]
    if brief.get("competitors") is not None:
        out["competitors"] = [{"name": c.get("name") or c["url"], "url": c["url"],
                               "review_urls": _unique(c.get("review_urls", []))}
                              for c in brief["competitors"] if c.get("url")]
    out["topics"] = [{
        "id": t.get("id") or t["name"].lower(),
        "name": t["name"],
        "priority": t.get("priority", "medium"),
        "weight": PRIORITY_WEIGHT.get(t.get("priority", "medium"), 0.8),
        "seed_terms": _unique(t.get("seed_terms", [])),
        "benefit_subjects": _unique(t.get("benefit_subjects", [])),
    } for t in topics]
    out["keywords"] = _unique(s for t in out["topics"] for s in t["seed_terms"])
    subjects = [s for t in out["topics"] for s in t["benefit_subjects"]]
    names = [t["name"].lower() for t in out["topics"]]
    out["topic_terms"] = _unique(cfg.get("topic_terms", []) + subjects + names)
    out["product_terms"] = _unique(cfg.get("product_terms", []) + subjects)
    out["exclude_terms"] = _unique(cfg.get("exclude_terms", []) + [x for t in topics for x in t.get("exclude_terms", [])])
    topic_ids = [t["id"] for t in out["topics"]]
    out["benefits"] = [{"id": b.get("id") or b["name"].lower(), "name": b["name"],
                        "wordings": _unique(b.get("wordings", [])),
                        "topics": [t for t in (b.get("topics") or topic_ids) if t in topic_ids],
                        # "compete": a rival ranking doesn't count against a wording (appear alongside, win later).
                        "stance": b.get("stance") if b.get("stance") in ("own", "compete") else "own",
                        # Optional {x} words for this benefit only, in place of its topics' "benefits apply to" words.
                        "subjects": _unique(b.get("subjects", []))}
                       for b in brief.get("benefits", []) if b.get("name")]
    for key in ("differentiators", "questions"):
        if brief.get(key):
            out[key] = _unique(brief[key])
    out["claims"] = _unique(brief.get("claims", []))
    out["customer_quotes"] = [q.strip() for q in brief.get("customer_quotes", []) if q.strip()]
    # Pasted reviews live in their own documents on the setup page; Claude copies them in before a run.
    out["pasted_reviews"] = [r for r in brief.get("pasted_reviews", []) if r.get("text")]
    out["weights"] = brief.get("settings", {}).get("weights", {})
    # The setup page's "Things to confirm" items (own documents); Claude copies them in before a run.
    out["confirm"] = brief.get("confirm", [])
    settings = brief.get("settings", {})
    for key in ("max_pages", "serp_budget"):
        if settings.get(key):
            out[key] = int(settings[key])
    return out


def load_brief(path: Path) -> dict:
    return json.loads(path.read_text())
