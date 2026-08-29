from __future__ import annotations

import re
import urllib.parse
import urllib.request
import zipfile
from datetime import date
from pathlib import Path

from .errors import QuoinError
from .manifest import inside, load
from .normalize import (
    DECLARED_EXT_TYPE,
    MEDIA_EXT,
    body_inner,
    extract_article,
    is_ornamental,
    normalized_path,
    rewrite_images,
    sniff_image_type,
    validate_xhtml,
    word_count,
    xhtml,
)
from .record import read_json, sha256_bytes, write_json

UA = "quoin/0.2 (+deterministic book compiler)"
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


def _media_dir(root: Path, source_id: str) -> Path:
    """Namespaced media store: sources/media/<source_id>/ — one directory per
    source so two sources referencing an image named the same way (e.g. both
    donating "figure1.png") never collide (plan 005 Step 1)."""
    return root / "sources" / "media" / source_id


def _safe_stem(src: str) -> str:
    name = urllib.parse.urlsplit(src).path if "://" in src else src
    stem = Path(name.split("?", 1)[0]).stem or "image"
    return re.sub(r"[^A-Za-z0-9._-]", "_", stem) or "image"


def _store_media(media_dir: Path, stem: str, ext: str, data: bytes) -> str:
    """Write data under media_dir named <stem>.<ext>, deduplicating identical bytes
    and disambiguating a same-name/different-bytes collision with a digest suffix."""
    media_dir.mkdir(parents=True, exist_ok=True)
    digest = sha256_bytes(data)
    candidate = f"{stem}.{ext}"
    target = media_dir / candidate
    if target.exists() and sha256_bytes(target.read_bytes()) != digest:
        candidate = f"{stem}-{digest[:8]}.{ext}"
        target = media_dir / candidate
    if not target.exists():
        target.write_bytes(data)
    return candidate


def _classify_and_store(
    media_dir: Path, index: dict, cache_key: str, src: str, data: bytes, source_id: str, notes: list[str]
) -> str | None:
    """Shared tail of every image resolver: sniff, reject malformed/ornamental,
    store namespaced, and record in the per-source index.json. Returns the stored
    filename, or None if the image was dropped (a note is always appended in that case)."""
    sniffed = sniff_image_type(data)
    if sniffed is None:
        notes.append(f"{source_id}: unrecognized/malformed image type, dropped: {src}")
        return None
    declared_ext = Path(src.split("?", 1)[0]).suffix.lstrip(".").lower()
    if declared_ext in DECLARED_EXT_TYPE and DECLARED_EXT_TYPE[declared_ext] != sniffed:
        notes.append(f"{source_id}: {src} declared .{declared_ext} but sniffed as {sniffed}")
    if is_ornamental(data, sniffed):
        notes.append(f"{source_id}: ornamental image dropped: {src}")
        return None
    cached = index.get(cache_key)
    if cached and (media_dir / cached["file"]).exists() and sha256_bytes((media_dir / cached["file"]).read_bytes()) == sha256_bytes(data):
        stored_name = cached["file"]
    else:
        stored_name = _store_media(media_dir, _safe_stem(src), MEDIA_EXT[sniffed], data)
    index[cache_key] = {"file": stored_name, "sha256": sha256_bytes(data), "sniffed_type": sniffed}
    return stored_name


