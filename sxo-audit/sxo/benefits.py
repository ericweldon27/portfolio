"""Benefit wording: for each benefit, which way of saying it has demand, who ranks for it, how strongly
rivals are associated with it, and what kind of searcher looks for it. Every score keeps its parts and
the evidence behind them, so the pick can be checked."""
from __future__ import annotations

import math
import re
from collections import Counter

from .checks.common import stem
from .keywords import TOP, _demand, is_info_site
from .research import Research, domain_of
from .signals import INTENT_FACTOR, funnel_for, intent_for, intent_guess

GENERIC_ANCHORS = {"storage", "chain", "management", "system", "systems", "service", "services"}


def fill(wording: str, subject: str) -> str:
    """Put the subject into {x}, then drop a repeated word: 'fewer manual report reports' -> 'fewer manual reports'."""
    words = wording.replace("{x}", subject).split()
    out = []
    for w in words:
        if out and stem(out[-1].lower()) == stem(w.lower()):
            out[-1] = w
        else:
            out.append(w)
    return " ".join(out)


def _word_rx(word: str) -> str:
    """'reduce' also matches reduces/reducing/reduced; 'costs' matches cost."""
    w = re.escape(word.lower())
    if word.endswith("e") and len(word) > 3:
        w = w[:-1]
    elif word.endswith("s") and len(word) > 3:
        w = w[:-1]
    return w + r"[a-z]*"


def usage_pattern(wording: str) -> re.Pattern:
    """The wording's own words around {x}, with up to three words in between ('reduce your hauling costs')."""
    pre, _, post = wording.lower().partition("{x}")
    pre_rx = r"[\s-]+".join(_word_rx(w) for w in pre.split())
    post_rx = r"[\s-]+".join(_word_rx(w) for w in post.split())
    if pre_rx and post_rx:
        rx = rf"\b{pre_rx}(?:\s+[a-z0-9'’-]+){{0,3}}?\s+{post_rx}\b"
    else:
        rx = rf"\b{pre_rx or post_rx}\b"
    return re.compile(rx)


def site_chunks(site) -> list[dict]:
    """Every title, heading and paragraph, tagged with where it sits. Prominent = title, heading or homepage."""
    out = []
    for i, p in enumerate(site.pages):
        out.append({"path": p.path, "kind": "title", "text": p.title, "prominent": True})
        out.extend({"path": p.path, "kind": f"H{lvl}", "text": t, "prominent": True} for lvl, t in p.headings)
        out.extend({"path": p.path, "kind": "copy", "text": t, "prominent": i == 0} for t in p.paragraphs)
    return [c for c in out if c["text"]]


def anchors_for(topic: dict) -> list[str]:
    words = {w for phrase in topic["benefit_subjects"] + [topic["name"]] for w in re.findall(r"[a-z]+", phrase.lower())}
    return sorted(w for w in words if len(w) > 3 and w not in GENERIC_ANCHORS)


def in_topic(text: str, anchors: list[str]) -> bool:
    t = text.lower()
    return any(re.search(rf"\b{re.escape(a[:-1] if a.endswith('s') else a)}", t) for a in anchors)


def _association(uses: list[dict], rank) -> tuple[str, str]:
    """How strongly searchers likely tie a wording to a site. Mentions alone are not association."""
    prominent = [u for u in uses if u["prominent"]]
    if rank and rank <= TOP:
        return "strong", f"ranks #{rank}"
    if prominent:
        return "medium", f"in {len(prominent)} title/heading/homepage line{'s' if len(prominent) > 1 else ''}"
    if uses:
        return "weak", f"{len(uses)} body mention{'s' if len(uses) > 1 else ''} only"
    return "none", "not used"


# Scoring weights; the setup page can override each (brief settings.weights).
DEFAULT_WEIGHTS = {"rival_prominent": 0.9, "ours_prominent": 1.05, "customer_quote": 1.15,
                   "consumer_intent": 0.5, "mixed_intent": 0.85, "trends_floor": 0.5}


