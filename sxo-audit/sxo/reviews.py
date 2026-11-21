"""Competitor reviews: what buyers like and dislike, mapped to where we can attack or must defend.

Reviews come from two places:
  - pasted on the setup page (any source: BBB, Birdeye, G2, Yelp, Google), split into one review per block;
  - review pages listed on the setup page, read only where robots.txt allows it and the page publishes
    schema.org Review data. Sites that block automated readers (BBB, Birdeye today) are reported, not worked around.
Each review is judged by Claude into aspects with like/dislike (see judge.py); unjudged reviews are counted
but not classified.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from urllib import robotparser
from urllib.parse import urlparse

from .fetch import AGENT_TOKEN, Fetcher
from .judge import REVIEW_ASPECTS

# Where we have an answer to each aspect. "None" means the aspect is about something we don't
# provide: worth watching, not attacking.
# Replace these with your own product's answers; the aspect keys come from judge.REVIEW_ASPECTS.
ASPECT_ANSWERS = {
    "billing and pricing": "Our answer on cost and billing transparency",
    "missed or late pickups": "Our answer on reliability of service",
    "service and responsiveness": None,
    "contract terms": None,
    "technology and data": "Our answer on measurement accuracy and reporting",
    "savings delivered": "Our answer on proving savings",
    "sustainability and reporting": "Our answer on sustainability reporting",
    "setup and onboarding": "Our answer on how fast setup is",
}


def split_pasted(text: str) -> list[str]:
    """One review per block: blank lines or a line of dashes separate them."""
    blocks = re.split(r"\n\s*(?:-{3,}|={3,})?\s*\n", text.strip())
    return [b.strip() for b in blocks if len(b.split()) >= 5]


def _schema_reviews(html: str) -> list[dict]:
    out = []
    for block in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', html, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if not isinstance(item, dict):
                continue
            if "Review" in str(item.get("@type", "")) and (item.get("reviewBody") or item.get("description")):
                rating = item.get("reviewRating", {})
                out.append({"text": (item.get("reviewBody") or item.get("description")).strip(),
                            "rating": rating.get("ratingValue") if isinstance(rating, dict) else None,
                            "date": item.get("datePublished", "")})
            for v in item.values():
                if isinstance(v, (list, dict)):
                    stack.extend(v if isinstance(v, list) else [v])
    return out


def fetch_review_pages(urls: list[str], fetcher: Fetcher) -> tuple[list[dict], list[dict]]:
    """Read review pages that allow it. Returns (reviews, per-source status)."""
    reviews, status = [], []
    robots: dict[str, robotparser.RobotFileParser] = {}
    for url in urls:
        origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
        if origin not in robots:
            rp = robotparser.RobotFileParser()
            rp.parse(fetcher.get(origin + "/robots.txt").text.splitlines())
            robots[origin] = rp
        if not robots[origin].can_fetch(AGENT_TOKEN, url):
            status.append({"url": url, "result": "robots.txt disallows automated reading: paste these reviews"})
            continue
        resp = fetcher.get(url)
        if resp.status in (401, 403, 429) or resp.status == 0:
            status.append({"url": url, "result": f"blocked (HTTP {resp.status}): paste these reviews"})
            continue
        if urlparse(resp.final_url).path.rstrip("/") != urlparse(url).path.rstrip("/"):
            status.append({"url": url, "result": "redirected away from the review page: paste these reviews"})
            continue
        found = _schema_reviews(resp.text)
        status.append({"url": url, "result": f"read {len(found)} reviews" if found else
                       "no machine-readable reviews on the page: paste these reviews"})
        reviews += [dict(r, source=urlparse(url).netloc.removeprefix("www.")) for r in found]
    return reviews, status


def build(cfg, fetcher: Fetcher, judge, log=print) -> dict:
    by_comp = defaultdict(list)
    sources = []
    for comp in cfg.get("competitors", []):
        name = comp.get("name") or comp.get("url")
        fetched, status = fetch_review_pages(comp.get("review_urls", []), fetcher)
        sources += [dict(s, competitor=name) for s in status]
        by_comp[name] += fetched
    for item in cfg.get("pasted_reviews", []):
        for text in split_pasted(item.get("text", "")):
            by_comp[item.get("competitor", "Unknown")].append({"text": text, "rating": None, "date": "",
                                                               "source": item.get("source", "pasted")})
    log(f"[reviews] {sum(len(v) for v in by_comp.values())} reviews for {len(by_comp)} competitors")

    reviews, agg = [], defaultdict(lambda: {"likes": 0, "dislikes": 0, "like_quotes": [], "dislike_quotes": []})
    for comp, items in by_comp.items():
        for r in items:
            j = judge.ask("review", {"competitor": comp, "source": r["source"], "text": r["text"][:1500],
                                     "aspects": REVIEW_ASPECTS})
            aspects = (j or {}).get("aspects", [])
            reviews.append({"competitor": comp, "source": r["source"], "rating": r["rating"], "date": r["date"],
                            "text": r["text"][:600], "judged": j is not None,
                            "summary": (j or {}).get("summary", ""),
                            "aspects": "; ".join(f"{a['aspect']} ({a['sentiment']})" for a in aspects)})
            for a in aspects:
                key = (comp, a.get("aspect", ""))
                side = "likes" if a.get("sentiment") == "like" else "dislikes"
                agg[key][side] += 1
                if a.get("quote"):
                    agg[key][side[:-1] + "_quotes"].append(a["quote"][:200])

    rows = []
    for (comp, aspect), v in agg.items():
        answer = ASPECT_ANSWERS.get(aspect)
        if v["dislikes"] > v["likes"] and answer:
            stance = "attack"
        elif v["likes"] >= v["dislikes"] and v["likes"]:
            stance = "defend"
        else:
            stance = "watch"
        rows.append({"competitor": comp, "aspect": aspect, "likes": v["likes"], "dislikes": v["dislikes"],
                     "stance": stance, "our_answer": answer or "We don't do this; not ours to win",
                     "like_quotes": " || ".join(v["like_quotes"][:3]),
                     "dislike_quotes": " || ".join(v["dislike_quotes"][:3])})
    rows.sort(key=lambda r: (r["competitor"], -(r["likes"] + r["dislikes"])))
    return {"aspects": rows, "reviews": reviews, "sources": sources,
            "pending": sum(1 for r in reviews if not r["judged"])}
