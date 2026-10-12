"""LevelShifter transaction components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pyuvm import uvm_sequence_item


class LevelShifterItem(uvm_sequence_item):
    def __init__(self, label, data, *, hold_ns=0.001):
        super().__init__(label)
        assert math.isfinite(hold_ns) and hold_ns >= 0.001
        self.data = data
        self.hold_ns = hold_ns


@dataclass(frozen=True)
class Observation:
    label: str
    source: str
    output: str
    requested: str
    stage: str
    hold_ns: float


@dataclass(frozen=True)
class OutputActivity:
    value: str
    stable_input: bool
