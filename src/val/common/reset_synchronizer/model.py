"""ResetSynchronizer model components for specification-based PyUVM validation."""

from __future__ import annotations

from decimal import Decimal
import os


def picoseconds(variable: str, default: str) -> int:
    value = Decimal(os.getenv(variable, default)) * 1000
    assert value.is_finite() and value == int(value), f"{variable} must be a whole number of ps"
    return int(value)


def reset_negedge(before: str, after: str) -> bool:
    """IEEE four-state edge rules: 1 to 0/X/Z, or X/Z to 0."""
    return before == "1" and after in "0xz" or before in "xz" and after == "0"