def build(sites, cfg, research: Research, judge, trends=None, log=print) -> dict:
    W = {**DEFAULT_WEIGHTS, **{k: float(v) for k, v in (cfg.get("weights") or {}).items() if k in DEFAULT_WEIGHTS}}
    intent_factor = dict(INTENT_FACTOR, consumer=W["consumer_intent"], mixed=W["mixed_intent"])
    ours = next(s for s in sites if s.is_ours)
    domains = {s.name: domain_of(s.origin or s.base_url) for s in sites}
    chunks = {s.name: site_chunks(s) for s in sites}
    topics = {t["id"]: t for t in cfg.get("topics", [])}

    phrases = []
    for b in cfg.get("benefits", []):
        ticked = sorted((topics[t] for t in b["topics"] if t in topics), key=lambda t: -t["weight"])
        for w in b["wordings"]:
            if b.get("subjects") and ticked:
                pairs = [(ticked[0], s) for s in b["subjects"]]
            else:
                pairs = [(t, s) for t in ticked for s in t["benefit_subjects"]]
            seen = set()
            for t, subj in pairs:
                phrase = fill(w, subj)
                if phrase.lower() in seen:
                    continue
                seen.add(phrase.lower())
                phrases.append({"benefit": b["name"], "wording": w, "topic": t["name"], "weight": t["weight"], "phrase": phrase})
    log(f"[benefits] {len(phrases)} benefit phrases from {len(cfg.get('benefits', []))} benefits")

    for ph in phrases:
        ph["demand"], _ = _demand(ph["phrase"], research.suggestions(ph["phrase"]), None)
    # Spend ranking searches on the phrases people actually search, best first.
    for ph in sorted(phrases, key=lambda p: -p["demand"] * p["weight"]):
        serp = research.serp(ph["phrase"])
        ph["serp"] = serp
        ph["ranks"], ph["owners"] = {}, []
        if serp:
            for s in sites:
                hits = [r["rank"] for r in serp["results"] if r["domain"].endswith(domains[s.name])]
                ph["ranks"][s.name] = min(hits) if hits else None
            ph["owners"] = [d for d in dict.fromkeys(r["domain"] for r in serp["results"][:TOP]) if not is_info_site(d)][:5]
            ph["intent"], ph["intent_reason"], ph["intent_source"] = intent_for(ph["phrase"], serp, judge)
        else:
            ph["intent"], ph["intent_reason"], ph["intent_source"] = "unknown", "not searched", "none"

    rows = []
    for b in cfg.get("benefits", []):
        stance = b.get("stance", "own")
        anchors = sorted({a for t in b["topics"] if t in topics for a in anchors_for(topics[t])})
        # Google Trends head-to-head: every wording filled with the same subject (the one with the most
        # Autocomplete demand overall), so the comparison is like for like.
        mine = [p for p in phrases if p["benefit"] == b["name"]]
        subj_demand = Counter()
        for p in mine:
            for subj in (b.get("subjects") or [s for t in b["topics"] if t in topics for s in topics[t]["benefit_subjects"]]):
                if p["phrase"] == fill(p["wording"], subj):
                    subj_demand[subj] += p["demand"]
        # Niche phrases have too little Trends data to compare; fall back to broader subjects (fewest words
        # first) and skip the factor when even those are below 1 point of interest.
        subjects = sorted(subj_demand, key=lambda x: (-subj_demand[x], len(x.split())))
        subjects = sorted(subjects[:3], key=lambda x: len(x.split()))
        trend_subject, trend_rel, trend_raw = None, {}, {}
        if trends:
            head = sorted(b["wordings"], key=lambda w: -max([p["demand"] for p in mine if p["wording"] == w] or [0]))[:5]
            for subj in subjects[:2]:
                got = trends.compare([fill(w, subj) for w in head])
                if got and max(got.values()) >= 1.0:
                    trend_subject, top = subj, max(got.values())
                    for w in head:
                        trend_raw[w] = got.get(fill(w, subj), 0.0)
                        trend_rel[w] = trend_raw[w] / top
                    break
        for w in b["wordings"]:
            group = [p for p in phrases if p["wording"] == w and p["benefit"] == b["name"]]
            if not group:
                continue
            rx = usage_pattern(w)
            uses = {name: [c for c in cs if rx.search(c["text"].lower()) and in_topic(c["text"], anchors)]
                    for name, cs in chunks.items()}
            checked = [p for p in group if p["serp"]]
            best = max(group, key=lambda p: (p["demand"] * p["weight"], bool(p["serp"])))
            demand = max(p["demand"] for p in group)
            weight = best["weight"]

            def best_rank(name):
                rs = [p["ranks"].get(name) for p in checked if p["ranks"].get(name)]
                return min(rs) if rs else None

            our_rank = best_rank(ours.name)
            rival_ranks = {s.name: best_rank(s.name) for s in sites if not s.is_ours}
            ranked = [(n, r) for n, r in rival_ranks.items() if r]
            best_rival = min(ranked, key=lambda x: x[1]) if ranked else None

            our_assoc = _association(uses[ours.name], our_rank)
            rival_assoc = {n: _association(uses[n], rival_ranks[n]) for n in rival_ranks}
            strongest = max(rival_assoc.values(), key=lambda a: ["none", "weak", "medium", "strong"].index(a[0]),
                            default=("none", "not used"))

            rival_top = best_rival and best_rival[1] <= TOP
            if stance == "compete" or not rival_top:
                beat = 1.0
            else:
                beat = 0.4 + 0.06 * (best_rival[1] - 1)
            # A rival ranking is already in `beat`; a prominent rival use is softer evidence of association.
            if strongest[0] == "medium":
                assoc = W["rival_prominent"]
            elif our_assoc[0] in ("strong", "medium") and strongest[0] in ("none", "weak"):
                assoc = W["ours_prominent"]
            else:
                assoc = 1.0
            # Intent: the demand-weighted majority of the checked phrases' intents (judged where possible).
            votes = Counter()
            for p in checked:
                votes[p["intent"]] += max(p["demand"], 0.05)
            intent = votes.most_common(1)[0][0] if votes else "unknown"
            _, signals = intent_guess([p["serp"] for p in checked])
            intent_reasons = [f"{p['phrase']}: {p['intent']} ({p['intent_source']}) {p.get('intent_reason', '')}".strip()
                              for p in checked]
            intent_f = intent_factor[intent]
            # The strongest evidence of all: your own customers describe the benefit this way.
            cust = [q for q in cfg.get("customer_quotes", []) if rx.search(q.lower())]
            cust_f = W["customer_quote"] if cust else 1.0
            trend_f = W["trends_floor"] + (1 - W["trends_floor"]) * trend_rel[w] if w in trend_rel else 1.0
            stage, stage_reason, stage_source = funnel_for(best["phrase"], judge)
            win = math.sqrt(demand) * trend_f * beat * assoc * intent_f * weight * cust_f

            if not checked:
                status = "not checked"
            elif our_rank and our_rank <= TOP:
                status = "ours"
            elif rival_top:
                status = "compete" if stance == "compete" else "theirs"
            else:
                status = "open"

            parts = [f"demand {round(demand * 100)} → {math.sqrt(demand):.2f}"]
            if w in trend_rel:
                parts.append(f"Google Trends \"{fill(w, trend_subject)}\" {trend_raw[w]:.1f} vs. top "
                             f"{max(trend_raw.values()):.1f} → {trend_f:.2f}")
            if rival_top:
                parts.append(f"{best_rival[0]} ranks #{best_rival[1]} → " +
                             ("1.00 (compete stance: appear alongside them)" if stance == "compete" else f"{beat:.2f}"))
            else:
                parts.append("no tracked rival in the top 10 → 1.00")
            if assoc != 1.0:
                parts.append(("a rival uses it prominently" if assoc < 1 else "we use it prominently, rivals don't") + f" → {assoc:.2f}")
            parts.append(f"{intent} searchers → {intent_f:.2f}")
            if cust:
                parts.append(f"{len(cust)} customer quote{'s' if len(cust) > 1 else ''} use it → {cust_f:.2f}")
            parts.append(f"{best['topic']} priority → {weight:.2f}")

            def quotes(name):
                cs = sorted(uses[name], key=lambda c: (not c["prominent"], len(c["text"])))
                return [f"{c['path']} ({c['kind']}): {c['text'][:160]}" for c in cs[:3]]

            rows.append({
                "benefit": b["name"], "wording": w, "stance": stance, "example": best["phrase"], "status": status,
                "win": min(100, round(win * 100)), "demand": round(demand * 100),
                "factors": {"demand": round(math.sqrt(demand), 2), "beatability": round(beat, 2),
                            "association": round(assoc, 2), "intent": round(intent_f, 2), "priority": round(weight, 2),
                            "customers": round(cust_f, 2), "trends": round(trend_f, 2)},
                "trend_phrase": fill(w, trend_subject) if w in trend_rel else "",
                "trend_interest": trend_raw.get(w),
                "why": " × ".join(parts) + f" = {min(100, round(win * 100))}",
                "intent": intent, "intent_signals": signals, "intent_reasons": intent_reasons,
                "stage": stage, "stage_reason": stage_reason, "stage_source": stage_source,
                "customer_quotes": cust[:3],
                "our_rank": our_rank, "best_rival": best_rival[0] if best_rival else None,
                "rival_rank": best_rival[1] if best_rival else None,
                "our_mentions": len(uses[ours.name]), "rival_mentions": sum(len(uses[n]) for n in rival_ranks),
                "our_association": our_assoc[0], "our_association_detail": our_assoc[1],
                "rival_association": strongest[0],
                "rival_association_detail": "; ".join(f"{n}: {a[1]}" for n, a in rival_assoc.items()),
                "our_quotes": quotes(ours.name), "rival_quotes": [q for n in rival_ranks for q in quotes(n)][:3],
                "owners": [d for d, _ in Counter(d for p in checked for d in p["owners"][:3]).most_common(3)],
                "phrases_tested": len(group), "phrases_ranked": len(checked),
            })

    for b in cfg.get("benefits", []):
        mine = sorted((r for r in rows if r["benefit"] == b["name"]), key=lambda r: (-r["win"], -r["demand"]))
        for i, r in enumerate(mine):
            r["rank_in_benefit"] = i + 1
            r["recommended"] = i == 0

    phrase_rows = [{"benefit": p["benefit"], "wording": p["wording"], "topic": p["topic"], "phrase": p["phrase"],
                    "demand": round(p["demand"] * 100), "our_rank": p["ranks"].get(ours.name),
                    "rival_rank": min([r for n, r in p["ranks"].items() if n != ours.name and r], default=None),
                    "owners": p["owners"][:3], "intent": p["intent"], "intent_reason": p.get("intent_reason", ""),
                    "intent_source": p.get("intent_source", "none"), "checked": bool(p["serp"])} for p in phrases]
    return {"wordings": rows, "phrases": phrase_rows}
