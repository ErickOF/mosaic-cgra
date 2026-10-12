"""IsolationCell model components for specification-based PyUVM validation."""

from __future__ import annotations


def isolation_state(control: str, active_high: bool) -> str:
    if control not in ("0", "1"):
        return "unknown"
    return "active" if int(control) == int(active_high) else "inactive"


def expected_data(data: str, control: str, clamp: str, active_high: bool) -> str:
    """Merge each unknown-control bit independently; preserve inactive X/Z data."""
    state = isolation_state(control, active_high)
    if state == "inactive":
        return data
    if state == "active":
        return clamp
    return "".join(bit if bit == clamp_bit else "x" for bit, clamp_bit in zip(data, clamp, strict=True))


def pattern_classes(data: str) -> set[str]:
    classes = set()
    width = len(data)
    if set(data) <= {"0", "1"}:
        value, maximum = int(data, 2), (1 << width) - 1
        if value == 0:
            classes.add("zero")
        if value == maximum:
            classes.add("one")
        if value.bit_count() == 1:
            classes.add("walking_one")
        if (value ^ maximum).bit_count() == 1:
            classes.add("walking_zero")
        if data in (("01" * width)[:width], ("10" * width)[:width]):
            classes.add("alternating")
    if data == "x" * width:
        classes.add("all_x")
    if data == "z" * width:
        classes.add("all_z")
    if {"x", "z"} <= set(data):
        classes.add("mixed_x_z")
    return classes
