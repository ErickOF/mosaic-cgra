"""PriorityEncoder model components for specification-based PyUVM validation."""

from __future__ import annotations

from priority_encoder.config import PriorityEncoderConfig
from priority_encoder.transaction import Reference


def expected_outputs(config: PriorityEncoderConfig, request: str) -> Reference:
    """Use sets of possible winners/count bounds, rather than the RTL scan.

Unknown bits can be either zero or one. An optional no-request outcome counts
as a separate outcome, so even one isolated unknown request is ambiguous.
No enumeration of 2**WIDTH completions is needed for wide unknown vectors.
"""
    known = frozenset(index for index, state in enumerate(reversed(request)) if state == "1")
    unknown = frozenset(index for index, state in enumerate(reversed(request)) if state in "xz")
    best_known = (min(known) if config.lsb_high_priority else max(known)) if known else None
    possible = {best_known} | {index for index in unknown if best_known is None or config.higher(index, best_known)}
    ambiguous = len(possible) > 1
    valid = "1" if known else "x" if unknown else "0"
    multiple = "1" if len(known) > 1 else "0" if len(known) + len(unknown) <= 1 else "x"
    selected = best_known if not ambiguous else None
    index = "x" * config.index_width if ambiguous else f"{selected or 0:0{config.index_width}b}"
    onehot = "x" * config.width if ambiguous else f"{0 if selected is None else 1 << selected:0{config.width}b}"
    return Reference((valid, index, onehot, multiple), ambiguous, selected, known, unknown)


def pattern_classes(value: int, width: int) -> set[str]:
    population = value.bit_count()
    classes = set()
    if population == 0:
        classes.add("none")
    if population == 1:
        classes.add("single")
    if population == 2:
        classes.add("pair")
    if value == (1 << width) - 1:
        classes.add("all")
    if population:
        low, high = (value & -value).bit_length() - 1, value.bit_length() - 1
        classes.add("contiguous" if population == high - low + 1 else "noncontiguous")
    if value in (int((pattern * width)[:width], 2) for pattern in ("01", "10")):
        classes.add("alternating")
    return classes
