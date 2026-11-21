"""SEO checks: crawlability, on-page basics, content depth and keyword coverage."""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median

from ..page import normalize, path_of
from .common import Check, share, tokens

S = "SEO"


def robots_txt(site, cfg) -> Check:
    r = site.robots
    if r.get("valid"):
        return Check("seo.robots", S, "robots.txt", 1.0, "Valid robots.txt found.", details=r["text"].splitlines()[:40])
    why = "the server returns an HTML page at /robots.txt" if r.get("served_html") else f"HTTP {r.get('status')}"
    return Check("seo.robots", S, "robots.txt", 0.0, f"No real robots.txt: {why}.", weight=1.5,
                 recommendation="Publish a plain-text /robots.txt that allows crawling and lists the sitemap URL.")


def sitemap(site, cfg) -> Check:
    sm = site.sitemap
    if sm.get("valid"):
        return Check("seo.sitemap", S, "XML sitemap", 1.0, f"Sitemap with {sm['count']} URLs at {sm['source']}.",
                     details=[path_of(u) for u in sm["urls"][:100]])
    return Check("seo.sitemap", S, "XML sitemap", 0.0, "No XML sitemap found (checked robots.txt and /sitemap.xml).",
                 weight=1.5, recommendation="Generate sitemap.xml at build time and submit it in Google Search Console.")


def not_found_handling(site, cfg) -> Check:
    sf = site.soft404
    if sf.get("status") == 404:
        return Check("seo.soft404", S, "Missing pages return 404", 1.0, "A made-up URL correctly returns HTTP 404.")
    detail = " and serves the homepage" if sf.get("same_as_home") else ""
    return Check("seo.soft404", S, "Missing pages return 404", 0.0,
                 f"A made-up URL returns HTTP {sf.get('status')}{detail} (a \"soft 404\").", weight=2,
                 recommendation="Configure the host to return a real 404 status with a 404 page. Otherwise every typo URL, "
                                "robots.txt and sitemap.xml look like duplicate homepages to Google and AI crawlers.",
                 details=[sf.get("probe_url", "")])


def discoverability(site, cfg) -> Check:
    """Pages that exist but that no plain HTML link points to (e.g. menus built in JavaScript)."""
    if site.sitemap.get("valid") and not site.js_routes:
        return Check("seo.discover", S, "Pages discoverable through HTML links", 1.0,
                     f"Sitemap lists {site.sitemap['count']} URLs, so crawlers can find pages even if they aren't linked.",
                     weight=2)
    home = normalize(site.home.final_url)
    known = {normalize(p.final_url) for p in site.pages[1:] if p.status < 400} | {normalize(u) for u in site.js_routes}
    known.discard(home)
    hidden = sorted(u for u in known if u not in site.html_linked)
    sitemap_note = "" if site.sitemap.get("valid") else " There is no sitemap to make up for it."
    if not known:
        return Check("seo.discover", S, "Pages discoverable through HTML links", None, "No other pages found.")
    return Check("seo.discover", S, "Pages discoverable through HTML links", 1 - share(len(hidden), len(known)),
                 f"{len(known) - len(hidden)} of {len(known)} pages are reachable through plain HTML links.{sitemap_note}",
                 weight=2,
                 recommendation="Render the navigation menu as real <a href> links in the HTML (not only after JavaScript runs) "
                                "and publish a sitemap.xml, so search and AI crawlers can find every solution and industry page.",
                 details=[{"page not linked in HTML": path_of(u), "found via": "JS bundle" if u in {normalize(r) for r in site.js_routes} else "sitemap"}
                          for u in hidden])


def https(site, cfg) -> Check:
    ok = site.origin.startswith("https://")
    return Check("seo.https", S, "HTTPS", 1.0 if ok else 0.0, "Served over HTTPS." if ok else "Not served over HTTPS.",
                 recommendation="Redirect all HTTP traffic to HTTPS.")


def titles(site, cfg) -> Check:
    counts = Counter(p.title for p in site.pages)
    rows, good = [], 0
    for p in site.pages:
        n = len(p.title)
        issue = ("missing" if not n else "too short" if n < 30 else "too long" if n > 65 else
                 "duplicate" if counts[p.title] > 1 else "")
        good += not issue
        rows.append({"page": p.path, "title": p.title or "—", "length": n, "issue": issue})
    return Check("seo.titles", S, "Unique, descriptive titles", share(good, len(rows)),
                 f"{good} of {len(rows)} pages have a unique 30–65 character title.", weight=1.5,
                 recommendation="Lead each title with the page's keyword, e.g. \"Primary Keyword | Brand Name\".",
                 details=sorted(rows, key=lambda r: r["issue"] == ""))


