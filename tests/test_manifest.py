import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from quoin.errors import ManifestError
from quoin.manifest import load, validate


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
        "movements": [{"id": "m1", "title": "One", "items": [{"ref": "source:article"}, {"ref": "block:intro"}]}],
        "blocks": [{"id": "intro", "kind": "introduction", "brief": "Introduce it.", "evidence": []}],
    }


class ManifestValidationTests(unittest.TestCase):
    def test_valid_manifest_passes(self) -> None:
        self.assertEqual(validate(valid_manifest()), [])

    def test_each_missing_top_level_field(self) -> None:
        for key in valid_manifest():
            with self.subTest(key=key):
                manifest = valid_manifest()
                del manifest[key]
                self.assertIn(f"manifest.json: {key} is required", validate(manifest))

    def test_sources_must_be_list(self) -> None:
        manifest = valid_manifest()
        manifest["sources"] = {}
        self.assertIn("manifest.json: sources must be a list", validate(manifest))

    def test_chapter_locator_wrong_type(self) -> None:
        manifest = valid_manifest()
        manifest["sources"] = [{"id": "book", "type": "epub", "locator": "book.epub", "chapter_locator": 3}]
        self.assertIn("manifest.json: sources[0].chapter_locator must be a string or list of strings", validate(manifest))

    def test_traversal_source_id_is_rejected(self) -> None:
        manifest = valid_manifest()
        manifest["sources"][0]["id"] = "../evil"
        manifest["movements"][0]["items"][0]["ref"] = "source:../evil"
        errors = validate(manifest)
        self.assertTrue(any("sources[0].id" in error and "../evil" in error for error in errors))

    def test_traversal_block_id_is_rejected(self) -> None:
        manifest = valid_manifest()
        manifest["blocks"][0]["id"] = "../evil"
        manifest["movements"][0]["items"][1]["ref"] = "block:../evil"
        self.assertTrue(any("blocks[0].id" in error for error in validate(manifest)))

    def test_unreferenced_source_is_rejected(self) -> None:
        manifest = valid_manifest()
        manifest["movements"][0]["items"] = [{"ref": "block:intro"}]
        self.assertIn("manifest.json: source article must be referenced exactly once; found 0", validate(manifest))

    def test_duplicate_source_reference_is_rejected(self) -> None:
        manifest = valid_manifest()
        manifest["movements"][0]["items"].insert(1, {"ref": "source:article"})
        self.assertIn("manifest.json: source article must be referenced exactly once; found 2", validate(manifest))

    def test_unknown_ref(self) -> None:
        manifest = valid_manifest()
        manifest["movements"][0]["items"] = [{"ref": "source:missing"}]
        self.assertIn("manifest.json: movements[0].items[0].ref names unknown reference source:missing", validate(manifest))

    def test_duplicate_source_id(self) -> None:
        manifest = valid_manifest()
        manifest["sources"].append(dict(manifest["sources"][0]))
        self.assertIn("manifest.json: sources[1].id duplicates article", validate(manifest))

    def test_epub_requires_chapter_locator(self) -> None:
        manifest = valid_manifest()
        manifest["sources"] = [{"id": "book", "type": "epub", "locator": "book.epub"}]
        self.assertIn("manifest.json: sources[0].chapter_locator is required for epub sources", validate(manifest))

    def test_escaping_cover_image_names_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "book.toml").write_text('cover_image = "../../x.png"\n', encoding="utf-8")
            (root / "manifest.json").write_text(json.dumps(valid_manifest()), encoding="utf-8")
            with self.assertRaisesRegex(Exception, "cover_image"):
                load(root)

    def test_escaping_file_locator_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "book"
            root.mkdir()
            manifest = valid_manifest()
            manifest["sources"][0] = {"id": "article", "type": "file", "locator": "../outside.html"}
            (root / "book.toml").touch()
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(Exception, r"sources\[0\]\.locator"):
                load(root)

    def test_malformed_toml_names_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "book.toml").write_text("bad = [", encoding="utf-8")
            (root / "manifest.json").write_text(json.dumps(valid_manifest()), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "book.toml"):
                load(root)

    def test_malformed_json_names_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "book.toml").touch()
            (root / "manifest.json").write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "manifest.json"):
                load(root)


class CliTaxonomyTests(unittest.TestCase):
    def run_cli(self, root: Path, command: str = "fetch") -> subprocess.CompletedProcess[str]:
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        return subprocess.run(
            [sys.executable, "-m", "quoin", command], cwd=root, env=environment,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )

    def test_empty_directory_is_user_error_with_init_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            result = self.run_cli(Path(temp))
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a book directory", result.stderr)
        self.assertIn("quoin init", result.stderr)

    def test_malformed_json_is_user_error_with_position(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "book.toml").touch()
            (root / "manifest.json").write_text("{", encoding="utf-8")
            result = self.run_cli(root)
        self.assertEqual(result.returncode, 1)
        self.assertIn("manifest.json", result.stderr)
        self.assertIn("line 1 column 2", result.stderr)

    def test_unexpected_exception_is_bug_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "book.toml").touch()
            (root / "manifest.json").write_text(json.dumps(valid_manifest()), encoding="utf-8")
            result = self.run_cli(root, "build")
        self.assertEqual(result.returncode, 2)
        self.assertIn("quoin build crashed (bug):", result.stderr)
        self.assertIn("cli.py", result.stderr)


if __name__ == "__main__":
    unittest.main()
