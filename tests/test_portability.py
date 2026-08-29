import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from quoin.assemble import cover_font
from quoin.check import epubcheck_command
from quoin.errors import QuoinError


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


if __name__ == "__main__":
    unittest.main()
