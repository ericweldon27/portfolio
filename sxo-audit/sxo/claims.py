"""Claims and proof.

Claim check: each claim we want to make (from the brief, plus bold claims found on its site) set
against what competitors say on their pages and who ranks for the same idea. Claude judges each one
defensible, risky or unsupported, with a safer wording (see judge.py).

Proof matrix: per site and funnel stage, what it promises (headings) and what proof it shows (numbers,
testimonials, case studies, client logos).
"""
from __future__ import annotations

import re
from collections import defaultdict

from .checks.common import tokens

BOLD_RX = re.compile(r"\b(the (first|only|best|leading|fastest|most \w+)|first and only|#1|number one|"
                     r"industry[- ]leading|best[- ]in[- ]class|guarantee[ds]?|patent(ed|-pending)|"
                     r"world'?s (first|only|leading|most)|everyone else|no one else|nobody else|only pay)\b", re.I)
STAT_RX = re.compile(r"\d+(?:\.\d+)?\s?%|\$\s?\d[\d,.]*\s?(?:k|m|million|billion)?|\b\d[\d,]{2,}\s(?:tons|pickups|hours|sites|"
                     r"units|customers|data points|locations)\b", re.I)
STAGE_BY_KIND = {"blog": "awareness", "home": "consideration", "product": "consideration", "industry": "consideration",
                 "other": "consideration", "proof": "decision", "company": "decision"}


def _chunks(site):
    for p in site.pages:
        for lvl, t in p.headings:
            yield p, f"H{lvl}", t
        for t in p.paragraphs:
            yield p, "copy", t


def _related(claim: str, site, limit: int = 4) -> list[str]:
    ct = tokens(claim)
    scored = []
    for p, kind, text in _chunks(site):
        overlap = len(ct & tokens(text))
        if overlap >= 2:
            scored.append((overlap, f"{p.path} ({kind}): {text[:180]}"))
    return [t for _, t in sorted(scored, key=lambda x: -x[0])[:limit]]


def check_claims(sites, cfg, keyword_rows: list[dict], judge) -> list[dict]:
    ours = next(s for s in sites if s.is_ours)
    rivals = [s for s in sites if not s.is_ours]
    claims = [(c, "brief") for c in cfg.get("claims", [])]
    seen = {c.lower() for c, _ in claims}
    for p, kind, text in _chunks(ours):
        if re.search(r"/(careers|apply|jobs)", p.path):
            continue  # hiring copy isn't product messaging
        if BOLD_RX.search(text) and 4 <= len(text.split()) <= 40 and text.lower() not in seen:
            seen.add(text.lower())
            claims.append((text, f"site {p.path}"))
    rows = []
    for claim, origin in claims[:20]:
        ct = tokens(claim)
        rival_lines = [f"{s.name} · {line}" for s in rivals for line in _related(claim, s, 3)]
        # Companies that rank for the same idea are evidence the claim isn't unique.
        rankers = []
        for k in keyword_rows:
            if len(ct & tokens(k["keyword"])) >= 2 and k.get("top_domains"):
                rankers.append(f"{k['keyword']}: {', '.join(k['top_domains'][:4])}")
        j = judge.ask("claim", {"claim": claim, "competitor_lines": rival_lines[:6], "who_ranks": rankers[:6]}, stable=claim)
        if j and j.get("verdict") in ("defensible", "risky", "unsupported"):
            verdict, reason, safer, source = j["verdict"], j.get("reason", ""), j.get("safer_wording", ""), "judged"
        else:
            bold = bool(BOLD_RX.search(claim))
            verdict = "risky" if bold and (rival_lines or rankers) else "unverified"
            reason = ("uses an absolute word and competitors cover the same idea" if verdict == "risky"
                      else "not judged yet")
            safer, source = "", "heuristic"
        rows.append({"claim": claim, "origin": origin, "verdict": verdict, "reason": reason, "safer_wording": safer,
                     "source": source, "competitor_lines": " || ".join(rival_lines[:4]),
                     "who_ranks": " || ".join(rankers[:4])})
    return rows


def proof_matrix(sites) -> list[dict]:
    rows = []
    for s in sites:
        by_stage = defaultdict(list)
        for p in s.pages:
            by_stage[STAGE_BY_KIND.get(p.kind, "consideration")].append(p)
        for stage in ("awareness", "consideration", "decision"):
            pages = by_stage.get(stage, [])
            text = " ".join(t for p in pages for t in p.paragraphs)
            promises = [t for p in pages for lvl, t in p.headings if lvl <= 2][:6]
            logos = {i.src for p in pages for i in p.images if "logo" in (i.src + (i.alt or "")).lower()}
            rows.append({
                "site": s.name, "stage": stage, "pages": len(pages),
                "promises": " || ".join(promises),
                "stats": len(STAT_RX.findall(text)),
                "testimonials": sum(p.blockquote_count for p in pages) + text.count("“"),
                "case_studies": sum(1 for p in pages for l in p.links if re.search(r"case-stud|customer-stor|success", l.url)),
                "client_logos": len(logos),
                "ctas": sum(len(p.ctas) for p in pages),
                "examples": " || ".join(m.group(0) + " · " + p.path for p in pages for m in list(STAT_RX.finditer(" ".join(p.paragraphs)))[:1])[:400],
            })
    return rows
