"""Conservative, root-anchored Git-path glob matching.

Only * (inside a segment), ? and ** (as a complete segment) are supported.
Unlike fnmatch, * never crosses directory separators.
"""
from __future__ import annotations

import re
from functools import lru_cache


class PatternError(ValueError):
    """A policy pattern cannot be safely interpreted."""


def validate_pattern(pattern: str) -> str:
    if not isinstance(pattern, str) or not pattern:
        raise PatternError("Glob must be a nonempty string")
    if pattern != pattern.strip() or pattern.startswith("/") or "\\" in pattern:
        raise PatternError(f"Invalid root-relative glob: {pattern!r}")
    if "\x00" in pattern or "[" in pattern or "]" in pattern or "{" in pattern or "}" in pattern:
        raise PatternError(f"Unsupported syntax in glob: {pattern!r}")
    parts = pattern.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise PatternError(f"Invalid path component in glob: {pattern!r}")
    if any("**" in part and part != "**" for part in parts):
        raise PatternError(f"** must occupy an entire component: {pattern!r}")
    return pattern


@lru_cache(maxsize=2048)
def compile_pattern(pattern: str) -> re.Pattern[str]:
    parts = validate_pattern(pattern).split("/")
    regex = "^"
    for index, part in enumerate(parts):
        last = index == len(parts) - 1
        if part == "**":
            if last:
                regex += r"(?:[^/]+(?:/[^/]+)*)?"
            else:
                regex += r"(?:[^/]+/)*"
            continue
        regex += "".join(
            r"[^/]*" if c == "*" else r"[^/]" if c == "?" else re.escape(c)
            for c in part
        )
        if not last:
            regex += "/"
    return re.compile(regex + "$")


def matches(patterns: tuple[str, ...], path: str) -> bool:
    return any(compile_pattern(pattern).fullmatch(path) is not None for pattern in patterns)
