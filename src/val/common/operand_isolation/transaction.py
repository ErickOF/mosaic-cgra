"""OperandIsolation transaction components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pyuvm import uvm_sequence_item


@dataclass(frozen=True)
class Inputs:
    data: int | str
    isolate: int | str


class OperandIsolationItem(uvm_sequence_item):
    def __init__(self, label, inputs, *, expected_unknown=None, hold_ns=0.001):
        super().__init__(label)
        assert math.isfinite(hold_ns) and hold_ns >= 0.001
        self.inputs = inputs
        self.expected_unknown = expected_unknown
        self.hold_ns = hold_ns


@dataclass(frozen=True)
class Observation:
    label: str
    data: str
    isolate: str
    output: str
    requested: Inputs
    expected_unknown: str | None
    stage: str
    hold_ns: float


@dataclass(frozen=True)
class OutputActivity:
    value: str
    quiet: bool
