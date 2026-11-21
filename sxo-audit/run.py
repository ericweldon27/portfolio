"""Run the SXO audit: python3 run.py [--config config.json] [--max-pages N] [--no-pagespeed] [--no-serp]"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from sxo.checks import run_all
from sxo.crawl import crawl_site
from sxo.export import write_tables
from sxo.fetch import Fetcher
from sxo.benefits import build as build_benefits
from sxo.citations import build as build_citations
from sxo.claims import check_claims, proof_matrix
from sxo.judge import Judgments
from sxo.content import build as build_content
from sxo.drafts import build as build_drafts
from sxo.messaging import build as build_messaging
from sxo.reviews import build as build_reviews
from sxo.trends import Trends
from sxo.brief import apply_brief, load_brief
from sxo.keywords import build as build_keywords
from sxo.report import write_dashboard
from sxo.research import Research, load_env
from sxo.score import fix_first, gaps, section_scores

HERE = Path(__file__).resolve().parent


def site_summary(site) -> dict:
    return {"name": site.name, "url": site.base_url, "is_ours": site.is_ours, "origin": site.origin,
            "pages_crawled": len(site.pages), "pages": [p.path for p in site.pages],
            "sitemap_urls": site.sitemap.get("count", 0), "errors": site.errors}


def append_history(report: dict, out_dir: Path, path: Path) -> None:
    """One line per run: when, what brief, how much it cost, headline results."""
    history = [h for h in (json.loads(path.read_text()) if path.exists() else []) if h["run"] != out_dir.name]
    kw = report["keywords"]["keywords"]
    history.append({
        "run": out_dir.name, "generated": report["generated"],
        "topics": ", ".join(t["name"] for t in (report.get("brief") or {}).get("topics", [])),
        "competitors": len(report["sites"]) - 1, "new_searches": report["run"]["new_searches"],
        "pages_from_cache": report["run"]["pages_from_cache"],
        "keywords": len(kw), "open_gaps": sum(1 for k in kw if k.get("label") == "open"),
        "fight_for": sum(1 for k in kw if k.get("label") == "fight for"),
        "drafted": sum(1 for p in report["content"]["pieces"] if p.get("draft") == "drafted"),
        "ours": sum(1 for k in kw if k.get("label") == "ours"),
        "overall_score": report["sites"][0]["scores"]["overall"],
        "reviews": len(report["reviews"]["reviews"]), "judgments_pending": report["run"]["judgments_pending"],
    })
    path.write_text(json.dumps(history, indent=1))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--brief", default=str(HERE / "brief.json"), help="research brief from the setup page")
    ap.add_argument("--max-pages", type=int)
    ap.add_argument("--no-pagespeed", action="store_true")
    ap.add_argument("--no-serp", action="store_true", help="skip Brave Search ranking lookups (uses cache only)")
    ap.add_argument("--out", default=str(HERE / "output"))
    ap.add_argument("--fresh", action="store_true", help="ignore cached pages and re-crawl every site")
    args = ap.parse_args()

    load_env(HERE / ".env")
    cfg = json.loads(Path(args.config).read_text())
    brief = None
    if Path(args.brief).exists():
        brief = load_brief(Path(args.brief))
        cfg = apply_brief(cfg, brief)
        print(f"Brief: {len(cfg['topics'])} topics, {len(cfg['benefits'])} benefits, {len(cfg['competitors'])} competitors")
    max_pages = args.max_pages or cfg.get("max_pages", 25)
    run_psi = cfg.get("run_pagespeed", True) and not args.no_pagespeed
    fetcher = Fetcher(delay=cfg.get("request_delay_seconds", 1.0),
                      cache_dir=None if args.fresh else HERE / "output" / "cache" / "pages")

    targets = [(cfg["our_site"], True)] + [(c, False) for c in cfg["competitors"]]
    results, crawled = [], []
    for target, is_ours in targets:
        site = crawl_site(target["name"], target["url"], is_ours, fetcher, cfg["keywords"], max_pages, run_psi)
        crawled.append(site)
        checks = [c.to_dict() for c in run_all(site, cfg)]
        results.append({"site": site_summary(site), "scores": section_scores(checks), "checks": checks})
        print(f"[{site.name}] scores: {results[-1]['scores']}  (pages by type: "
              f"{dict(Counter(p.kind for p in site.pages))})")

    budget = 0 if args.no_serp else cfg.get("serp_budget", 60)
    # Keywords get 60% of the new searches; benefit wordings get the rest.
    research = Research(HERE / "output" / "cache", int(budget * 0.6))
    judge = Judgments(HERE / "output" / "judgments")
    usable = [s for s in crawled if s.pages]
    keywords = build_keywords(usable, cfg, research, judge)
    print(f"[keywords] {keywords['checked']} keywords with ranking data; {keywords['serp_calls']} new Brave searches")
    research.serp_budget = budget
    trends = Trends(HERE / "output" / "cache")
    benefits = (build_benefits(usable, cfg, research, judge, trends) if cfg.get("benefits")
                else {"wordings": [], "phrases": []})
    print(f"[benefits] {len(benefits['wordings'])} wordings scored; {research.serp_calls} new Brave searches in total")
    reviews = build_reviews(cfg, fetcher, judge)
    claims = check_claims(usable, cfg, keywords["keywords"], judge)
    proof = proof_matrix(usable)
    citations = build_citations(usable, research.seen, fetcher)
    messaging = build_messaging(keywords["keywords"], benefits["wordings"], claims, proof, cfg, judge)
    content = build_content(usable, keywords["keywords"], benefits["wordings"], claims, messaging, cfg, judge)
    pending = judge.save_queue()
    if pending:
        print(f"[judgments] {pending} items wait for Claude's judgment in output/judgments/queue.json "
              "(heuristics used meanwhile)")

    ours = results[0]
    report = {
        "generated": datetime.now().isoformat(timespec="minutes"),
        "config": {"keywords": cfg["keywords"], "questions": cfg["questions"], "max_pages": max_pages},
        "sites": results,
        "keywords": keywords,
        "benefits": benefits,
        "brief": brief,
        "reviews": reviews,
        "claims": claims,
        "proof": proof,
        "citations": citations,
        "messaging": messaging,
        "content": content,
        "run": {"pages_from_cache": fetcher.cache_hits, "new_searches": research.serp_calls,
                "judgments_pending": pending, "judgments_known": len(judge.answers)},
        "gaps": gaps(ours["checks"], {r["site"]["name"]: r["checks"] for r in results[1:]}),
        "fix_first": fix_first(ours["checks"]),
    }
    out_dir = Path(args.out) / datetime.now().strftime("%Y-%m-%d_%H%M")
    out_dir.mkdir(parents=True, exist_ok=True)
    report["draft_checks"] = build_drafts(content["pieces"], cfg, claims, HERE / "drafts", out_dir)
    (out_dir / "results.json").write_text(json.dumps(report, indent=2))
    dashboard = write_dashboard(report, out_dir / "dashboard.html")
    append_history(report, out_dir, HERE / "output" / "history.json")
    data_dir = write_tables(report, out_dir)
    print(f"\nResults:   {out_dir / 'results.json'}\nDashboard: {dashboard}\nDashboard data: {data_dir}")


if __name__ == "__main__":
    main()
