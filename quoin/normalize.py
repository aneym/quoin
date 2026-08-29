from __future__ import annotations

import html
import io
import re
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

WORD = re.compile(r"[^\W_]+(?:[’'][^\W_]+)*", re.UNICODE)
CONTAMINATION = re.compile(
    r"subscribe|sign up|newsletter|cookie|comments|next post|previous post", re.I
)
VOID = {
    "br",
    "hr",
    "meta",
    "link",
    "input",
    "area",
    "base",
    "col",
    "embed",
    "param",
    "track",
    "wbr",
    "img",
    "source",
}
BLOCK_TAGS = {
    "address",
    "article",
    "aside",
    "blockquote",
    "div",
    "dl",
    "fieldset",
    "figure",
    "footer",
    "form",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "hr",
    "main",
    "nav",
    "ol",
    "p",
    "pre",
    "section",
    "table",
    "ul",
}
DROP_SUBTREES = {
    "nav",
    "header",
    "footer",
    "script",
    "style",
    "form",
    "aside",
    "picture",
    "source",
    "button",
    "svg",
    "iframe",
}
DROP_CLASSES = {"md-content__button", "headerlink", "captioned-image-container"}

# Media (plan 005): pure, I/O-free helpers for image handling. Network fetches and
# filesystem placement live in fetch.py; this module only sniffs bytes, judges
# ornamentality, and rewrites <img> markup.
ORNAMENTAL_MIN_EDGE = 120
ORNAMENTAL_MIN_BYTES = 2560  # 2.5 KB
MEDIA_EXT = {"jpeg": "jpg", "png": "png", "gif": "gif", "webp": "webp", "svg": "svg"}
MEDIA_MIME = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
}
DECLARED_EXT_TYPE = {
    "jpg": "jpeg",
    "jpeg": "jpeg",
    "png": "png",
    "gif": "gif",
    "webp": "webp",
    "svg": "svg",
}
_IMG_TAG = re.compile(r"<img\b((?:[^>\"']|\"[^\"]*\"|'[^']*')*)/?>", re.I)
_ATTR = re.compile(r"""([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+))""")


