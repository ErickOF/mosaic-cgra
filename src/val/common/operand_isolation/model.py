"""OperandIsolation model components for specification-based PyUVM validation."""

from __future__ import annotations


def expected_data(data: str, isolate: str, clamp: str) -> str:
    """An unknown request poisons the entire operand, even equal clamp bits."""
    return {"0": data, "1": clamp}.get(isolate, "x" * len(data))
