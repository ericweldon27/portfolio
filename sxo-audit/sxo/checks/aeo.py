"""AEO checks: can AI answer engines reach, understand, trust and quote the site?"""
from __future__ import annotations

import re

from ..page import host_key, path_of
from .common import Check, share, tokens

S = "AEO"
ANSWER_SCHEMA = {"FAQPage", "HowTo", "QAPage", "Article", "BlogPosting", "NewsArticle", "TechArticle",
                 "Product", "Service", "Review", "AggregateRating"}
AI_ONLY = ["GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "PerplexityBot",
           "Google-Extended", "Applebot-Extended", "CCBot"]


def ai_crawler_access(site, cfg) -> Check:
    allowed = [b for b in AI_ONLY if site.ai_bots.get(b)]
    explicit = site.robots.get("valid") and any(b.lower() in site.robots.get("text", "").lower() for b in AI_ONLY)
    s = share(len(allowed), len(AI_ONLY))
    note = "" if site.robots.get("valid") else " (no robots.txt, so allowed by default)"
    return Check("aeo.ai_bots", S, "AI crawlers allowed", s,
                 f"{len(allowed)} of {len(AI_ONLY)} AI crawlers allowed{note}; "
                 f"{'has' if explicit else 'no'} explicit AI-bot rules.", weight=2,
                 recommendation="Allow the AI search crawlers (OAI-SearchBot, ClaudeBot, PerplexityBot, Google-Extended) "
                                "in robots.txt so answer engines can read and cite you.",
                 details=[{"crawler": b, "allowed": "yes" if site.ai_bots.get(b) else "BLOCKED"} for b in AI_ONLY])


def llms_txt(site, cfg) -> Check:
    ok = site.llms_txt.get("valid")
    return Check("aeo.llms_txt", S, "llms.txt file", 1.0 if ok else 0.0,
                 f"llms.txt present ({site.llms_txt['bytes']} bytes)." if ok else
                 f"No llms.txt (HTTP {site.llms_txt.get('status')}{', served HTML' if site.llms_txt.get('status') == 200 else ''}).",
                 weight=0.5,
                 recommendation="Add /llms.txt: a short plain-text summary of what the company does with links to key pages. "
                                "It's an emerging convention that costs minutes to add.")


def raw_html_content(site, cfg) -> Check:
    thin = [(p.path, p.word_count) for p in site.pages if p.word_count < 150]
    s = 1 - share(len(thin), len(site.pages))
    return Check("aeo.raw_html", S, "Content readable without JavaScript", s,
                 f"{len(site.pages) - len(thin)} of {len(site.pages)} pages have 150+ words in the raw HTML. "
                 "Most AI crawlers don't run JavaScript.", weight=1.5,
                 recommendation="Server-render or pre-render page copy so it's in the HTML, not injected by scripts.",
                 details=[{"page": path, "raw-HTML words": n} for path, n in thin])


def question_headings(site, cfg) -> Check:
    qs = [(p.path, q) for p in site.pages for q in p.questions]
    n = len(qs)
    s = 1.0 if n >= 12 else 0.75 if n >= 6 else 0.4 if n >= 2 else 0.0
    return Check("aeo.questions", S, "Question-style headings", s,
                 f"{n} headings phrased as questions across {len(site.pages)} pages.", weight=1.5,
                 recommendation="Turn key sections into the questions buyers ask: \"How does the product work?\"",
                 details=[{"page": path, "question": q.question} for path, q in qs])


def direct_answers(site, cfg) -> Check:
    qs = [(p.path, q) for p in site.pages for q in p.questions]
    if not qs:
        return Check("aeo.answers", S, "Short direct answers under questions", 0.0,
                     "No question headings, so no answer blocks to evaluate.", weight=1.5,
                     recommendation="Under each question heading, answer in 40–60 words first, then expand.")
    good = [(path, q) for path, q in qs if 25 <= q.answer_words <= 90]
    return Check("aeo.answers", S, "Short direct answers under questions", share(len(good), len(qs)),
                 f"{len(good)} of {len(qs)} question headings are followed by a 25–90 word answer.", weight=1.5,
                 recommendation="Lead with the answer in one short paragraph; answer engines lift that paragraph verbatim.",
                 details=[{"question": q.question[:80], "answer words": q.answer_words, "answer starts": q.answer[:120]}
                          for _, q in qs])


def structured_content(site, cfg) -> Check:
    lists = sum(p.list_count for p in site.pages)
    tables = sum(p.table_count for p in site.pages)
    per_page = lists / max(1, len(site.pages))
    s = min(1.0, per_page / 3) * (0.8 if tables == 0 else 1.0)
    return Check("aeo.structure", S, "Lists and tables", s,
                 f"{lists} lists and {tables} tables in body content ({per_page:.1f} lists per page).",
                 recommendation="Use comparison tables (e.g. measured vs. estimated fill-level) and step lists; "
                                "answer engines quote them readily.")


def answer_schema(site, cfg) -> Check:
    found = sorted({t for p in site.pages for t in p.schema_types if t in ANSWER_SCHEMA})
    s = min(1.0, len(found) / 3)
    return Check("aeo.schema", S, "Answer-friendly schema", s,
                 f"Answer-type schema found: {', '.join(found) or 'none'}.", weight=1.5,
                 recommendation="Mark up FAQs with FAQPage, solutions with Product/Service, and posts with Article (with author and dates).",
                 details=[{"page": p.path, "types": ", ".join(p.schema_types) or "—"} for p in site.pages])


