"""Stage 1: keyword ownership. Who targets each keyword, who ranks for it, and where we can win."""
from __future__ import annotations

import math
from collections import Counter

from .checks.common import tokens
from .research import Research, domain_of
from .signals import INTENT_FACTOR, funnel_for, intent_for
from .terms import canonical, class_tfidf

TOP = 10  # "ranks" means a top-10 result
# Results from these are reference/marketplace pages, not companies competing for the buyer.
INFO_SITES = ("wikipedia.org", "youtube.com", "reddit.com", "linkedin.com", "sciencedirect.com", "researchgate.net",
              "mdpi.com", "scribd.com", "github.com", "amazon.com", "ebay.com", "quora.com", "facebook.com",
              "ncbi.nlm.nih.gov", "springer.com", "geeksforgeeks.org", "medium.com", "angi.com", "homeadvisor.com")


def is_info_site(domain: str) -> bool:
    return domain.endswith((".gov", ".edu")) or ".gov." in domain or any(domain.endswith(d) for d in INFO_SITES)


def _contains(phrase: str, terms: list[str]) -> bool:
    """Whole-phrase match on stemmed words, so "cold chain" doesn't match "supply chain"."""
    p = f" {canonical(phrase.lower())} "
    return any(f" {canonical(t.lower())} " in p for t in terms)


def _relevant(phrase: str, cfg) -> bool:
    """Mentions one of our topics and none of the off-topic terms (trucks for sale, guitar pickups...)."""
    return _contains(phrase, cfg["topic_terms"]) and not _contains(phrase, cfg.get("exclude_terms", []))


def _fit(phrase: str, cfg) -> float:
    """Share of the keyword's words found in our closest differentiator, discounted when the keyword
    doesn't name something we sell (broad category terms rather than the product itself)."""
    kt = tokens(phrase)
    if not kt:
        return 0.0
    overlap = max((len(kt & tokens(d)) / len(kt) for d in cfg["differentiators"]), default=0.0)
    return overlap * (1.0 if _contains(phrase, cfg.get("product_terms", [])) else 0.35)


def _demand(phrase: str, suggestions: list[str], serp: dict | None) -> tuple[float, list[str]]:
    """Relative demand from Autocomplete: Google only completes queries people actually type, and
    popular queries grow many longer variants. Not a search volume, just a ranking signal."""
    key = canonical(phrase)
    extensions = [s for s in suggestions if canonical(s).startswith(key) and canonical(s) != key]
    exact = any(canonical(s) == key for s in suggestions)
    if exact or extensions:
        score = 0.45 + 0.055 * min(len(extensions), 10)
    elif suggestions:
        score = 0.25
    else:
        score = 0.1
    if serp and serp.get("faq"):
        score += 0.05
    return min(1.0, score), extensions[:6]


def _topic(phrase: str, cfg) -> tuple[str, float]:
    """The brief's topic area a keyword belongs to, and that topic's priority weight."""
    key = canonical(phrase.lower())
    best, best_hits = None, 0
    for t in cfg.get("topics", []):
        if key in {canonical(s.lower()) for s in t["seed_terms"]}:
            return t["name"], t["weight"]
        anchors = t["benefit_subjects"] + [t["name"]] + [s.split()[0] for s in t["seed_terms"] if len(s.split()[0]) > 3]
        hits = sum(_contains(phrase, [a]) for a in set(anchors))
        if hits > best_hits:
            best, best_hits = t, hits
    return (best["name"], best["weight"]) if best else ("Other", 0.8)


