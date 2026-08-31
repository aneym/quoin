"""Unit tests for the code_fingerprint() cache-key fix (QUOIN-FINDINGS item 5).

Before this fix, quoin's build cache keyed stage outputs on file/book inputs
only, never on the compiler's own source. Editing assemble.py between two
builds left the cache key unchanged, so `quoin build --draft` could serve a
stale pre-edit artifact forever. code_fingerprint() hashes quoin's own .py
files and gets mixed into the assemble stage's cache key so a compiler edit
always forces a rebuild.

Covers: fingerprint stability across calls, that patching the fingerprint
changes the computed cache-key inputs (tested directly against
build_inputs(), the function that builds the key), and an end-to-end double
build on evals/fixtures/sample -- following the fixture pattern in
tests/test_release_gates.py -- where an unchanged fingerprint cache-hits and
a patched one forces a miss.
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quoin.assemble import build, build_inputs
from quoin.fetch import run as fetch
from quoin.manifest import load
from quoin.record import code_fingerprint

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "evals" / "fixtures" / "sample"


def _prepare_book(parent: Path, name: str) -> Path:
    """Same recipe as test_release_gates.py: a real, fetched, buildable book."""
    book = parent / name
    shutil.copytree(FIXTURE, book)
    for file in (FIXTURE / "blocks-valid").iterdir():
        shutil.copy2(file, book / "blocks" / file.name)
    fetch(book, offline=True)
    return book


class CodeFingerprintTests(unittest.TestCase):
    def test_fingerprint_is_stable_across_calls(self) -> None:
        self.assertEqual(code_fingerprint(), code_fingerprint())

    def test_fingerprint_is_a_hex_sha256(self) -> None:
        value = code_fingerprint()
        self.assertEqual(len(value), 64)
        int(value, 16)  # raises ValueError if not hex

    def test_patched_fingerprint_changes_the_cache_key(self) -> None:
        """Test the key function directly: build_inputs() is what assemble's
        cache key is built from, so patching code_fingerprint (as imported into
        quoin.assemble) must change the "code_fingerprint" entry it returns,
        independent of anything else in the book."""
        with tempfile.TemporaryDirectory(prefix="quoin-test-fingerprint-") as temp:
            book = _prepare_book(Path(temp), "book")
            book_toml, manifest = load(book)
            records_path = book / "sources" / "records.json"
            baseline = build_inputs(book, manifest, book_toml, records_path, draft=True)
            with patch("quoin.assemble.code_fingerprint", return_value="deadbeef" * 8):
                patched = build_inputs(book, manifest, book_toml, records_path, draft=True)
        self.assertNotEqual(baseline["code_fingerprint"], patched["code_fingerprint"])
        self.assertEqual(patched["code_fingerprint"], "deadbeef" * 8)
        # every other input is untouched by the patch
        unrelated = {k: v for k, v in baseline.items() if k != "code_fingerprint"}
        for key, value in unrelated.items():
            self.assertEqual(patched[key], value)

    def test_double_build_reuses_cache_when_fingerprint_unchanged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="quoin-test-fingerprint-") as temp:
            book = _prepare_book(Path(temp), "book")
            first = build(book, draft=True)[1]
            second = build(book, draft=True)[1]
        self.assertFalse(first["stages"]["assemble"]["cache_hit"])
        self.assertTrue(second["stages"]["assemble"]["cache_hit"])

    def test_double_build_rebuilds_when_fingerprint_changes(self) -> None:
        """A patched fingerprint between two otherwise-identical builds must
        force a miss: this is the exact scenario from QUOIN-FINDINGS item 5,
        where a compiler-code edit needs to invalidate the stale cache."""
        with tempfile.TemporaryDirectory(prefix="quoin-test-fingerprint-") as temp:
            book = _prepare_book(Path(temp), "book")
            first = build(book, draft=True)[1]
            with patch("quoin.assemble.code_fingerprint", return_value="cafebabe" * 8):
                second = build(book, draft=True)[1]
        self.assertFalse(first["stages"]["assemble"]["cache_hit"])
        self.assertFalse(second["stages"]["assemble"]["cache_hit"])
        self.assertEqual(
            second["stages"]["assemble"]["input_sha256s"]["code_fingerprint"],
            "cafebabe" * 8,
        )


if __name__ == "__main__":
    unittest.main()
