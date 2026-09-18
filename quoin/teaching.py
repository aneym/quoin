"""Opt-in version-2 teaching semantics. Version-1 books retain their contract."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

TEACHING_KINDS = {"lesson", "exercise", "answer", "debrief"}
ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
SHA = re.compile(r"^[a-f0-9]{64}$")


def string_ids(value) -> bool:
    return (
        isinstance(value, list)
        and bool(value)
        and all(isinstance(v, str) and ID.fullmatch(v) for v in value)
        and len(set(value)) == len(value)
    )


def validate_teaching(manifest: dict) -> list[str]:
    """Called only after basic manifest validation succeeds."""
    if manifest.get("format_version") != 2:
        return []
    errors = []
    if "series" in manifest and (
        not isinstance(manifest["series"], str) or not manifest["series"].strip()
    ):
        errors.append("series must be a nonempty string")
    blocks = {b["id"]: b for b in manifest["blocks"]}
    sources = {s["id"]: s for s in manifest["sources"]}
    ordered = [i["ref"] for m in manifest["movements"] for i in m["items"]]
    counts = Counter(ordered)
    figures = set()
    for block in blocks.values():
        bid = block["id"]
        if counts[f"block:{bid}"] != 1:
            errors.append(f"block {bid} must be referenced exactly once")
        if not isinstance(block.get("editorial_ref"), str) or not block["editorial_ref"].strip():
            errors.append(f"block {bid} requires editorial_ref to its canonical editorial record")
        if block["kind"] in {"exercise", "answer"}:
            group = block.get("recall_group")
            if not isinstance(group, str) or not ID.fullmatch(group):
                errors.append(f"block {bid} requires a safe recall_group")
        if block["kind"] == "answer":
            if not string_ids(block.get("answers")):
                errors.append(f"answer {bid} requires unique exercise ids in answers")
        elif "answers" in block:
            errors.append(f"block {bid}: answers is only valid on answer blocks")
        if "introduces" in block:
            if block["kind"] != "introduction" or not string_ids(block["introduces"]):
                errors.append(
                    f"block {bid}: introduces requires an introduction and unique person ids"
                )
        if "figures" in block:
            if not isinstance(block["figures"], list):
                errors.append(f"block {bid}: figures must be a list")
                continue
            for figure in block["figures"]:
                if not isinstance(figure, dict):
                    errors.append(f"block {bid}: figure must be an object")
                    continue
                fid = figure.get("id")
                if not isinstance(fid, str) or not ID.fullmatch(fid) or fid in figures:
                    errors.append(f"block {bid}: figure id must be safe and globally unique")
                else:
                    figures.add(fid)
                path = figure.get("path")
                if (
                    not isinstance(path, str)
                    or not path
                    or Path(path).is_absolute()
                    or ".." in Path(path).parts
                    or Path(path).suffix.lower() not in {".png", ".jpg", ".jpeg"}
                ):
                    errors.append(f"block {bid}: figure path must be a local PNG or JPEG")
                if not isinstance(figure.get("sha256"), str) or not SHA.fullmatch(figure["sha256"]):
                    errors.append(f"block {bid}: figure requires sha256")
                for key in ("alt", "caption"):
                    if not isinstance(figure.get(key), str) or len(figure[key].strip()) < 8:
                        errors.append(f"block {bid}: figure requires descriptive {key}")
    for declaration in [*blocks.values(), *sources.values()]:
        if "contributors" in declaration and not string_ids(declaration["contributors"]):
            errors.append(f"{declaration['id']}: contributors requires unique person ids")
    if errors:
        return errors
    errors.extend(recall_errors(manifest, ordered))
    full_order = [
        ref
        for m in manifest["movements"]
        for ref in ["movement:" + m["id"], *[i["ref"] for i in m["items"]]]
    ]
    errors.extend(adjacency_errors(manifest, full_order))
    return errors


def recall_errors(manifest: dict, ordered: list[str]) -> list[str]:
    if manifest.get("format_version") != 2:
        return []
    blocks = {b["id"]: b for b in manifest["blocks"]}
    pos = {ref: i for i, ref in enumerate(ordered)}
    exercises = {bid: b for bid, b in blocks.items() if b["kind"] == "exercise"}
    covered: Counter = Counter()
    errors = []
    for bid, block in blocks.items():
        if block["kind"] != "answer":
            continue
        for eid in block["answers"]:
            if eid not in exercises:
                errors.append(f"answer {bid} names unknown exercise {eid}")
            elif exercises[eid]["recall_group"] != block["recall_group"]:
                errors.append(f"answer {bid} crosses recall_group for {eid}")
            else:
                covered[eid] += 1
        group = [eid for eid, e in exercises.items() if e["recall_group"] == block["recall_group"]]
        if any(
            pos.get(f"block:{eid}", float("inf")) >= pos.get(f"block:{bid}", -1) for eid in group
        ):
            errors.append(f"answer {bid} must follow every exercise in its recall_group")
    for eid in exercises:
        if covered[eid] != 1:
            errors.append(f"exercise {eid} requires exactly one answer; found {covered[eid]}")
    return errors


def adjacency_errors(manifest: dict, ordered: list[str]) -> list[str]:
    if manifest.get("format_version") != 2:
        return []
    declarations = {f"block:{b['id']}": b for b in manifest["blocks"]}
    declarations.update({f"source:{s['id']}": s for s in manifest["sources"]})
    seen: set[str] = set()
    consumed: set[str] = set()
    errors = []
    for index, ref in enumerate(ordered):
        declaration = declarations.get(ref, {})
        first = set(declaration.get("contributors", [])) - seen
        if not first:
            continue
        prior = index - 1
        introductions = []
        while prior >= 0:
            intro = declarations.get(ordered[prior], {})
            if intro.get("kind") != "introduction":
                break
            introductions.extend(intro.get("introduces", []))
            consumed.add(ordered[prior])
            prior -= 1
        if Counter(introductions) != Counter(first):
            errors.append(
                f"{ref}: first contributors require exactly one adjacent introduction each"
            )
        seen.update(first)
    for ref, declaration in declarations.items():
        if declaration.get("introduces") and ref not in consumed:
            errors.append(f"{ref}: duplicate or unused contributor introduction")
    return errors


def figure_files(root: Path, manifest: dict) -> list[tuple[dict, Path]]:
    from .manifest import inside

    if manifest.get("format_version") != 2:
        return []
    result = []
    for block in manifest["blocks"]:
        for figure in block.get("figures", []):
            inside(root, root / figure["path"], "figure path")
            result.append((figure, root / figure["path"]))
    return result


def validate_assets(root: Path, manifest: dict, book: dict) -> None:
    from .errors import QuoinError
    from .manifest import inside

    if manifest.get("format_version") != 2:
        return
    if not book.get("cover_image"):
        raise QuoinError("version 2 requires a designed book.toml cover_image")
    cover = inside(root, root / book["cover_image"], "cover_image")
    with Image.open(cover) as image:
        if image.format != "PNG":
            raise QuoinError("cover_image must be PNG")
        image.verify()
    for figure, path in figure_files(root, manifest):
        if hashlib.sha256(path.read_bytes()).hexdigest() != figure["sha256"]:
            raise QuoinError(f"figure {figure['id']}: sha256 mismatch")
        with Image.open(path) as image:
            expected = "PNG" if path.suffix.lower() == ".png" else "JPEG"
            if image.format != expected:
                raise QuoinError(f"figure {figure['id']}: media type mismatch")
            image.verify()


def authored_html_errors(markup: str) -> list[str]:
    """V2 blocks cannot add hidden reveals or undeclared media/execution."""
    try:
        tree = ET.fromstring(f"<root>{markup}</root>")
    except ET.ParseError as exc:
        return [f"invalid XHTML: {exc}"]
    allowed = {
        "p",
        "h2",
        "h3",
        "h4",
        "ul",
        "ol",
        "li",
        "blockquote",
        "pre",
        "code",
        "em",
        "strong",
        "b",
        "i",
        "span",
        "a",
        "br",
        "hr",
        "table",
        "thead",
        "tbody",
        "tr",
        "td",
        "th",
        "caption",
        "dl",
        "dt",
        "dd",
        "sup",
        "sub",
        "div",
    }
    allowed_attrs = {"id", "lang", "title", "href", "colspan", "rowspan", "scope"}
    errors = []
    for element in tree.iter():
        if element is tree:
            continue
        tag = element.tag.rsplit("}", 1)[-1]
        if tag not in allowed:
            errors.append(f"{tag} is not allowed in version-2 authored HTML; declare figures")
        for attr, value in element.attrib.items():
            key = attr.rsplit("}", 1)[-1].lower()
            if key not in allowed_attrs:
                errors.append(f"attribute {key} is not allowed in version-2 authored HTML")
            if key == "href":
                from urllib.parse import urlsplit

                normalized = re.sub(r"[\x00-\x20\x7f]", "", value).lower()
                scheme = urlsplit(normalized).scheme
                if scheme not in ("", "http", "https", "mailto") or normalized.startswith("//"):
                    errors.append("unsafe authored link")
    return errors
