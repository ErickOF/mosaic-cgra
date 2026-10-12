"""Decoder model components for specification-based PyUVM validation."""

from __future__ import annotations


def expected_outputs(num_outputs: int, enable: str, select: str) -> tuple[int, int]:
    """Decode known, enabled, in-range inputs; everything else fails closed."""
    if enable != "1" or set(select) - {"0", "1"}:
        return 0, 0
    selected = int(select, 2)
    return (1 << selected, 1) if selected < num_outputs else (0, 0)
