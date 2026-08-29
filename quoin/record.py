from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, TypeVar

T = TypeVar("T")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes()) if path.exists() else "MISSING"


def hashes(root: Path, paths: list[Path], extra: dict[str, str] | None = None) -> dict[str, str]:
    result = {str(path.relative_to(root)): file_hash(path) for path in paths}
    result.update(extra or {})
    return dict(sorted(result.items()))


def read_json(path: Path, fallback):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def run_stage(name: str, input_hashes: dict[str, str], cache: dict, stages: dict, outputs_ok: bool, action: Callable[[], T]) -> tuple[bool, T | None]:
    started = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    begin = time.perf_counter()
    hit = outputs_ok and cache.get(name, {}).get("input_sha256s") == input_hashes
    value = None if hit else action()
    stages[name] = {
        "start_iso": started,
        "wall_ms": round((time.perf_counter() - begin) * 1000, 3),
        "cache_hit": hit,
        "input_sha256s": input_hashes,
    }
    cache[name] = {"input_sha256s": input_hashes}
    return hit, value
