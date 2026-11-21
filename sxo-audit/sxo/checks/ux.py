"""UX checks: speed, mobile, accessibility, clarity, conversion and trust."""
from __future__ import annotations

import re
from statistics import mean

from ..page import VAGUE_LINK_PATTERN, path_of, words
from .common import Check, flesch, pct, share

S = "UX"


def lighthouse_performance(site, cfg) -> Check:
    psi = site.psi
    if not psi or "error" in psi:
        reason = psi.get("error", "skipped") if psi else "skipped"
        return Check("ux.performance", S, "Mobile performance (Lighthouse)", None,
                     f"PageSpeed Insights not available ({reason}). Set a free PSI_API_KEY to raise the quota.")
    perf = psi["categories"].get("performance", 0)
    rows = [{"metric": k.replace("-", " "), "value": v} for k, v in psi["lab"].items()]
    rows += [{"metric": f"real users: {k.lower().replace('_', ' ')}", "value": v} for k, v in psi["field"].items()]
    return Check("ux.performance", S, "Mobile performance (Lighthouse)", perf / 100,
                 f"Lighthouse mobile performance {perf}/100 on the homepage.", weight=2,
                 recommendation="Compress and lazy-load large images, cut unused JavaScript, and size images to their display slot.",
                 details=rows)


def lighthouse_accessibility(site, cfg) -> Check:
    psi = site.psi
    if not psi or "error" in psi:
        return Check("ux.lh_a11y", S, "Accessibility score (Lighthouse)", None, "PageSpeed Insights not available.")
    score = psi["categories"].get("accessibility", 0)
    return Check("ux.lh_a11y", S, "Accessibility score (Lighthouse)", score / 100,
                 f"Lighthouse accessibility {score}/100 on the homepage.",
                 recommendation="Open the homepage in PageSpeed Insights and fix the listed contrast, label and name issues.")


def mobile_viewport(site, cfg) -> Check:
    ok = [p for p in site.pages if "width=device-width" in p.viewport.replace(" ", "")]
    s = share(len(ok), len(site.pages))
    return Check("ux.viewport", S, "Mobile viewport set", s,
                 f"{len(ok)} of {len(site.pages)} pages declare a responsive viewport.",
                 recommendation="Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> to every page.",
                 details=[p.path for p in site.pages if p not in ok])


def alt_text(site, cfg) -> Check:
    seen: dict[str, dict] = {}
    for p in site.pages:
        for img in p.images:
            if img.src not in seen:
                seen[img.src] = {"image": img.src.rsplit("/", 1)[-1][:80], "alt text": img.alt, "first seen on": p.path}
    rows = list(seen.values())
    described = [r for r in rows if r["alt text"]]
    empty = [r for r in rows if r["alt text"] == ""]
    missing = [r for r in rows if r["alt text"] is None]
    for r in rows:
        r["alt text"] = "— missing —" if r["alt text"] is None else (r["alt text"] or "(empty: decorative)")
    rows.sort(key=lambda r: (r["alt text"] != "— missing —", r["alt text"] != "(empty: decorative)"))
    s = share(len(described), len(rows))
    return Check("ux.alt_text", S, "Images have alt text", s,
                 f"{len(described)} of {len(rows)} unique images have alt text; {len(missing)} missing, {len(empty)} empty.",
                 weight=1.5,
                 recommendation="Describe every meaningful image, especially charts and cost graphics, e.g. "
                                "alt=\"Dashboard showing current fill level at 72%\". Leave alt=\"\" only on decoration.",
                 details=rows)


def hero_cta(site, cfg) -> Check:
    home = site.home
    first_screen = home.cta_before_h2
    return Check("ux.hero_cta", S, "Call to action in the first screen", 1.0 if first_screen else (0.5 if home.nav_ctas else 0.0),
                 ("A CTA appears before the first section heading." if first_screen else
                  "No CTA before the first section heading" + (" (only in the nav)." if home.nav_ctas else ".")),
                 weight=1.5,
                 recommendation="Put one specific primary CTA (e.g. \"See your savings\") in the hero, next to the headline.",
                 details=[f"Hero/body CTAs: {', '.join(dict.fromkeys(home.ctas)) or 'none'}",
                          f"Nav CTAs: {', '.join(dict.fromkeys(home.nav_ctas)) or 'none'}"])


