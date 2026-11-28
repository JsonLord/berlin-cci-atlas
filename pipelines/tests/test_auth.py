"""The API-key middleware's decision table, pinned.

Run from the repository root with:

    PYTHONPATH=./pipelines/src python -m pytest pipelines/tests -v

Two of these tests are the reason the module was rewritten rather than merely
accepted. The first is that an empty key set allows *everything*: that is a
deliberate fail-open default, and a test states it so nobody discovers it by
deploying. The second is that a configured key set protects *every* path,
including ``/health`` and ``/``: the earlier version exempted those three paths,
which is an open endpoint with extra steps.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PIPELINE_SRC = REPO / "pipelines" / "src"
if str(PIPELINE_SRC) not in sys.path:
    sys.path.insert(0, str(PIPELINE_SRC))

from kiez_atlas.auth import APIKeyAuthMiddleware, verify_token  # noqa: E402


def dummy_app(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [b"OK"]


def call(app, environ):
    """Drive a WSGI app and return (status, headers, body)."""
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(app(environ, start_response))
    return captured["status"], captured["headers"], body


class TestVerifyToken(unittest.TestCase):
    def test_valid_token(self):
        valid = {"secret-123", "token-abc"}
        self.assertTrue(verify_token("secret-123", valid))
        self.assertTrue(verify_token("token-abc", valid))

    def test_invalid_token(self):
        valid = {"secret-123", "token-abc"}
        self.assertFalse(verify_token("wrong", valid))
        self.assertFalse(verify_token("", valid))

    def test_empty_valid_set(self):
        self.assertFalse(verify_token("any-token", set()))

    def test_prefix_of_a_valid_key_is_not_valid(self):
        """A timing-safe comparison must also be a correct one."""
        self.assertFalse(verify_token("secret-12", {"secret-123"}))
        self.assertFalse(verify_token("secret-1234", {"secret-123"}))

    def test_accepts_any_iterable(self):
        self.assertTrue(verify_token("k", (k for k in ["k"])))


class TestNoKeysConfigured(unittest.TestCase):
    """An empty key set means 'no authentication', and says so."""

    def test_every_path_is_allowed(self):
        app = APIKeyAuthMiddleware(dummy_app, api_keys=set())
        for path in ("/", "/health", "/status", "/data", "/internal/anything"):
            status, _, body = call(app, {"PATH_INFO": path})
            self.assertEqual("200 OK", status, path)
            self.assertEqual(b"OK", body)

    def test_warns_at_construction(self):
        with self.assertLogs("kiez_atlas.auth", level="WARNING") as logs:
            APIKeyAuthMiddleware(dummy_app, api_keys=set())
        self.assertIn("no api_keys", "\n".join(logs.output))


class TestKeysConfigured(unittest.TestCase):
    def setUp(self):
        self.app = APIKeyAuthMiddleware(dummy_app, api_keys={"secret-123"})

    def test_api_key_header_allows(self):
        status, _, body = call(
            self.app, {"PATH_INFO": "/data", "HTTP_X_API_KEY": "secret-123"}
        )
        self.assertEqual("200 OK", status)
        self.assertEqual(b"OK", body)

    def test_bearer_token_allows(self):
        status, _, _ = call(
            self.app,
            {"PATH_INFO": "/data", "HTTP_AUTHORIZATION": "Bearer secret-123"},
        )
        self.assertEqual("200 OK", status)

    def test_bare_authorization_token_allows(self):
        status, _, _ = call(
            self.app, {"PATH_INFO": "/data", "HTTP_AUTHORIZATION": "secret-123"}
        )
        self.assertEqual("200 OK", status)

    def test_surrounding_whitespace_is_tolerated(self):
        status, _, _ = call(
            self.app, {"PATH_INFO": "/data", "HTTP_X_API_KEY": "  secret-123  "}
        )
        self.assertEqual("200 OK", status)

    def test_wrong_key_is_rejected(self):
        status, headers, body = call(
            self.app, {"PATH_INFO": "/data", "HTTP_X_API_KEY": "wrong-key"}
        )
        self.assertIn("401", status)
        self.assertIn(b"Unauthorized", body)
        self.assertIn("Bearer", headers["WWW-Authenticate"])

    def test_missing_key_is_rejected(self):
        status, _, body = call(self.app, {"PATH_INFO": "/data"})
        self.assertIn("401", status)
        self.assertIn(b"Unauthorized", body)

    def test_wrong_bearer_token_is_rejected(self):
        status, _, _ = call(
            self.app,
            {"PATH_INFO": "/data", "HTTP_AUTHORIZATION": "Bearer nope"},
        )
        self.assertIn("401", status)

    def test_health_and_root_are_not_exempt(self):
        """The regression this module was rewritten for."""
        for path in ("/health", "/", "/status"):
            status, _, _ = call(self.app, {"PATH_INFO": path})
            self.assertIn("401", status, f"{path} was left unauthenticated")

    def test_rejection_does_not_call_the_wrapped_app(self):
        calls = []

        def spy(environ, start_response):
            calls.append(environ.get("PATH_INFO"))
            return dummy_app(environ, start_response)

        app = APIKeyAuthMiddleware(spy, api_keys={"secret-123"})
        call(app, {"PATH_INFO": "/data"})
        self.assertEqual([], calls)

    def test_rejection_does_not_log_the_presented_key(self):
        with self.assertLogs("kiez_atlas.auth", level="WARNING") as logs:
            call(self.app, {"PATH_INFO": "/data", "HTTP_X_API_KEY": "leaked-value"})
        joined = "\n".join(logs.output)
        self.assertIn("/data", joined)
        self.assertNotIn("leaked-value", joined)


if __name__ == "__main__":
    unittest.main()