def _candidates(sites, cfg, tfidf, research: Research) -> list[tuple[str, str]]:
    """(phrase, source) pairs in priority order: seeds, differentiators, autocomplete, distinctive terms."""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(phrase: str, source: str) -> None:
        key = canonical(phrase.lower().strip())
        if key and key not in seen and 1 <= len(phrase.split()) <= 6:
            seen.add(key)
            out.append((phrase.lower().strip(), source))

    for kw in cfg["keywords"]:
        add(kw, "seed")
    for d in cfg["differentiators"]:
        add(d, "differentiator")
    for kw in cfg["keywords"]:
        for s in research.suggestions(kw)[:5]:
            if _relevant(s, cfg):
                add(s, "autocomplete")
    for s in sites:
        ranked = sorted(tfidf[s.name].values(), key=lambda r: -r["score"])
        picked = [r["phrase"] for r in ranked if len(r["phrase"].split()) >= 2 and _relevant(r["phrase"], cfg)]
        for phrase in picked[: cfg.get("distinctive_per_site", 15)]:
            add(phrase, f"distinctive: {s.name}")
    return out


LABELS = ("ours", "open", "fight for", "not winnable", "not worth it", "not checked")


def _competitor_notes() -> str:
    """The verified competitor findings (research/*.md), for judging where we have an edge."""
    from pathlib import Path
    folder = Path(__file__).resolve().parent.parent / "research"
    return " ".join(p.read_text()[:1500] for p in sorted(folder.glob("*.md")))[:3000] if folder.exists() else ""


def label_for(row: dict, serp: dict | None, cfg, judge, notes: str) -> tuple[str, str, str]:
    """(label, reason, source). Facts decide ours / open / not worth it / not checked; whether a keyword a
    competitor holds is worth fighting for is a judgment against our own advantages."""
    if not serp:
        return "not checked", "No ranking data yet", "rule"
    research_only = row.get("intent") == "research" and row["fit"] < 0.7
    if row["fit"] < 0.4 or row.get("intent") in ("consumer", "jobs") or research_only:
        why = row.get("fit_reason") if row["fit"] < 0.4 else f"{row['intent']} searchers: {row.get('intent_reason', '')}"
        return "not worth it", why, "rule"
    if row["our_rank"] and row["our_rank"] <= TOP:
        return "ours", f"We rank #{row['our_rank']}", "rule"
    held = {n: r for n, r in row["rival_ranks"].items() if r <= TOP}
    if not held:
        return "open", "No tracked competitor in the top 10" + (
            f"; ranking now: {', '.join(row['top_domains'][:3])}" if row["top_domains"] else ""), "rule"
    j = judge.ask("winnable", {"keyword": row["keyword"], "fit": row["fit"], "intent": row.get("intent"),
                               "held_by": held, "results": [{"rank": r["rank"], "domain": r["domain"], "title": r.get("title", "")[:90]}
                                                            for r in serp["results"][:TOP]],
                               "advantages": cfg["differentiators"], "competitor_notes": notes},
                  stable=row["keyword"])
    if j and j.get("label") in ("fight for", "not winnable"):
        return j["label"], j.get("reason", ""), "judged"
    best = min(held.values())
    if row["fit"] >= 0.7 and best >= 4:
        return "fight for", f"Good fit, and the best tracked competitor is only #{best}", "heuristic"
    return "not winnable", f"Held by {', '.join(held)} (best #{best})", "heuristic"


