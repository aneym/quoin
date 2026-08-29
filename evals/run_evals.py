#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evals" / "fixtures" / "sample"
FURNITURE_FIXTURE = ROOT / "evals" / "fixtures" / "furniture"

sys.path.insert(0, str(ROOT))
from quoin.normalize import body_inner, word_count  # noqa: E402


def command(book: Path, *args: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(ROOT)
    return subprocess.run(
        [sys.executable, "-m", "quoin", *args],
        cwd=book,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def packaged_source_text(target: Path, source_id: str) -> str:
    with zipfile.ZipFile(target) as archive:
        return archive.read(f"OEBPS/text/source-{source_id}.xhtml").decode("utf-8")


def prepare_release_book(parent: Path, name: str) -> Path:
    """Copy the sample fixture for a release-mode run (E16-E18): waive the one real
    alt="" figure the fixture honestly ships (moesta 00013.jpg, docs/SPEC-M2-NOTES.md)
    via an alt_overrides entry patched into THIS TEMP COPY's manifest only -- the
    checked-in evals/fixtures/sample/manifest.json is never touched -- then drop the
    valid authored blocks-valid/ set into blocks/ so a release build/check has real,
    non-placeholder content to work with."""
    book = parent / name
    shutil.copytree(FIXTURE, book)
    manifest_path = book / "manifest.json"
    manifest_data = json.loads(manifest_path.read_text())
    for source in manifest_data["sources"]:
        if source["id"] == "moesta":
            source["alt_overrides"] = {
                "00013.jpg": (
                    "Unlabeled figure from the sourced chapter (eval fixture waiver, "
                    "not shipped in the checked-in manifest)."
                )
            }
    manifest_path.write_text(json.dumps(manifest_data, indent=2))
    fetched = command(book, "fetch", "--offline")
    if fetched.returncode:
        raise RuntimeError(f"fetch failed for {name}: {fetched.stdout}")
    for file in (FIXTURE / "blocks-valid").iterdir():
        shutil.copy2(file, book / "blocks" / file.name)
    return book


def check_results(book: Path) -> dict:
    path = book / "out" / "check-results.json"
    return json.loads(path.read_text()) if path.exists() else {"tests": {}}


# Furniture markers proven fixed by the mkdocs (unquoted attrs, headerlink pilcrows,
# md-content__button edit/view SVG links, trailing Comments section) and substack/newsletter
# (button-in-anchor, picture-without-img, remote img, fragment-only anchor) failure classes.
FURNITURE_MARKERS = {
    "mkdocs-ugly": {
        "absent": ["headerlink", "md-content__button", "<svg", "Reader feedback"],
        "present": ["Swarm season entries"],
    },
    "dock-frag": {
        "absent": ["<picture", "<button", "<img", 'href="#foo"'],
        "present": ["the batch numbering guide", "Get the weekly digest"],
    },
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--iteration", type=int, required=True)
    args = parser.parse_args()
    evals: dict[str, dict] = {}

    def evaluate(identifier: str, started: float, passed: bool, detail: str) -> None:
        evals[identifier] = {
            "pass": bool(passed),
            "detail": detail,
            "ms": round((time.perf_counter() - started) * 1000, 3),
        }

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
        evaluate(
            "E4",
            started,
            draft.returncode == 0,
            draft.stdout.strip().splitlines()[-1] if draft.stdout.strip() else "draft failed",
        )
        cold_ms = (time.perf_counter() - fetch_started) * 1000
        evaluate("E9", fetch_started, cold_ms < 10000, f"cold loop {cold_ms:.3f} ms")

        target = book / "out" / "quoin-m1-sample.epub"
        first = target.read_bytes() if target.exists() else b""
        started = time.perf_counter()
        warm = command(book, "build", "--draft")
        second = target.read_bytes() if target.exists() else b""
        evaluate(
            "E1",
            started,
            bool(first) and first == second,
            "two builds are byte-identical" if first == second else "builds differ",
        )
        cache = json.loads((book / "out" / "build-record.json").read_text())
        evaluate(
            "E5",
            started,
            warm.returncode == 0 and cache["stages"]["assemble"]["cache_hit"],
            f"assemble cache_hit={cache['stages']['assemble']['cache_hit']}",
        )

        started = time.perf_counter()
        checked = command(book, "check")
        results = (
            json.loads((book / "out" / "check-results.json").read_text())
            if (book / "out" / "check-results.json").exists()
            else {"tests": {}}
        )
        tests = results.get("tests", {})
        evaluate(
            "E2",
            started,
            tests.get("epubcheck", {}).get("pass", False),
            tests.get("epubcheck", {}).get("detail", checked.stdout.strip()),
        )
        evaluate(
            "E3",
            started,
            tests.get("word_counts", {}).get("pass", False),
            tests.get("word_counts", {}).get("detail", "missing result"),
        )
        evaluate(
            "E6",
            started,
            tests.get("contamination", {}).get("pass", False),
            tests.get("contamination", {}).get("detail", "missing result"),
        )
        evaluate(
            "E7",
            started,
            tests.get("privacy", {}).get("pass", False),
            tests.get("privacy", {}).get("detail", "missing result"),
        )

        started = time.perf_counter()
        orders = command(book, "blocks", "--missing", "--json")
        try:
            payload = json.loads(orders.stdout)
            required = {"block_id", "kind", "brief", "evidence", "schema", "gates", "output_path"}
            valid = (
                orders.returncode == 0
                and len(payload) == 2
                and all(required <= item.keys() for item in payload)
            )
            detail = f"{len(payload)} valid work orders"
        except Exception as exc:
            valid, detail = False, str(exc)
        evaluate("E8", started, valid, detail)

        started = time.perf_counter()
        doctor = command(book, "doctor")
        evaluate("E10", started, doctor.returncode == 0, doctor.stdout.strip().replace("\n", "; "))

    # E16-E18 exercise `quoin check --release`, which nothing above touches (it only
    # ever runs draft mode with blocks missing). Each gets its own temp copy of the
    # sample fixture so one test's mutation (a deleted block, a corrupted sidecar)
    # can never leak into another's.
    with tempfile.TemporaryDirectory(prefix="quoin-eval-release-") as temp:
        temp_root = Path(temp)

        started = time.perf_counter()
        try:
            book16 = prepare_release_book(temp_root, "sample-release-e16")
            built16 = command(book16, "build")
            checked16 = command(book16, "check", "--release")
            results16 = check_results(book16)
            e16_pass = (
                built16.returncode == 0
                and checked16.returncode == 0
                and results16.get("all_pass", False)
            )
            e16_detail = (
                f"build exit={built16.returncode} check exit={checked16.returncode} "
                f"all_pass={results16.get('all_pass')}"
            )
        except Exception as exc:
            e16_pass, e16_detail = False, str(exc)
        evaluate("E16", started, e16_pass, e16_detail)

        # E17: one authored block goes missing after a successful build. check.py's
        # release branch always recomputes block presence via read_for_build(..., True)
        # rather than trusting the already-built epub, so this must surface as a
        # "placeholders" failure naming the missing block, without a rebuild.
        started = time.perf_counter()
        try:
            book17 = prepare_release_book(temp_root, "sample-release-e17")
            command(book17, "build")
            (book17 / "blocks" / "bridge.json").unlink()
            (book17 / "blocks" / "bridge.stylepass.json").unlink()
            checked17 = command(book17, "check", "--release")
            placeholders_row = check_results(book17).get("tests", {}).get("placeholders", {})
            e17_pass = (
                checked17.returncode != 0
                and not placeholders_row.get("pass", True)
                and "bridge" in placeholders_row.get("detail", "")
            )
            e17_detail = f"check exit={checked17.returncode}; placeholders row={placeholders_row}"
        except Exception as exc:
            e17_pass, e17_detail = False, str(exc)
        evaluate("E17", started, e17_pass, e17_detail)

        # E18: corrupted sidecar, claims: [] -- plan 006's own spec for this eval.
        # This proved a real gate defect: check.py's claims_ok used to only flag
        # per-entry blanks -- any(not claim.get("claim") or not claim.get("support")
        # for claim in data.get("claims", [])) -- which is vacuously False over an
        # empty list, so a sidecar asserting zero claims used to pass the "claims"
        # row. Fixed in check.py (require a non-empty claims list before checking
        # per-entry blanks) per plan 006's gate-enforcement clause; this eval now
        # proves the fix holds.
        started = time.perf_counter()
        try:
            book18 = prepare_release_book(temp_root, "sample-release-e18")
            command(book18, "build")
            sidecar_path = book18 / "blocks" / "bridge.stylepass.json"
            sidecar_data = json.loads(sidecar_path.read_text())
            sidecar_data["claims"] = []
            sidecar_path.write_text(json.dumps(sidecar_data, indent=2))
            checked18 = command(book18, "check", "--release")
            claims_row = check_results(book18).get("tests", {}).get("claims", {})
            e18_pass = checked18.returncode != 0 and not claims_row.get("pass", True)
            e18_detail = f"check exit={checked18.returncode}; claims row={claims_row}"
        except Exception as exc:
            e18_pass, e18_detail = False, str(exc)
        evaluate("E18", started, e18_pass, e18_detail)

    with tempfile.TemporaryDirectory(prefix="quoin-eval-furniture-") as temp:
        book = Path(temp) / "furniture"
        shutil.copytree(FURNITURE_FIXTURE, book)
        furniture_manifest = json.loads((book / "manifest.json").read_text())
        expected_words = {
            source["id"]: source["expected_words"] for source in furniture_manifest["sources"]
        }
        target = book / "out" / f"{furniture_manifest['slug']}.epub"

        fetched = command(book, "fetch", "--offline")
        if fetched.returncode:
            print(fetched.stdout, file=sys.stderr)
            return 1
        command(book, "build", "--draft")

        started = time.perf_counter()
        command(book, "check")
        results = (
            json.loads((book / "out" / "check-results.json").read_text())
            if (book / "out" / "check-results.json").exists()
            else {"tests": {}}
        )
        tests = results.get("tests", {})

        marker_names, marker_failures = [], []
        try:
            for source_id, checks in FURNITURE_MARKERS.items():
                text = packaged_source_text(target, source_id)
                for needle in checks["absent"]:
                    marker_names.append(f"{source_id}: no {needle!r}")
                    if needle in text:
                        marker_failures.append(f"{source_id} still contains {needle!r}")
                for needle in checks["present"]:
                    marker_names.append(f"{source_id}: keeps {needle!r}")
                    if needle not in text:
                        marker_failures.append(f"{source_id} lost {needle!r}")
        except Exception as exc:
            marker_failures.append(str(exc))
        e11_pass = (
            tests.get("epubcheck", {}).get("pass", False)
            and tests.get("contamination", {}).get("pass", False)
            and not marker_failures
        )
        e11_detail = (
            f"checked {len(marker_names)} furniture markers ({'; '.join(marker_names)}); "
            f"epubcheck={tests.get('epubcheck', {}).get('detail', 'missing result')}; "
            f"contamination={tests.get('contamination', {}).get('detail', 'missing result')}"
            + ("" if not marker_failures else f"; FAILURES: {'; '.join(marker_failures)}")
        )
        evaluate("E11", started, e11_pass, e11_detail)

        started = time.perf_counter()
        try:
            packaged_counts = {
                source_id: word_count(body_inner(packaged_source_text(target, source_id)))
                for source_id in expected_words
            }
            e12_pass, e12_detail = (
                packaged_counts == expected_words,
                f"packaged={packaged_counts} expected={expected_words}",
            )
        except Exception as exc:
            e12_pass, e12_detail = False, str(exc)
        evaluate("E12", started, e12_pass, e12_detail)

        started = time.perf_counter()
        try:
            mini_book_text = packaged_source_text(target, "mini-book")
            no_dangling_href, anchor_text_kept = (
                "other-chapter.xhtml" not in mini_book_text,
                "the next chapter" in mini_book_text,
            )
            e13_pass, e13_detail = (
                no_dangling_href and anchor_text_kept,
                f"href stripped={no_dangling_href}, anchor text kept={anchor_text_kept}",
            )
        except Exception as exc:
            e13_pass, e13_detail = False, str(exc)
        evaluate("E13", started, e13_pass, e13_detail)

        # E14/E15 exercise plan 005's media-check furniture source: two images
        # pre-seeded as an offline-reusable fetch snapshot (SPEC-M2-NOTES second
        # donation items 1, 2, 3, 6, 7, 9 - namespacing/hash integrity, ornamental
        # floor, byte identity, orphan detection, link resolution, magic-byte sniffing).
        started = time.perf_counter()
        try:
            with zipfile.ZipFile(target) as archive:
                names = set(archive.namelist())
            media_check_text = packaged_source_text(target, "media-check")
            dock_crate_packaged = "OEBPS/text/media/media-check/dock-crate.jpg" in names
            # declared .png but sniffed as JPEG: packaged and referenced by its sniffed
            # extension, never the misleading declared one (SPEC-M2-NOTES item 9/3-second-donation)
            cover_fig_packaged = "OEBPS/text/media/media-check/cover-fig.jpg" in names
            cover_fig_referenced = "media/media-check/cover-fig.jpg" in media_check_text
            no_stale_png_ref = "cover-fig.png" not in media_check_text
            e14_pass = (
                dock_crate_packaged
                and cover_fig_packaged
                and cover_fig_referenced
                and no_stale_png_ref
            )
            image_integrity_detail = tests.get("image_integrity", {}).get(
                "detail", "missing result"
            )
            e14_detail = (
                f"dock-crate.jpg packaged={dock_crate_packaged}; "
                f"cover-fig.jpg packaged={cover_fig_packaged} (sniffed from declared .png); "
                f"referenced={cover_fig_referenced}; no stale .png ref={no_stale_png_ref}; "
                f"image_integrity={image_integrity_detail}"
            )
        except Exception as exc:
            e14_pass, e14_detail = False, str(exc)
        evaluate("E14", started, e14_pass, e14_detail)

        started = time.perf_counter()
        try:
            notification = json.loads((book / "sources" / "normalization.json").read_text())
            sniff_note = any(
                "declared .png but sniffed as jpeg" in note for note in notification["notes"]
            )
            alt_text_row = tests.get("alt_text", {})
            image_integrity_row = tests.get("image_integrity", {})
            # cover-fig.jpg ships with alt="" from the source; check.py's alt_text
            # row must accept the manifest's alt_overrides[basename] as curing it
            # (SPEC-M2-NOTES second donation item 1), and image_integrity must
            # confirm the packaged bytes hash-match the fetch-time snapshot.
            e15_pass = (
                sniff_note
                and alt_text_row.get("pass", False)
                and image_integrity_row.get("pass", False)
            )
            alt_text_detail = alt_text_row.get("detail", "missing result")
            image_integrity_detail = image_integrity_row.get("detail", "missing result")
            e15_detail = (
                f"sniff mismatch note recorded={sniff_note}; "
                f"alt_text={alt_text_detail}; image_integrity={image_integrity_detail}"
            )
        except Exception as exc:
            e15_pass, e15_detail = False, str(exc)
        evaluate("E15", started, e15_pass, e15_detail)

        # E19 (plan 011): kepub build of this same furniture book passes EPUBCheck
        # and every koboSpan id is unique and sequential within its own document.
        started = time.perf_counter()
        try:
            built_kepub = command(book, "build", "--draft", "--profile", "kepub")
            checked_kepub = command(book, "check", "--profile", "kepub")
            kepub_results = (
                json.loads((book / "out" / "check-results.json").read_text())
                if (book / "out" / "check-results.json").exists()
                else {"tests": {}}
            )
            kepub_epubcheck = kepub_results.get("tests", {}).get("epubcheck", {})
            kepub_target = book / "out" / f"{furniture_manifest['slug']}.kepub.epub"
            span_id_re = re.compile(r'<span class="koboSpan" id="(kobo\.\d+\.\d+)">')
            offenders: list[str] = []
            span_count = 0
            with zipfile.ZipFile(kepub_target) as archive:
                for name in sorted(archive.namelist()):
                    if not (name.startswith("OEBPS/text/") and name.endswith(".xhtml")):
                        continue
                    markup = archive.read(name).decode("utf-8")
                    ids = span_id_re.findall(markup)
                    span_count += len(ids)
                    if len(ids) != len(set(ids)):
                        offenders.append(f"{name}: duplicate span id")
                        continue
                    paragraphs: dict[int, int] = {}
                    order: list[int] = []
                    for raw in ids:
                        _, n, m = raw.split(".")
                        n, m = int(n), int(m)
                        if n not in paragraphs:
                            order.append(n)
                            paragraphs[n] = 0
                        paragraphs[n] += 1
                        if m != paragraphs[n]:
                            offenders.append(f"{name}: {raw} out of sequence")
                    if order != list(range(1, len(order) + 1)):
                        offenders.append(f"{name}: paragraph numbers not sequential {order}")
            e19_pass = (
                built_kepub.returncode == 0
                and checked_kepub.returncode == 0
                and kepub_epubcheck.get("pass", False)
                and span_count > 0
                and not offenders
            )
            e19_detail = (
                f"build exit={built_kepub.returncode} check exit={checked_kepub.returncode} "
                f"epubcheck={kepub_epubcheck.get('detail', 'missing result')}; "
                f"{span_count} spans checked"
                + ("" if not offenders else f"; FAILURES: {'; '.join(offenders)}")
            )
        except Exception as exc:
            e19_pass, e19_detail = False, str(exc)
        evaluate("E19", started, e19_pass, e19_detail)

    payload = {
        "iteration": args.iteration,
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "evals": evals,
        "all_pass": all(value["pass"] for value in evals.values()),
    }
    output = ROOT / "evals" / f"results-i{args.iteration}.json"
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    print("eval  result  ms       detail")
    for identifier in sorted(evals, key=lambda value: int(value[1:])):
        item = evals[identifier]
        status = "PASS" if item["pass"] else "FAIL"
        print(f"{identifier:<5} {status:<6} {item['ms']:>8.3f} {item['detail']}")
    print(f"all_pass: {str(payload['all_pass']).lower()}")
    return 0 if payload["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
