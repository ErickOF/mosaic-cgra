"""ClockGate transaction components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from pyuvm import uvm_sequence_item


@dataclass(frozen=True)
class ControlChange:
    offset_ps: int
    enable: int | str | None = None
    test_enable: int | str | None = None


class ClockGateItem(uvm_sequence_item):
    """One complete low/high source-clock cycle, with timed control changes."""

    def __init__(self, label, changes=(), *, unknown=None):
        super().__init__(label)
        self.changes = changes
        self.unknown = unknown


@dataclass(frozen=True)
class Snapshot:
    time_ps: int
    clk: str
    enable: str
    test_enable: str
    gclk: str
    label: str
    expected_unknown: tuple[str, str] | None


@dataclass(frozen=True)
class OutputChange:
    time_ps: int
    previous: str
    current: str
    source_level: str
