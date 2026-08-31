"""Unit tests for the contamination_allow opt-in allowlist.

The CONTAMINATION regex in normalize.py (subscribe/sign up/newsletter/cookie/
comments/next post/previous post) also fires on real source prose that uses one
of those words innocently -- McPhee's "a salient comment", McKenzie's "HN
comments", Sloan's "The comments on Matt's post" -- so a book quoting that prose
verbatim could never pass the gate. contamination_hits() (check.py) and the
manifest.json sources[].contamination_allow field (manifest.py) let a source
declare an exact quote of its own prose that excuses the regex hits inside it,
without weakening the gate for anything else: furniture text and any hit
outside a declared quote still fails.

Covers contamination_hits() directly, manifest.validate() for the new field,
and one end-to-end check() run built from the evals/fixtures/sample pattern
used by tests/test_release_gates.py.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from quoin.check import check, contamination_hits
from quoin.fetch import run as fetch
from quoin.manifest import validate

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = REPO_ROOT / "evals" / "fixtures" / "sample"


def valid_manifest() -> dict:
    return {
        "format_version": 1,
        "slug": "sample",
        "title": "Sample",
        "brand": "Quoin",
        "language": "en",
        "governing_question": "What works?",
        "privacy": {"forbidden_terms": ["private"]},
        "sources": [{"id": "article", "type": "web", "locator": "https://example.com/article"}],
        "movements": [
            {
                "id": "m1",
                "title": "One",
                "items": [{"ref": "source:article"}, {"ref": "block:intro"}],
            }
        ],
        "blocks": [
            {"id": "intro", "kind": "introduction", "brief": "Introduce it.", "evidence": []}
        ],
    }


def _prepare_book(parent: Path, name: str) -> Path:
    """Copy the sample fixture, drop the valid authored blocks-valid/ set into
    blocks/, and fetch offline so build()/check() have real, non-placeholder
    content and populated sources/normalized/ to assemble from. Mirrors
    tests/test_release_gates.py's helper of the same name."""
    book = parent / name
    shutil.copytree(FIXTURE, book)
    for file in (FIXTURE / "blocks-valid").iterdir():
        shutil.copy2(file, book / "blocks" / file.name)
    fetch(book, offline=True)
    return book


class ContaminationHitsTests(unittest.TestCase):
    def test_furniture_still_fails_even_when_other_allowances_exist(self) -> None:
        markup = "<p>Subscribe below for updates.</p>"
        allowances = ["The comments on Matt's post were revealing."]
        hits = contamination_hits(markup, allowances)
        self.assertEqual([hit.group(0) for hit in hits], ["Subscribe"])

    def test_declared_prose_quote_containing_comments_passes(self) -> None:
        markup = "<p>Sloan wrote: The comments on Matt's post were revealing.</p>"
        allowances = ["The comments on Matt's post were revealing."]
        self.assertEqual(contamination_hits(markup, allowances), [])

    def test_allowance_not_present_in_markup_excuses_nothing(self) -> None:
        markup = "<p>The novel drew a wave of comments online.</p>"
        allowances = ["This exact sentence never appears in the markup."]
        hits = contamination_hits(markup, allowances)
        self.assertEqual([hit.group(0) for hit in hits], ["comments"])

    def test_same_word_outside_allowed_span_still_fails(self) -> None:
        markup = "<p>The comments on the post were mixed. Also HN comments flooded in.</p>"
        allowances = ["The comments on the post were mixed."]
        hits = contamination_hits(markup, allowances)
        # Only the second, unquoted "comments" should survive -- the first is
        # covered by the allowance.
        self.assertEqual(len(hits), 1)
        self.assertEqual(markup[hits[0].start() : hits[0].end()], "comments")
        self.assertIn("HN comments", markup[hits[0].start() - 3 : hits[0].end()])

    def test_no_allowances_behaves_like_bare_contamination_search(self) -> None:
        markup = "<p>Please subscribe below.</p>"
        self.assertEqual([hit.group(0) for hit in contamination_hits(markup, [])], ["subscribe"])
        self.assertEqual([hit.group(0) for hit in contamination_hits(markup, None)], ["subscribe"])

    def test_clean_markup_has_no_hits(self) -> None:
        self.assertEqual(contamination_hits("<p>Nothing forbidden here.</p>", []), [])


class ManifestContaminationAllowValidationTests(unittest.TestCase):
    def test_absent_field_is_fine(self) -> None:
        self.assertEqual(validate(valid_manifest()), [])

    def test_valid_list_of_strings_is_fine(self) -> None:
        manifest = valid_manifest()
        manifest["sources"][0]["contamination_allow"] = ["A quoted line of prose."]
        self.assertEqual(validate(manifest), [])

    def test_non_list_is_rejected(self) -> None:
        manifest = valid_manifest()
        manifest["sources"][0]["contamination_allow"] = "not a list"
        errors = validate(manifest)
        self.assertIn(
            "manifest.json: sources[0].contamination_allow must be a list of non-empty strings",
            errors,
        )

    def test_empty_string_entry_is_rejected(self) -> None:
        manifest = valid_manifest()
        manifest["sources"][0]["contamination_allow"] = ["a fine quote", ""]
        errors = validate(manifest)
        self.assertIn(
            "manifest.json: sources[0].contamination_allow must be a list of non-empty strings",
            errors,
        )

    def test_non_string_entry_is_rejected(self) -> None:
        manifest = valid_manifest()
        manifest["sources"][0]["contamination_allow"] = [123]
        errors = validate(manifest)
        self.assertIn(
            "manifest.json: sources[0].contamination_allow must be a list of non-empty strings",
            errors,
        )


class ContaminationAllowEndToEndTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="quoin-test-contamination-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

    def test_declared_quote_clears_the_contamination_gate(self) -> None:
        book = _prepare_book(self.tmp_path, "contamination-allow")
        quote = "The comments on Matt's post were revealing."

        # Inject the quote into the source's own normalized prose, the way a
        # real source's body would carry it, then declare it as an allowance.
        normalized = book / "sources" / "normalized" / "kanekar.xhtml"
        text = normalized.read_text(encoding="utf-8")
        self.assertIn("</body>", text)
        normalized.write_text(text.replace("</body>", f"<p>{quote}</p></body>"), encoding="utf-8")

        manifest_path = book / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for source in manifest["sources"]:
            if source["id"] == "kanekar":
                source["contamination_allow"] = [quote]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        passed, payload = check(book)
        contamination_row = payload["tests"]["contamination"]
        self.assertTrue(contamination_row["pass"], contamination_row["detail"])
        self.assertEqual(contamination_row["detail"], "clean")

    def test_without_the_allowance_the_same_quote_fails_the_gate(self) -> None:
        # Control for the test above: the same injected prose, minus the
        # manifest declaration, must still trip the gate -- proving the pass
        # above comes from the allowance, not from some other side effect of
        # editing the normalized source.
        book = _prepare_book(self.tmp_path, "contamination-not-allowed")
        quote = "The comments on Matt's post were revealing."
        normalized = book / "sources" / "normalized" / "kanekar.xhtml"
        text = normalized.read_text(encoding="utf-8")
        normalized.write_text(text.replace("</body>", f"<p>{quote}</p></body>"), encoding="utf-8")

        passed, payload = check(book)
        contamination_row = payload["tests"]["contamination"]
        self.assertFalse(contamination_row["pass"])
        self.assertIn("comments", contamination_row["detail"])


if __name__ == "__main__":
    unittest.main()
