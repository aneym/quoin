#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evals" / "fixtures" / "sample"


def command(book: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT)
    return subprocess.run([sys.executable, "-m", "quoin", *args], cwd=book, env=environment, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration", type=int, required=True)
    args = parser.parse_args()
    evals: dict[str, dict] = {}

    def evaluate(identifier: str, started: float, passed: bool, detail: str) -> None:
        evals[identifier] = {"pass": bool(passed), "detail": detail, "ms": round((time.perf_counter() - started) * 1000, 3)}

    with tempfile.TemporaryDirectory(prefix="quoin-eval-") as temp:
        book = Path(temp) / "sample"
        shutil.copytree(FIXTURE, book)
        fetch_started = time.perf_counter()
        fetched = command(book, "fetch", "--offline")
        if fetched.returncode:
            print(fetched.stdout, file=sys.stderr)
            return 1

        started = time.perf_counter()
        draft = command(book, "build", "--draft")
        evaluate("E4", started, draft.returncode == 0, draft.stdout.strip().splitlines()[-1] if draft.stdout.strip() else "draft failed")
        cold_ms = (time.perf_counter() - fetch_started) * 1000
        evaluate("E9", fetch_started, cold_ms < 10000, f"cold loop {cold_ms:.3f} ms")

        target = book / "out" / "quoin-m1-sample.epub"
        first = target.read_bytes() if target.exists() else b""
        started = time.perf_counter()
        warm = command(book, "build", "--draft")
        second = target.read_bytes() if target.exists() else b""
        evaluate("E1", started, bool(first) and first == second, "two builds are byte-identical" if first == second else "builds differ")
        cache = json.loads((book / "out" / "build-record.json").read_text())
        evaluate("E5", started, warm.returncode == 0 and cache["stages"]["assemble"]["cache_hit"], f"assemble cache_hit={cache['stages']['assemble']['cache_hit']}")

        started = time.perf_counter()
        checked = command(book, "check")
        results = json.loads((book / "out" / "check-results.json").read_text()) if (book / "out" / "check-results.json").exists() else {"tests": {}}
        tests = results.get("tests", {})
        evaluate("E2", started, tests.get("epubcheck", {}).get("pass", False), tests.get("epubcheck", {}).get("detail", checked.stdout.strip()))
        evaluate("E3", started, tests.get("word_counts", {}).get("pass", False), tests.get("word_counts", {}).get("detail", "missing result"))
        evaluate("E6", started, tests.get("contamination", {}).get("pass", False), tests.get("contamination", {}).get("detail", "missing result"))
        evaluate("E7", started, tests.get("privacy", {}).get("pass", False), tests.get("privacy", {}).get("detail", "missing result"))

        started = time.perf_counter()
        orders = command(book, "blocks", "--missing", "--json")
        try:
            payload = json.loads(orders.stdout)
            required = {"block_id", "kind", "brief", "evidence", "schema", "gates", "output_path"}
            valid = orders.returncode == 0 and len(payload) == 2 and all(required <= item.keys() for item in payload)
            detail = f"{len(payload)} valid work orders"
        except Exception as exc:
            valid, detail = False, str(exc)
        evaluate("E8", started, valid, detail)

        started = time.perf_counter()
        doctor = command(book, "doctor")
        evaluate("E10", started, doctor.returncode == 0, doctor.stdout.strip().replace("\n", "; "))

    payload = {"iteration": args.iteration, "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "evals": evals, "all_pass": all(value["pass"] for value in evals.values())}
    output = ROOT / "evals" / f"results-i{args.iteration}.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print("eval  result  ms       detail")
    for identifier in sorted(evals, key=lambda value: int(value[1:])):
        item = evals[identifier]
        print(f"{identifier:<5} {'PASS' if item['pass'] else 'FAIL':<6} {item['ms']:>8.3f} {item['detail']}")
    print(f"all_pass: {str(payload['all_pass']).lower()}")
    return 0 if payload["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
