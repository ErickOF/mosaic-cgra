"""Dff model components for specification-based PyUVM validation."""

from __future__ import annotations


def illegal_control(rstb: str, enable: str, has_enable: bool) -> tuple[str, str] | None:
    """Reset must be known; enable must be known only when it is relevant."""
    if rstb not in ("0", "1"):
        return "rstb", rstb
    if rstb == "1" and has_enable and enable not in ("0", "1"):
        return "enable", enable
    return None
