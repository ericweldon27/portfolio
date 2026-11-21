"""Briefs and draft checks for the content plan.

Briefs: each run writes output/<run>/briefs/<slug>.md, everything a writer needs for one piece (target and
related keywords, the question to answer first, the angle, confirmed facts, proof, next step, rules).
Claude drafts from the brief in the session, in a Claude Docs doc the user reviews.

Draft checks: a draft saved as drafts/<slug>.md (exported from the doc) is checked against its brief before
publishing: the keyword in the right places, answer-first, question headings with short answers, an FAQ,
length, a link onward, numbers that trace back to confirmed facts, and the house style rules.
"""
from __future__ import annotations

import re
from pathlib import Path

from .checks.common import tokens

NUM_RX = re.compile(r"\$\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?%|\b\d[\d,]{2,}(?:\.\d+)?\b")
ABSOLUTE_RX = re.compile(r"\b(first and only|the only|everyone else|no one else|nobody else|guarantee[ds]?|#1)\b", re.I)
RULES = [
    "Answer the question in the first paragraph, in under 60 words.",
    "Use question headings, each followed by a short direct answer (under 70 words), then detail.",
    "No em dashes. Plain verbs. Concrete numbers with their basis. Don't overclaim: ranges and 'up to' where that's what the data supports.",
    "Only use numbers from the confirmed facts below, or simple math on them that the text shows.",
]


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80]


def confirmed_facts(cfg) -> list[str]:
    return [f"{c.get('title', '')}: {c['note']}" for c in cfg.get("confirm", [])
            if c.get("status") == "confirmed" and c.get("note", "").strip()]


def write_briefs(pieces: list[dict], cfg, out_dir: Path) -> None:
    folder = out_dir / "briefs"
    folder.mkdir(parents=True, exist_ok=True)
    facts = confirmed_facts(cfg)
    for p in pieces:
        lines = [f"# Brief: {p['title']}", "",
                 f"- Format: {p['format']} · stage: {p['stage']} · priority {p['priority']}",
                 f"- Target keyword: {p['target_keyword']}",
                 f"- Also cover: {p['supporting_keywords'] or 'none'}",
                 f"- Question to answer first: {p['question'] or 'none'}",
                 f"- Angle: {p['angle']}",
                 f"- Proof needed: {p['proof_needed'] or 'none'}",
                 f"- Leads to: {p['next_step'] or 'none'}",
                 f"- Why this piece: {p['why']}", "", "## Confirmed facts", ""]
        lines += [f"- {f}" for f in facts] + ["", "## Rules", ""] + [f"- {r}" for r in RULES]
        (folder / f"{slugify(p['title'])}.md").write_text("\n".join(lines) + "\n")


def _parse(md: str) -> tuple[str, list[tuple[int, str]], list[str], list[tuple[int, str, str]]]:
    """(H1, headings, paragraphs, [(level, heading, the first paragraph after it)])."""
    h1, heads, paras, after = "", [], [], []
    pending = None
    for block in re.split(r"\n\s*\n", md):
        b = block.strip()
        if not b or b.startswith(">"):
            continue
        m = re.match(r"^(#{1,6})\s+(.*)", b)
        if m:
            lvl, text = len(m.group(1)), m.group(2).strip()
            if lvl == 1 and not h1:
                h1 = text
            heads.append((lvl, text))
            pending = (lvl, text)
            continue
        text = re.sub(r"[*_`]", "", b)
        if not re.match(r"^[-*\d]", b):
            paras.append(text)
        if pending:
            after.append((pending[0], pending[1], text))
            pending = None
    return h1, heads, paras, after


def _has(text: str, keyword: str) -> bool:
    kt = tokens(keyword)
    return bool(kt) and len(kt & tokens(text)) / len(kt) >= 0.75


