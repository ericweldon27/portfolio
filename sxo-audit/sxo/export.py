"""Flatten a run's report into row tables (JSON) for the hosted dashboard."""
from __future__ import annotations

import json
import re
from pathlib import Path

from .citations import PUBLICATION_RX


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower().split("(")[0]).strip("_")


def aeo_prompts() -> list[dict]:
    """The AI-answer prompt map (research/aeo-results.json), checked by hand in a browser for now."""
    path = Path(__file__).resolve().parent.parent / "research" / "aeo-results.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return [dict(p, cited=", ".join(p["cited"]) or "none", competitors_named=", ".join(p["competitors_named"]) or "none",
                 checked=data["checked"], engine=data["engine"]) for p in data["prompts"]]


def tables(report: dict) -> dict[str, list[dict]]:
    sites = report["sites"]
    kw = report.get("keywords", {})
    ours = next(s for s in sites if s["site"]["is_ours"])

    scores = [{"site": s["site"]["name"], "is_ours": s["site"]["is_ours"], "overall": s["scores"]["overall"],
               "ux": s["scores"]["UX"], "seo": s["scores"]["SEO"], "aeo": s["scores"]["AEO"],
               "pages": s["site"]["pages_crawled"]} for s in sites]

    by_site = [(slug(s["site"]["name"]), {c["id"]: c for c in s["checks"]}) for s in sites]
    checks = []
    for c in ours["checks"]:
        row = {"id": c["id"], "section": c["section"], "check": c["name"], "how_to_improve": c["recommendation"]}
        for key, m in by_site:
            other = m.get(c["id"], {})
            row[f"{key}_status"] = other.get("status", "")
            row[f"{key}_score"] = None if other.get("score") is None else round(other["score"] * 100)
            row[f"{key}_summary"] = other.get("summary", "")
        checks.append(row)

    fix_first = [{"priority": i, "check": f["name"], "section": f["section"], "status": f["status"],
                  "summary": f["summary"], "recommendation": f["recommendation"]}
                 for i, f in enumerate(report["fix_first"], 1)]

    keywords = []
    for k in kw.get("keywords", []):
        rival = k.get("best_rival")
        keywords.append({
            "keyword": k["keyword"], "topic": k.get("topic", ""), "status": k.get("label", k["status"]),
            "ownership": k["status"], "label_reason": k.get("label_reason", ""), "opportunity": k["opportunity"],
            "demand": round(k["demand"] * 100), "fit": round(k["fit"] * 100), "our_rank": k["our_rank"],
            "best_rival": rival or "", "rival_rank": k["rival_ranks"].get(rival) if rival else None,
            "ranking_now": ", ".join(k["top_domains"][:3]), "source": k["source"].split(":")[0],
            "related": "; ".join((k.get("autocomplete") or []) + (k.get("related") or []))[:300],
            "questions": "; ".join(k.get("faq") or [])[:300],
            "stage": k.get("stage", ""), "stage_reason": k.get("stage_reason", ""),
            "intent": k.get("intent", ""), "intent_reason": k.get("intent_reason", ""),
            "fit_reason": k.get("fit_reason", ""), "judged": k.get("fit_source") == "judged",
        })

    winners = [{"domain": w["domain"], "top10_count": w["top10_count"], "tracked": w["tracked"]}
               for w in kw.get("search_winners", [])]
    distinctive = [{"site": name, "rank": i, "phrase": p["phrase"]}
                   for name, phrases in kw.get("distinctive", {}).items() for i, p in enumerate(phrases[:20], 1)]

    ben = report.get("benefits") or {"wordings": [], "phrases": []}
    wordings = [{"benefit": w["benefit"], "wording": w["wording"], "key": f"{w['benefit']}|{w['wording']}",
                 "rank_in_benefit": w.get("rank_in_benefit"), "recommended": bool(w.get("recommended")),
                 "stance": w["stance"], "example": w["example"], "status": w["status"], "win": w["win"],
                 "demand": w["demand"], "f_demand": w["factors"]["demand"], "f_beat": w["factors"]["beatability"],
                 "f_assoc": w["factors"]["association"], "f_intent": w["factors"]["intent"],
                 "f_priority": w["factors"]["priority"], "f_trends": w["factors"].get("trends", 1.0),
                 "f_customers": w["factors"].get("customers", 1.0), "trend_phrase": w.get("trend_phrase", ""),
                 "trend_interest": w.get("trend_interest"), "stage": w.get("stage", ""),
                 "stage_reason": w.get("stage_reason", ""), "customer_quotes": " || ".join(w.get("customer_quotes", [])),
                 "intent_reasons": " || ".join(w.get("intent_reasons", [])),
                 "why": w["why"], "intent": w["intent"],
                 "intent_business": w["intent_signals"]["business_results"],
                 "intent_consumer": w["intent_signals"]["consumer_results"],
                 "our_rank": w["our_rank"], "best_rival": w["best_rival"] or "", "rival_rank": w["rival_rank"],
                 "our_mentions": w["our_mentions"], "rival_mentions": w["rival_mentions"],
                 "our_association": w["our_association"], "our_association_detail": w["our_association_detail"],
                 "rival_association": w["rival_association"], "rival_association_detail": w["rival_association_detail"],
                 "our_quotes": " || ".join(w["our_quotes"]), "rival_quotes": " || ".join(w["rival_quotes"]),
                 "owners": ", ".join(w["owners"]), "phrases_tested": w["phrases_tested"],
                 "phrases_ranked": w["phrases_ranked"]} for w in ben["wordings"]]
    # A tie at the top means the data can't separate the wordings; say so rather than pick by list order.
    top_win = {}
    for w in wordings:
        top_win[w["benefit"]] = max(top_win.get(w["benefit"], 0), w["win"])
    for w in wordings:
        w["top_tie"] = w["win"] == top_win[w["benefit"]] and sum(
            1 for x in wordings if x["benefit"] == w["benefit"] and x["win"] == w["win"]) > 1
    phrases = [{"phrase": p["phrase"], "benefit": p["benefit"], "wording": p["wording"], "topic": p["topic"],
                "demand": p["demand"], "our_rank": p["our_rank"], "rival_rank": p["rival_rank"],
                "owners": ", ".join(p["owners"]), "intent": p.get("intent", ""), "checked": p["checked"]}
               for p in ben["phrases"]]

    brief = report.get("brief") or {}
    brief_rows = [{"kind": "topic", "name": t["name"], "priority": t.get("priority", ""),
                   "items": ", ".join(t.get("seed_terms", [])), "applies_to": ", ".join(t.get("benefit_subjects", []))}
                  for t in brief.get("topics", [])]
    brief_rows += [{"kind": "benefit", "name": b["name"], "priority": b.get("stance", "own"),
                    "items": ", ".join(b.get("wordings", [])), "applies_to": ", ".join(b.get("topics", []))}
                   for b in brief.get("benefits", [])]

    rv = report.get("reviews") or {"aspects": [], "reviews": [], "sources": []}
    review_aspects = [dict(a, key=f"{a['competitor']}|{a['aspect']}") for a in rv["aspects"]]
    review_list = [dict(r, id=i) for i, r in enumerate(rv["reviews"], 1)]
    review_sources = [dict(r, id=i) for i, r in enumerate(rv["sources"], 1)]
    claims = [dict(c, id=i) for i, c in enumerate(report.get("claims") or [], 1)]
    proof = [dict(p, key=f"{p['site']}|{p['stage']}") for p in report.get("proof") or []]
    citations = report.get("citations") or []
    msg = report.get("messaging") or {"sections": [], "placeholders": []}
    messaging = msg["sections"]
    placeholders = [dict(p, id=p["confirm_id"]) for p in msg["placeholders"]]
    suggestions = [{"domain": w["domain"], "top10_count": w["top10_count"]}
                   for w in kw.get("search_winners", [])
                   if not w["tracked"] and not PUBLICATION_RX.search(w["domain"])][:8]

    return {"keywords": keywords, "scores": scores, "checks": checks, "fix_first": fix_first,
            "winners": winners, "distinctive": distinctive, "benefits": wordings,
            "benefit_phrases": phrases, "brief": brief_rows, "review_aspects": review_aspects,
            "reviews": review_list, "review_sources": review_sources, "claims": claims, "proof": proof,
            "citations": citations, "suggestions": suggestions, "messaging": messaging,
            "placeholders": placeholders, "content_plan": (report.get("content") or {}).get("pieces", []),
            "draft_checks": report.get("draft_checks", []), "prompts": aeo_prompts()}


def write_tables(report: dict, out_dir: Path) -> Path:
    folder = out_dir / "dashboard-data"
    folder.mkdir(parents=True, exist_ok=True)
    for name, rows in tables(report).items():
        (folder / f"{name}.json").write_text(json.dumps(rows, indent=1))
    history = out_dir.parent / "history.json"
    if history.exists():
        (folder / "history.json").write_text(history.read_text())
    return folder
