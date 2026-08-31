"""Unit tests for book.toml-configurable User-Agent (fetch.resolve_user_agent).

Covers the pure resolver (default, override, and fallback-on-junk-input cases)
plus one integration check that _fetch_web actually sends the resolved UA on
the outgoing Request, with urllib.request.urlopen monkeypatched so no real
network call happens.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from quoin.fetch import UA, _fetch_web, resolve_user_agent


class ResolveUserAgentTests(unittest.TestCase):
    def test_default_when_key_absent(self) -> None:
        self.assertEqual(resolve_user_agent({}), UA)

    def test_override_returned_when_set(self) -> None:
        book = {"user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        self.assertEqual(resolve_user_agent(book), book["user_agent"])

    def test_empty_string_falls_back_to_default(self) -> None:
        self.assertEqual(resolve_user_agent({"user_agent": ""}), UA)

    def test_non_string_falls_back_to_default(self) -> None:
        # A misconfigured book.toml (e.g. user_agent = 4) must never propagate a
        # non-string value into a header — fall back rather than error here, since
        # this is a resolver, not a validator.
        self.assertEqual(resolve_user_agent({"user_agent": 4}), UA)
        self.assertEqual(resolve_user_agent({"user_agent": None}), UA)
        self.assertEqual(resolve_user_agent({"user_agent": ["x"]}), UA)


class FetchWebUserAgentTests(unittest.TestCase):
    def test_fetch_web_sends_configured_ua(self) -> None:
        book = {"user_agent": "Mozilla/5.0 (compatible; test-browser)"}
        ua = resolve_user_agent(book)
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
                ua=ua,
            )
        sent_request = urlopen.call_args.args[0]
        self.assertEqual(sent_request.get_header("User-agent"), ua)
        self.assertNotEqual(sent_request.get_header("User-agent"), UA)

    def test_fetch_web_defaults_to_ua_constant_when_no_override(self) -> None:
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
        sent_request = urlopen.call_args.args[0]
        self.assertEqual(sent_request.get_header("User-agent"), UA)


if __name__ == "__main__":
    unittest.main()
