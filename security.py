"""Defensive validation for untrusted LaTeX input."""

from __future__ import annotations

import re

# Shell escape is disabled at the compiler level as the primary control.
# These checks add defense-in-depth against common file/process primitives.
_FORBIDDEN_PATTERNS = [
    (re.compile(r"\\write18\b", re.IGNORECASE), "write18 shell execution"),
    (re.compile(r"\\immediate\s*\\write18\b", re.IGNORECASE), "immediate write18"),
    (re.compile(r"\\ShellEscape\b", re.IGNORECASE), "ShellEscape"),
    (re.compile(r"\\input\b", re.IGNORECASE), "input file inclusion"),
    (re.compile(r"\\include\b", re.IGNORECASE), "include file inclusion"),
    (re.compile(r"\\openin\b", re.IGNORECASE), "openin file read"),
    (re.compile(r"\\openout\b", re.IGNORECASE), "openout file write"),
    (re.compile(r"\\read\b", re.IGNORECASE), "read primitive"),
    (re.compile(r"\\catcode\b", re.IGNORECASE), "catcode manipulation"),
    (re.compile(r"\\csname\b", re.IGNORECASE), "csname dynamic command"),
    (re.compile(r"\\directlua\b", re.IGNORECASE), "directlua execution"),
    (re.compile(r"\\newwrite\b", re.IGNORECASE), "newwrite file handle"),
]


class UnsafeLaTeXError(ValueError):
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Unsafe LaTeX input: {reason}")


def sanitise(latex: str) -> str:
    """Reject known-dangerous TeX primitives and return the input unchanged."""
    for pattern, description in _FORBIDDEN_PATTERNS:
        if pattern.search(latex):
            raise UnsafeLaTeXError(description)
    return latex


