import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image

from quoin.assemble import build, cover_font
from quoin.check import check, epubcheck_command, run_epubcheck
from quoin.errors import QuoinError
from quoin.fetch import MAX_DOWNLOAD_BYTES, _fetch_web


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
            with (
                patch.dict(os.environ, {"QUOIN_COVER_FONT": str(environment)}),
                patch("quoin.assemble.FONT_CANDIDATES", (Path(temp) / "candidate.ttf",)),
            ):
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
                self.assertEqual(
                    epubcheck_command({"epubcheck_jar": str(configured)})[0][-1], str(configured)
                )

    def test_epubcheck_env_wins_over_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            environment = Path(temp) / "environment.jar"
            environment.touch()
            with (
                patch.dict(os.environ, {"QUOIN_EPUBCHECK_JAR": str(environment)}),
                patch("quoin.check.shutil.which", return_value="/bin/epubcheck"),
            ):
                self.assertEqual(epubcheck_command({})[0][-1], str(environment))

    def test_epubcheck_error_names_routes(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("quoin.check.shutil.which", return_value=None),
        ):
            with self.assertRaises(QuoinError) as caught:
                epubcheck_command({})
        message = str(caught.exception)
        self.assertIn("epubcheck_jar", message)
        self.assertIn("QUOIN_EPUBCHECK_JAR", message)
        self.assertIn("which epubcheck", message)

    def test_epubcheck_path_wrapper_discovered_and_parsed(self) -> None:
        # 003/009 residual: tier 3 (shutil.which) discovery, exercised against a
        # real executable on a real PATH rather than a mocked shutil.which, plus
        # the shared run_epubcheck output parser against that wrapper's output.
        with tempfile.TemporaryDirectory() as temp:
            wrapper = Path(temp) / "epubcheck"
            wrapper.write_text(
                "#!/bin/sh\necho 'Messages: 0 fatals / 0 errors / 0 warnings'\n",
                encoding="utf-8",
            )
            wrapper.chmod(0o755)
            environment = dict(os.environ)
            environment.pop("QUOIN_EPUBCHECK_JAR", None)
            environment["PATH"] = temp
            with patch.dict(os.environ, environment, clear=True):
                command, route = epubcheck_command({})
            self.assertEqual(command, [str(wrapper)])
            self.assertEqual(route, "which epubcheck")
            clean, line = run_epubcheck(command, Path(temp) / "book.epub")
            self.assertTrue(clean)
            self.assertIn("0 fatals", line)

    def test_web_fetch_sets_timeout(self) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"<article>text</article>"
        response.status = 200
        with (
            tempfile.TemporaryDirectory() as temp,
            patch("quoin.fetch.urllib.request.urlopen", return_value=response) as urlopen,
        ):
            _fetch_web(
                Path(temp),
                {"id": "article", "type": "web", "locator": "https://example.com"},
                False,
            )
        self.assertEqual(urlopen.call_args.kwargs["timeout"], 30)

    def test_web_fetch_just_under_cap_passes(self) -> None:
        # 010 residual: a stream one byte under the 20 MB cap must pass cleanly.
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"x" * (MAX_DOWNLOAD_BYTES - 1)
        response.status = 200
        with (
            tempfile.TemporaryDirectory() as temp,
            patch("quoin.fetch.urllib.request.urlopen", return_value=response),
        ):
            data, status, _ = _fetch_web(
                Path(temp),
                {"id": "article", "type": "web", "locator": "https://example.com"},
                False,
            )
        self.assertEqual(len(data), MAX_DOWNLOAD_BYTES - 1)
        self.assertEqual(status, 200)

    def test_web_fetch_just_over_cap_raises(self) -> None:
        # 010 residual: a stream one byte over the 20 MB cap must raise the
        # named QuoinError rather than silently accepting an oversized fetch.
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b"x" * (MAX_DOWNLOAD_BYTES + 1)
        response.status = 200
        with (
            tempfile.TemporaryDirectory() as temp,
            patch("quoin.fetch.urllib.request.urlopen", return_value=response),
        ):
            with self.assertRaises(QuoinError) as caught:
                _fetch_web(
                    Path(temp),
                    {"id": "article", "type": "web", "locator": "https://example.com"},
                    False,
                )
        self.assertIn("20 MB download limit", str(caught.exception))
        self.assertIn("article", str(caught.exception))

    def test_cover_image_change_invalidates_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for directory in ("sources/normalized", "blocks"):
                (root / directory).mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (2, 2), "red").save(root / "cover.png")
            (root / "book.toml").write_text('cover_image = "cover.png"\n', encoding="utf-8")
            manifest = {
                "format_version": 1,
                "slug": "sample",
                "title": "Sample",
                "brand": "Quoin",
                "language": "en",
                "governing_question": "Why?",
                "privacy": {"forbidden_terms": []},
                "sources": [],
                "movements": [],
                "blocks": [],
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
                "format_version": 1,
                "slug": "sample",
                "title": "Sample",
                "brand": "Quoin",
                "language": "en",
                "governing_question": "Why?",
                "privacy": {"forbidden_terms": []},
                "sources": [],
                "movements": [],
                "blocks": [],
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "sources/records.json").write_text("{}", encoding="utf-8")
            (root / "out/sample.epub").write_bytes(b"not a zip")
            with (
                patch("quoin.check.epubcheck_command", return_value=(["epubcheck"], "test")),
                patch("quoin.check.run_epubcheck", return_value=(False, "bad")),
                patch("quoin.check.assemble", return_value=None),
                # check() now unconditionally calls build() to catch stale artifacts
                # (plan 013 fix 2); build's own internal assemble() call isn't the
                # one patched above (it's the same-module reference inside
                # quoin.assemble, not quoin.check's imported alias), so left
                # unpatched it would silently overwrite the deliberately corrupted
                # bytes below with a real, valid empty-book epub. Patch check()'s
                # own build reference to a no-op instead, same as assemble above.
                patch("quoin.check.build", return_value=None),
            ):
                _, payload = check(root)
        self.assertIn("mimetype", payload["tests"])
        self.assertIn("spine", payload["tests"])


if __name__ == "__main__":
    unittest.main()
