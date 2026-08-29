from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree as ET

from .manifest import load, validate_block

SCHEMAS_DIR = Path(__file__).parent / "schemas"


def _schema(name: str) -> dict:
    return json.loads((SCHEMAS_DIR / name).read_text(encoding="utf-8"))


def _block_example(declaration: dict) -> dict:
    return {
        "block_id": declaration["id"],
        "kind": declaration["kind"],
        "title": "Working title",
        "html": "<p>Two plain, concrete sentences drawn from the evidence, no em dashes.</p>",
    }


def _stylepass_example(declaration: dict) -> dict:
    return {
        "block_id": declaration["id"],
        "changed": True,
        "findings": ["removed one adverb", "shortened a run-on sentence"],
        "claims": [
            {
                "claim": "The workshop ran for three seasons.",
                "support": '"now in its third season" (evidence file, line 4)',
            }
        ],
    }


def status(root: Path, declaration: dict) -> tuple[str, str | None]:
    path = root / "blocks" / f"{declaration['id']}.json"
    if not path.exists():
        return "missing", None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        errors = validate_block(data, declaration["id"], declaration["kind"])
        if errors:
            raise ValueError("; ".join(errors))
        if "<script" in data["html"].lower():
            raise ValueError("script is not allowed")
        ET.fromstring(f'<root xmlns="http://www.w3.org/1999/xhtml">{data["html"]}</root>')
        return "present", None
    except Exception as exc:
        return "invalid", str(exc)


def work_orders(root: Path, missing_only: bool = False) -> list[dict]:
    _, manifest = load(root)
    block_schema = _schema("block.schema.json")
    stylepass_schema = _schema("stylepass.schema.json")
    orders = []
    for block in manifest["blocks"]:
        state, error = status(root, block)
        if missing_only and state == "present":
            continue
        brief_path = root / "briefs" / f"{block['kind']}.md"
        kind_brief = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""
        orders.append(
            {
                "block_id": block["id"],
                "kind": block["kind"],
                "status": state,
                "brief": "\n\n".join(part for part in (block.get("brief", ""), kind_brief) if part),
                "evidence": block.get("evidence", []),
                "schema": {"block": block_schema, "stylepass": stylepass_schema},
                "example": {"block": _block_example(block), "stylepass": _stylepass_example(block)},
                "gates": [
                    "plain concrete prose",
                    "no em dash",
                    "claims quote evidence",
                    "read aloud",
                ],
                "output_path": {
                    "block": str(root / "blocks" / f"{block['id']}.json"),
                    "stylepass": str(root / "blocks" / f"{block['id']}.stylepass.json"),
                },
                "commands": {"draft": "quoin check", "release": "quoin check --release"},
                **({"error": error} if error else {}),
            }
        )
    return orders


def read_for_build(root: Path, manifest: dict, draft: bool) -> tuple[dict[str, dict], list[str]]:
    resolved, placeholders = {}, []
    for declaration in manifest["blocks"]:
        state, error = status(root, declaration)
        if state == "present":
            resolved[declaration["id"]] = json.loads(
                (root / "blocks" / f"{declaration['id']}.json").read_text(encoding="utf-8")
            )
        elif draft:
            placeholders.append(declaration["id"])
            resolved[declaration["id"]] = {
                "block_id": declaration["id"],
                "kind": declaration["kind"],
                "title": declaration["id"],
                "html": f"<p>[TODO: {declaration['id']} not yet authored]</p>",
            }
        else:
            raise ValueError(f"block {declaration['id']} is {state}: {error or 'not authored'}")
    return resolved, placeholders
