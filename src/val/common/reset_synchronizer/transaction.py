"""ResetSynchronizer transaction components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from pyuvm import uvm_sequence_item


class ResetSynchronizerItem(uvm_sequence_item):
    def __init__(self, label, clk, rstb, *, duration_ps, context="running", expected_unknown=None):
        super().__init__(label)
        assert clk in (0, 1) and str(rstb).lower() in "01xz"
        assert duration_ps >= 3 and context in ("running", "stopped")
        self.clk, self.rstb, self.duration_ps = clk, str(rstb).lower(), duration_ps
        self.context, self.expected_unknown = context, expected_unknown


@dataclass(frozen=True)
class Observation:
    time_ps: int
    clk: str
    rstb: str
    output: str
    stages: str | None
    label: str
    item: ResetSynchronizerItem
    stage: str


@dataclass(frozen=True)
class Activity:
    signal: str
    value: str
    clk: str
    rstb: str
    allowed: bool
    rising_clock: bool
