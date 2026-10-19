# Marketing Analytics Notebooks

Python notebooks from my MBA coursework in Marketing and Data Science at Santa Clara University. Both start from a marketing question, not a modeling exercise — the analysis exists to support a spending or targeting decision, and each one ends with the recommendation I'd actually make.

I'm a B2B demand generation and growth marketer. These are here because I'd rather build the segmentation and attribution myself than file a ticket for it.

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

> **Attribution:** team project

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

## Running these

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