def build(sites, cfg, research: Research, judge, log=print) -> dict:
    tfidf = class_tfidf(sites)
    ours = next(s for s in sites if s.is_ours)
    domains = {s.name: domain_of(s.origin or s.base_url) for s in sites}

    candidates = _candidates(sites, cfg, tfidf, research)
    log(f"[keywords] {len(candidates)} candidate keywords; checking demand and rankings "
        f"(search budget {research.serp_budget})")

    rows, winners = [], Counter()
    notes = _competitor_notes()
    for phrase, source in candidates:
        key = canonical(phrase)
        suggestions = research.suggestions(phrase)
        serp = research.serp(phrase)
        demand, extensions = _demand(phrase, suggestions, serp)
        fit = _fit(phrase, cfg)
        fit_reason, fit_source = "word overlap with the differentiators", "heuristic"
        j = judge.ask("fit", {"keyword": phrase, "differentiators": cfg["differentiators"]})
        if j and isinstance(j.get("fit"), (int, float)):
            fit, fit_reason, fit_source = max(0.0, min(1.0, float(j["fit"]))), j.get("reason", ""), "judged"
        topic, weight = _topic(phrase, cfg)
        intent, intent_reason, intent_source = intent_for(phrase, serp, judge)
        stage, stage_reason, stage_source = funnel_for(phrase, judge)

        targeting = {s.name: round(min(1.0, tfidf[s.name].get(key, {}).get("weight", 0) / 15), 2) for s in sites}
        ranks = {}
        top_domains = []
        if serp:
            for s in sites:
                hits = [r["rank"] for r in serp["results"] if r["domain"].endswith(domains[s.name])]
                ranks[s.name] = min(hits) if hits else None
            top_domains = list(dict.fromkeys(r["domain"] for r in serp["results"][:TOP]))
            winners.update(d for d in top_domains if not is_info_site(d))

        our_rank = ranks.get(ours.name)
        rival_ranks = {n: r for n, r in ranks.items() if n != ours.name and r}
        best_rival = min(rival_ranks.items(), key=lambda kv: kv[1]) if rival_ranks else None

        if not serp:
            status = "not checked"
        elif our_rank and our_rank <= TOP and best_rival and best_rival[1] <= TOP:
            status = "contested"
        elif our_rank and our_rank <= TOP:
            status = "ours"
        elif best_rival and best_rival[1] <= TOP:
            status = "theirs"
        else:
            status = "open gap"

        beat = 1.0
        if best_rival and best_rival[1] <= TOP:
            beat = 0.4 + 0.06 * (best_rival[1] - 1)
        if our_rank and our_rank <= 3:
            beat *= 0.3  # already won; keep defending, but it's not the next opportunity
        # Fit outweighs raw demand: a specific phrase we can credibly own beats a broad one we can't.
        opportunity = math.sqrt(demand) * fit * beat * weight * INTENT_FACTOR[intent]
        if status == "not checked":
            opportunity *= 0.8

        rows.append({
            "keyword": phrase, "topic": topic, "source": source, "status": status,
            "fit_reason": fit_reason, "fit_source": fit_source,
            "intent": intent, "intent_reason": intent_reason, "intent_source": intent_source,
            "stage": stage, "stage_reason": stage_reason, "stage_source": stage_source,
            "opportunity": round(opportunity * 100), "demand": round(demand, 2), "fit": round(fit, 2),
            "our_rank": our_rank, "rival_ranks": rival_ranks,
            "best_rival": best_rival[0] if best_rival else None,
            "targeting": targeting, "top_domains": [d for d in top_domains if not is_info_site(d)][:5],
            "autocomplete": extensions, "related": (serp or {}).get("related", [])[:6],
            "faq": (serp or {}).get("faq", [])[:6],
        })
        rows[-1]["label"], rows[-1]["label_reason"], rows[-1]["label_source"] = label_for(rows[-1], serp, cfg, judge, notes)

    rows.sort(key=lambda r: -r["opportunity"])
    distinctive = {}
    for s in sites:
        ranked = sorted(tfidf[s.name].values(), key=lambda r: -r["score"])
        distinctive[s.name] = [{"phrase": r["phrase"], "score": round(r["score"], 1), "share": r["share"]}
                               for r in ranked if len(r["phrase"].split()) >= 2][:30]
    tracked = set(domains.values())
    return {
        "keywords": rows,
        "distinctive": distinctive,
        "search_winners": [{"domain": d, "top10_count": n, "tracked": any(d.endswith(t) for t in tracked)}
                           for d, n in winners.most_common(25)],
        "serp_calls": research.serp_calls,
        "checked": sum(1 for r in rows if r["status"] != "not checked"),
    }
