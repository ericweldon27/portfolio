"""Draft messaging for the new site: one section per funnel stage (awareness, consideration, decision),
written from the run's evidence. Facts only we can supply appear as placeholders like [x]% full,
each tied to an item on the setup page's "Things to confirm" list, until that item is answered.

The copy itself is written by Claude in the session (judge kind "messaging"); this module gathers the evidence
and, until a draft exists, returns the inputs so the dashboard can show what the draft will be built from.
"""
from __future__ import annotations

import re

# Checklist item -> the placeholder the copy uses while it's unanswered.
PLACEHOLDERS = {
    "fill-at-pickup": "[x]% full",
    "pickups-reduced": "[x]% fewer pickups",
    "savings": "$[x]",
    "disputed-pickup": "[disputed-pickup example]",
    "named-customers": "[customer name]",
}
STAGES = ("awareness", "consideration", "decision")


def placeholders(cfg) -> list[dict]:
    by_id = {c.get("id"): c for c in cfg.get("confirm", [])}
    out = []
    for cid, token in PLACEHOLDERS.items():
        c = by_id.get(cid, {})
        answered = c.get("status") == "confirmed" and c.get("note", "").strip()
        out.append({"token": token, "confirm_id": cid, "title": c.get("title", cid),
                    "status": c.get("status", "open"), "value": c.get("note", "").strip() if answered else ""})
    return out


def evidence(keywords: list[dict], wordings: list[dict], claims: list[dict], proof: list[dict], cfg) -> dict:
    """The compact facts the copy must rest on."""
    by_stage = {s: [] for s in STAGES}
    for k in sorted(keywords, key=lambda k: -k["opportunity"]):
        st = k.get("stage") or "consideration"
        if st in by_stage and len(by_stage[st]) < 5 and k.get("intent") not in ("consumer", "jobs"):
            by_stage[st].append({"keyword": k["keyword"], "opportunity": k["opportunity"], "status": k["status"],
                                 "intent": k.get("intent", "")})
    picks = []
    for w in wordings:
        if w.get("recommended") or w.get("top_tie"):
            picks.append({"benefit": w["benefit"], "wording": w["wording"], "example": w["example"],
                          "stance": w["stance"], "stage": w.get("stage", ""), "win": w["win"],
                          "rival_rank": w.get("rival_rank"), "tied": bool(w.get("top_tie") and not w.get("recommended"))})
    ours = [p for p in proof if p.get("site") == cfg["our_site"]["name"]]
    return {
        "company": cfg["our_site"]["name"],
        "keywords_by_stage": by_stage,
        "benefit_picks": picks,
        "claims": [{"claim": c["claim"], "verdict": c["verdict"], "safer_wording": c.get("safer_wording", "")} for c in claims],
        "our_proof_by_stage": {p["stage"]: {"stats": p["stats"], "testimonials": p["testimonials"],
                                             "case_studies": p["case_studies"]} for p in ours},
        "differentiators": cfg.get("differentiators", []),
        "customer_quotes": cfg.get("customer_quotes", [])[:10],
        "placeholders": placeholders(cfg),
        "goal": "move a visitor from awareness to consideration to booking a meeting",
    }


def build(keywords, wordings, claims, proof, cfg, judge) -> dict:
    ev = evidence(keywords, wordings, claims, proof, cfg)
    draft = judge.ask("messaging", ev, stable="draft")
    sections = []
    if draft and isinstance(draft.get("sections"), list):
        for i, s in enumerate(draft["sections"], 1):
            text = " ".join(" ".join(v) if isinstance(v, list) else str(v) for v in s.values())
            sections.append({
                "id": i, "stage": s.get("stage", ""), "page": s.get("page", ""), "headline": s.get("headline", ""),
                "subhead": s.get("subhead", ""), "points": " || ".join(s.get("points", [])),
                "proof": s.get("proof", ""), "cta": s.get("cta", ""), "next_step": s.get("next_step", ""),
                "targets": ", ".join(s.get("targets", [])), "why": s.get("why", ""),
                # Every bracketed gap: the named checklist tokens plus any bare [x] the copy needs.
                "placeholders": ", ".join(dict.fromkeys(
                    [p for p in PLACEHOLDERS.values() if p in text] +
                    [m for m in re.findall(r"\[[^\]]+\]", text)
                     if not any(m in p for p in PLACEHOLDERS.values())])),
            })
    return {"sections": sections, "placeholders": ev["placeholders"], "drafted": bool(sections)}
