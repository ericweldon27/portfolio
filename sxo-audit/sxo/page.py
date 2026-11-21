"""Parse one fetched HTML page into the facts every check reads."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from .fetch import Response

CTA_PATTERN = re.compile(
    r"\b(demo|contact|get started|quote|talk to|book|schedule|sign up|request|free trial|"
    r"try it|start now|pricing|call us|get in touch|see how)\b", re.I)
VAGUE_LINK_PATTERN = re.compile(
    r"^(learn more|read more|click here|here|more|see more|find out more|details|view more|"
    r"discover more|explore|go)$", re.I)
# Headings without a "?" only count when they open like a real question ("How does...", "What is...").
QUESTION_START = re.compile(
    r"^(how (do|does|can|to|much|many|long|often|is|are|should)|what (is|are|does|do|should|happens)|"
    r"why (do|does|is|are|should)|can (i|you|we)|do (i|you|we)|does|should (i|you|we))\b", re.I)
CTA_QUESTION = re.compile(r"^(ready|have (any )?questions|want to|interested|looking for|need help)\b", re.I)
NON_HTML_EXT = re.compile(
    r"\.(pdf|jpe?g|png|gif|webp|avif|svg|zip|mp4|mov|docx?|xlsx?|pptx?|csv|xml|txt|ico)$", re.I)


def host_key(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def normalize(url: str) -> str:
    """Drop fragment and query, and the trailing slash on paths, so URLs dedupe."""
    url, _ = urldefrag(url)
    p = urlparse(url)
    path = p.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return f"{p.scheme}://{p.netloc.lower()}{path}"


def path_of(url: str) -> str:
    return urlparse(url).path or "/"


def words(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", text)


@dataclass
class Link:
    url: str
    text: str
    internal: bool
    in_nav: bool


@dataclass
class Image:
    src: str
    alt: Optional[str]  # None when the attribute is missing entirely


@dataclass
class Form:
    fields: int
    labeled: int


@dataclass
class QuestionBlock:
    question: str
    answer: str
    answer_words: int


@dataclass
class Page:
    url: str
    final_url: str
    status: int
    size: int
    elapsed: float
    title: str = ""
    meta_description: str = ""
    canonical: str = ""
    meta_robots: str = ""
    lang: str = ""
    viewport: str = ""
    headings: list = field(default_factory=list)  # (level, text)
    text: str = ""
    word_count: int = 0
    paragraphs: list = field(default_factory=list)
    images: list = field(default_factory=list)
    links: list = field(default_factory=list)
    forms: list = field(default_factory=list)
    ctas: list = field(default_factory=list)  # CTA texts outside the nav
    nav_ctas: list = field(default_factory=list)
    cta_before_h2: bool = False
    jsonld: list = field(default_factory=list)
    schema_types: list = field(default_factory=list)
    og: dict = field(default_factory=dict)
    dates: list = field(default_factory=list)
    authors: list = field(default_factory=list)
    questions: list = field(default_factory=list)
    list_count: int = 0
    table_count: int = 0
    script_count: int = 0
    blockquote_count: int = 0
    kind: str = "other"  # home, product, industry, proof, blog, company, other

    @property
    def path(self) -> str:
        return path_of(self.final_url)

    @property
    def h1s(self) -> list[str]:
        return [t for level, t in self.headings if level == 1]


def _clean(text: str) -> str:
    return " ".join(text.split())


def _flatten_jsonld(data) -> list[dict]:
    items = data if isinstance(data, list) else [data]
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        out.append(item)
        if "@graph" in item:
            out.extend(_flatten_jsonld(item["@graph"]))
    return out


def _types(item: dict) -> list[str]:
    t = item.get("@type", [])
    return [t] if isinstance(t, str) else [x for x in t if isinstance(x, str)]


def _accessible_name(a: Tag) -> str:
    text = _clean(a.get_text(" "))
    if text:
        return text
    if a.get("aria-label"):
        return _clean(a["aria-label"])
    if a.get("title"):
        return _clean(a["title"])
    img = a.find("img", alt=True)
    return _clean(img["alt"]) if img else ""


def _in(tag: Tag, names: tuple) -> bool:
    return any(parent.name in names for parent in tag.parents)


def parse_page(resp: Response) -> Page:
    soup = BeautifulSoup(resp.text, "html.parser")
    base = resp.final_url
    page = Page(resp.url, resp.final_url, resp.status, resp.size, resp.elapsed)
    site_host = host_key(base)

    page.script_count = len(soup.find_all("script", src=True))
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            page.jsonld.extend(_flatten_jsonld(json.loads(script.string or "")))
        except (json.JSONDecodeError, TypeError):
            continue
    page.schema_types = sorted({t for item in page.jsonld for t in _types(item)})

    if soup.title and soup.title.string:
        page.title = _clean(soup.title.string)
    html_tag = soup.find("html")
    page.lang = (html_tag.get("lang") or "") if html_tag else ""
    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").lower()
        prop = (meta.get("property") or "").lower()
        content = _clean(meta.get("content") or "")
        if name == "description":
            page.meta_description = content
        elif name == "robots":
            page.meta_robots = content.lower()
        elif name == "viewport":
            page.viewport = content
        elif name == "author" and content:
            page.authors.append(content)
        if prop.startswith("og:"):
            page.og[prop] = content
        if prop in ("article:published_time", "article:modified_time") and content:
            page.dates.append(content)
    canonical = soup.find("link", rel=lambda v: v and "canonical" in v)
    if canonical and canonical.get("href"):
        page.canonical = urljoin(base, canonical["href"])

    for item in page.jsonld:
        for key in ("datePublished", "dateModified"):
            if isinstance(item.get(key), str):
                page.dates.append(item[key])
        author = item.get("author")
        for a in (author if isinstance(author, list) else [author]):
            if isinstance(a, dict) and a.get("name"):
                page.authors.append(a["name"])
            elif isinstance(a, str):
                page.authors.append(a)
    for t in soup.find_all("time"):
        if t.get("datetime"):
            page.dates.append(t["datetime"])

    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()

    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if src.startswith("data:"):
            continue
        page.images.append(Image(urljoin(base, src), img.get("alt")))

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        url = urljoin(base, href)
        if not url.startswith("http"):
            continue
        page.links.append(Link(url, _accessible_name(a), host_key(url) == site_host,
                               _in(a, ("nav", "header"))))

    seen_h2 = False
    for el in soup.find_all(["a", "button", "h2"]):
        if el.name == "h2":
            seen_h2 = True
            continue
        label = _accessible_name(el) if el.name == "a" else _clean(el.get_text(" "))
        if not label or len(label) > 60 or not CTA_PATTERN.search(label):
            continue
        if _in(el, ("nav", "header")):
            page.nav_ctas.append(label)
        else:
            page.ctas.append(label)
            if not seen_h2:
                page.cta_before_h2 = True

    labels_for = {lab.get("for") for lab in soup.find_all("label") if lab.get("for")}
    for form in soup.find_all("form"):
        fields = [f for f in form.find_all(["input", "select", "textarea"])
                  if (f.get("type") or "text").lower() not in ("hidden", "submit", "button", "image", "reset")]
        labeled = sum(1 for f in fields
                      if f.get("aria-label") or f.get("aria-labelledby")
                      or (f.get("id") and f.get("id") in labels_for) or f.find_parent("label"))
        page.forms.append(Form(len(fields), labeled))

    # Body content below excludes nav and footer chrome.
    for tag in soup(["nav", "footer"]):
        tag.decompose()

    for h in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"]):
        text = _clean(h.get_text(" "))
        if not text:
            continue
        page.headings.append((int(h.name[1]), text))
        is_question = text.endswith("?") or (QUESTION_START.match(text) and len(words(text)) >= 4)
        if h.name in ("h2", "h3", "h4") and is_question and not CTA_QUESTION.match(text):
            answer = ""
            for nxt in h.find_all_next(["p", "li", "h1", "h2", "h3", "h4", "h5", "h6"]):
                if nxt.name.startswith("h"):
                    break
                answer = _clean(nxt.get_text(" "))
                if answer:
                    break
            page.questions.append(QuestionBlock(text, answer[:400], len(words(answer))))

    page.paragraphs = [t for t in (_clean(p.get_text(" ")) for p in soup.find_all(["p", "li"]))
                       if len(words(t)) >= 6]
    page.list_count = len(soup.find_all(["ul", "ol"]))
    page.table_count = len(soup.find_all("table"))
    page.blockquote_count = len(soup.find_all("blockquote"))
    body = soup.body or soup
    page.text = _clean(body.get_text(" "))
    page.word_count = len(words(page.text))
    return page
