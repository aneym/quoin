from __future__ import annotations

import glob
import json
import shutil
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

from .manifest import load
from .normalize import extract_article, normalized_path, word_count, xhtml
from .record import sha256_bytes, write_json

UA = "quoin/0.1 (+deterministic book compiler)"


def _raw_path(root: Path, source: dict) -> Path:
    suffix = ".html" if source["type"] == "web" else Path(source["locator"]).suffix or ".bin"
    return root / "sources" / "raw" / f"{source['id']}{suffix}"


def _fetch_web(root: Path, source: dict, offline: bool) -> tuple[bytes, int, str]:
    raw_path = _raw_path(root, source)
    if raw_path.exists():
        return raw_path.read_bytes(), 200, str(raw_path.relative_to(root))
    if offline:
        raise FileNotFoundError(f"offline raw source missing: {source['id']}")
    request = urllib.request.Request(source["locator"], headers={"User-Agent": UA})
    with urllib.request.urlopen(request) as response:
        data, status = response.read(), response.status
    digest = sha256_bytes(data)
    raw_path = root / "sources" / "raw" / f"{source['id']}-{digest}.html"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(data)
    return data, status, str(raw_path.relative_to(root))


def _epub_files(source: dict, names: list[str]) -> list[str]:
    locator = source.get("chapter_locator")
    if isinstance(locator, list):
        return locator
    if isinstance(locator, str):
        return [name for name in names if Path(name).match(locator)]
    raise ValueError(f"epub source needs chapter_locator: {source['id']}")


def _normalize_epub(root: Path, source: dict, epub_path: Path) -> tuple[str, list[str]]:
    pieces: list[str] = []
    media_names: list[str] = []
    with zipfile.ZipFile(epub_path) as archive:
        names = archive.namelist()
        selected = _epub_files(source, names)
        if not selected:
            raise ValueError(f"chapter locator matched no files: {source['id']}")
        for index, name in enumerate(selected):
            markup = archive.read(name).decode("utf-8")
            body = __import__("quoin.normalize", fromlist=["body_inner"]).body_inner(markup)
            body = __import__("re").sub(r'\bid=(["\'])([^"\']+)\1', lambda match: f'id={match.group(1)}q{index}-{match.group(2)}{match.group(1)}', body, flags=__import__("re").I)
            body = __import__("re").sub(r'\bhref=(["\'])#([^"\']+)\1', lambda match: f'href={match.group(1)}#q{index}-{match.group(2)}{match.group(1)}', body, flags=__import__("re").I)
            base = Path(name).parent
            for ref in __import__("re").findall(r'<img\b[^>]*\bsrc=["\']([^"\']+)', body, __import__("re").I):
                archive_name = str((base / ref).as_posix())
                archive_name = str(Path(archive_name))
                while archive_name.startswith("../"):
                    archive_name = archive_name[3:]
                candidates = [n for n in names if n.endswith(Path(ref).name)]
                if not candidates:
                    raise ValueError(f"referenced image missing: {ref}")
                member = candidates[0]
                media_dir = root / "sources" / "normalized" / f"{source['id']}_media"
                media_dir.mkdir(parents=True, exist_ok=True)
                target = media_dir / Path(member).name
                target.write_bytes(archive.read(member))
                body = body.replace(ref, f"{source['id']}_media/{target.name}")
                media_names.append(str(target.relative_to(root)))
            pieces.append(body)
    return "\n".join(pieces), media_names


def run(root: Path, offline: bool = False) -> dict:
    _, manifest = load(root)
    records: dict[str, dict] = {}
    normalized_dir = root / "sources" / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    for source in manifest["sources"]:
        source_type = source["type"]
        if source_type == "web":
            raw, status, stored = _fetch_web(root, source, offline)
            body = extract_article(raw.decode("utf-8"))
            media: list[str] = []
        elif source_type == "epub":
            epub_path = (root / source["locator"]).resolve() if not Path(source["locator"]).is_absolute() else Path(source["locator"])
            if not epub_path.exists():
                raise FileNotFoundError(f"epub source missing: {source['id']}")
            raw, status, stored = epub_path.read_bytes(), 200, str(epub_path)
            body, media = _normalize_epub(root, source, epub_path)
        elif source_type == "file":
            path = (root / source["locator"]).resolve()
            raw, status, stored = path.read_bytes(), 200, str(path.relative_to(root))
            body, media = extract_article(raw.decode("utf-8")), []
        else:
            raise ValueError(f"unsupported source type: {source_type}")
        document = xhtml(source.get("title", source["id"]), f'<main class="source">{body}</main>')
        normalized_path(root, source["id"]).write_text(document, encoding="utf-8")
        records[source["id"]] = {
            "id": source["id"], "type": source_type, "url": source["locator"],
            "date": date.today().isoformat(), "bytes": len(raw), "sha256": sha256_bytes(raw),
            "http_status": status, "stored_path": stored, "word_count": word_count(body), "media": media,
            "rights": source.get("rights", {}),
        }
    write_json(root / "sources" / "records.json", records)
    return records
