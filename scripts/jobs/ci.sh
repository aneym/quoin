#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/../.."
python3 - <<'PY'
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

root = Path.cwd()
output = Path(os.environ.get("CI_RESULT_DIR", ".scratch/ci")).resolve()
output.mkdir(parents=True, exist_ok=True)
cache = Path(os.environ.get("UV_CACHE_DIR", Path.home() / ".cache/uv")).resolve()
shared = Path(os.environ.get("QUOIN_CI_ENV_ROOT", cache / "quoin-ci")).resolve()
shared.mkdir(parents=True, exist_ok=True)
fingerprint = hashlib.sha256(
    (root / "uv.lock").read_bytes() + (root / "pyproject.toml").read_bytes()
).hexdigest()
report = {
    "source_workflow": ".github/workflows/ci.yml@b66679c8d8f5693ca12646bbf714f84c4815d8ad",
    "commands": [],
    "artifacts": [],
    "result_path": str(output / "result.json"),
    "status": "running",
}
failed = False


def save():
    temporary = output / "result.json.tmp"
    temporary.write_text(json.dumps(report, indent=2) + "\n")
    temporary.replace(output / "result.json")


def run(version, name, argv, environment):
    global failed
    log = output / f"python-{version}-{name}.log"
    record = {
        "python": version,
        "name": name,
        "command": argv,
        "cwd": str(root),
        "log": str(log),
        "status": "running",
    }
    report["commands"].append(record)
    save()
    started = time.monotonic()
    with log.open("w") as stream:
        try:
            result = subprocess.run(argv, env=environment, stdout=stream, stderr=subprocess.STDOUT)
            code = result.returncode
        except OSError as error:
            stream.write(str(error) + "\n")
            code = 127
    record.update(
        status="passed" if code == 0 else "failed",
        returncode=code,
        seconds=round(time.monotonic() - started, 3),
    )
    failed = failed or code != 0
    save()
    print(json.dumps(record), flush=True)
    return code == 0


save()
try:
    for version in ("3.12", "3.13"):
        environment = dict(os.environ)
        environment["UV_CACHE_DIR"] = str(cache)
        venv = shared / f"python-{version}-{fingerprint}"
        environment["UV_PROJECT_ENVIRONMENT"] = str(venv)
        with (shared / f"python-{version}-{fingerprint}.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            ready = venv / ".quoin-ci-ready"
            if not ready.is_file() or not (venv / "bin/python").exists():
                if not run(
                    version,
                    "dependencies",
                    [
                        "uv",
                        "sync",
                        "--locked",
                        "--python",
                        version,
                        "--extra",
                        "dev",
                        "--no-install-project",
                    ],
                    environment,
                ):
                    continue
                ready.touch()
            else:
                report["commands"].append(
                    {
                        "python": version,
                        "name": "dependencies",
                        "status": "reused",
                        "environment": str(venv),
                        "fingerprint": fingerprint,
                    }
                )
                save()
            python = str(venv / "bin/python")
            environment["VIRTUAL_ENV"] = str(venv)
            environment["PATH"] = str(venv / "bin") + os.pathsep + environment.get("PATH", "")
            for name, args in (
                ("ruff", ["-m", "ruff", "check", "."]),
                ("format", ["-m", "ruff", "format", "--check", "."]),
                ("mypy", ["-m", "mypy", "quoin"]),
                ("unittest", ["-m", "unittest", "discover", "-s", "tests"]),
            ):
                run(version, name, [python, *args], environment)
            if version == "3.12":
                artifact = root / "evals/results-i2.json"
                entry = {"path": "evals/results-i2.json", "status": "unavailable"}
                report["artifacts"].append(entry)
                jar = os.environ.get("QUOIN_EPUBCHECK_JAR", "")
                available = bool(shutil.which("java", path=environment["PATH"])) and (
                    bool(shutil.which("epubcheck", path=environment["PATH"]))
                    or bool(jar and Path(jar).is_file())
                )
                if available:
                    artifact.unlink(missing_ok=True)
                    run(
                        version,
                        "evals",
                        [python, "evals/run_evals.py", "--iteration", "2"],
                        environment,
                    )
                    entry["status"] = "present" if artifact.is_file() else "missing"
                    if not artifact.is_file():
                        failed = True
                    if artifact.is_file():
                        retained = output / artifact.name
                        shutil.copyfile(artifact, retained)
                        entry["retained_path"] = str(retained)
                else:
                    record = {
                        "python": version,
                        "name": "evals",
                        "command": [python, "evals/run_evals.py", "--iteration", "2"],
                        "status": "unavailable",
                        "reason": "Skipping evals: requires Java plus an EPUBCheck wrapper on PATH "
                        "or QUOIN_EPUBCHECK_JAR pointing to a file.",
                    }
                    report["commands"].append(record)
                    print(json.dumps(record), flush=True)
                save()
except Exception as error:
    failed = True
    report["error"] = str(error)
finally:
    report["status"] = "failed" if failed else "passed"
    save()
    print(
        json.dumps(
            {
                "status": report["status"],
                "result_path": report["result_path"],
                "artifacts": report["artifacts"],
            }
        ),
        flush=True,
    )
sys.exit(1 if failed else 0)
PY
