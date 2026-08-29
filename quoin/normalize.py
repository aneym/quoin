from __future__ import annotations

import html
import re
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

WORD = re.compile(r"[^\W_]+(?:[’'][^\W_]+)*", re.UNICODE)
DROP = re.compile(r"<(nav|header|footer|script|style|form|aside)\b[^>]*>.*?</\1\s*>", re.I | re.S)
CONTAMINATION = re.compile(r"subscribe|sign up|newsletter|cookie|comments|next post|previous post", re.I)


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


def extract_article(markup: str) -> str:
    match = re.search(r"<article\b[^>]*>(.*?)</article\s*>", markup, re.I | re.S)
    body = match.group(1) if match else body_inner(markup)
    body = DROP.sub("", body)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    body = re.sub(r"<img\b[^>]*?/?>", "", body, flags=re.I | re.S)
    return body


def validate_xhtml(markup: str) -> None:
    ET.fromstring(markup)


def normalized_path(root: Path, source_id: str) -> Path:
    return root / "sources" / "normalized" / f"{source_id}.xhtml"
