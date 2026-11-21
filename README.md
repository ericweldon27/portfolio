# Marketing Analytics & Internal Tools

Work from my MBA in Marketing and Data Science at Santa Clara University, plus the internal tools I build and run as a B2B demand generation and growth marketer.

Everything here starts from a marketing question, not a modeling exercise. The analysis exists to support a spending or targeting decision, and each piece ends with the recommendation I'd actually make.

These are here because I'd rather build the segmentation, the attribution and the competitive research myself than file a ticket for them.

---

## 1. Predicting Purchase Intent from Session Behavior

**Question:** Which website sessions are likely to end in a purchase, and which behavioral signals identify them early enough to act on?

**Data:** [UCI Online Shoppers Purchasing Intention dataset](https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset) — ~12,330 e-commerce sessions with page-type counts, time-on-page, bounce and exit rates, Google Analytics page values, traffic source, visitor type, and proximity to special days. The target class is heavily imbalanced, which drives most of the modeling decisions below.

**Approach:**
- Preprocessing pipeline with `make_column_transformer` — imputation, scaling for numeric features, one-hot encoding for categoricals
- Compared a **Gradient Boosting Classifier** and a **Multi-layer Perceptron (MLP)**
- Hyperparameter tuning via `GridSearchCV`
- Evaluated on **balanced accuracy and ROC AUC** rather than raw accuracy, since a model that predicts "no purchase" every time scores well on accuracy alone and is useless

**Results:** Best model reached **0.83 accuracy, 0.83 balanced accuracy, and 0.83 ROC AUC** on held-out data. Confusion matrices, ROC curves, and precision-recall curves are included for both models.

**Why it matters for marketing:** Page value and visitor type carry most of the signal. A model like this is the basis for deciding which sessions deserve retargeting spend and which should be left alone — the same scoring logic I use on B2B accounts, applied to sessions.

> **Attribution:** team project, built with two classmates.

---

## 2. Which Marketing Channels Actually Drive Revenue (P&G)

**Question:** P&G spends across five channels. Which ones move revenue, and what is the return on each dollar?

**Data:** Course-provided dataset of P&G marketing activity — social media posts (X/WeChat), events, and in-store, digital, and TV spend, against revenue.

**Approach:**
- Exploratory analysis and correlation review per channel
- **OLS multiple regression** (`statsmodels`) to isolate each channel's contribution, with single-variable models run alongside to check stability
- Coefficients read as marginal revenue per unit of spend

**Results:** The full model explains **82% of revenue variance (R² = 0.820, adjusted R² = 0.818)**. Estimated return per dollar:

| Channel | Return per $1 |
|---|---|
| In-store | $4.00 |
| Digital | $3.31 |
| TV | $1.66 |
| Social media | No measurable effect |
| Events | Slight negative |

**Recommendation:** Shift budget toward in-store and digital. Pause event spend pending a review of why it isn't converting, and audit the social strategy with sentiment analysis before writing the channel off — low posting volume, not low channel value, may be the problem.

**Why it matters for marketing:** This is channel attribution and budget allocation, which is the same argument I make with dashboards in a live role — just with the regression shown rather than assumed.

---

## 3. Keyword Opportunity Scoring, Step by Step

**Question:** Of the keywords a small B2B team could chase, which are already ours, which are open, which are worth taking off a competitor, and which are not worth the effort?

**Notebook:** `SXO_Keyword_Opportunity_(Eric_Weldon).ipynb`

This is the scoring method from the SXO tool below, pulled out and run on a built-in sample for a fictional company so you can follow it end to end. No API keys, no internet, runs top to bottom.

**What it does:**
- **Finds each site's distinctive phrases** with field-weighted TF-IDF: title and URL count 5x, H1 3x, subheadings 2x, body 1x. The output shows each competitor's positioning falling out of its own copy.
- **Scores demand, fit and who ranks.** Demand from autocomplete variants, fit as the best overlap between a keyword and any single differentiator (discounted when the keyword names none of the product terms), rankings from a snapshot.
- **Labels and prioritises.** Each keyword lands as *ours*, *open*, *fight for*, *not winnable* or *not worth it*, with opportunity = √demand × fit × beatability × intent factor, where beatability rises as the best competitor's rank falls and is discounted when we already rank top three.
- **Checks a draft against its brief:** keyword in the H1 and first paragraph, an answer under 60 words up front, at least three question headings, an FAQ, every number traceable to a confirmed fact, and no absolute claims.

