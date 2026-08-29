from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

WORD = re.compile(r"[^\W_]+(?:[’'][^\W_]+)*", re.UNICODE)
CONTAMINATION = re.compile(r"subscribe|sign up|newsletter|cookie|comments|next post|previous post", re.I)
VOID = {"br", "hr", "meta", "link", "input", "area", "base", "col", "embed", "param", "track", "wbr"}
BLOCK_TAGS = {"address", "article", "aside", "blockquote", "div", "dl", "fieldset", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "main", "nav", "ol", "p", "pre", "section", "table", "ul"}
DROP_SUBTREES = {"nav", "header", "footer", "script", "style", "form", "aside", "picture", "source", "button", "svg", "iframe"}
DROP_CLASSES = {"md-content__button", "headerlink", "captioned-image-container"}


class TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def visible_text(markup: str) -> str:
    parser = TextCollector()
    parser.feed(markup)
    return " ".join(parser.parts)


def word_count(markup: str) -> int:
    return len(WORD.findall(visible_text(markup)))


def body_inner(source: str) -> str:
    match = re.search(r"<body\b[^>]*>(.*?)</body\s*>", source, re.I | re.S)
    if not match:
        raise ValueError("source has no body element")
    return match.group(1)


def xhtml(title: str, body: str, stylesheet: bool = True) -> str:
    link = '<link rel="stylesheet" type="text/css" href="../styles/book.css"/>' if stylesheet else ""
    return ("<?xml version=\"1.0\" encoding=\"utf-8\"?>\n<!DOCTYPE html>\n"
            '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">'
            f"<head><title>{html.escape(title)}</title>{link}</head><body>{body}</body></html>\n")


class XHTMLCleaner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.output: list[str] = []
        self.drop_depth = 0
        self.open_tags: list[tuple[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        classes = set(dict(attrs).get("class", "").split())
        if self.drop_depth:
            if tag not in VOID:
                self.drop_depth += 1
            return
        if tag in DROP_SUBTREES or classes & DROP_CLASSES:
            if tag not in VOID:
                self.drop_depth = 1
            return
        if tag == "img":
            return
        if tag in BLOCK_TAGS:
            for container in ("p", "h1", "h2", "h3", "h4", "h5", "h6"):
                if any(original == container for original, _ in self.open_tags):
                    self.handle_endtag(container)
                    break
        original_tag = tag
        clean_attrs = []
        for key, value in attrs:
            if value is None or key.lower().startswith("on"):
                continue
            if key.lower() == "src":
                continue
            if key.lower() == "href" and not re.match(r"https?://", value, re.I):
                continue
            if key.lower().startswith("epub:") or key.lower().startswith("aria-") or key.lower() == "target":
                continue
            clean_attrs.append(f' {key}="{html.escape(value, quote=True)}"')
        if tag == "a" and not any(attr.startswith(" href=") for attr in clean_attrs):
            tag = "span"
        suffix = " /" if tag in VOID else ""
        self.output.append(f"<{tag}{''.join(clean_attrs)}{suffix}>")
        if tag not in VOID:
            self.open_tags.append((original_tag, tag))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag.lower() not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self.drop_depth:
            self.drop_depth -= 1
            return
        if tag in VOID or tag == "img":
            return
        if any(original == tag for original, _ in self.open_tags):
            while self.open_tags:
                original, emitted = self.open_tags.pop()
                self.output.append(f"</{emitted}>")
                if original == tag:
                    break

    def handle_data(self, data: str) -> None:
        if not self.drop_depth:
            self.output.append(html.escape(data, quote=False))

    def handle_entityref(self, name: str) -> None:
        if not self.drop_depth:
            self.output.append(f"&amp;{name};")


def extract_article(markup: str) -> str:
    match = re.search(r"<article\b[^>]*>(.*?)</article\s*>", markup, re.I | re.S)
    body = match.group(1) if match else body_inner(markup)
    body = re.sub(r"<h[1-6]\b[^>]*>\s*(?:comments?|subscribe)\s*</h[1-6]>.*$", "", body, flags=re.I | re.S)
    cleaner = XHTMLCleaner()
    cleaner.feed(body)
    while cleaner.open_tags:
        _, emitted = cleaner.open_tags.pop()
        cleaner.output.append(f"</{emitted}>")
    return "".join(cleaner.output)


def validate_xhtml(markup: str) -> None:
    ET.fromstring(markup)


def normalized_path(root: Path, source_id: str) -> Path:
    return root / "sources" / "normalized" / f"{source_id}.xhtml"
