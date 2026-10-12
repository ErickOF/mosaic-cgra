"""Retention transaction components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from pyuvm import uvm_sequence_item


@dataclass(frozen=True)
class Inputs:
    clk: int
    rstb: int | str
    enable: int | str
    save: int | str
    restore: int | str
    data: int | str


@dataclass(frozen=True)
class State:
    visible: str
    retained: str


class RetentionItem(uvm_sequence_item):
    def __init__(self, label, inputs, *, duration_ps, expected=(), context="running"):
        super().__init__(label)
        assert inputs.clk in (0, 1) and all(str(value).lower() in ("0", "1", "x", "z") for value in (inputs.rstb, inputs.enable, inputs.save, inputs.restore))
        assert duration_ps >= 3 and context in ("running", "stopped")
        self.inputs, self.duration_ps, self.expected, self.context = inputs, duration_ps, frozenset(expected), context


@dataclass(frozen=True)
class Observation:
    time_ps: int
    inputs: Inputs
    visible: str
    retained: str | None
    item: RetentionItem
    stage: str


@dataclass(frozen=True)
class Activity:
    signal: str
    value: str
    inputs: Inputs
    allowed: bool
