"""WriteGate model components for specification-based PyUVM validation."""

from __future__ import annotations


def control_violations(write: str, suppress: str) -> set[str]:
    violations = set()
    if set(write) & set("xz"):
        violations.add("unknown_write_enable")
    if any(w != "0" and s in "xz" for w, s in zip(write, suppress, strict=True)):
        violations.add("unknown_requested_suppression")
    return violations


def mask_class(word: str) -> str:
    if word == "0" * len(word):
        return "zero"
    if word == "1" * len(word):
        return "one"
    if word in (("01" * len(word))[:len(word)], ("10" * len(word))[:len(word)]):
        return "alternating"
    return "other" if set(word) <= set("01") else "unknown"


def decision(write: str, suppress: str) -> str:
    if set(write + suppress) - set("01"):
        return "unknown"
    requested = write.count("1")
    blocked = sum(w == s == "1" for w, s in zip(write, suppress, strict=True))
    return "no_request" if not requested else "permitted" if not blocked else "suppressed" if blocked == requested else "mixed"
