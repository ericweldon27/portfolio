"""Who gets cited: third-party pages (publications, directories, other vendors' blogs) that rank for our
keywords, and which tracked companies they mention. These are the sources search engines and AI answers
lean on, so they're the PR and placement targets."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from urllib import robotparser
from urllib.parse import urlparse

from .fetch import AGENT_TOKEN, Fetcher
from .keywords import is_info_site
from .page import parse_page

PUBLICATION_RX = re.compile(r"(magazine|today|news|journal|times|daily|wire|digest|insider|world|weekly|report|"
                            r"recycling|waste360|resource-recycling|swana)", re.I)


def aliases(name: str) -> list[str]:
    """'Acme Corp (Acme)' -> ['Acme Corp', 'Acme']."""
    parts = re.split(r"[()/,]", name)
    return [p.strip() for p in parts if len(p.strip()) > 2]


def build(sites, serps: dict, fetcher: Fetcher, limit: int = 15, log=print) -> list[dict]:
    tracked = {s.name: urlparse(s.origin or s.base_url).netloc.lower().removeprefix("www.") for s in sites}
    pages = defaultdict(lambda: {"queries": set(), "best_rank": 99, "title": ""})
    for query, serp in serps.items():
        for r in serp["results"][:10]:
            d = r["domain"]
            if any(d.endswith(t) for t in tracked.values()) or is_info_site(d):
                continue
            page = pages[r["url"]]
            page["queries"].add(query)
            page["best_rank"] = min(page["best_rank"], r["rank"])
            page["title"] = r.get("title", "")
    ranked = sorted(pages.items(), key=lambda kv: (-len(kv[1]["queries"]), kv[1]["best_rank"]))
    picked, domains_seen = [], set()
    for url, info in ranked:  # one page per domain: its best-ranking one
        d = urlparse(url).netloc.lower().removeprefix("www.")
        if d not in domains_seen:
            domains_seen.add(d)
            picked.append((url, info))
    picked = picked[:limit]
    log(f"[citations] reading {len(picked)} third-party pages that rank for our keywords")

    robots: dict[str, robotparser.RobotFileParser] = {}
    rows = []
    for url, info in picked:
        origin = "{0.scheme}://{0.netloc}".format(urlparse(url))
        if origin not in robots:
            rp = robotparser.RobotFileParser()
            rp.parse(fetcher.get(origin + "/robots.txt").text.splitlines())
            robots[origin] = rp
        mentions, note = {}, ""
        if not robots[origin].can_fetch(AGENT_TOKEN, url):
            note = "robots.txt disallows reading"
        else:
            resp = fetcher.get(url)
            if not resp.ok:
                note = f"HTTP {resp.status}"
            else:
                text = parse_page(resp).text.lower() if resp.is_html else ""
                for s in sites:
                    n = sum(len(re.findall(rf"\b{re.escape(a.lower())}\b", text)) for a in aliases(s.name))
                    mentions[s.name] = n
        domain = urlparse(url).netloc.lower().removeprefix("www.")
        kind = "publication" if PUBLICATION_RX.search(domain) else "vendor or directory"
        rows.append({"domain": domain, "url": url, "title": info["title"][:120], "kind": kind,
                     "ranks_for": len(info["queries"]), "best_rank": info["best_rank"],
                     "queries": ", ".join(sorted(info["queries"])[:5]),
                     "mentions": ", ".join(f"{n}: {c}" for n, c in mentions.items()) if mentions else note,
                     "mentions_us": mentions.get(next(s.name for s in sites if s.is_ours), 0) if mentions else None,
                     "mentions_rivals": sum(c for n, c in mentions.items()
                                            if n != next(s.name for s in sites if s.is_ours)) if mentions else None})
    return rows
