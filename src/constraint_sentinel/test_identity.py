"""Conservative filename-level identification of test preservation.

A broad policy glob such as tests/** names a protected area but does not prove
that tests/test_calc.py renamed to tests/helper.py remains an executable test.
This is only a heuristic: a human review is needed for nonstandard test names.
"""
from __future__ import annotations

from pathlib import PurePosixPath


def _family(filename: str) -> str | None:
    suffix = PurePosixPath(filename).suffix.lower()
    if filename.startswith("test_") and suffix in {
        ".py", ".js", ".jsx", ".ts", ".tsx", ".rs", ".rb",
    }:
        return "prefix-" + suffix
    for pattern in (".test.js", ".test.ts", ".test.jsx", ".test.tsx",
                    ".spec.js", ".spec.ts", ".spec.jsx", ".spec.tsx",
                    "_test.go", "_test.py", "_test.rs"):
        if filename.endswith(pattern):
            return pattern
    return None


def preserves_test_identity(before: str, after: str) -> bool:
    old = PurePosixPath(before).name
    new = PurePosixPath(after).name
    if not old or not new:
        return False
    if old == new:
        return True
    family = _family(old)
    return family is not None and _family(new) == family
