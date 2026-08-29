from __future__ import annotations

import json
import tomllib
from pathlib import Path
from urllib.parse import urlparse

from .errors import ManifestError

REQUIRED = ("format_version", "slug", "title", "brand", "language", "governing_question", "privacy", "sources", "movements", "blocks")
SOURCE_TYPES = {"web", "epub", "file"}
BLOCK_KINDS = {"title_deck", "introduction", "interlude", "cover_copy"}


def root(path: Path | None = None) -> Path:
    return (path or Path.cwd()).resolve()


def validate(manifest) -> list[str]:
    errors: list[str] = []
    prefix = "manifest.json: "
    if not isinstance(manifest, dict):
        return [prefix + "document must be an object"]
    for key in REQUIRED:
        if key not in manifest:
            errors.append(prefix + f"{key} is required")
    if manifest.get("format_version") != 1:
        errors.append(prefix + "format_version must be 1")
    for key in ("slug", "title", "brand", "language", "governing_question"):
        if key in manifest and not isinstance(manifest[key], str):
            errors.append(prefix + f"{key} must be a string")
    privacy = manifest.get("privacy")
    if privacy is not None:
        if not isinstance(privacy, dict):
            errors.append(prefix + "privacy must be an object")
        elif "forbidden_terms" not in privacy:
            errors.append(prefix + "privacy.forbidden_terms is required")
        elif not isinstance(privacy["forbidden_terms"], list) or not all(isinstance(item, str) for item in privacy["forbidden_terms"]):
            errors.append(prefix + "privacy.forbidden_terms must be a list of strings")

    sources = manifest.get("sources")
    source_ids: set[str] = set()
    if sources is not None and not isinstance(sources, list):
        errors.append(prefix + "sources must be a list")
    elif isinstance(sources, list):
        for index, source in enumerate(sources):
            path = f"sources[{index}]"
            if not isinstance(source, dict):
                errors.append(prefix + f"{path} must be an object")
                continue
            for key in ("id", "type", "locator"):
                if key not in source:
                    errors.append(prefix + f"{path}.{key} is required")
            identifier = source.get("id")
            if identifier is not None and not isinstance(identifier, str):
                errors.append(prefix + f"{path}.id must be a string")
            elif identifier in source_ids:
                errors.append(prefix + f"{path}.id duplicates {identifier}")
            elif isinstance(identifier, str):
                source_ids.add(identifier)
            source_type = source.get("type")
            if source_type not in SOURCE_TYPES:
                errors.append(prefix + f"{path}.type must be one of web, epub, file")
            locator = source.get("locator")
            if locator is not None and not isinstance(locator, str):
                errors.append(prefix + f"{path}.locator must be a string")
            if source_type == "web" and isinstance(locator, str) and urlparse(locator).scheme not in {"http", "https"}:
                errors.append(prefix + f"{path}.locator must be an http or https URL")
            if source_type == "epub":
                chapter_locator = source.get("chapter_locator")
                if chapter_locator is None:
                    errors.append(prefix + f"{path}.chapter_locator is required for epub sources")
                elif isinstance(chapter_locator, str):
                    pass
                elif not isinstance(chapter_locator, list) or not all(isinstance(item, str) for item in chapter_locator):
                    errors.append(prefix + f"{path}.chapter_locator must be a string or list of strings")

    blocks = manifest.get("blocks")
    block_ids: set[str] = set()
    if blocks is not None and not isinstance(blocks, list):
        errors.append(prefix + "blocks must be a list")
    elif isinstance(blocks, list):
        for index, block in enumerate(blocks):
            path = f"blocks[{index}]"
            if not isinstance(block, dict):
                errors.append(prefix + f"{path} must be an object")
                continue
            for key in ("id", "kind", "brief", "evidence"):
                if key not in block:
                    errors.append(prefix + f"{path}.{key} is required")
            identifier = block.get("id")
            if identifier is not None and not isinstance(identifier, str):
                errors.append(prefix + f"{path}.id must be a string")
            elif identifier in block_ids:
                errors.append(prefix + f"{path}.id duplicates {identifier}")
            elif isinstance(identifier, str):
                block_ids.add(identifier)
            if block.get("kind") not in BLOCK_KINDS:
                errors.append(prefix + f"{path}.kind must be one of title_deck, introduction, interlude, cover_copy")
            if "brief" in block and not isinstance(block["brief"], str):
                errors.append(prefix + f"{path}.brief must be a string")
            if "evidence" in block and not isinstance(block["evidence"], list):
                errors.append(prefix + f"{path}.evidence must be a list")

    movements = manifest.get("movements")
    movement_ids: set[str] = set()
    if movements is not None and not isinstance(movements, list):
        errors.append(prefix + "movements must be a list")
    elif isinstance(movements, list):
        for movement_index, movement in enumerate(movements):
            path = f"movements[{movement_index}]"
            if not isinstance(movement, dict):
                errors.append(prefix + f"{path} must be an object")
                continue
            for key in ("id", "title", "items"):
                if key not in movement:
                    errors.append(prefix + f"{path}.{key} is required")
            identifier = movement.get("id")
            if identifier in movement_ids:
                errors.append(prefix + f"{path}.id duplicates {identifier}")
            elif isinstance(identifier, str):
                movement_ids.add(identifier)
            elif identifier is not None:
                errors.append(prefix + f"{path}.id must be a string")
            if "title" in movement and not isinstance(movement["title"], str):
                errors.append(prefix + f"{path}.title must be a string")
            items = movement.get("items")
            if items is not None and not isinstance(items, list):
                errors.append(prefix + f"{path}.items must be a list")
                continue
            for item_index, item in enumerate(items or []):
                item_path = f"{path}.items[{item_index}]"
                if not isinstance(item, dict) or not isinstance(item.get("ref"), str):
                    errors.append(prefix + f"{item_path}.ref must be a string")
                    continue
                ref = item["ref"]
                kind, separator, identifier = ref.partition(":")
                known = source_ids if kind == "source" else block_ids if kind == "block" else set()
                if not separator or identifier not in known:
                    errors.append(prefix + f"{item_path}.ref names unknown reference {ref}")
    return errors


