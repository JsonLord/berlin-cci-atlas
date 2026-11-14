"""Extract the embedded ATLAS data blob from index.html without modifying it.

index.html line 695 holds `window.ATLAS = {...}` (3.26 MB). We brace-match the
object literal rather than regex it, because the JSON contains braces inside
strings (descriptions, coordinates).

This module is strictly read-only with respect to index.html.
"""
from __future__ import annotations

import json
from pathlib import Path

ATLAS_MARKER = "window.ATLAS="
SEARCH_MARKER = "window.ATLAS_SEARCH="


def _brace_match(text: str, start: int) -> str:
    """Return the balanced {...} literal beginning at `start`, respecting strings."""
    if text[start] != "{":
        raise ValueError(f"expected '{{' at offset {start}, got {text[start]!r}")
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    raise ValueError("unbalanced braces: object literal never closed")


def load_atlas(index_html: Path) -> dict:
    """Return the parsed window.ATLAS object."""
    text = index_html.read_text(encoding="utf-8")
    idx = text.find(ATLAS_MARKER)
    if idx < 0:
        raise ValueError(f"{ATLAS_MARKER!r} not found in {index_html}")
    return json.loads(_brace_match(text, idx + len(ATLAS_MARKER)))


def load_search(index_html: Path) -> dict | None:
    """Return window.ATLAS_SEARCH, or None when absent."""
    text = index_html.read_text(encoding="utf-8")
    idx = text.find(SEARCH_MARKER)
    if idx < 0:
        return None
    return json.loads(_brace_match(text, idx + len(SEARCH_MARKER)))


def sha256_of(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
