"""Polite HTTP fetching shared by the crawler and the checks."""
from __future__ import annotations

import os

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests

AGENT_TOKEN = "SXO-Audit"
USER_AGENT = f"Mozilla/5.0 (compatible; {AGENT_TOKEN}/0.1; +{os.environ.get('SXO_CONTACT_URL', 'https://example.com/')})"


@dataclass
class Response:
    url: str
    final_url: str
    status: int
    content_type: str
    text: str
    size: int
    elapsed: float
    error: str = ""

    @property
    def ok(self) -> bool:
        return 200 <= self.status < 300

    @property
    def is_html(self) -> bool:
        return "html" in self.content_type.lower()

    @property
    def looks_like_html(self) -> bool:
        """True when the body is an HTML page, whatever the header claims."""
        head = self.text.lstrip()[:200].lower()
        return head.startswith("<!doctype html") or head.startswith("<html")


class Fetcher:
    """Fetches URLs with a fixed delay between requests to the same host. With a cache folder, successful
    GETs are reused for `cache_days`, so changing the brief and rerunning doesn't re-crawl every site."""

    def __init__(self, delay: float = 1.0, timeout: float = 20.0, cache_dir: Path | None = None, cache_days: float = 7):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
        self.delay = delay
        self.timeout = timeout
        self._last_hit: dict[str, float] = {}
        self.cache_dir = cache_dir
        self.cache_seconds = cache_days * 86400
        self.cache_hits = 0
        if cache_dir:
            cache_dir.mkdir(parents=True, exist_ok=True)

    def _cache_path(self, url: str) -> Path:
        return self.cache_dir / (hashlib.sha1(url.encode()).hexdigest()[:20] + ".json")

    def _cached(self, url: str) -> Response | None:
        if not self.cache_dir:
            return None
        path = self._cache_path(url)
        if not path.exists() or time.time() - path.stat().st_mtime > self.cache_seconds:
            return None
        try:
            return Response(**json.loads(path.read_text()))
        except (ValueError, TypeError):
            return None

    def _wait_for(self, host: str) -> None:
        last = self._last_hit.get(host)
        if last is not None:
            remaining = self.delay - (time.monotonic() - last)
            if remaining > 0:
                time.sleep(remaining)

    def get(self, url: str, method: str = "GET", timeout: float | None = None, cache: bool = True) -> Response:
        use_cache = cache and method == "GET"
        hit = self._cached(url) if use_cache else None
        if hit:
            self.cache_hits += 1
            return hit
        host = urlparse(url).netloc
        self._wait_for(host)
        try:
            r = self.session.request(method, url, timeout=timeout or self.timeout, allow_redirects=True)
        except requests.RequestException as exc:
            return Response(url, url, 0, "", "", 0, 0.0, str(exc))
        finally:
            self._last_hit[host] = time.monotonic()
        text = r.text if method == "GET" else ""
        resp = Response(url, r.url, r.status_code, r.headers.get("content-type", ""), text,
                        len(r.content), r.elapsed.total_seconds())
        if use_cache and self.cache_dir and resp.ok:
            self._cache_path(url).write_text(json.dumps(asdict(resp)))
        return resp
