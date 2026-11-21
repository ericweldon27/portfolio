"""Content plan: the pieces to create, by funnel stage, from the run's keywords, buyer questions, benefit
wordings and claims. Claude groups keywords into pieces and picks each one's format, angle and AI-answer
question (judge kind "content_plan"); without that, keywords are grouped by shared words and given a
default format for their stage.

Status is checked on every run, so the plan tracks itself: not started, page exists (we have a
page whose title or H1 covers the target keyword), or ranking (Brave top 20).
"""
from __future__ import annotations

from .checks.common import tokens

DEFAULT_FORMAT = {"awareness": "guide", "consideration": "comparison page", "decision": "case study"}
STAGE_ORDER = {"awareness": 0, "consideration": 1, "decision": 2}


def _candidates(keywords: list[dict], limit: int = 40) -> list[dict]:
    good = [k for k in keywords if k.get("intent") not in ("consumer", "jobs") and k["opportunity"] >= 10]
    return [{"keyword": k["keyword"], "stage": k.get("stage", ""), "intent": k.get("intent", ""),
             "opportunity": k["opportunity"], "status": k["status"], "owners": k.get("top_domains", [])[:3]}
            for k in sorted(good, key=lambda k: -k["opportunity"])[:limit]]


def _fallback(cands: list[dict]) -> list[dict]:
    """Group keywords that share most of their words under the strongest one."""
    pieces = []
    for c in cands:
        ct = tokens(c["keyword"])
        home = next((p for p in pieces if p["stage"] == c["stage"] and
                     len(ct & tokens(p["target_keyword"])) / max(1, len(ct)) >= 0.6), None)
        if home:
            home["supporting_keywords"].append(c["keyword"])
            continue
        pieces.append({"title": c["keyword"].capitalize(), "format": DEFAULT_FORMAT.get(c["stage"], "guide"),
                       "stage": c["stage"], "target_keyword": c["keyword"], "supporting_keywords": [],
                       "question": "", "angle": "", "proof_needed": [], "next_step": "", "priority": 3,
                       "why": "Grouped automatically by shared words; not yet reviewed."})
    return pieces[:15]


def _status(piece: dict, sites, keywords: list[dict]) -> tuple[str, str]:
    ours = next(s for s in sites if s.is_ours)
    kt = tokens(piece["target_keyword"])
    rank = next((k["our_rank"] for k in keywords if k["keyword"] == piece["target_keyword"]), None)
    if rank:
        return "ranking", f"#{rank} on Brave"
    for p in ours.pages:
        heads = [p.title] + [t for lvl, t in p.headings if lvl == 1]
        if any(kt and kt <= tokens(h) for h in heads):
            return "related page exists", p.path
    return "not started", ""


def build(sites, keywords: list[dict], wordings: list[dict], claims: list[dict], messaging: dict, cfg, judge) -> dict:
    cands = _candidates(keywords)
    evidence = {
        "keywords": cands,
        "buyer_questions": cfg.get("questions", []),
        "benefit_picks": [{"benefit": w["benefit"], "wording": w["wording"], "stance": w["stance"]}
                          for w in wordings if w.get("recommended")],
        "claims": [{"claim": c["claim"], "verdict": c["verdict"]} for c in claims],
        "pages_already_drafted": [s["page"] for s in messaging.get("sections", [])],
        "placeholders_open": [p["token"] for p in messaging.get("placeholders", []) if p["status"] != "confirmed"],
        "formats": ["guide", "comparison page", "product page", "case study", "FAQ", "calculator", "checklist",
                    "blog post", "industry page"],
    }
    plan = judge.ask("content_plan", evidence, stable="draft")
    source = "judged" if plan and isinstance(plan.get("pieces"), list) else "heuristic"
    pieces = plan["pieces"] if source == "judged" else _fallback(cands)
    by_kw = {k["keyword"]: k for k in keywords}
    rows = []
    for i, p in enumerate(pieces, 1):
        status, where = _status(p, sites, keywords)
        k = by_kw.get(p["target_keyword"], {})
        rows.append({
            "id": i, "priority": p.get("priority", 3), "title": p.get("title", ""), "format": p.get("format", ""),
            "stage": p.get("stage", ""), "target_keyword": p["target_keyword"],
            "supporting_keywords": ", ".join(p.get("supporting_keywords", [])),
            "opportunity": k.get("opportunity"), "keyword_status": k.get("status", ""),
            "question": p.get("question", ""), "angle": p.get("angle", ""),
            "proof_needed": ", ".join(p.get("proof_needed", [])), "next_step": p.get("next_step", ""),
            "status": status, "where": where, "why": p.get("why", ""), "source": source,
        })
    rows.sort(key=lambda r: (r["priority"], STAGE_ORDER.get(r["stage"], 9), -(r["opportunity"] or 0)))
    for i, r in enumerate(rows, 1):
        r["order"] = i
    return {"pieces": rows, "source": source}
