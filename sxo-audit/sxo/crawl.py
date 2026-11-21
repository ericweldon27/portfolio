"""Collect everything the checks need about one site: pages plus site-wide files."""
from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from urllib import robotparser
from urllib.parse import urlencode, urlparse

from .fetch import AGENT_TOKEN, Fetcher, Response
from .page import NON_HTML_EXT, Page, host_key, normalize, parse_page

AI_BOTS = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot",
           "PerplexityBot", "Google-Extended", "Applebot-Extended", "CCBot", "Bingbot", "Googlebot"]
PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

# Page types, checked in order, and each type's share of the page budget. Sampling by type keeps the
# comparison like-for-like: a blog-heavy site doesn't crowd out its own product pages.
PAGE_TYPES = [
    ("proof", r"/(case-stud|customers?/|customer-stor|success|testimonial|results)", 0.10),
    ("industry", r"/(industr\w*|who-we-serve|sectors?|use-cases?|markets?)\b", 0.20),
    ("product", r"/(solutions?|technology|products?|services?|waste-services|features|platform|how-it-works|"
                r"monitoring|metering|sensors?)\b", 0.35),
    ("blog", r"/(blog|news|resources?|insights|articles?|learn|guides?|knowledge)\b", 0.25),
    ("company", r"/(about|company|contact|careers|pricing|demo|request|team|partners)", 0.10),
]


def page_type(url: str) -> str:
    path = urlparse(url).path.lower()
    if path in ("", "/"):
        return "home"
    for name, rx, _ in PAGE_TYPES:
        if re.search(rx, path):
            return name
    return "other"


@dataclass
class SiteData:
    name: str
    base_url: str
    is_ours: bool
    origin: str = ""
    pages: list = field(default_factory=list)
    robots: dict = field(default_factory=dict)
    sitemap: dict = field(default_factory=dict)
    soft404: dict = field(default_factory=dict)
    llms_txt: dict = field(default_factory=dict)
    ai_bots: dict = field(default_factory=dict)  # bot -> allowed (bool)
    psi: dict = field(default_factory=dict)
    js_routes: list = field(default_factory=list)  # pages found only in the JS bundle
    html_linked: set = field(default_factory=set)  # internal URLs reachable via plain <a href>
    broken_links: list = field(default_factory=list)
    links_checked: int = 0
    errors: list = field(default_factory=list)

    @property
    def home(self) -> Page:
        return self.pages[0]


def _plain_file(resp: Response) -> bool:
    """A real robots.txt/llms.txt, not an HTML page served under that path."""
    return resp.ok and not resp.looks_like_html


def _fetch_robots(site: SiteData, fetcher: Fetcher) -> robotparser.RobotFileParser | None:
    resp = fetcher.get(site.origin + "/robots.txt")
    valid = _plain_file(resp)
    sitemaps = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", resp.text) if valid else []
    site.robots = {"status": resp.status, "valid": valid, "served_html": resp.ok and resp.looks_like_html,
                   "sitemaps": sitemaps, "text": resp.text[:4000] if valid else ""}
    parser = robotparser.RobotFileParser()
    parser.parse(resp.text.splitlines() if valid else [])
    for bot in AI_BOTS:
        site.ai_bots[bot] = parser.can_fetch(bot, site.origin + "/")
    return parser if valid else None


