"""WriteGate transaction components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pyuvm import uvm_sequence_item


@dataclass(frozen=True)
class Inputs:
    write: int | str
    suppress: int | str
    data: int = 0
    destination: str = "register"
    address: int = 0
    protocol: str = "accepted"
    reason: str = "none"


class WriteGateItem(uvm_sequence_item):
    def __init__(self, label, inputs, *, expected_violations=(), hold_ns=0.001):
        super().__init__(label)
        assert math.isfinite(hold_ns) and hold_ns >= 0.001
        self.inputs = inputs
        self.expected_violations = set(expected_violations)
        self.hold_ns = hold_ns


@dataclass(frozen=True)
class Observation:
    item: WriteGateItem
    stage: str
    write: str
    suppress: str
    permitted: str
    suppressed: str
    data: str | None
    destination: int | None
    address: int | None
    valid: int | None
    register: str | None
    memory: str | None


@dataclass(frozen=True)
class Activity:
    signal: str
    value: str
    quiet: bool
    capture_window: bool
