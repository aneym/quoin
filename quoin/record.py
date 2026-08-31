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


_CODE_FINGERPRINT: str | None = None


def code_fingerprint() -> str:
    """Sha256 over the bytes of every quoin/*.py file, sorted by filename.

    Mixed into build-stage cache keys so an edit to the compiler itself
    invalidates every cached stage output, not just a manual __version__ bump.
    Without this, a stage cache built before a code change looked identical to
    one built after -- a compiler edit could serve stale cached bytes forever
    (see QUOIN-FINDINGS item 5: `quoin build --draft` served a stale artifact
    after assemble.py changed, while check's internal rebuild produced new
    bytes, surfacing as a bogus determinism FAIL).

    Cached in a module global after the first call: quoin's own source does not
    change mid-process, and re-hashing every file on every cache lookup would be
    wasteful.
    """
    global _CODE_FINGERPRINT
    if _CODE_FINGERPRINT is None:
        package_dir = Path(__file__).resolve().parent
        digest = hashlib.sha256()
        for path in sorted(package_dir.glob("*.py"), key=lambda p: p.name):
            digest.update(path.read_bytes())
        _CODE_FINGERPRINT = digest.hexdigest()
    return _CODE_FINGERPRINT


def hashes(root: Path, paths: list[Path], extra: dict[str, str] | None = None) -> dict[str, str]:
    result = {str(path.relative_to(root)): file_hash(path) for path in paths}
    result.update(extra or {})
    return dict(sorted(result.items()))


def read_json(path: Path, fallback):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8"
    )


def run_stage(
    name: str,
    input_hashes: dict[str, str],
    cache: dict,
    stages: dict,
    outputs_ok: bool,
    action: Callable[[], T],
) -> tuple[bool, T | None]:
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