def entity_clarity(site, cfg) -> Check:
    orgs = [i for p in site.pages for i in p.jsonld if "Organization" in str(i.get("@type", "")) or
            str(i.get("@type", "")) in ("Corporation", "LocalBusiness")]
    org = orgs[0] if orgs else {}
    same_as = org.get("sameAs", [])
    same_as = [same_as] if isinstance(same_as, str) else same_as
    text = " ".join(p.text for p in site.pages)
    has_about = any(re.search(r"/(about|company|who-we-are|team)", path_of(l.url)) for p in site.pages for l in p.links if l.internal)
    social = {host_key(l.url) for p in site.pages for l in p.links
              if re.search(r"linkedin|youtube|twitter|x\.com|facebook|instagram|crunchbase", l.url)}
    parts = {
        "Organization schema": bool(org),
        "schema has logo + url": bool(org.get("logo") and org.get("url")),
        "sameAs profile links (2+)": len(same_as) >= 2,
        "about/company page": has_about,
        "contact details on site": bool(re.search(r"@[a-z0-9-]+\.[a-z]{2,}|\(\d{3}\)\s?\d{3}-\d{4}|\d{3}[-.]\d{3}[-.]\d{4}", text)),
        "social profiles linked": bool(social),
    }
    return Check("aeo.entity", S, "Brand entity clarity", sum(parts.values()) / len(parts),
                 f"{sum(parts.values())} of {len(parts)} entity signals present.", weight=1.5,
                 recommendation="Add Organization JSON-LD with name, logo, url, and sameAs links to LinkedIn, Crunchbase, etc., "
                                "so AI models resolve the brand name to one clear company.",
                 details=[{"signal": k, "present": "yes" if v else "no"} for k, v in parts.items()] +
                         [{"signal": "sameAs", "present": ", ".join(same_as) or "—"}])


def expertise_signals(site, cfg) -> Check:
    authors = sorted({a for p in site.pages for a in p.authors if a})
    dated = sum(1 for p in site.pages if p.dates)
    external = [l.url for p in site.pages for l in p.links if not l.internal]
    citations = [u for u in external if re.search(r"\.gov\b|\.edu\b|doi\.org|ncbi|epa\.|researchgate|\.org/", u)]
    parts = {
        "named authors": bool(authors),
        "dated pages (25%+)": dated >= len(site.pages) / 4,
        "cites authoritative sources": len(citations) >= 2,
    }
    return Check("aeo.eeat", S, "Expertise and trust (E-E-A-T)", sum(parts.values()) / len(parts),
                 f"{len(authors)} named authors, {dated} dated pages, {len(citations)} citations to authoritative sources.",
                 weight=1.5,
                 recommendation="Put a named expert byline and bio on guides, date them, and cite sources (EPA, tipping-fee data, research).",
                 details=[{"signal": k, "present": "yes" if v else "no"} for k, v in parts.items()] +
                         [{"signal": "authors", "present": ", ".join(authors[:10]) or "—"}] +
                         [{"signal": "citation", "present": u} for u in sorted(set(citations))[:15]])


def citable_facts(site, cfg) -> Check:
    stats = []
    for p in site.pages:
        for para in p.paragraphs:
            if re.search(r"\d+(?:\.\d+)?\s?%|\$\s?\d[\d,]*|\b\d[\d,]{2,}\s(?:tons|units|hours|customers|sites)", para):
                stats.append({"page": p.path, "statement": para[:160]})
    n = len(stats)
    s = 1.0 if n >= 10 else 0.7 if n >= 5 else 0.35 if n >= 1 else 0.0
    return Check("aeo.facts", S, "Quotable facts and numbers", s,
                 f"{n} paragraphs contain a specific number, cost or percentage.", weight=1.5,
                 recommendation="State concrete numbers in plain sentences (\"Pickups cost $600–$900 each\"); "
                                "answer engines prefer citing specific, attributable facts.",
                 details=stats)


def question_coverage(site, cfg) -> Check:
    rows, covered = [], 0
    for q in cfg["questions"]:
        qt = tokens(q)
        best = ("—", 0.0, "")
        for p in site.pages:
            body = len(qt & tokens(p.text)) / len(qt)
            heads = [p.title] + [t for _, t in p.headings]
            head_score, head_text = max(((len(qt & tokens(h)) / len(qt), h) for h in heads), default=(0.0, ""))
            score = 0.6 * head_score + 0.4 * body
            if score > best[1]:
                best = (p.path, score, head_text)
        covered += best[1] >= 0.55
        rows.append({"question": q, "best page": best[0], "match": f"{round(best[1] * 100)}%", "closest heading": best[2][:80]})
    return Check("aeo.coverage", S, "Answers our buyers' questions", share(covered, len(rows)),
                 f"{covered} of {len(rows)} target questions have a page that clearly addresses them (55%+ match).", weight=2.5,
                 recommendation="Create one focused section or page per buyer question, with the question as a heading.",
                 details=rows)


def share_of_voice(site, cfg) -> Check:
    return Check("aeo.sov", S, "AI share of voice", None,
                 "Not measured yet. Next step: ask the target questions in ChatGPT, Perplexity, Gemini and Claude, "
                 "and record which brands are named or cited.")


def run(site, cfg) -> list[Check]:
    return [f(site, cfg) for f in (ai_crawler_access, llms_txt, raw_html_content, question_headings, direct_answers,
                                   structured_content, answer_schema, entity_clarity, expertise_signals,
                                   citable_facts, question_coverage, share_of_voice)]