def meta_descriptions(site, cfg) -> Check:
    counts = Counter(p.meta_description for p in site.pages)
    rows, good = [], 0
    for p in site.pages:
        n = len(p.meta_description)
        issue = ("missing" if not n else "too short" if n < 70 else "too long" if n > 160 else
                 "duplicate" if counts[p.meta_description] > 1 else "")
        good += not issue
        rows.append({"page": p.path, "description": p.meta_description[:160] or "—", "length": n, "issue": issue})
    return Check("seo.meta_desc", S, "Meta descriptions", share(good, len(rows)),
                 f"{good} of {len(rows)} pages have a unique 70–160 character description.",
                 recommendation="Write a one-sentence benefit + proof per page; it's the snippet people read in search.",
                 details=sorted(rows, key=lambda r: r["issue"] == ""))


def h1(site, cfg) -> Check:
    rows = [{"page": p.path, "H1": " | ".join(p.h1s) or "—", "count": len(p.h1s)} for p in site.pages]
    good = sum(1 for r in rows if r["count"] == 1)
    return Check("seo.h1", S, "One H1 per page", share(good, len(rows)), f"{good} of {len(rows)} pages have exactly one H1.",
                 recommendation="One H1 per page that states the topic in the words buyers search.",
                 details=sorted(rows, key=lambda r: r["count"] == 1))


def canonical(site, cfg) -> Check:
    rows = []
    for p in site.pages:
        state = "missing" if not p.canonical else "self" if normalize(p.canonical) == normalize(p.final_url) else "points elsewhere"
        rows.append({"page": p.path, "canonical": path_of(p.canonical) if p.canonical else "—", "state": state})
    good = sum(1 for r in rows if r["state"] != "missing")
    return Check("seo.canonical", S, "Canonical tags", share(good, len(rows)), f"{good} of {len(rows)} pages declare a canonical URL.",
                 recommendation="Add a self-referencing <link rel=\"canonical\"> to every page.",
                 details=sorted(rows, key=lambda r: r["state"] != "missing"))


def indexable(site, cfg) -> Check:
    blocked = [p.path for p in site.pages if "noindex" in p.meta_robots]
    return Check("seo.indexable", S, "Pages are indexable", 1 - share(len(blocked), len(site.pages)),
                 f"{len(blocked)} crawled pages carry noindex.", details=blocked,
                 recommendation="Remove noindex from pages you want found.")


def structured_data(site, cfg) -> Check:
    types = Counter(t for p in site.pages for t in p.schema_types)
    with_schema = sum(1 for p in site.pages if p.schema_types)
    s = share(with_schema, len(site.pages))
    return Check("seo.schema", S, "Structured data (schema.org)", s,
                 f"{with_schema} of {len(site.pages)} pages have JSON-LD; types: {', '.join(types) or 'none'}.", weight=1.5,
                 recommendation="Add Organization + WebSite sitewide, Product/Service on solution pages, Article on posts.",
                 details=[{"type": t, "pages": n} for t, n in types.most_common()])


def open_graph(site, cfg) -> Check:
    need = ("og:title", "og:description", "og:image")
    good = [p for p in site.pages if all(p.og.get(k) for k in need)]
    return Check("seo.og", S, "Social share tags (Open Graph)", share(len(good), len(site.pages)),
                 f"{len(good)} of {len(site.pages)} pages have og:title, og:description and og:image.", weight=0.5,
                 recommendation="Add Open Graph tags so LinkedIn shares show a proper card.",
                 details=[p.path for p in site.pages if p not in good])


def content_depth(site, cfg) -> Check:
    counts = [(p.path, p.word_count) for p in site.pages]
    med = median(c for _, c in counts)
    s = 1.0 if med >= 800 else 0.75 if med >= 450 else 0.4 if med >= 200 else 0.15
    return Check("seo.depth", S, "Content depth", s, f"Median {med:.0f} words of body text per page (nav/footer excluded).",
                 weight=1.5,
                 recommendation="Key solution pages need enough copy to answer how it works, who it's for, cost and proof (≈600–1,200 words).",
                 details=[{"page": path, "words": n} for path, n in sorted(counts, key=lambda x: x[1])])


def internal_linking(site, cfg) -> Check:
    linked_to = Counter(normalize(l.url) for p in site.pages for l in p.links if l.internal and not l.in_nav)
    per_page = [(p.path, sum(1 for l in p.links if l.internal and not l.in_nav)) for p in site.pages]
    weak = [path for path, n in per_page if n < 3]
    s = 1 - share(len(weak), len(per_page))
    return Check("seo.internal_links", S, "In-content internal links", s,
                 f"{len(weak)} of {len(per_page)} pages have fewer than 3 internal links outside the nav/header.",
                 recommendation="Link solution pages to each other, to case studies and to the demo page in the body copy.",
                 details=[{"page": path, "body links out": n, "body links in": linked_to.get(normalize(site.origin + path), 0)}
                          for path, n in sorted(per_page, key=lambda x: x[1])])


