from __future__ import annotations

import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import __version__ as PIL_VERSION

from .assemble import _ordered, assemble, build, cover_font
from .blocks import status
from .errors import QuoinError
from .manifest import load
from .normalize import CONTAMINATION, body_inner, word_count
from .record import file_hash, read_json, write_json


def epubcheck_command(book: dict) -> tuple[list[str], str]:
    configured = book.get("epubcheck_jar")
    if configured:
        path = Path(configured)
        if path.is_file():
            return ["java", "-jar", str(path)], "book.toml epubcheck_jar"
    environment = os.environ.get("QUOIN_EPUBCHECK_JAR")
    if environment:
        path = Path(environment)
        if path.is_file():
            return ["java", "-jar", str(path)], "QUOIN_EPUBCHECK_JAR"
    wrapper = shutil.which("epubcheck")
    if wrapper:
        return [wrapper], "which epubcheck"
    raise QuoinError(
        "EPUBCheck not found; set book.toml epubcheck_jar or QUOIN_EPUBCHECK_JAR, "
        "or install an epubcheck wrapper discoverable by which epubcheck"
    )


def epubcheck_jar(book: dict) -> Path:
    command, _ = epubcheck_command(book)
    if command[:2] != ["java", "-jar"]:
        raise QuoinError("EPUBCheck resolved via which epubcheck, not a jar")
    return Path(command[2])


def run_epubcheck(command: list[str] | Path, target: Path) -> tuple[bool, str]:
    prefix = ["java", "-jar", str(command)] if isinstance(command, Path) else command
    result = subprocess.run([*prefix, str(target)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.stdout.strip()
    match = re.search(r"Messages:\s*(\d+) fatals? / (\d+) errors? / (\d+) warnings?", output, re.I)
    clean = bool(match and not result.returncode and all(int(value) == 0 for value in match.groups()))
    return clean, output.splitlines()[-1] if output else "no EPUBCheck output"


def doctor(root: Path) -> tuple[bool, dict[str, str]]:
    book, _ = load(root)
    values = {"python": platform.python_version(), "Pillow": PIL_VERSION}
    try:
        font, font_route = cover_font(book)
        values["cover_font"] = f"{font} ({font_route})"
    except QuoinError as exc:
        values["cover_font"] = str(exc)
    try:
        command, epubcheck_route = epubcheck_command(book)
        version = subprocess.run([*command, "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.strip().splitlines()
        values["epubcheck"] = f"{version[-1] if version else 'missing'} ({epubcheck_route})"
    except QuoinError as exc:
        version = []
        values["epubcheck"] = str(exc)
    needs_java = bool("command" in locals() and command[:2] == ["java", "-jar"])
    java = subprocess.run(["java", "-version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.splitlines() if needs_java else ["not required"]
    values["java"] = java[0] if java else "missing"
    passed = bool(version and java and "font" in locals() and tuple(map(int, platform.python_version_tuple())) >= (3, 12))
    return passed, values


def check(root: Path, release: bool = False) -> tuple[bool, dict]:
    book, manifest = load(root)
    target = root / "out" / f"{manifest['slug']}.epub"
    if not target.exists():
        build(root, draft=not release)
    records = read_json(root / "sources" / "records.json", {})
    tests: dict[str, dict] = {}
    def result(name: str, passed: bool, detail: str) -> None:
        tests[name] = {"pass": bool(passed), "detail": detail}
    try:
        with zipfile.ZipFile(target) as archive:
            infos = archive.infolist()
            mime_ok = bool(infos and infos[0].filename == "mimetype" and infos[0].compress_type == zipfile.ZIP_STORED and archive.read("mimetype") == b"application/epub+zip")
            result("mimetype", mime_ok, "mimetype is first and stored" if mime_ok else "invalid mimetype entry")
            opf = ET.fromstring(archive.read("OEBPS/content.opf"))
            ns = {"o": "http://www.idpf.org/2007/opf"}
            actual = [node.attrib["idref"] for node in opf.findall("o:spine/o:itemref", ns)]
            expected = ["cover", "title", *[item[0] for item in _ordered(manifest)], "attribution"]
            result("spine", actual == expected, f"{len(actual)} spine entries")
            counts, contamination = {}, []
            for source in manifest["sources"]:
                name = f"OEBPS/text/source-{source['id']}.xhtml"
                markup = archive.read(name).decode("utf-8")
                counts[source["id"]] = word_count(body_inner(markup))
                hit = CONTAMINATION.search(markup)
                if hit:
                    contamination.append(f"{source['id']}: {hit.group(0)}")
            expected_counts = {key: value["word_count"] for key, value in records.items()}
            result("word_counts", counts == expected_counts, f"packaged={counts} recorded={expected_counts}")
            result("contamination", not contamination, ", ".join(contamination) or "clean")
            privacy_hits = []
            for name in archive.namelist():
                text = archive.read(name).decode("utf-8", errors="ignore")
                for term in manifest["privacy"].get("forbidden_terms", []):
                    if re.search(re.escape(term), text, re.I):
                        privacy_hits.append(f"{name}: {term}")
            result("privacy", not privacy_hits, ", ".join(privacy_hits) or "clean")
    except Exception as exc:
        result("package", False, str(exc))
    clean, line = run_epubcheck(epubcheck_command(book)[0], target)
    result("epubcheck", clean, line)
    blocks, placeholders = __import__("quoin.blocks", fromlist=["read_for_build"]).read_for_build(root, manifest, True)
    with tempfile.TemporaryDirectory(dir=root / "out") as temp_dir:
        rebuilt = Path(temp_dir) / "rebuilt.epub"
        assemble(root, rebuilt, manifest, book, blocks, records)
        result("determinism", file_hash(target) == file_hash(rebuilt), f"built={file_hash(target)} rebuilt={file_hash(rebuilt)}")
    if release:
        result("placeholders", not placeholders, ", ".join(placeholders) or "none")
        sidecars_ok, claims_ok, details = True, True, []
        for declaration in manifest["blocks"]:
            sidecar = root / "blocks" / f"{declaration['id']}.stylepass.json"
            if not sidecar.exists():
                sidecars_ok = False
                details.append(f"missing {sidecar.name}")
                continue
            data = json.loads(sidecar.read_text(encoding="utf-8"))
            if any(not claim.get("claim") or not claim.get("support") for claim in data.get("claims", [])):
                claims_ok = False
                details.append(f"empty claim in {sidecar.name}")
        result("stylepass", sidecars_ok, ", ".join(details) or "all present")
        result("claims", claims_ok, ", ".join(details) or "all non-empty")
    all_pass = all(item["pass"] for item in tests.values())
    payload = {"all_pass": all_pass, "release": release, "tests": tests}
    write_json(root / "out" / "check-results.json", payload)
    return all_pass, payload