def _process_images(
    root: Path, source: dict, body: str, offline: bool, notes: list[str], base_dir: Path | None = None
) -> tuple[str, list[str]]:
    """Snapshot every <img> in body for a web/file source into its namespaced media
    dir, rewrite src to the packaged path, and drop what can't be resolved (with a
    note). Remote images are downloaded once and cached via index.json so re-fetches
    and --offline runs reuse the same bytes (plan 005 Step 2)."""
    source_id = source["id"]
    media_dir = _media_dir(root, source_id)
    index_path = media_dir / "index.json"
    index = read_json(index_path, {})
    alt_overrides = source.get("alt_overrides", {})
    media_names: list[str] = []

    def resolver(src: str, alt: str) -> tuple[str, str] | None:
        if not src:
            return None
        cache_key = src
        cached = index.get(cache_key)
        data: bytes | None = None
        if cached and (media_dir / cached["file"]).exists():
            data = (media_dir / cached["file"]).read_bytes()
        elif src.startswith(("http://", "https://")):
            if offline:
                notes.append(f"{source_id}: offline, no snapshot for {src}")
                return None
            try:
                request = urllib.request.Request(src, headers={"User-Agent": UA})
                with urllib.request.urlopen(request, timeout=30) as response:
                    data = response.read(MAX_DOWNLOAD_BYTES + 1)
            except Exception as exc:
                notes.append(f"{source_id}: image download failed for {src}: {exc}")
                return None
            if len(data) > MAX_DOWNLOAD_BYTES:
                notes.append(f"{source_id}: image exceeds download limit: {src}")
                return None
        elif base_dir is not None:
            local = (base_dir / src).resolve()
            if base_dir.resolve() not in local.parents and local != base_dir.resolve():
                notes.append(f"{source_id}: local image escapes source directory, dropped: {src}")
                return None
            if not local.exists():
                notes.append(f"{source_id}: local image missing, dropped: {src}")
                return None
            data = local.read_bytes()
        else:
            notes.append(f"{source_id}: relative image with no local base, dropped: {src}")
            return None

        stored_name = _classify_and_store(media_dir, index, cache_key, src, data, source_id, notes)
        if stored_name is None:
            return None
        media_names.append(str((media_dir / stored_name).relative_to(root)))
        return f"media/{source_id}/{stored_name}", alt_overrides.get(src, alt)

    result = rewrite_images(body, resolver)
    if index:
        write_json(index_path, index)
    return result, sorted(set(media_names))


def _raw_path(root: Path, source: dict) -> Path:
    suffix = ".html" if source["type"] == "web" else Path(source["locator"]).suffix or ".bin"
    return root / "sources" / "raw" / f"{source['id']}{suffix}"


def _fetch_web(root: Path, source: dict, offline: bool) -> tuple[bytes, int, str]:
    raw_path = _raw_path(root, source)
    candidates = [raw_path, *sorted((root / "sources" / "raw").glob(f"{source['id']}-*.html"))]
    for candidate in candidates:
        if candidate.exists():
            return candidate.read_bytes(), 200, str(candidate.relative_to(root))
    if offline:
        raise FileNotFoundError(f"offline raw source missing: {source['id']}")
    request = urllib.request.Request(source["locator"], headers={"User-Agent": UA})
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read(MAX_DOWNLOAD_BYTES + 1)
        status = response.status
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise QuoinError(f"web source exceeds 20 MB download limit: {source['id']}")
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