def cta_coverage(site, cfg) -> Check:
    with_cta = [p for p in site.pages if p.ctas]
    s = share(len(with_cta), len(site.pages))
    return Check("ux.cta_coverage", S, "Pages with a call to action", s,
                 f"{len(with_cta)} of {len(site.pages)} pages have a CTA in the page body.",
                 recommendation="End every solution and industry page with a next step that matches it.",
                 details=[{"page": p.path, "CTAs": ", ".join(dict.fromkeys(p.ctas))[:120] or "none"} for p in site.pages])


def vague_links(site, cfg) -> Check:
    rows, seen = [], set()
    total = 0
    for p in site.pages:
        for l in p.links:
            total += 1
            if VAGUE_LINK_PATTERN.match(l.text.strip()) and (p.path, l.url) not in seen:
                seen.add((p.path, l.url))
                rows.append({"link text": l.text, "goes to": path_of(l.url) if l.internal else l.url, "on page": p.path})
    s = 1.0 if not rows else max(0.0, 1 - len(rows) / 15)
    return Check("ux.vague_links", S, "Descriptive link and button text", s,
                 f"{len(rows)} vague links (\"Learn more\", \"Read more\"...) across crawled pages.",
                 recommendation="Say where the link goes: \"Learn more\" → \"See how the monitoring works\". "
                                "Helps users, screen readers and search engines.",
                 details=rows)


def nav_map(site, cfg) -> Check:
    rows, seen = [], set()
    for l in site.home.links:
        if not (l.in_nav and l.internal) or l.url in seen or not l.text:
            continue
        seen.add(l.url)
        label = {w.lower() for w in words(l.text) if len(w) > 3}
        path = path_of(l.url).lower()
        mismatch = bool(label) and path != "/" and not any(w[:5] in path for w in label)
        rows.append({"label": l.text[:60], "goes to": path_of(l.url), "check": "review: label not in URL" if mismatch else ""})
    flagged = sum(1 for r in rows if r["check"])
    return Check("ux.nav_map", S, "Navigation map", None,
                 f"{len(rows)} nav links on the homepage; {flagged} where the label and URL don't share a word.",
                 recommendation="Make each nav label lead to a page whose URL and H1 use the same words.",
                 details=rows)


def forms(site, cfg) -> Check:
    all_forms = [(p.path, f) for p in site.pages for f in p.forms if f.fields > 0]
    if not all_forms:
        return Check("ux.forms", S, "Short lead forms", 0.5,
                     "No HTML forms found on crawled pages (could be an embedded widget or a separate page).",
                     recommendation="Make sure a short contact/demo form is one click from every page.")
    avg = mean(f.fields for _, f in all_forms)
    s = 1.0 if avg <= 4 else 0.7 if avg <= 7 else 0.4
    return Check("ux.forms", S, "Short lead forms", s,
                 f"{len(all_forms)} forms, {avg:.1f} fields on average.",
                 recommendation="Ask only what sales needs for the first call (name, email, company, number of sites).",
                 details=[{"page": path, "fields": f.fields, "labeled": f.labeled} for path, f in all_forms])


def trust_signals(site, cfg) -> Check:
    text = " ".join(p.text for p in site.pages).lower()
    own = re.sub(r"[^a-z]", "", site.name.lower().split()[0])
    logos = {i.src for p in site.pages for i in p.images
             if "logo" in (i.src + (i.alt or "")).lower() and own not in i.src.rsplit("/", 1)[-1].lower()}
    found = {
        "client logos (3+)": len(logos) >= 3,
        "testimonials / quotes": any(p.blockquote_count for p in site.pages) or "testimonial" in text or "“" in text,
        "case studies": bool(re.search(r"case stud|customer stor|success stor", text)),
        "quantified results": len(re.findall(r"\d+(?:\.\d+)?\s?%|\$\s?\d", text)) >= 3,
        "security / certifications": bool(re.search(r"soc ?2|iso ?\d{4}|ul listed|gdpr|certified", text)),
    }
    s = sum(found.values()) / len(found)
    return Check("ux.trust", S, "Trust signals", s,
                 f"{sum(found.values())} of {len(found)} trust signal types found ({len(logos)} logo images).",
                 weight=1.5,
                 recommendation="Pair client logos with a named quote and one hard number (e.g. \"cut pickups X% at <client>\").",
                 details=[{"signal": k, "found": "yes" if v else "no"} for k, v in found.items()])


