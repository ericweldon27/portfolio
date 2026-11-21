# SXO Audit — UX, SEO and AEO in one pass

Benchmarks a website against its competitors on three things at once: whether people can use it, whether search engines can rank it, and whether AI answer engines can cite it. Then it turns the gaps into a prioritised content plan with a brief per piece, and checks finished drafts back against those briefs.

Everything runs on free data sources. I built it because the commercial equivalent is roughly $400 to $700 a month across three or four tools, and because none of them had caught up on the answer-engine side.

---

## What it checks

| Section | Checks |
|---|---|
| **UX** | Lighthouse performance and accessibility, viewport, alt text, hero CTA, CTA coverage, vague link text, nav map, form length, trust signals, readability, accessibility basics, page weight |
| **SEO** | robots.txt, sitemap, real 404s, discoverability without JavaScript, HTTPS, titles, meta descriptions, H1, canonicals, noindex, schema, Open Graph, content depth, internal links, keyword coverage, freshness, content types, broken links |
| **AEO** | AI crawler access, `llms.txt`, content present in raw HTML, question headings, short direct answers, lists and tables, answer schema, brand entity clarity, E-E-A-T signals, quotable facts, buyer-question coverage |

## Keyword ownership

Rather than asking "how hard is this keyword," it asks "is this keyword worth *us* owning."

- **Distinctive phrases:** class TF-IDF across each site's pages, weighted by title and URL (5x), H1 (3x), subheadings and link text (2x), body (1x).
- **Demand:** Google Autocomplete. A relative signal, not search volume, and reported as such.
- **Ranking:** search results, top 20. A tracked site in the top 10 means *ours*, *theirs* or *contested*; nobody tracked in the top 10 means an *open gap*.
- **Fit:** overlap with your stated differentiators, discounted when the keyword names none of your product terms.
- **Opportunity** = √demand × fit × beatability.

Labels are *ours*, *open*, *fight for*, *not winnable*, *not worth it*, *not checked*. The line between "fight for" and "not winnable" is a judgment against your own advantages, not a formula.

## Briefs and draft checks

Each run writes a content brief per planned piece. Export a finished draft to `drafts/<slug>.md` and the next run checks it against its brief: keyword placement, answer-first structure, question headings, FAQ, length, links, whether every number traces to a confirmed fact, absolute claims, and em dashes.

## Judgment where matching fails

Fit by meaning, searcher intent, funnel stage and review aspects need reading, not string matching. A run writes unanswered items to a queue; they get judged once, cached, and reused on later runs. Unjudged items fall back to heuristics.

---

## Running it

```bash
pip install -r requirements.txt
cp config.example.json config.json      # then edit: your site, competitors, keywords, differentiators
cp .env.example .env                    # then add your own API keys
python3 run.py
```

Useful flags:

```bash
python3 run.py --no-pagespeed    # skip Lighthouse checks, much faster
python3 run.py --no-serp         # use cached rankings only, no new searches
python3 run.py --max-pages 10    # smaller crawl
python3 run.py --fresh           # ignore the page cache and re-crawl
```

Output lands in `output/<date_time>/`:
- `dashboard.html` — a single self-contained file, open it in any browser
- `results.json` — every check's raw evidence

### Keys you supply

Nothing is bundled. `.env.example` lists what to provide and where to get it:

| Variable | Used for | Cost |
|---|---|---|
| `BRAVE_API_KEY` | Ranking data in the keyword module | Free tier available |
| `PSI_API_KEY` | Lighthouse performance and accessibility | Free from Google Cloud |
| `SXO_CONTACT_URL` | Contact URL in the crawler's User-Agent | None |

Every search you run bills to your own key, not mine. Results are cached in `output/cache/`, so re-runs cost nothing, rankings older than 30 days are refreshed within each run's budget, and crawled pages are reused for 7 days.

### Crawling politely

One request per second per host, the crawler identifies itself in its User-Agent with a contact URL you set, and it respects robots.txt. Sites that block automated readers are reported rather than worked around.

---

## What is not in this repo

My own `config.json`, `brief.json`, run output, drafts and competitor research are excluded, because they hold a real company's keyword strategy, competitive findings and customer information. `config.example.json` is a fictional substitute so the tool runs out of the box. The export module that formatted findings for my own writing is also excluded for the same reason.

## Limits worth knowing

- **No backlink or domain authority data.** That is a real hole in competitive SEO, and the tools that have it have spent a decade building the index.
- **Autocomplete is a demand proxy**, not search volume. It ranks keywords against each other and nothing more.
- **The opportunity formula is a heuristic.** It has not been calibrated against whether the pages it prioritised actually ranked.
- **Crawl scale is modest.** Capped page counts and polite pacing, not a hundred-thousand-URL enterprise crawl with JavaScript rendering.
- **Trends data is brittle.** The unofficial Google Trends client breaks from time to time.

## How this was built

I specified it, designed the scoring logic and decided what each check measures. AI coding tools wrote most of the code. I would rather say that plainly than imply I hand-wrote it.
