"""Mux transaction components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pyuvm import uvm_sequence_item
from mosaic_uvm.logic import bits
from mux.config import MuxConfig


@dataclass(frozen=True)
class Inputs:
    select: int | str
    words: tuple[int | str, ...]

    def packed_data(self, config: MuxConfig) -> str:
        assert len(self.words) == config.num_inputs, "Wrong number of source words"
        return "".join(bits(word, config.data_width) for word in reversed(self.words))


class MuxItem(uvm_sequence_item):
    def __init__(self, label, inputs, *, hold_ns=0.001):
        super().__init__(label)
        assert math.isfinite(hold_ns) and hold_ns >= 0.001
        self.inputs = inputs
        self.hold_ns = hold_ns


@dataclass(frozen=True)
class Observation:
    label: str
    packed_data: str
    select: str
    output: str
    valid: str
    requested: Inputs
    stage: str
    kind: str
    hold_ns: float


@dataclass(frozen=True)
class OutputActivity:
    signal: str
    value: str
    quiet: bool
