import os
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from quoin.assemble import build, cover_font
from quoin.check import check, epubcheck_command
from quoin.errors import QuoinError
from quoin.fetch import _fetch_web


class PortabilityTests(unittest.TestCase):
    def test_cover_font_config_wins_over_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            configured = Path(temp) / "configured.ttf"
            environment = Path(temp) / "environment.ttf"
            configured.touch()
            environment.touch()
            with patch.dict(os.environ, {"QUOIN_COVER_FONT": str(environment)}):
                self.assertEqual(cover_font({"cover_font": str(configured)})[0], configured)

    def test_cover_font_env_wins_over_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            environment = Path(temp) / "environment.ttf"
            environment.touch()
            with patch.dict(os.environ, {"QUOIN_COVER_FONT": str(environment)}), patch("quoin.assemble.FONT_CANDIDATES", (Path(temp) / "candidate.ttf",)):
                self.assertEqual(cover_font({})[0], environment)

    def test_cover_font_error_names_routes(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch("quoin.assemble.FONT_CANDIDATES", ()):
            with self.assertRaises(QuoinError) as caught:
                cover_font({})
        self.assertIn("cover_font", str(caught.exception))
        self.assertIn("QUOIN_COVER_FONT", str(caught.exception))
        self.assertIn("install", str(caught.exception))

    def test_epubcheck_config_wins_over_env(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            configured = Path(temp) / "configured.jar"
            environment = Path(temp) / "environment.jar"
            configured.touch()
            environment.touch()
            with patch.dict(os.environ, {"QUOIN_EPUBCHECK_JAR": str(environment)}):
                self.assertEqual(epubcheck_command({"epubcheck_jar": str(configured)})[0][-1], str(configured))

    def test_epubcheck_env_wins_over_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            environment = Path(temp) / "environment.jar"
            environment.touch()
            with patch.dict(os.environ, {"QUOIN_EPUBCHECK_JAR": str(environment)}), patch("quoin.check.shutil.which", return_value="/bin/epubcheck"):
                self.assertEqual(epubcheck_command({})[0][-1], str(environment))

    def test_epubcheck_error_names_routes(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch("quoin.check.shutil.which", return_value=None):
            with self.assertRaises(QuoinError) as caught:
                epubcheck_command({})
        message = str(caught.exception)
        self.assertIn("epubcheck_jar", message)
        self.assertIn("QUOIN_EPUBCHECK_JAR", message)
        self.assertIn("which epubcheck", message)

    def test_web_fetch_sets_timeout(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"<article>text</article>"
        response.status = 200
        with tempfile.TemporaryDirectory() as temp, patch("quoin.fetch.urllib.request.urlopen", return_value=response) as urlopen:
            _fetch_web(Path(temp), {"id": "article", "type": "web", "locator": "https://example.com"}, False)
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 30)

    def test_cover_image_change_invalidates_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory in ("sources/normalized", "blocks"):
                (root / directory).mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (2, 2), "red").save(root / "cover.png")
            (root / "book.toml").write_text('cover_image = "cover.png"\n', encoding="utf-8")
            manifest = {
                "format_version": 1, "slug": "sample", "title": "Sample", "brand": "Quoin", "language": "en",
                "governing_question": "Why?", "privacy": {"forbidden_terms": []}, "sources": [], "movements": [], "blocks": [],
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "sources/records.json").write_text("{}", encoding="utf-8")
            first = build(root, draft=True)[1]
            second = build(root, draft=True)[1]
            Image.new("RGB", (2, 2), "blue").save(root / "cover.png")
            third = build(root, draft=True)[1]
        self.assertFalse(first["stages"]["assemble"]["cache_hit"])
        self.assertTrue(second["stages"]["assemble"]["cache_hit"])
        self.assertFalse(third["stages"]["assemble"]["cache_hit"])

    def test_corrupted_zip_reports_independent_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "out").mkdir()
            (root / "sources").mkdir()
            (root / "book.toml").write_text('epubcheck_jar = "/fake.jar"\n', encoding="utf-8")
            manifest = {
                "format_version": 1, "slug": "sample", "title": "Sample", "brand": "Quoin", "language": "en",
                "governing_question": "Why?", "privacy": {"forbidden_terms": []}, "sources": [], "movements": [], "blocks": [],
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "sources/records.json").write_text("{}", encoding="utf-8")
            (root / "out/sample.epub").write_bytes(b"not a zip")
            with patch("quoin.check.epubcheck_command", return_value=(["epubcheck"], "test")), patch("quoin.check.run_epubcheck", return_value=(False, "bad")), patch("quoin.check.assemble", return_value=None):
                _, payload = check(root)
        self.assertIn("mimetype", payload["tests"])
        self.assertIn("spine", payload["tests"])


if __name__ == "__main__":
    unittest.main()
