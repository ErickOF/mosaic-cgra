"""LaneMask model components for specification-based PyUVM validation."""

from __future__ import annotations

from lane_mask.constants import SOURCES


def expected_outputs(ports: tuple[str, str, str, str]) -> tuple[str, str, str]:
    """Evaluate one lane at a time using a truth table, without RTL internals.

    A zero dominates even unknown inputs; only four asserted controls activate
    a lane. Z is an unknown logic operand, so derived controls cannot be Z.
    """
    operation, valid, mask, predicate = ports
    active = []
    for controls in zip(valid, mask, predicate, strict=True):
        lane = (operation, *controls)
        active.append("0" if "0" in lane else "1" if all(bit == "1" for bit in lane) else "x")
    active_word = "".join(active)
    return active_word, active_word.translate(str.maketrans("01x", "10x")), active_word


def unknown_controls(ports: tuple[str, str, str, str]) -> tuple[str, ...]:
    """Local controls are required known only for a known, valid operation."""
    operation, *vectors = ports
    unknown = []
    if operation not in ("0", "1"):
        unknown.append("i_operation_valid")
    if operation == "1":
        unknown.extend(name for name, word in zip(SOURCES, vectors, strict=True) if set(word) & {"x", "z"})
    return tuple(unknown)
