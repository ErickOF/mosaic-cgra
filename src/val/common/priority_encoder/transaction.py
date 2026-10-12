"""PriorityEncoder transaction components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pyuvm import uvm_sequence_item


@dataclass(frozen=True)
class Reference:
    outputs: tuple[str, str, str, str]
    ambiguous: bool
    selected: int | None
    known: frozenset[int]
    unknown: frozenset[int]


class PriorityEncoderItem(uvm_sequence_item):
    def __init__(self, label, request, *, expected_ambiguity=False, hold_ns=0.001):
        super().__init__(label)
        assert math.isfinite(hold_ns) and hold_ns >= 0.001
        self.request, self.expected_ambiguity, self.hold_ns = request, expected_ambiguity, hold_ns


@dataclass(frozen=True)
class Observation:
    label: str
    request: str
    outputs: tuple[str, str, str, str]
    requested: int | str
    expected_ambiguity: bool
    stage: str
    hold_ns: float


@dataclass(frozen=True)
class OutputActivity:
    signal: str
    value: str
    quiet: bool
