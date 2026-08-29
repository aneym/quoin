"""Unit tests for plan 006: a failing-input test for every release-branch gate.

Each test corrupts one thing about an otherwise-valid book (built from a temp copy
of evals/fixtures/sample plus its blocks-valid/ authored set) and asserts the
specific, named complaint the gate must produce — not just "it failed somehow".
Modeled on plan 005's tests/test_media.py layout (unittest.TestCase, direct
function calls, tempfile.TemporaryDirectory per test).
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from quoin.assemble import build
from quoin.blocks import status
from quoin.check import check
from quoin.fetch import run as fetch
from quoin.manifest import load

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "evals" / "fixtures" / "sample"


def _prepare_book(parent: Path, name: str) -> Path:
    """Copy the sample fixture, drop the valid authored blocks-valid/ set into
    blocks/, and fetch offline so build()/check() have real, non-placeholder
    content and populated sources/normalized/ to assemble from."""
    book = parent / name
    shutil.copytree(FIXTURE, book)
    for file in (FIXTURE / "blocks-valid").iterdir():
        shutil.copy2(file, book / "blocks" / file.name)
    fetch(book, offline=True)
    return book


def _block_declaration(book: Path, block_id: str) -> dict:
    _, manifest = load(book)
    return next(block for block in manifest["blocks"] if block["id"] == block_id)


class ReleaseGateFailureMatrixTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="quoin-test-release-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    # -- block validation (status()), exercised via a corrupted authored block --

    def test_malformed_block_json_reports_invalid(self) -> None:
        book = _prepare_book(self.tmp_path, "malformed")
        (book / "blocks" / "intro-kanekar.json").write_text("{not valid json", encoding="utf-8")
        state, error = status(book, _block_declaration(book, "intro-kanekar"))
        self.assertEqual(state, "invalid")
        self.assertIn("Expecting property name enclosed in double quotes", error)

    def test_block_id_mismatch_with_filename(self) -> None:
        book = _prepare_book(self.tmp_path, "id-mismatch")
        path = book / "blocks" / "intro-kanekar.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["block_id"] = "some-other-id"
        path.write_text(json.dumps(data), encoding="utf-8")
        state, error = status(book, _block_declaration(book, "intro-kanekar"))
        self.assertEqual(state, "invalid")
        self.assertIn("block_id must equal intro-kanekar", error)

    def test_script_tag_in_html_rejected(self) -> None:
        book = _prepare_book(self.tmp_path, "script-tag")
        path = book / "blocks" / "intro-kanekar.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["html"] = "<p>Hello.</p><script>alert(1)</script>"
        path.write_text(json.dumps(data), encoding="utf-8")
        state, error = status(book, _block_declaration(book, "intro-kanekar"))
        self.assertEqual(state, "invalid")
        self.assertIn("script is not allowed", error)

    def test_invalid_xhtml_fragment_rejected(self) -> None:
        book = _prepare_book(self.tmp_path, "bad-xhtml")
        path = book / "blocks" / "intro-kanekar.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["html"] = "<p>An unclosed <em>tag</p>"
        path.write_text(json.dumps(data), encoding="utf-8")
        state, error = status(book, _block_declaration(book, "intro-kanekar"))
        self.assertEqual(state, "invalid")
        self.assertIn("mismatched tag", error)

    # -- release-branch gates (check(root, release=True)) --

    def test_missing_sidecar_fails_release_stylepass_gate(self) -> None:
        book = _prepare_book(self.tmp_path, "missing-sidecar")
        build(book, draft=False)
        (book / "blocks" / "bridge.stylepass.json").unlink()
        passed, payload = check(book, release=True)
        self.assertFalse(passed)
        stylepass_row = payload["tests"]["stylepass"]
        self.assertFalse(stylepass_row["pass"])
        self.assertIn("bridge.stylepass.json", stylepass_row["detail"])

    def test_empty_claims_list_fails_release_claims_gate(self) -> None:
        # Proves the one-line claims_ok fix (plan 006's E18, gate-enforcement clause):
        # a sidecar asserting zero claims must fail the "claims" row, not vacuously pass it.
        book = _prepare_book(self.tmp_path, "empty-claims")
        build(book, draft=False)
        sidecar = book / "blocks" / "bridge.stylepass.json"
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        data["claims"] = []
        sidecar.write_text(json.dumps(data), encoding="utf-8")
        passed, payload = check(book, release=True)
        self.assertFalse(passed)
        claims_row = payload["tests"]["claims"]
        self.assertFalse(claims_row["pass"])
        self.assertIn("bridge.stylepass.json", claims_row["detail"])

    def test_missing_block_in_release_build_is_hard_error(self) -> None:
        book = _prepare_book(self.tmp_path, "missing-block")
        (book / "blocks" / "intro-kanekar.json").unlink()
        with self.assertRaises(ValueError) as ctx:
            build(book, draft=False)
        self.assertIn("intro-kanekar", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
