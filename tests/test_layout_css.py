"""Layout CSS regression tests (2026-09-10 repair).

MuPDF 1.28.3 rendering the real vol. 7 EPUB reported
`css syntax error: expected value ... p{margin:0 0>:<.92em}` and clipped a
40-hex commit hash at a 390px viewport. The repair is scoped to
format_version 2 so version-1 books keep their exact stylesheet and title
page bytes. These tests pin both sides of that line without any renderer.
"""

import json
import re
import tempfile
import unittest
import zipfile
from pathlib import Path

from quoin.assemble import CSS, build
from quoin.manifest import load
from tests.test_teaching import prepare

HASH = "d0df324862cb2244a40789a5ca45392165f1b950"


def declarations(css: str):
    """Yield (selector, property, value) for every declaration in a stylesheet
    that has no nested blocks, strings, or url() -- true of quoin's CSS."""
    body = re.sub(r"@charset\s+\"[^\"]*\";", "", css)
    for selector, block in re.findall(r"([^{}]+)\{([^{}]*)\}", body):
        for declaration in filter(None, (d.strip() for d in block.split(";"))):
            yield selector.strip(), declaration


def stylesheet_errors(css: str) -> list[str]:
    errors = []
    for selector, declaration in declarations(css):
        if declaration.count(":") != 1:
            errors.append(f"{selector}{{{declaration}}}")
    return errors


class SharedConstantTests(unittest.TestCase):
    def test_version1_constant_is_byte_stable_and_still_carries_the_known_typo(self):
        # Deliberate: the shared constant is not touched so every version-1
        # book rebuilds byte-identical. The typo is fixed at version-2 assembly.
        self.assertIn("p{margin:0 0:.92em}", CSS)
        self.assertEqual(stylesheet_errors(CSS), ["p{margin:0 0:.92em}"])


class TeachingV2StylesheetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        prepare(self.root)
        # A lesson carrying a long unbreakable inline token, linked and plain,
        # exactly the shape that clipped in vol. 7 u2.
        lesson = self.root / "blocks" / "lesson.json"
        data = json.loads(lesson.read_text())
        data["html"] = (
            f'<p>The inspected pin is <a href="https://example.test/tree/{HASH}">{HASH}</a>. '
            f"A later snapshot, {HASH}. Both report packaged bytes.</p>"
        )
        lesson.write_text(json.dumps(data))
        self.authored = data["html"]
        _, self.record = build(self.root, draft=True)
        _, manifest = load(self.root)
        self.target = self.root / "out" / f"{manifest['slug']}.epub"
        with zipfile.ZipFile(self.target) as archive:
            self.css = archive.read("OEBPS/styles/book.css").decode("utf-8")
            self.title = archive.read("OEBPS/text/title.xhtml").decode("utf-8")
            self.lesson = archive.read("OEBPS/text/block-lesson.xhtml").decode("utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_v2_stylesheet_has_no_invalid_declaration(self):
        self.assertEqual(stylesheet_errors(self.css), [])
        self.assertNotIn("0 0:", self.css)
        self.assertIn("p{margin:0 0 .92em}", self.css)

    def test_v2_stylesheet_wraps_unbreakable_inline_tokens(self):
        self.assertIn("body{word-wrap:break-word;overflow-wrap:anywhere}", self.css)
        # The pre rule from before the repair is still there.
        self.assertIn("pre{white-space:pre-wrap;overflow-wrap:anywhere}", self.css)

    def test_v2_repair_is_css_only_and_never_splits_authored_bytes(self):
        # No <wbr>, zero-width space, or soft hyphen furniture inside the hash:
        # the authored HTML is packaged verbatim, so teaching_fidelity holds.
        self.assertIn(self.authored, self.lesson)
        self.assertNotIn("<wbr", self.lesson)
        self.assertNotIn("​", self.lesson)
        self.assertNotIn("­", self.lesson)

    def test_v2_title_page_says_print_equivalent_pages(self):
        self.assertRegex(self.title, r"about \d+ print-equivalent pages")


class Version1UnchangedTests(unittest.TestCase):
    def test_v1_stylesheet_and_title_wording_unchanged(self):
        from tests.test_source_headers import _prepare_book

        with tempfile.TemporaryDirectory() as temp:
            book = _prepare_book(Path(temp), "book")
            build(book, draft=True)
            _, manifest = load(book)
            self.assertEqual(manifest.get("format_version"), 1)
            with zipfile.ZipFile(book / "out" / f"{manifest['slug']}.epub") as archive:
                css = archive.read("OEBPS/styles/book.css").decode("utf-8")
                title = archive.read("OEBPS/text/title.xhtml").decode("utf-8")
        self.assertEqual(css, CSS)
        self.assertNotIn("print-equivalent", title)
        self.assertRegex(title, r"about \d+ pages")


if __name__ == "__main__":
    unittest.main()