def readability(site, cfg) -> Check:
    # Bullets rarely end in a period; treat each paragraph or list item as its own sentence.
    scores = [(p.path, flesch(" ".join(t if t[-1] in ".!?" else t + "." for t in p.paragraphs))) for p in site.pages]
    scored = [(path, s) for path, s in scores if s is not None]
    if not scored:
        return Check("ux.readability", S, "Readability", None, "Not enough paragraph text to score.")
    avg = mean(s for _, s in scored)
    s = 1.0 if avg >= 50 else 0.75 if avg >= 30 else 0.45
    return Check("ux.readability", S, "Readability", s,
                 f"Average Flesch reading ease {avg:.0f} (50+ is easy for busy buyers; B2B sites often sit at 30–50).",
                 recommendation="Shorter sentences, plain words, one idea per bullet.",
                 details=[{"page": path, "reading ease": round(v)} for path, v in sorted(scored, key=lambda x: x[1])])


def accessibility_basics(site, cfg) -> Check:
    home = site.home
    unnamed = [(p.path, l.url) for p in site.pages for l in p.links if not l.text]
    fields = [f for p in site.pages for f in p.forms]
    total_fields = sum(f.fields for f in fields)
    skips = []
    for p in site.pages:
        prev = 0
        for level, text in p.headings:
            if prev and level > prev + 1:
                skips.append({"page": p.path, "jump": f"H{prev} → H{level}", "heading": text[:60]})
            prev = level
    parts = {
        "page language set": 1.0 if home.lang else 0.0,
        "links have names": 1.0 if not unnamed else max(0.0, 1 - len(unnamed) / 20),
        "form fields labeled": 1.0 if not total_fields else sum(f.labeled for f in fields) / total_fields,
        "no skipped heading levels": 1.0 if not skips else max(0.0, 1 - len(skips) / 10),
    }
    s = mean(parts.values())
    rows = [{"item": k, "score": pct(v)} for k, v in parts.items()]
    rows += [{"item": f"unnamed link on {path}", "score": url[:80]} for path, url in unnamed[:20]]
    rows += [{"item": f"heading skip on {r['page']}", "score": f"{r['jump']}: {r['heading']}"} for r in skips[:20]]
    return Check("ux.a11y", S, "Accessibility basics", s,
                 f"{len(unnamed)} links with no text, {len(skips)} heading-level skips, lang=\"{home.lang or 'missing'}\".",
                 recommendation="Give icon links an aria-label, label every form field, keep headings in order.",
                 details=rows)


def page_weight(site, cfg) -> Check:
    home = site.home
    kb = home.size / 1024
    s = 1.0 if home.script_count <= 20 and kb <= 150 else 0.7 if home.script_count <= 40 and kb <= 400 else 0.4
    return Check("ux.weight", S, "Homepage HTML weight", s,
                 f"{kb:.0f} KB of HTML, {home.script_count} external scripts, {len(home.images)} images; "
                 f"server responded in {home.elapsed:.2f}s.",
                 weight=0.5,
                 recommendation="Drop unused tag-manager scripts and widgets.")


def run(site, cfg) -> list[Check]:
    return [f(site, cfg) for f in (lighthouse_performance, lighthouse_accessibility, mobile_viewport, alt_text,
                                   hero_cta, cta_coverage, vague_links, nav_map, forms, trust_signals,
                                   readability, accessibility_basics, page_weight)]
