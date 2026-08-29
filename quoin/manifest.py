from __future__ import annotations

import json
import tomllib
from pathlib import Path


class ManifestError(ValueError):
    pass


def root(path: Path | None = None) -> Path:
    return (path or Path.cwd()).resolve()


def load(root_dir: Path) -> tuple[dict, dict]:
    book_path = root_dir / "book.toml"
    manifest_path = root_dir / "manifest.json"
    if not book_path.is_file() or not manifest_path.is_file():
        raise ManifestError("book.toml and manifest.json are required")
    with book_path.open("rb") as handle:
        book = tomllib.load(handle)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    required = {"format_version", "slug", "title", "brand", "language", "governing_question", "privacy", "sources", "movements", "blocks"}
    missing = sorted(required - manifest.keys())
    if missing:
        raise ManifestError(f"manifest fields missing: {', '.join(missing)}")
    if manifest["format_version"] != 1:
        raise ManifestError("manifest format_version must be 1")
    return book, manifest


def source_map(manifest: dict) -> dict[str, dict]:
    return {source["id"]: source for source in manifest["sources"]}


def block_map(manifest: dict) -> dict[str, dict]:
    return {block["id"]: block for block in manifest["blocks"]}