def _fetch_sitemap(site: SiteData, fetcher: Fetcher) -> None:
    candidates = site.robots.get("sitemaps") or [site.origin + "/sitemap.xml"]
    locs, lastmods, source, status = [], [], "", 0
    for url in candidates[:2]:
        resp = fetcher.get(url, timeout=40)
        status = resp.status
        if not resp.ok or resp.looks_like_html or "<loc>" not in resp.text:
            continue
        source = url
        if "<sitemapindex" in resp.text:
            for child in re.findall(r"<loc>\s*(.*?)\s*</loc>", resp.text)[:5]:
                child_resp = fetcher.get(child, timeout=40)
                if child_resp.ok and "<loc>" in child_resp.text:
                    locs += re.findall(r"<loc>\s*(.*?)\s*</loc>", child_resp.text)
                    lastmods += re.findall(r"<lastmod>\s*(.*?)\s*</lastmod>", child_resp.text)
        else:
            locs += re.findall(r"<loc>\s*(.*?)\s*</loc>", resp.text)
            lastmods += re.findall(r"<lastmod>\s*(.*?)\s*</lastmod>", resp.text)
        break
    site.sitemap = {"valid": bool(locs), "source": source, "status": status,
                    "urls": locs, "lastmods": lastmods, "count": len(locs)}


def _probe_site_files(site: SiteData, fetcher: Fetcher) -> None:
    probe = f"{site.origin}/sxo-probe-{uuid.uuid4().hex[:8]}-does-not-exist"
    resp = fetcher.get(probe, cache=False)
    site.soft404 = {"probe_url": probe, "status": resp.status,
                    "same_as_home": resp.ok and abs(resp.size - site.home.size) < 200}
    llms = fetcher.get(site.origin + "/llms.txt")
    site.llms_txt = {"status": llms.status, "valid": _plain_file(llms),
                     "bytes": llms.size if _plain_file(llms) else 0}


def _is_home_fallback(site: SiteData, resp: Response) -> bool:
    """On soft-404 sites, a URL that just serves the homepage is really a missing page."""
    return bool(site.soft404.get("same_as_home")) and resp.ok and abs(resp.size - site.home.size) < 200


def _discover_js_routes(site: SiteData, fetcher: Fetcher) -> None:
    """Next.js sites list every page route in _buildManifest.js, even ones no HTML links to."""
    m = re.search(r'(/_next/static/[^"\']+/_buildManifest\.js)', fetcher.get(site.home.final_url).text)
    if not m:
        return
    manifest = fetcher.get(site.origin + m.group(1)).text
    routes = sorted(set(re.findall(r'"(/[a-z0-9/_-]*)"', manifest)))
    site.js_routes = [site.origin + r for r in routes if r != "/" and not r.startswith("/_")]


def _keyword_tokens(keywords: list[str]) -> set[str]:
    return {w for kw in keywords for w in re.findall(r"[a-z]+", kw.lower()) if len(w) > 3}


def _choose_urls(site: SiteData, keywords: list[str], max_pages: int) -> list[str]:
    """Homepage, then nav pages, then sitemap pages that match our keywords, then the rest."""
    tokens = _keyword_tokens(keywords)
    home_host = host_key(site.home.final_url)

    def usable(url: str) -> bool:
        return host_key(url) == home_host and not NON_HTML_EXT.search(urlparse(url).path)

    def relevance(url: str) -> tuple:
        path = urlparse(url).path.lower()
        depth = len([p for p in path.split("/") if p])
        return (-sum(t in path for t in tokens), depth)

    ordered: list[str] = []
    nav = [l.url for l in site.home.links if l.internal and l.in_nav]
    body = [l.url for l in site.home.links if l.internal and not l.in_nav]
    sitemap = [u for u in site.sitemap.get("urls", [])]
    matching = sorted((u for u in sitemap if relevance(u)[0] < 0), key=relevance)
    shallow = sorted((u for u in sitemap if relevance(u)[0] == 0), key=relevance)
    for group in (nav, site.js_routes, matching, body, shallow):
        for url in group:
            n = normalize(url)
            if usable(n) and n not in ordered and n != normalize(site.home.final_url):
                ordered.append(n)
    # Fill each page type's share first (in priority order), then use what's left on anything.
    budget = max_pages - 1
    chosen: list[str] = []
    for name, _, share in PAGE_TYPES:
        quota = max(1, round(budget * share))
        chosen += [u for u in ordered if page_type(u) == name and u not in chosen][:quota]
    chosen += [u for u in ordered if u not in chosen][: max(0, budget - len(chosen))]
    return chosen[:budget]


