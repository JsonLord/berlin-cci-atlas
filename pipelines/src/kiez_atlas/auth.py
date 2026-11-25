"""
Authentication middleware and utilities for Berlin CCI Atlas.
Provides WSGI/ASGI and Flask/FastAPI compatible token / API key authentication middleware.
"""

import logging
from typing import Callable, Optional, Dict, Any

logger = logging.getLogger(__name__)

class APIKeyAuthMiddleware:
    """
    WSGI / generic Python middleware for API Key / Bearer Token authentication.
    """
    def __init__(self, app: Callable, api_keys: Optional[set] = None, header_name: str = "HTTP_X_API_KEY"):
        self.app = app
        self.api_keys = api_keys or set()
        self.header_name = header_name

    def __call__(self, environ: Dict[str, Any], start_response: Callable) -> Any:
        # Allow health checks or public endpoints if needed
        path = environ.get("PATH_INFO", "")
        if path in ("/health", "/", "/status") and not self.api_keys:
            return self.app(environ, start_response)

        client_key = environ.get(self.header_name) or environ.get("HTTP_AUTHORIZATION", "")
        
        # If Bearer token format
        if client_key.startswith("Bearer "):
            client_key = client_key[7:]

        if self.api_keys and client_key not in self.api_keys:
            logger.warning(f"Unauthorized access attempt to {path}")
            start_response("401 Unauthorized", [("Content-Type", "text/plain")])
            return [b"Unauthorized: Invalid or missing API key\n"]

        return self.app(environ, start_response)


def verify_token(token: str, valid_tokens: set) -> bool:
    """Helper function to verify token validity."""
    return token in valid_tokens
