"""API-key / bearer-token authentication for a WSGI application.

Nothing in this repository serves HTTP yet: the deployed product is a static
site (`index.html` + `config.js` + `data/public/`), and `data/deploy-allowlist.txt`
publishes no Python at all. This module exists so that a future read-only API
over the internal data has one reviewed way to authenticate, rather than each
caller inventing one.

Scope, stated plainly:

* **WSGI only.** The `__call__(environ, start_response)` signature is the WSGI
  contract. It is not ASGI, and it is not a Flask/FastAPI dependency — those
  frameworks would wrap or replace it, not use it directly.
* **Static keys only.** Keys are compared against an in-memory set. There is no
  rotation, expiry, per-key scoping or audit trail. That is deliberate: a
  credential store is a decision, not an implementation detail, and this module
  does not make it.
* **Fail-closed when keys are configured, fail-open when they are not.** An
  empty key set means "no authentication configured" and lets every request
  through, with a warning at construction time. A non-empty set rejects every
  request that does not present one of its keys — including ``/health`` and
  ``/``. There is no unauthenticated path once keys exist, because a path
  exemption is the kind of thing that quietly becomes an open endpoint.
"""

from __future__ import annotations

import hmac
import logging
from collections.abc import Callable, Iterable, Mapping
from typing import Any

logger = logging.getLogger(__name__)

BEARER_PREFIX = "Bearer "


class APIKeyAuthMiddleware:
    """Reject requests that do not carry one of the configured keys.

    The key is read from ``header_name`` (a WSGI ``environ`` key such as
    ``HTTP_X_API_KEY``) and, failing that, from ``HTTP_AUTHORIZATION``, where
    both a bare token and ``Bearer <token>`` are accepted.
    """

    def __init__(
        self,
        app: Callable[[Mapping[str, Any], Callable[..., Any]], Iterable[bytes]],
        api_keys: Iterable[str] | None = None,
        header_name: str = "HTTP_X_API_KEY",
    ) -> None:
        self.app = app
        self.api_keys = frozenset(api_keys or ())
        self.header_name = header_name
        if not self.api_keys:
            logger.warning(
                "APIKeyAuthMiddleware constructed with no api_keys: "
                "every request will be allowed through unauthenticated"
            )

    def _presented_key(self, environ: Mapping[str, Any]) -> str:
        raw = environ.get(self.header_name) or environ.get("HTTP_AUTHORIZATION") or ""
        raw = raw.strip()
        if raw.startswith(BEARER_PREFIX):
            raw = raw[len(BEARER_PREFIX):].strip()
        return raw

    def _is_valid(self, presented: str) -> bool:
        """True when `presented` is one of the configured keys.

        Each comparison goes through `hmac.compare_digest` rather than `==`, so
        the time taken does not depend on how many leading characters of a
        valid key the caller guessed correctly.
        """
        return any(verify_token(presented, {key}) for key in self.api_keys)

    def __call__(
        self,
        environ: Mapping[str, Any],
        start_response: Callable[..., Any],
    ) -> Iterable[bytes]:
        path = environ.get("PATH_INFO", "")

        if not self.api_keys:
            return self.app(environ, start_response)

        if not self._is_valid(self._presented_key(environ)):
            # The path is logged, the presented credential never is: a wrong
            # key is often a real key for the wrong environment.
            logger.warning("unauthorized access attempt to %s", path)
            start_response(
                "401 Unauthorized",
                [
                    ("Content-Type", "text/plain; charset=utf-8"),
                    ("WWW-Authenticate", 'Bearer realm="kiez-atlas"'),
                ],
            )
            return [b"Unauthorized: invalid or missing API key\n"]

        return self.app(environ, start_response)


def verify_token(token: str, valid_tokens: Iterable[str]) -> bool:
    """Return True when ``token`` is one of ``valid_tokens``, in constant time."""
    if not token:
        return False
    return any(hmac.compare_digest(token, candidate) for candidate in valid_tokens)
