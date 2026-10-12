"""Counter transaction components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from pyuvm import uvm_sequence_item
from counter.constants import CONTROLS


@dataclass(frozen=True)
class Inputs:
    """Controls observed on the interface; strings preserve X/Z values."""

    rstb: int | str = 1
    clear: int | str = 0
    load: int | str = 0
    enable: int | str = 0
    direction: int | str = 0
    load_value: int = 0

    @property
    def invalid_controls(self) -> set[str]:
        return {name for name in CONTROLS if getattr(self, name) not in (0, 1)}

    @property
    def command(self) -> str:
        if not self.rstb:
            return "reset"
        if self.clear:
            return "clear"
        if self.load:
            return "load"
        if self.enable:
            return "decrement" if self.direction else "increment"
        return "hold"


@dataclass(frozen=True)
class State:
    count: int
    overflow: int = 0
    underflow: int = 0


class CounterItem(uvm_sequence_item):
    """One clocked command, optionally including a short reset pulse."""

    def __init__(self, name, inputs, *, unknown=None, pulse_reset=False):
        super().__init__(name)
        self.inputs = inputs
        self.unknown = unknown
        self.pulse_reset = pulse_reset


@dataclass(frozen=True)
class Observation:
    label: str
    mid_inputs: Inputs
    edge_inputs: Inputs
    mid_state: State
    edge_state: State
    mid_terminal: int
    edge_terminal: int
    expected_unknown: str | None
    pulse_reset: bool