**What the output shows:** eleven candidate keywords sorted by opportunity, from an open gap at 88 down to a competitor's home turf at 0, plus a draft check that passes structure but fails on an untraceable statistic and an unsupported "the only" claim.

**Why it matters for marketing:** keyword difficulty tells you what is hard to rank for. This asks the different and more useful question of what is worth ranking for *given what you actually sell*, and then holds the finished writing to the brief it came from.

> **Note:** the thresholds and intent weights are reasoned rules of thumb, not calibrated against outcomes. The sample company, its rankings and its "confirmed fact" are invented for the walkthrough.

---

## 4. Internal Tools I Built and Run

Two tools I built for my own marketing work because I needed the output and didn't have an engineer. Both are here in full. Neither ships with my own configuration, keys or run data: you supply your own, and nothing you run bills to me.

### SXO Audit (UX · SEO · AEO)

Benchmarks a site against its competitors using only free data sources, then writes a one-file dashboard anyone can open. **Source is in [`sxo-audit/`](./sxo-audit/)** with its own README. The method behind the keyword scoring is also walked through, step by step on sample data, in the notebook below.

- **Keyword ownership:** class TF-IDF across each site's pages, weighted by title and URL (5x), H1 (3x), subheadings and link text (2x), body (1x). Demand comes from autocomplete as a relative signal, rankings from search results, and opportunity scores as the square root of demand times fit times beatability.
- **Three audit sections:** UX (Lighthouse performance and accessibility, CTA coverage, form length, readability), SEO (titles, schema, canonicals, internal links, content depth, broken links), and AEO (AI crawler access, `llms.txt`, question headings, short direct answers, quotable facts, buyer-question coverage).
- **Content briefs:** each run writes a brief per planned piece, and a finished draft gets checked back against its brief for keyword placement, answer-first structure, question headings, length, and whether every number traces to a confirmed fact.
- **Judgment where matching fails:** fit by meaning, searcher intent and funnel stage get queued for a reading pass instead of being scored by keyword overlap, and answers are cached so each item is judged once.

### Social Audit Console

A competitive social media audit across rival brands, built around the metrics that are actually public. **Source is in [`social-audit-console/`](./social-audit-console/)** with its own README.

- **Engagement normalized per follower** so brands with different audience sizes compare fairly, grouped by media type and charted side by side.
- **Theme ownership:** scores 0 to 100 how strongly each brand is associated with each recurring theme, rendered as a heatmap. This is positioning whitespace analysis: it shows which messages are already taken and which are open.
- **Review-site analysis** across G2, Capterra, TrustRadius, Software Advice and Gartner Peer Insights, scoring what customers actually credit each vendor with.
- **Also covers** platform presence and cadence, comment sentiment, paid ad tracking from the public ad libraries, visual style from uploaded screenshots, and app store listings.
- **Snapshots over time** so movement is visible across runs rather than only the current state.
- Platform-aware metric labels (reactions vs. likes vs. impressions) so the numbers mean the same thing when summed across platforms.

Data entry is manual, by design: there is no API access to a competitor's account. That keeps samples small and makes this a tool for a considered periodic read rather than always-on monitoring. The `social-audit-console/README.md` covers that tradeoff and how to publish your own copy.

**How these were built:** I specified them, designed the scoring logic and decided what each check measures. AI coding tools wrote most of the code. The notebooks above are my own work; these tools are the product of directing a build rather than hand-writing an application, and I would rather say that plainly than imply otherwise.

---

## Running the notebooks

```bash
pip install pandas numpy scikit-learn statsmodels matplotlib seaborn scipy jupyter
jupyter notebook
```

Built on Python 3 (Anaconda). The online shoppers dataset is public and linked above. The P&G dataset was provided for coursework and is not redistributed here, so that notebook reads as a record of the analysis rather than something you can re-run as-is.

---

## About

Eric Weldon — demand generation and growth marketing, B2B IoT and hardware.
MBA, Marketing and Data Science, Santa Clara University.

[LinkedIn](https://www.linkedin.com/in/eric-weldon/)
