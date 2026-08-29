from __future__ import annotations

import json
import platform
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import __version__ as PIL_VERSION

from .assemble import _ordered, assemble, build
from .blocks import status
from .manifest import load
from .normalize import CONTAMINATION, body_inner, word_count
from .record import file_hash, read_json, write_json


def epubcheck_jar(book: dict) -> Path:
    return Path(book.get("epubcheck_jar", "/Users/aneyman/artifacts/reading-packets/build/epubcheck-5.3.0/epubcheck-5.3.0/epubcheck.jar"))


def run_epubcheck(jar: Path, target: Path) -> tuple[bool, str]:
    result = subprocess.run(["java", "-jar", str(jar), str(target)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = result.stdout.strip()
    match = re.search(r"Messages:\s*(\d+) fatals? / (\d+) errors? / (\d+) warnings?", output, re.I)
    clean = bool(match and not result.returncode and all(int(value) == 0 for value in match.groups()))
    return clean, output.splitlines()[-1] if output else "no EPUBCheck output"


def doctor(root: Path) -> tuple[bool, dict[str, str]]:
    book, _ = load(root)
    jar = epubcheck_jar(book)
    java = subprocess.run(["java", "-version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.splitlines()
    version = subprocess.run(["java", "-jar", str(jar), "--version"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT).stdout.strip().splitlines() if jar.exists() else []
    values = {"python": platform.python_version(), "Pillow": PIL_VERSION, "java": java[0] if java else "missing", "epubcheck": version[-1] if version else "missing"}
    return bool(java and version and tuple(map(int, platform.python_version_tuple())) >= (3, 12)), values


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
    clean, line = run_epubcheck(epubcheck_jar(book), target)
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
