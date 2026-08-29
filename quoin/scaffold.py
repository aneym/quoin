from __future__ import annotations

import shutil
from pathlib import Path


def init(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    source = Path(__file__).resolve().parent.parent / "scaffold"
    for path in source.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(source)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.stat().st_size:
            raise FileExistsError(f"refusing to overwrite non-empty file: {destination}")
        shutil.copyfile(path, destination)
    for directory in ("blocks", "sources", "sources/raw", "sources/normalized"):
        (target / directory).mkdir(parents=True, exist_ok=True)
