# Social Audit Console (B2B)

A competitive social media audit for B2B brands. You pick a target brand and three or four competitors, log what each one publishes, and the console turns it into comparisons a marketer can act on: who out-engages whom and with what format, which themes each brand already owns, what customers say in reviews, and what everyone is running as paid.

I built this for my own competitive research. It is here so you can see how it works, and run it yourself if it is useful.

---

## What it does

| Module | What it answers |
|---|---|
| **Presence** | Where each brand shows up, how many followers, how often they post, how stale the account is. Used to decide which platforms deserve a deep audit. |
| **Engagement** | Engagement rate by content type, normalized per follower so a 2,000-follower brand and a 200,000-follower brand compare fairly. Grouped bar chart by media type and brand. |
| **Terms** | Scores 0 to 100 how strongly each brand is associated with each recurring theme, as a heatmap. This is positioning whitespace analysis: it shows which messages are already taken and which are open. |
| **Sentiment** | What commenters actually say, by aspect, rather than a single positive/negative number. |
| **Paid Ads** | What each brand is running, logged from the public ad libraries (links built into the page). |
| **Visual Style** | Reads uploaded screenshots and describes each brand's visual language. |
| **Review Sites** | G2, Capterra, TrustRadius, Software Advice, Gartner Peer Insights: positioning taglines, ideal-customer descriptions and recurring themes, scored the same way as Terms. |
| **App Store** | Listing titles, subtitles, keyword fields and descriptions, scored as ASO term ownership. |
| **Synthesis** | A written read across every module. |
| **Trends** | Snapshots per run so movement is visible over time rather than only the current state. |

A few design decisions worth calling out:

- **Engagement is per-follower, not raw.** Raw likes just tell you who has the biggest audience.
- **Metric labels follow the platform.** LinkedIn says reactions and impressions, X says reposts and replies, Pinterest says saves. The underlying field names stay canonical so totals still sum correctly across platforms.
- **The analysis modules explain rather than report.** The charts show what happened; the analysis says which content characteristics correlate with it and what to do differently.
- **Only public metrics.** Nothing here needs access to anyone's ad account or analytics.

---

## Running it

This is a Claude artifact, not a static web page. Opening `index.html` in a browser will render the layout and then stop, because the page expects a Claude runtime for storage and analysis.

To actually use it, publish `index.html` as your own artifact on claude.ai with these capabilities enabled:

| Capability | Used for |
|---|---|
| `db` | Storing brands, posts, comments, ads, listings and analysis results |
| `sample` | The written analysis in Engagement, Terms, Sentiment, Visual Style, Reviews, App Store and Synthesis |
| `assets` | Screenshot uploads |
| `user` | Identifying the current viewer |

**On cost:** the analysis buttons call a model. Those calls bill to whoever publishes the artifact, so if you publish your own copy, they are yours. There are no API keys in this file and nothing to configure.

**On data:** the database starts empty. Nothing from my audits ships with this file — the brands, posts and analysis live in the artifact's own storage, not in the source.

---

## The honest tradeoff

Data entry is manual. You copy each post's public metrics into a form rather than pulling them through a platform API. That was a deliberate choice, since API access to competitors' accounts does not exist, but it has real consequences: samples are small, they reflect whichever posts you chose to log, and there is no historical backfill. Commercial tools like Rival IQ or Socialinsider pull complete post histories automatically and cost a few hundred dollars a month.

The exception is YouTube, which has a public Data API. There is a helper script pattern for pulling a channel's videos and pasting the output into the Engagement tab's bulk-import box.

So: this is worth running when you need a considered read on a competitive set, not as always-on monitoring.

---

## How this was built

I specified it, designed the scoring logic and decided what each module measures. AI coding tools wrote most of the code. I would rather say that plainly than imply I hand-wrote an application.

There is a B2C version of this console as well. The only substantive differences are the Review Sites module, which is B2B-specific, and the framing of the analysis prompts.
