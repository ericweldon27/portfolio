"""Signals shared by keywords and benefits: who searches a phrase, and where it sits in the funnel.
Each has a quick heuristic, replaced by Claude's judgment once one exists (see judge.py)."""
from __future__ import annotations

import re

TOP = 10
CONSUMER_SITES = ("discover.com", "nerdwallet.com", "bankrate.com", "thespruce.com", "homeguide.com", "homeadvisor.com",
                  "angi.com", "move.org", "thriftyfun.com", "moneycrashers.com", "thepennyhoarder.com")
CONSUMER_RX = re.compile(r"\b(home|homes|household|homeowners?|residential|family|personal|frugal|money tips|"
                         r"apartment|kitchen|diy|garbage bill|your house)\b", re.I)
BUSINESS_RX = re.compile(r"\b(commercial|business|businesses|facility|facilities|industrial|enterprise|propert(y|ies)|"
                         r"manufactur\w*|warehouse|b2b|compan(y|ies)|municipal|campus|universit(y|ies)|hospital|"
                         r"restaurant|retail|operations|vendor|vendors|supplier|suppliers)\b", re.I)
INTENT_FACTOR = {"business": 1.0, "mixed": 0.85, "research": 0.8, "consumer": 0.5, "jobs": 0.3, "unknown": 1.0}

AWARENESS_RX = re.compile(r"^(what|why|how|when|is|are|can|does|do)\b|\b(meaning|definition|tips|ways to|guide|"
                          r"bridging|hidden costs|problems?|signs)\b", re.I)
DECISION_RX = re.compile(r"\b(pricing|price|prices|cost of|quote|vendors?|compan(y|ies)|providers?|best|top|vs|"
                         r"versus|compare|comparison|reviews?|for sale|buy|demo|near me)\b", re.I)


def results_for_judging(serp: dict) -> list[dict]:
    return [{"domain": r["domain"], "title": r.get("title", "")[:90]} for r in serp["results"][:TOP]]


def intent_guess(serps: list[dict]) -> tuple[str, dict]:
    """Business or consumer searchers, judged from the result titles and sites ranking now."""
    cons = biz = 0
    for serp in serps:
        for r in serp["results"][:TOP]:
            text = f"{r.get('title', '')} {r['domain']}"
            cons += bool(CONSUMER_RX.search(text)) or r["domain"].endswith(CONSUMER_SITES)
            biz += bool(BUSINESS_RX.search(text))
    if not serps:
        label = "unknown"
    elif biz >= cons + 2:
        label = "business"
    elif cons >= 2 and cons >= biz + 1:
        label = "consumer"
    else:
        label = "mixed"
    return label, {"business_results": biz, "consumer_results": cons}


def intent_for(phrase: str, serp: dict | None, judge) -> tuple[str, str, str]:
    """(intent, reason, source). Claude's judgment when there is one, else the title heuristic."""
    if not serp:
        return "unknown", "not searched", "none"
    j = judge.ask("intent", {"phrase": phrase, "results": results_for_judging(serp)})
    if j and j.get("intent") in INTENT_FACTOR:
        return j["intent"], j.get("reason", ""), "judged"
    label, s = intent_guess([serp])
    return label, f"{s['business_results']} business-looking and {s['consumer_results']} consumer-looking results", "heuristic"


def funnel_for(text: str, judge) -> tuple[str, str, str]:
    """(stage, reason, source): awareness (learning about the problem), consideration (comparing
    approaches), decision (choosing a vendor)."""
    j = judge.ask("funnel", {"text": text})
    if j and j.get("stage") in ("awareness", "consideration", "decision"):
        return j["stage"], j.get("reason", ""), "judged"
    if DECISION_RX.search(text):
        return "decision", "names vendors, prices or comparisons", "heuristic"
    if AWARENESS_RX.search(text):
        return "awareness", "a question or problem phrase", "heuristic"
    return "consideration", "names a solution or approach", "heuristic"