def check(md: str, piece: dict, cfg, claims: list[dict]) -> list[dict]:
    h1, heads, paras, after = _parse(md)
    body = re.sub(r"^>.*$", "", md, flags=re.M)
    words = len(re.findall(r"\b\w+\b", re.sub(r"\(https?://[^)]+\)", "", body)))
    kw = piece["target_keyword"]
    first = paras[0] if paras else ""
    questions = [(lvl, h, a) for lvl, h, a in after if h.rstrip().endswith("?")]
    long_answers = [h for _, h, a in questions if len(a.split()) > 70]
    faq_idx = next((i for i, (_, h) in enumerate(heads) if re.search(r"faq|frequently asked|questions", h, re.I)), None)
    faq_qs = [h for _, h in heads[faq_idx + 1:] if h.endswith("?")] if faq_idx is not None else []
    known = " ".join(confirmed_facts(cfg)) + " " + " ".join(str(v) for v in cfg.get("differentiators", []))
    known_nums = {n.replace(",", "").replace(" ", "") for n in NUM_RX.findall(known)}
    nums = sorted({n.strip() for n in NUM_RX.findall(body)} - {""})
    unverified = [n for n in nums if n.replace(",", "").replace(" ", "") not in known_nums]
    bad_claims = sorted({m.group(0) for m in ABSOLUTE_RX.finditer(body)})
    risky = [c["claim"] for c in claims if c["verdict"] in ("unsupported", "risky") and c["claim"].lower()[:40] in body.lower()]

    def row(name, ok, detail, warn=False):
        return {"check": name, "result": "pass" if ok else ("warn" if warn else "fail"), "detail": detail}

    return [
        row("Keyword in the H1", _has(h1, kw), f"H1: {h1 or 'none'}"),
        row("Keyword in the first paragraph", _has(first, kw), first[:140]),
        row("Keyword in a subheading", any(_has(h, kw) for lvl, h in heads if lvl > 1),
            "Add the keyword (or close wording) to one H2 or H3", warn=True),
        row("Answer first (under 60 words)", 0 < len(first.split()) <= 60, f"First paragraph: {len(first.split())} words"),
        row("Question headings (3 or more)", len(questions) >= 3, f"{len(questions)} question headings"),
        row("Short answers under questions", not long_answers,
            "All under 70 words" if not long_answers else "Over 70 words: " + "; ".join(long_answers[:3]), warn=True),
        row("FAQ section (3 or more questions)", len(faq_qs) >= 3,
            f"{len(faq_qs)} FAQ questions" + ("; mark them up with FAQPage schema" if faq_qs else "")),
        row("Length (800 to 1,600 words)", 800 <= words <= 1600, f"{words} words", warn=True),
        row("Links onward", "](" in body, f"Should lead to: {piece.get('next_step') or 'the next page'}"),
        row("Numbers trace to confirmed facts", not unverified,
            "All match confirmed facts" if not unverified else
            "Not in confirmed facts (fine if the text shows the math): " + ", ".join(unverified[:12]), warn=True),
        row("No absolute claims", not (bad_claims or risky),
            "None found" if not (bad_claims or risky) else "Found: " + ", ".join(bad_claims + risky)),
        row("No em dashes", "—" not in body, f"{body.count(chr(0x2014))} em dashes"),
        row("Draft notes removed", not re.search(r"^>\s*\*\*[^*]*Draft notes", md, re.M | re.I),
            "Remove the draft notes block before publishing", warn=True),
    ]


def build(pieces: list[dict], cfg, claims: list[dict], drafts_dir: Path, out_dir: Path, log=print) -> list[dict]:
    write_briefs(pieces, cfg, out_dir)
    rows = []
    for p in pieces:
        path = drafts_dir / f"{slugify(p['title'])}.md"
        p["slug"] = slugify(p["title"])
        if not path.exists():
            p["draft"], p["draft_result"] = "not drafted", ""
            continue
        results = check(path.read_text(), p, cfg, claims)
        fails = sum(r["result"] == "fail" for r in results)
        warns = sum(r["result"] == "warn" for r in results)
        p["draft"] = "drafted"
        p["draft_result"] = f"{len(results) - fails - warns} pass · {warns} warn · {fails} fail"
        rows += [dict(r, piece=p["title"], key=f"{p['slug']}|{r['check']}") for r in results]
    log(f"[drafts] {sum(p['draft'] == 'drafted' for p in pieces)} of {len(pieces)} pieces drafted; briefs in {out_dir / 'briefs'}")
    return rows
