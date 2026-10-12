"""ClockGate model components for specification-based PyUVM validation."""

from __future__ import annotations


def effective_enable(enable: str, test_enable: str) -> str:
    """Four-state OR: a known override masks X/Z, but the diagnostic remains."""
    if "1" in (enable, test_enable):
        return "1"
    return "0" if enable == test_enable == "0" else "x"
