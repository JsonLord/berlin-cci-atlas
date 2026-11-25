"""Authentication unit tests for Berlin CCI Atlas.

Run:  python -m pytest pipelines/tests/test_auth.py
      (or: python pipelines/tests/test_auth.py)
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "pipelines" / "src"))

from kiez_atlas.auth import APIKeyAuthMiddleware, verify_token  # noqa: E402


def dummy_app(environ, start_response):
    start_response("200 OK", [("Content-Type", "text/plain")])
    return [b"OK"]


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


class TestAuthMiddleware(unittest.TestCase):
    def _call(self, app, environ):
        status_code = []
        body = []

        def start_response(status, headers):
            status_code.append(status)

        res = app(environ, start_response)
        body.extend(res)
        return status_code, body

    def test_allowed_api_key_header(self):
        app = APIKeyAuthMiddleware(dummy_app, api_keys={"secret-123"})
        environ = {"PATH_INFO": "/data", "HTTP_X_API_KEY": "secret-123"}
        status, body = self._call(app, environ)
        self.assertEqual(status[0], "200 OK")
        self.assertEqual(body, [b"OK"])

    def test_allowed_bearer_token(self):
        app = APIKeyAuthMiddleware(dummy_app, api_keys={"secret-123"})
        environ = {"PATH_INFO": "/data", "HTTP_AUTHORIZATION": "Bearer secret-123"}
        status, body = self._call(app, environ)
        self.assertEqual(status[0], "200 OK")
        self.assertEqual(body, [b"OK"])

    def test_allowed_health_check_without_keys(self):
        app = APIKeyAuthMiddleware(dummy_app, api_keys=set())
        for path in ("/health", "/", "/status"):
            environ = {"PATH_INFO": path}
            status, body = self._call(app, environ)
            self.assertEqual(status[0], "200 OK")

    def test_allowed_empty_keys_all_requests(self):
        app = APIKeyAuthMiddleware(dummy_app, api_keys=set())
        environ = {"PATH_INFO": "/data", "HTTP_X_API_KEY": "whatever"}
        status, body = self._call(app, environ)
        self.assertEqual(status[0], "200 OK")

    def test_unauthorized_wrong_key(self):
        app = APIKeyAuthMiddleware(dummy_app, api_keys={"secret-123"})
        environ = {"PATH_INFO": "/data", "HTTP_X_API_KEY": "wrong-key"}
        status, body = self._call(app, environ)
        self.assertIn("401", status[0])
        self.assertIn(b"Unauthorized", body[0])

    def test_unauthorized_missing_key(self):
        app = APIKeyAuthMiddleware(dummy_app, api_keys={"secret-123"})
        environ = {"PATH_INFO": "/data"}
        status, body = self._call(app, environ)
        self.assertIn("401", status[0])
        self.assertIn(b"Unauthorized", body[0])

    def test_unauthorized_wrong_bearer_token(self):
        app = APIKeyAuthMiddleware(dummy_app, api_keys={"secret-123"})
        environ = {"PATH_INFO": "/data", "HTTP_AUTHORIZATION": "Bearer nope"}
        status, body = self._call(app, environ)
        self.assertIn("401", status[0])
        self.assertIn(b"Unauthorized", body[0])


if __name__ == "__main__":
    unittest.main()