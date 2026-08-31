"""Source-page headers (2026-08-30): every packaged source page opens with a
compiler-rendered header carrying the manifest title, the attribution byline,
and, for web sources, the canonical locator as a live link. The header is
compiler furniture, not source prose, so the word-count gate must still pass
against the recorded normalized body."""

import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from quoin.assemble import build
from quoin.check import check
from quoin.fetch import run as fetch
from quoin.manifest import load

FIXTURE = Path(__file__).resolve().parents[1] / "evals" / "fixtures" / "sample"


def _prepare_book(parent: Path, name: str) -> Path:
    book = parent / name
    shutil.copytree(FIXTURE, book)
    for file in (FIXTURE / "blocks-valid").iterdir():
        shutil.copy2(file, book / "blocks" / file.name)
    fetch(book, offline=True)
    return book


class SourceHeaderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.book = _prepare_book(Path(self._tmp.name), "book")
        self.addCleanup(self._tmp.cleanup)

    def test_source_pages_carry_header_and_canonical_link(self) -> None:
        build(self.book, draft=True)
        _, manifest = load(self.book)
        target = self.book / "out" / f"{manifest['slug']}.epub"
        with zipfile.ZipFile(target) as archive:
            for source in manifest["sources"]:
                markup = archive.read(f"OEBPS/text/source-{source['id']}.xhtml").decode("utf-8")
                self.assertIn('<header class="source-head">', markup, source["id"])
                title = source.get("title", source["id"])
                self.assertIn(f"<h1>{title}</h1>", markup, source["id"])
                locator = source.get("locator", "")
                if locator.startswith(("http://", "https://")):
                    self.assertIn(f'href="{locator}"', markup, source["id"])

    def test_word_count_gate_ignores_header(self) -> None:
        ok, results = check(self.book)
        self.assertTrue(results["tests"]["word_counts"]["pass"], results["tests"]["word_counts"])

    def test_title_page_carries_length_line(self) -> None:
        build(self.book, draft=True)
        _, manifest = load(self.book)
        target = self.book / "out" / f"{manifest['slug']}.epub"
        with zipfile.ZipFile(target) as archive:
            markup = archive.read("OEBPS/text/title.xhtml").decode("utf-8")
        self.assertIn("about", markup)
        self.assertIn("words", markup)
        self.assertIn("pages", markup)

    def test_expected_length_gate(self) -> None:
        import json

        manifest_path = self.book / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # absent: SKIP passes
        ok, results = check(self.book)
        self.assertTrue(results["tests"]["length"]["pass"])
        self.assertIn("SKIP", results["tests"]["length"]["detail"])
        # absurd expectation: gate fails with the named numbers
        manifest["expected_length"] = {"words": 1000000, "tolerance_pct": 10}
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        ok, results = check(self.book)
        self.assertFalse(results["tests"]["length"]["pass"])
        self.assertIn("expected 1000000", results["tests"]["length"]["detail"])