def _normalize_epub(root: Path, source: dict, epub_path: Path, offline: bool, notes: list[str]) -> tuple[str, list[str]]:
    source_id = source["id"]
    media_dir = _media_dir(root, source_id)
    index_path = media_dir / "index.json"
    index = read_json(index_path, {})
    alt_overrides = source.get("alt_overrides", {})
    pieces: list[str] = []
    media_names: list[str] = []
    with zipfile.ZipFile(epub_path) as archive:
        names = archive.namelist()
        selected = _epub_files(source, names)
        if not selected:
            raise ValueError(f"chapter locator matched no files: {source_id}")
        for chapter_index, name in enumerate(selected):
            markup = archive.read(name).decode("utf-8")
            body = body_inner(markup)
            body = re.sub(r'\bid=(["\'])([^"\']+)\1', lambda match: f'id={match.group(1)}q{chapter_index}-{match.group(2)}{match.group(1)}', body, flags=re.I)
            body = re.sub(r'\bhref=(["\'])#([^"\']+)\1', lambda match: f'href={match.group(1)}#q{chapter_index}-{match.group(2)}{match.group(1)}', body, flags=re.I)
            body = re.sub(r'\s+(?:epub:[\w-]+|aria-[\w-]+)=["\'][^"\']*["\']', "", body, flags=re.I)
            body = re.sub(r'<a\b[^>]*\bhref=["\'](?!#)[^"\']+["\'][^>]*>(.*?)</a\s*>', r'\1', body, flags=re.I | re.S)
            base = Path(name).parent

            def resolver(src: str, alt: str, base: Path = base) -> tuple[str, str] | None:
                if not src:
                    return None
                if src.startswith(("http://", "https://")):
                    # hotlinked image inside an epub chapter (plan 005 Step 1: route
                    # through the same download/snapshot path instead of aborting fetch)
                    cache_key = src
                    cached = index.get(cache_key)
                    if cached and (media_dir / cached["file"]).exists():
                        data = (media_dir / cached["file"]).read_bytes()
                    elif offline:
                        notes.append(f"{source_id}: offline, no snapshot for hotlinked {src}")
                        return None
                    else:
                        try:
                            request = urllib.request.Request(src, headers={"User-Agent": UA})
                            with urllib.request.urlopen(request, timeout=30) as response:
                                data = response.read(MAX_DOWNLOAD_BYTES + 1)
                        except Exception as exc:
                            notes.append(f"{source_id}: hotlinked image download failed for {src}: {exc}")
                            return None
                        if len(data) > MAX_DOWNLOAD_BYTES:
                            notes.append(f"{source_id}: hotlinked image exceeds download limit: {src}")
                            return None
                else:
                    archive_name = str(Path((base / src).as_posix()))
                    while archive_name.startswith("../"):
                        archive_name = archive_name[3:]
                    if archive_name in names:
                        member = archive_name
                    else:
                        candidates = [n for n in names if n.endswith(Path(src).name)]
                        if not candidates:
                            notes.append(f"{source_id}: referenced image missing, dropped: {src}")
                            return None
                        member = candidates[0]
                        notes.append(f"{source_id}: {src} not found by exact archive path, matched by basename to {member}")
                    cache_key = member
                    cached = index.get(cache_key)
                    if cached and (media_dir / cached["file"]).exists():
                        data = (media_dir / cached["file"]).read_bytes()
                    else:
                        data = archive.read(member)

                stored_name = _classify_and_store(media_dir, index, cache_key, src, data, source_id, notes)
                if stored_name is None:
                    return None
                relative = str((media_dir / stored_name).relative_to(root))
                if relative not in media_names:
                    media_names.append(relative)
                return f"media/{source_id}/{stored_name}", alt_overrides.get(src, alt)

            body = rewrite_images(body, resolver)
            pieces.append(body)
    if index:
        write_json(index_path, index)
    return "\n".join(pieces), media_names


def run(root: Path, offline: bool = False) -> dict:
    _, manifest = load(root)
    records: dict[str, dict] = {}
    normalization_notes: list[str] = []
    normalized_dir = root / "sources" / "normalized"
    normalized_dir.mkdir(parents=True, exist_ok=True)
    for source in manifest["sources"]:
        source_type = source["type"]
        if source_type == "web":
            raw, status, stored = _fetch_web(root, source, offline)
            body = extract_article(raw.decode("utf-8"))
            body, media = _process_images(root, source, body, offline, normalization_notes)
        elif source_type == "epub":
            epub_path = (root / source["locator"]).resolve() if not Path(source["locator"]).is_absolute() else Path(source["locator"]).resolve()
            if not epub_path.exists():
                raise FileNotFoundError(f"epub source missing: {source['id']}")
            raw, status, stored = epub_path.read_bytes(), 200, str(epub_path)
            body, media = _normalize_epub(root, source, epub_path, offline, normalization_notes)
        elif source_type == "file":
            path = inside(root, root / source["locator"], f"file source locator for {source['id']}")
            raw, status, stored = path.read_bytes(), 200, str(path.relative_to(root.resolve()))
            body = extract_article(raw.decode("utf-8"))
            body, media = _process_images(root, source, body, offline, normalization_notes, base_dir=path.parent)
        else:
            raise ValueError(f"unsupported source type: {source_type}")
        document = xhtml(source.get("title", source["id"]), f'<main class="source">{body}</main>')
        try:
            validate_xhtml(document)
        except Exception as exc:
            raise QuoinError(f"normalized document for {source['id']} is not well-formed XML: {exc}") from exc
        normalized_path(root, source["id"]).write_text(document, encoding="utf-8")
        records[source["id"]] = {
            "id": source["id"], "type": source_type, "url": source["locator"],
            "date": date.today().isoformat(), "bytes": len(raw), "sha256": sha256_bytes(raw),
            "http_status": status, "stored_path": stored, "word_count": word_count(body), "media": media,
            "rights": source.get("rights", {}),
            **({"external_input": {"path": str(epub_path), "sha256": sha256_bytes(raw)}} if source_type == "epub" and root.resolve() not in epub_path.parents else {}),
        }
    write_json(root / "sources" / "records.json", records)
    write_json(root / "sources" / "normalization.json", {"notes": normalization_notes})
    return records
