"""Field-weighted class TF-IDF: which 1–3 word phrases each site emphasizes.

Each site's crawled pages form one "class" document. A phrase scores high for a site when
that site uses it prominently (titles and URLs count most) and the other sites don't.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from .checks.common import STOPWORDS, stem
from .page import path_of

FIELD_WEIGHTS = {"title": 5.0, "url": 5.0, "h1": 3.0, "subheading": 2.0, "anchor": 2.0, "body": 1.0}
EXTRA_STOP = set("""also all any been but get got has have here into its just more most much new not now
one only other out over per same see such than then there these they those through too two under up use used
using very via was were well while who whose would yes about after again against because before being below
between both down during each few further having itself let off once own same some until www com http https
html amp nbsp inc llc contact learn read click today blog""".split())
STOP = STOPWORDS | EXTRA_STOP


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z][a-z0-9'-]*[a-z0-9]|[a-z]", text.lower().replace("’", "'"))


def ngrams(text: str, n_max: int = 3) -> list[str]:
    """Phrases of 1–3 words that don't start or end with a stopword and don't cross punctuation."""
    out = []
    for chunk in re.split(r"[.!?;:,()\[\]|/•–—\"]+", text):
        toks = _tokens(chunk)
        for n in range(1, n_max + 1):
            for i in range(len(toks) - n + 1):
                gram = toks[i:i + n]
                if gram[0] in STOP or gram[-1] in STOP or any(len(t) < 3 for t in (gram[0], gram[-1])):
                    continue
                if n == 1 and (gram[0] in STOP or len(gram[0]) < 4):
                    continue
                out.append(" ".join(gram))
    return out


def canonical(phrase: str) -> str:
    """Merge plural/tense variants: 'demand forecasts' and 'demand forecast' share a key."""
    return " ".join(stem(w) for w in phrase.split())


def site_field_counts(site) -> tuple[Counter, dict]:
    """Weighted phrase counts for one site, plus the most common surface form per key."""
    weighted: Counter = Counter()
    surface: dict[str, Counter] = defaultdict(Counter)

    def add(text: str, field: str) -> None:
        w = FIELD_WEIGHTS[field]
        for g in ngrams(text):
            key = canonical(g)
            weighted[key] += w
            surface[key][g] += 1

    for p in site.pages:
        add(p.title, "title")
        add(path_of(p.final_url).replace("-", " ").replace("/", " . "), "url")
        for level, text in p.headings:
            add(text, "h1" if level == 1 else "subheading")
        for l in p.links:
            if l.internal and not l.in_nav:
                add(l.text, "anchor")
        for para in p.paragraphs:
            add(para, "body")
    return weighted, {k: v.most_common(1)[0][0] for k, v in surface.items()}


def class_tfidf(sites: list, min_weight: float = 4.0) -> dict:
    """Returns {site_name: {key: {"phrase", "score", "weight", "share"}}} across all sites."""
    counts, surfaces = {}, {}
    for s in sites:
        counts[s.name], surfaces[s.name] = site_field_counts(s)
    total_by_term: Counter = Counter()
    for c in counts.values():
        total_by_term.update(c)
    avg_len = sum(sum(c.values()) for c in counts.values()) / max(1, len(counts))
    out = {}
    for name, c in counts.items():
        size = sum(c.values()) or 1
        rows = {}
        for key, w in c.items():
            if w < min_weight:
                continue
            tf = w / size
            idf = math.log(1 + avg_len / total_by_term[key])
            rows[key] = {"phrase": surfaces[name][key], "score": tf * idf * 1000, "weight": round(w, 1),
                         "share": round(w / total_by_term[key], 3)}
        out[name] = rows
    return out