def _check_links(site: SiteData, fetcher: Fetcher, limit: int = 20) -> None:
    fetched = {normalize(p.final_url) for p in site.pages} | {normalize(p.url) for p in site.pages} | {normalize(u) for u, _ in site.broken_links}
    targets = sorted({normalize(l.url) for p in site.pages for l in p.links
                      if l.internal and not NON_HTML_EXT.search(urlparse(l.url).path)} - fetched)
    broken = [(p.final_url, p.status) for p in site.pages if p.status >= 400] + site.broken_links
    for url in targets[:limit]:
        resp = fetcher.get(url)
        if resp.status == 0 or resp.status >= 400:
            broken.append((url, resp.status))
        elif _is_home_fallback(site, resp):
            broken.append((url, "200 but serves the homepage"))
    site.broken_links = broken
    site.links_checked = min(len(targets), limit) + len(site.pages)


def _run_pagespeed(site: SiteData, fetcher: Fetcher) -> None:
    params = [("url", site.home.final_url), ("strategy", "mobile")]
    params += [("category", c) for c in ("performance", "accessibility", "seo", "best-practices")]
    if os.environ.get("PSI_API_KEY"):
        params.append(("key", os.environ["PSI_API_KEY"]))
    resp = fetcher.get(f"{PSI_ENDPOINT}?{urlencode(params)}", timeout=120)
    if not resp.ok:
        site.psi = {"error": f"HTTP {resp.status} {resp.error}".strip()}
        return
    data = json.loads(resp.text)
    lh = data.get("lighthouseResult", {})
    cats = {k: round((v.get("score") or 0) * 100) for k, v in lh.get("categories", {}).items()}
    audits = lh.get("audits", {})
    lab = {key: audits.get(key, {}).get("displayValue", "")
           for key in ("largest-contentful-paint", "cumulative-layout-shift", "total-blocking-time",
                       "first-contentful-paint", "speed-index")}
    field_data = {k: v.get("percentile") for k, v in data.get("loadingExperience", {}).get("metrics", {}).items()}
    site.psi = {"categories": cats, "lab": lab, "field": field_data}


def crawl_site(name: str, url: str, is_ours: bool, fetcher: Fetcher, keywords: list[str],
               max_pages: int, run_pagespeed: bool, log=print) -> SiteData:
    site = SiteData(name, url, is_ours)
    log(f"[{name}] fetching homepage")
    home = fetcher.get(url)
    if not home.ok:
        site.errors.append(f"Homepage returned HTTP {home.status} {home.error}")
        return site
    p = urlparse(home.final_url)
    site.origin = f"{p.scheme}://{p.netloc}"
    site.pages.append(parse_page(home))
    site.pages[0].kind = "home"

    log(f"[{name}] robots.txt, sitemap, llms.txt, 404 handling")
    robots = _fetch_robots(site, fetcher)
    _fetch_sitemap(site, fetcher)
    _probe_site_files(site, fetcher)
    if not site.sitemap.get("valid"):
        _discover_js_routes(site, fetcher)

    urls = _choose_urls(site, keywords, max_pages)
    for i, target in enumerate(urls, 1):
        if robots and not robots.can_fetch(AGENT_TOKEN, target):
            continue
        log(f"[{name}] page {i}/{len(urls)} {urlparse(target).path}")
        resp = fetcher.get(target)
        if _is_home_fallback(site, resp):
            site.broken_links.append((target, "200 but serves the homepage"))
        elif resp.status and (resp.is_html or resp.status >= 400):
            site.pages.append(parse_page(resp))
            site.pages[-1].kind = page_type(target)

    site.html_linked = {normalize(l.url) for p in site.pages for l in p.links if l.internal}

    log(f"[{name}] checking internal links")
    _check_links(site, fetcher)
    if run_pagespeed:
        log(f"[{name}] PageSpeed Insights (mobile), can take a minute")
        _run_pagespeed(site, fetcher)
    return site