def validate_block(block, expected_id: str | None = None, expected_kind: str | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(block, dict):
        return ["block JSON must be an object"]
    for key in ("block_id", "kind", "title", "html"):
        if key not in block:
            errors.append(f"{key} is required")
        elif not isinstance(block[key], str):
            errors.append(f"{key} must be a string")
    if block.get("kind") not in BLOCK_KINDS:
        errors.append("kind must be one of title_deck, introduction, interlude, cover_copy")
    if expected_id is not None and block.get("block_id") != expected_id:
        errors.append(f"block_id must equal {expected_id}")
    if expected_kind is not None and block.get("kind") != expected_kind:
        errors.append(f"kind must equal {expected_kind}")
    return errors


def load(root_dir: Path) -> tuple[dict, dict]:
    book_path = root_dir / "book.toml"
    manifest_path = root_dir / "manifest.json"
    if not book_path.is_file() and not manifest_path.is_file():
        raise ManifestError(f"not a book directory: run quoin init {root_dir} or cd into a book directory")
    if not book_path.is_file() or not manifest_path.is_file():
        missing = "book.toml" if not book_path.is_file() else "manifest.json"
        raise ManifestError(f"{missing} is required")
    try:
        with book_path.open("rb") as handle:
            book = tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise ManifestError(f"book.toml: {exc}") from exc
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"manifest.json: {exc}") from exc
    errors = validate(manifest)
    if errors:
        raise ManifestError("\n".join(errors))
    return book, manifest


def source_map(manifest: dict) -> dict[str, dict]:
    return {source["id"]: source for source in manifest["sources"]}


def block_map(manifest: dict) -> dict[str, dict]:
    return {block["id"]: block for block in manifest["blocks"]}
