"""Free demand and ranking data: Google Autocomplete and the Brave Search API, both cached on disk."""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from urllib.parse import urlparse

import requests

from .fetch import USER_AGENT

BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
SUGGEST_ENDPOINT = "https://suggestqueries.google.com/complete/search"


def load_env(path: Path) -> None:
    """Read KEY=value lines from .env into os.environ without overriding what's already set."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        m = re.match(r"\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*?)\s*$", line)
        if m and m[1] not in os.environ:
            os.environ[m[1]] = m[2].strip("'\"")


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


class Research:
    """Caches every response so re-runs don't spend API quota on the same query twice."""

    def __init__(self, cache_dir: Path, serp_budget: int, log=print):
        self.cache_dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.serp_budget = serp_budget
        self.serp_calls = 0
        self.log = log
        self.brave_key = os.environ.get("BRAVE_API_KEY", "")
        self.session = requests.Session()
        self._last: dict[str, float] = {}
        self.seen: dict[str, dict] = {}  # every search result this run used, cached or new
        self.refresh_seconds = 30 * 86400  # rankings older than this are searched again while budget lasts
        self.refreshed = 0

    def _cache(self, kind: str, query: str) -> Path:
        h = hashlib.sha1(query.lower().strip().encode()).hexdigest()[:16]
        return self.cache_dir / f"{kind}-{h}.json"

    def _throttle(self, kind: str, delay: float) -> None:
        wait = delay - (time.monotonic() - self._last.get(kind, 0))
        if wait > 0:
            time.sleep(wait)
        self._last[kind] = time.monotonic()

    def suggestions(self, query: str) -> list[str]:
        path = self._cache("suggest", query)
        if path.exists():
            return json.loads(path.read_text())
        self._throttle("suggest", 1.0)
        try:
            r = self.session.get(SUGGEST_ENDPOINT, params={"client": "firefox", "hl": "en", "gl": "us", "q": query},
                                 headers={"User-Agent": USER_AGENT}, timeout=15)
            out = r.json()[1] if r.ok else []
        except (requests.RequestException, ValueError, IndexError):
            return []
        path.write_text(json.dumps(out))
        return out

    def serp(self, query: str) -> dict | None:
        """Top 20 Brave results; None when there's no key or the run's budget is spent."""
        path = self._cache("serp", query)
        stale = path.exists() and time.time() - path.stat().st_mtime > self.refresh_seconds
        can_search = bool(self.brave_key) and self.serp_calls < self.serp_budget
        if path.exists() and not (stale and can_search):
            # Fresh, or stale with no budget left: an old ranking beats none.
            self.seen[query] = json.loads(path.read_text())
            return self.seen[query]
        if not can_search:
            return None
        self.refreshed += stale
        self._throttle("serp", 1.1)
        self.serp_calls += 1
        try:
            r = self.session.get(BRAVE_ENDPOINT, params={"q": query, "count": 20, "country": "us"},
                                 headers={"X-Subscription-Token": self.brave_key, "Accept": "application/json"},
                                 timeout=20)
        except requests.RequestException as exc:
            self.log(f"  Brave error for {query!r}: {exc}")
            return None
        if not r.ok:
            self.log(f"  Brave HTTP {r.status_code} for {query!r}")
            return None
        d = r.json()
        out = {
            "query": query,
            "results": [{"rank": i, "url": x.get("url", ""), "domain": domain_of(x.get("url", "")),
                         "title": x.get("title", "")}
                        for i, x in enumerate(d.get("web", {}).get("results", []), 1)],
            "related": [q.get("query", q) if isinstance(q, dict) else q
                        for q in d.get("query", {}).get("related_queries", []) or []],
            "faq": [x.get("question", "") for x in d.get("faq", {}).get("results", [])],
        }
        path.write_text(json.dumps(out))
        self.seen[query] = out
        return out
