from __future__ import annotations

import html
import io
import os
import re
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from . import __version__
from .blocks import read_for_build
from .errors import QuoinError
from .manifest import inside, load
from .normalize import MEDIA_MIME, body_inner, xhtml
from .record import file_hash, hashes, read_json, run_stage, sha256_bytes, write_json

FIXED_TIME = (2026, 8, 29, 0, 0, 0)
MODIFIED = "2026-08-29T00:00:00Z"
FONT_CANDIDATES = (
    Path("/System/Library/Fonts/Helvetica.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
)
CSS = """@charset "UTF-8";
html{-webkit-text-size-adjust:100%}body{margin:5%;font-family:Charter,"Iowan Old Style",Palatino,Georgia,serif;font-size:1em;line-height:1.58;color:#20201f}h1,h2,h3{font-family:-apple-system,BlinkMacSystemFont,"Avenir Next",sans-serif;line-height:1.18;break-after:avoid-page}h1{font-size:1.78em}h2{font-size:1.28em;margin-top:1.7em}p{margin:0 0:.92em}ul,ol{padding-left:1.35em}li{margin:.22em 0}blockquote{margin:1.25em .5em 1.25em 0;padding-left:1em;border-left:.18em solid #9d8e78}.fullpage{min-height:82vh;display:flex;flex-direction:column;justify-content:center}.source{border-top:.2em solid #9d7950;padding-top:1em}.cover{margin:0;text-align:center}.cover img{max-width:100%;max-height:100vh}.small{font-size:.82em}
"""


def zip_write(archive: zipfile.ZipFile, name: str, data: bytes, stored: bool = False) -> None:
    info = zipfile.ZipInfo(name, FIXED_TIME)
    info.compress_type = zipfile.ZIP_STORED if stored else zipfile.ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    info.create_system = 3
    archive.writestr(info, data)


def cover_font(book: dict) -> tuple[Path, str]:
    configured = book.get("cover_font")
    if configured:
        path = Path(configured)
        if path.is_file():
            return path, "book.toml cover_font"
    environment = os.environ.get("QUOIN_COVER_FONT")
    if environment:
        path = Path(environment)
        if path.is_file():
            return path, "QUOIN_COVER_FONT"
    for candidate in FONT_CANDIDATES:
        if candidate.is_file():
            return candidate, f"candidate {candidate}"
    raise QuoinError(
        "cover font not found; set absolute book.toml cover_font or QUOIN_COVER_FONT, "
        "or install DejaVu Sans (https://dejavu-fonts.github.io/)"
    )


def _cover(title: str, brand: str, font_path: Path) -> bytes:
    image = Image.new("RGB", (1600, 2560), "#171a1d")
    draw = ImageDraw.Draw(image)
    title_font = ImageFont.truetype(str(font_path), 116, index=0)
    brand_font = ImageFont.truetype(str(font_path), 56, index=0)
    draw.multiline_text((170, 300), title, font=title_font, fill="#f2efe8", spacing=28)
    draw.text((170, 2150), brand, font=brand_font, fill="#d5c7ad")
    buffer = io.BytesIO()
    image.save(buffer, "PNG", optimize=False, compress_level=9)
    return buffer.getvalue()


def _ordered(manifest: dict) -> list[tuple[str, str, str]]:
    result: list[tuple[str, str, str]] = []
    for movement in manifest["movements"]:
        result.append((f"movement-{movement['id']}", movement["title"], "movement"))
        for item in movement["items"]:
            kind, identifier = item["ref"].split(":", 1)
            result.append((f"{kind}-{identifier}", identifier, kind))
    return result


def assemble(root: Path, target: Path, manifest: dict, book: dict, blocks: dict, records: dict) -> None:
    pages: dict[str, str] = {
        "cover": xhtml("Cover", '<section class="cover"><img src="../images/cover.png" alt="Cover"/></section>'),
        "title": xhtml("Title page", f'<section class="fullpage"><h1>{html.escape(manifest["title"])}</h1><p>{html.escape(manifest["brand"])}</p></section>'),
    }
    spine: list[tuple[str, str]] = [("cover", "Cover"), ("title", "Title page")]
    for slug, label, kind in _ordered(manifest):
        if kind == "movement":
            pages[slug] = xhtml(label, f'<section class="fullpage"><h1>{html.escape(label)}</h1></section>')
        elif kind == "block":
            block = blocks[label]
            pages[slug] = xhtml(block["title"], f'<section>{block["html"]}</section>')
            label = block["title"]
        else:
            source = (root / "sources" / "normalized" / f"{label}.xhtml").read_text(encoding="utf-8")
            pages[slug] = xhtml(label, body_inner(source))
        spine.append((slug, label))
    attribution = ["<section><h1>Attribution</h1>"]
    source_declarations = {source["id"]: source for source in manifest["sources"]}
    for source_id, record in records.items():
        declaration = source_declarations[source_id]
        attribution.append(f'<h2>{html.escape(declaration.get("title", source_id))}</h2><p>{html.escape(record["url"])}</p>')
    attribution.append("</section>")
    pages["attribution"] = xhtml("Attribution", "".join(attribution))
    spine.append(("attribution", "Attribution"))
    nav_items = "".join(f'<li><a href="text/{slug}.xhtml">{html.escape(title)}</a></li>' for slug, title in spine)
    nav = ('<?xml version="1.0" encoding="utf-8"?><!DOCTYPE html><html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops" xml:lang="en"><head><title>Contents</title></head>'
           f'<body><nav epub:type="toc" id="toc"><h1>Contents</h1><ol>{nav_items}</ol></nav></body></html>')
    manifest_items = ['<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>', '<item id="css" href="styles/book.css" media-type="text/css"/>', '<item id="cover-image" href="images/cover.png" media-type="image/png" properties="cover-image"/>']
    manifest_items += [f'<item id="{slug}" href="text/{slug}.xhtml" media-type="application/xhtml+xml"/>' for slug, _ in spine]
    media_files: list[Path] = []
    for source_id in records:
        media_dir = root / "sources" / "media" / source_id
        if media_dir.exists():
            for path in sorted(media_dir.iterdir()):
                if path.name == "index.json":
                    continue  # fetch-time download cache, not a packaged asset
                media_files.append(path)
                media_type = MEDIA_MIME.get(path.suffix.lower().lstrip("."), "application/octet-stream")
                manifest_items.append(f'<item id="media-{len(media_files)}" href="text/media/{source_id}/{path.name}" media-type="{media_type}"/>')
    spine_items = "".join(f'<itemref idref="{slug}"/>' for slug, _ in spine)
    identifier = f"urn:sha256:{sha256_bytes(manifest['slug'].encode())}"
    opf = (f'<?xml version="1.0" encoding="utf-8"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id" xml:lang="{html.escape(manifest["language"])}"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:identifier id="book-id">{identifier}</dc:identifier><dc:title>{html.escape(manifest["title"])}</dc:title><dc:language>{html.escape(manifest["language"])}</dc:language><dc:creator>{html.escape(manifest["brand"])}</dc:creator><meta property="dcterms:modified">{MODIFIED}</meta></metadata><manifest>{"".join(manifest_items)}</manifest><spine>{spine_items}</spine></package>')
    container = '<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    with zipfile.ZipFile(target, "w") as archive:
        zip_write(archive, "mimetype", b"application/epub+zip", True)
        zip_write(archive, "META-INF/container.xml", container.encode())
        zip_write(archive, "OEBPS/content.opf", opf.encode())
        zip_write(archive, "OEBPS/nav.xhtml", nav.encode())
        zip_write(archive, "OEBPS/styles/book.css", CSS.encode())
        cover_path = book.get("cover_image")
        cover = inside(root, root / cover_path, "book.toml cover_image").read_bytes() if cover_path else _cover(manifest["title"], manifest["brand"], cover_font(book)[0])
        zip_write(archive, "OEBPS/images/cover.png", cover)
        for slug, _ in spine:
            zip_write(archive, f"OEBPS/text/{slug}.xhtml", pages[slug].encode())
        for path in media_files:
            source_id = path.parent.name
            zip_write(archive, f"OEBPS/text/media/{source_id}/{path.name}", path.read_bytes())


def build(root: Path, draft: bool = False) -> tuple[Path, dict]:
    book, manifest = load(root)
    records_path = root / "sources" / "records.json"
    if not records_path.exists():
        raise FileNotFoundError("run quoin fetch first")
    records = read_json(records_path, {})
    blocks, placeholders = read_for_build(root, manifest, draft)
    out = root / "out"
    target = out / f"{manifest['slug']}.epub"
    cache_path, record_path = out / "cache.json", out / "build-record.json"
    cache, stages = read_json(cache_path, {}), {}
    source_paths = [root / "sources" / "normalized" / f"{source['id']}.xhtml" for source in manifest["sources"]]
    block_paths = [root / "blocks" / f"{block['id']}.json" for block in manifest["blocks"]]
    media_paths = sorted(
        path
        for source in manifest["sources"]
        for path in (root / "sources" / "media" / source["id"]).glob("*")
        if path.name != "index.json"
    )
    extra_inputs = {"draft": str(draft), "quoin_version": __version__}
    cover_image = book.get("cover_image")
    if cover_image:
        extra_inputs["cover_image"] = file_hash(inside(root, root / cover_image, "book.toml cover_image"))
    else:
        extra_inputs["cover_font"] = file_hash(cover_font(book)[0])
    inputs = hashes(root, [root / "book.toml", root / "manifest.json", records_path, *source_paths, *block_paths, *media_paths], extra_inputs)
    hit, _ = run_stage("assemble", inputs, cache, stages, target.exists(), lambda: assemble(root, target, manifest, book, blocks, records))
    normalization = read_json(root / "sources" / "normalization.json", {"notes": []})
    record = {"format_version": 1, "stages": stages, "placeholders": placeholders, "epub_sha256": file_hash(target), "draft": draft, "normalization_notes": normalization["notes"]}
    write_json(record_path, record)
    write_json(cache_path, cache)
    return target, record