def keyword_coverage(site, cfg) -> Check:
    rows, covered = [], 0
    for kw in cfg["keywords"]:
        kt = tokens(kw)
        best, best_where, best_score = "—", "not found", 0
        for p in site.pages:
            where = []
            if kt <= tokens(p.title):
                where.append("title")
            if any(kt <= tokens(t) for lvl, t in p.headings if lvl == 1):
                where.append("H1")
            if any(kt <= tokens(t) for lvl, t in p.headings if lvl > 1):
                where.append("subheading")
            body_hits = len(re.findall(re.escape(kw.lower()), p.text.lower()))
            if body_hits:
                where.append(f"body ×{body_hits}")
            score = 3 * ("title" in where) + 3 * ("H1" in where) + 2 * ("subheading" in where) + min(body_hits, 3)
            if score > best_score:
                best, best_where, best_score = p.path, ", ".join(where), score
        covered += best_score >= 3
        rows.append({"keyword": kw, "best page": best, "appears in": best_where})
    return Check("seo.keywords", S, "Target keyword coverage", share(covered, len(rows)),
                 f"{covered} of {len(rows)} target keywords appear in a title or heading.", weight=2,
                 recommendation="Give each priority keyword a page that uses it in the title, H1 and first paragraph.",
                 details=rows)


def _parse_date(s: str):
    try:
        d = datetime.fromisoformat(s.strip().replace("Z", "+00:00")[:25])
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
        return datetime(int(m[1]), int(m[2]), int(m[3]), tzinfo=timezone.utc) if m else None


def freshness(site, cfg) -> Check:
    dates = [d for d in (_parse_date(s) for s in site.sitemap.get("lastmods", []) + [x for p in site.pages for x in p.dates]) if d]
    if not dates:
        return Check("seo.freshness", S, "Content freshness", 0.3, "No publish/update dates found in the sitemap or pages.",
                     recommendation="Show and mark up \"last updated\" dates; publish on a regular cadence.")
    now = datetime.now(timezone.utc)
    recent = sum(1 for d in dates if now - d < timedelta(days=90))
    newest = max(dates)
    s = 1.0 if now - newest < timedelta(days=30) else 0.7 if now - newest < timedelta(days=120) else 0.35
    return Check("seo.freshness", S, "Content freshness", s,
                 f"Newest date {newest:%Y-%m-%d}; {recent} dated URLs/pages from the last 90 days.",
                 recommendation="Publish or refresh at least a couple of pages a month.")


def content_types(site, cfg) -> Check:
    urls = [path_of(u).lower() for u in site.sitemap.get("urls", [])] + [p.path.lower() for p in site.pages] + \
           [path_of(l.url).lower() for p in site.pages for l in p.links if l.internal]
    kinds = {
        "blog / articles": r"/(blog|news|articles?|insights)\b",
        "resources / guides": r"/(resources?|guides?|ebooks?|whitepapers?|learn)\b",
        "case studies": r"case-stud|customer|success",
        "FAQ": r"faq",
        "industry pages": r"/(industr|sectors?|who-we-serve)",
        "pricing / ROI": r"pricing|roi|calculator|savings",
    }
    found = {k: any(re.search(rx, u) for u in urls) for k, rx in kinds.items()}
    return Check("seo.content_types", S, "Content types", sum(found.values()) / len(found),
                 f"{sum(found.values())} of {len(found)} content types present.",
                 recommendation="Add the missing types; case studies and an ROI calculator are the highest-intent.",
                 details=[{"type": k, "present": "yes" if v else "no"} for k, v in found.items()])


def broken_links(site, cfg) -> Check:
    n = len(site.broken_links)
    caveat = " (this site answers every URL with 200, so broken links can't be detected)" if site.soft404.get("status") == 200 else ""
    return Check("seo.broken", S, "Broken internal links", 1.0 if n == 0 else max(0.0, 1 - n / 10),
                 f"{n} broken of {site.links_checked} internal URLs checked{caveat}.",
                 recommendation="Fix or redirect the broken URLs.",
                 details=[{"url": u, "status": s} for u, s in site.broken_links])


def lighthouse_seo(site, cfg) -> Check:
    psi = site.psi
    if not psi or "error" in psi:
        return Check("seo.lh_seo", S, "SEO score (Lighthouse)", None, "PageSpeed Insights not available.")
    v = psi["categories"].get("seo", 0)
    return Check("seo.lh_seo", S, "SEO score (Lighthouse)", v / 100, f"Lighthouse SEO {v}/100 on the homepage.", weight=0.5)


def run(site, cfg) -> list[Check]:
    return [f(site, cfg) for f in (robots_txt, sitemap, not_found_handling, discoverability, https, titles, meta_descriptions, h1,
                                   canonical, indexable, structured_data, open_graph, content_depth, internal_linking,
                                   keyword_coverage, freshness, content_types, broken_links, lighthouse_seo)]