def _parse_attrs(attr_source: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for match in _ATTR.finditer(attr_source):
        key = match.group(1).lower()
        value = next(group for group in match.groups()[1:] if group is not None)
        parsed[key] = html.unescape(value)
    return parsed


def find_images(markup: str) -> list[dict[str, str]]:
    """Return every <img> in markup as {"src": ..., "alt": ...}, in document order."""
    images = []
    for match in _IMG_TAG.finditer(markup):
        attrs = _parse_attrs(match.group(1))
        images.append({"src": attrs.get("src", ""), "alt": attrs.get("alt", "")})
    return images


def rewrite_images(markup: str, resolver) -> str:
    """Replace every <img> in markup using resolver(src, alt) -> (new_src, new_alt) | None.

    A None result drops the image entirely. Runs on plain markup text; performs no I/O
    itself, so it composes with either an XHTMLCleaner-produced body (web/file sources)
    or raw EPUB chapter markup (epub sources).
    """

    def replace(match: re.Match) -> str:
        attrs = _parse_attrs(match.group(1))
        result = resolver(attrs.get("src", ""), attrs.get("alt", ""))
        if result is None:
            return ""
        new_src, new_alt = result
        return (
            f'<img src="{html.escape(new_src, quote=True)}" '
            f'alt="{html.escape(new_alt, quote=True)}"/>'
        )

    return _IMG_TAG.sub(replace, markup)


def sniff_image_type(data: bytes) -> str | None:
    """Identify an image's real type from its magic bytes, ignoring any claimed extension."""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if data[:3] == b"\xff\xd8\xff":
        return "jpeg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    stripped = data.lstrip(b"\xef\xbb\xbf \t\r\n")[:512]
    if b"<svg" in stripped.lower():
        try:
            tag = ET.fromstring(data.decode("utf-8")).tag
        except Exception:
            return None
        if tag.rsplit("}", 1)[-1].lower() == "svg":
            return "svg"
    return None


def is_ornamental(data: bytes, sniffed_type: str) -> bool:
    """Drop-cap / section-rule detection: small-byte or small-pixel images render as specks."""
    if len(data) < ORNAMENTAL_MIN_BYTES:
        return True
    if sniffed_type == "svg":
        return False
    try:
        with Image.open(io.BytesIO(data)) as image:
            width, height = image.size
    except Exception:
        return True
    return width < ORNAMENTAL_MIN_EDGE or height < ORNAMENTAL_MIN_EDGE


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


def replace_body_inner(source: str, new_body: str) -> str:
    """Splice new_body in place of the current <body> contents, leaving the rest of
    source (head, title, doctype) untouched. Mirrors body_inner's own match so the
    two stay in lockstep."""
    match = re.search(r"<body\b[^>]*>(.*?)</body\s*>", source, re.I | re.S)
    if not match:
        raise ValueError("source has no body element")
    return source[: match.start(1)] + new_body + source[match.end(1) :]


def xhtml(title: str, body: str, stylesheet: bool = True) -> str:
    link = (
        '<link rel="stylesheet" type="text/css" href="../styles/book.css"/>' if stylesheet else ""
    )
    return (
        '<?xml version="1.0" encoding="utf-8"?>\n<!DOCTYPE html>\n'
        '<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">'
        f"<head><title>{html.escape(title)}</title>{link}</head><body>{body}</body></html>\n"
    )


class XHTMLCleaner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.output: list[str] = []
        self.drop_depth = 0
        self.open_tags: list[tuple[str, str | None]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        classes = set((dict(attrs).get("class") or "").split())
        if self.drop_depth:
            if tag not in VOID:
                self.drop_depth += 1
            return
        if tag in DROP_SUBTREES or classes & DROP_CLASSES:
            if tag not in VOID:
                self.drop_depth = 1
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
            if key.lower() == "src" and tag != "img":
                continue
            if key.lower() == "href" and not re.match(r"https?://", value, re.I):
                continue
            if (
                key.lower().startswith("epub:")
                or key.lower().startswith("aria-")
                or key.lower() == "target"
            ):
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
    body = re.sub(
        r"<h[1-6]\b[^>]*>\s*(?:comments?|subscribe)\s*</h[1-6]>.*$", "", body, flags=re.I | re.S
    )
    cleaner = XHTMLCleaner()
    cleaner.feed(body)
    while cleaner.open_tags:
        _, emitted = cleaner.open_tags.pop()
        cleaner.output.append(f"</{emitted}>")
    return "".join(cleaner.output)


class KoboSpanWrapper(HTMLParser):
    """Kobo kepub transform (plan 011): wrap every text node under a block-level
    ancestor in <span class="koboSpan" id="kobo.N.M">. Each BLOCK_TAGS element
    opens a frame; N is assigned to a frame lazily, the first time it actually
    gets a text node (so a text-less container like <section> wrapping an <h1>
    never consumes a paragraph number -- N stays a contiguous 1, 2, 3... over the
    spans that are actually emitted). M is a segment counter, scoped to the frame
    and incremented per text node inside it (including nested inline runs, so an
    <em> inside a <p> keeps the p's frame and its running segment count). Tags are
    re-emitted via get_starttag_text() so their original bytes -- attribute order,
    quoting, self-closing form -- pass through unchanged; only text nodes gain a
    wrapping span. Spans add no text, so word counts are unaffected."""

    class _Frame:
        __slots__ = ("paragraph", "segment")

        def __init__(self) -> None:
            self.paragraph: int | None = None
            self.segment = 0

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.output: list[str] = []
        self.next_paragraph = 0
        self.stack: list[KoboSpanWrapper._Frame] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.output.append(self.get_starttag_text() or f"<{tag}>")
        if tag.lower() in BLOCK_TAGS:
            self.stack.append(KoboSpanWrapper._Frame())

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.output.append(self.get_starttag_text() or f"<{tag}/>")

    def handle_endtag(self, tag: str) -> None:
        self.output.append(f"</{tag}>")
        if tag.lower() in BLOCK_TAGS and self.stack:
            self.stack.pop()

    def handle_data(self, data: str) -> None:
        if self.stack and data.strip():
            frame = self.stack[-1]
            if frame.paragraph is None:
                self.next_paragraph += 1
                frame.paragraph = self.next_paragraph
            frame.segment += 1
            span_id = f"kobo.{frame.paragraph}.{frame.segment}"
            self.output.append(f'<span class="koboSpan" id="{span_id}">{html.escape(data)}</span>')
        else:
            # Whitespace-only text nodes (e.g. pretty-printed indentation between
            # <li> siblings) are left unwrapped: some content models (ol/ul, table
            # row/section groups) only permit specific element children, and a
            # <span> landing directly inside one is an EPUBCheck content-model
            # error even though the text carries no visible words either way.
            self.output.append(html.escape(data))

    def handle_entityref(self, name: str) -> None:
        self.handle_data(f"&{name};")


def wrap_kobo_spans(body: str) -> str:
    """Run KoboSpanWrapper over one document's body markup and return the wrapped
    result. Called once per spine xhtml file, so paragraph/segment counters (and
    the ids they produce) reset per document -- ids only need to be unique within
    the XHTML document that declares them."""
    wrapper = KoboSpanWrapper()
    wrapper.feed(body)
    return "".join(wrapper.output)


def validate_xhtml(markup: str) -> None:
    ET.fromstring(markup)


def normalized_path(root: Path, source_id: str) -> Path:
    return root / "sources" / "normalized" / f"{source_id}.xhtml"
