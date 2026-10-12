"""Decoder transaction components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from pyuvm import uvm_sequence_item


@dataclass(frozen=True)
class Inputs:
    enable: int | str
    select: int | str

    def select_bits(self, width: int) -> str:
        if isinstance(self.select, int):
            assert 0 <= self.select < 1 << width, "Do not truncate input encodings"
            return f"{self.select:0{width}b}"
        assert len(self.select) == width and set(self.select.lower()) <= set("01xz")
        return self.select.lower()


class DecoderItem(uvm_sequence_item):
    def __init__(self, label, inputs):
        super().__init__(label)
        self.inputs = inputs


@dataclass(frozen=True)
class Observation:
    label: str
    enable: str
    select: str
    decoded: str
    valid: str
    requested: Inputs
    continuously_disabled: bool


@dataclass(frozen=True)
class OutputActivity:
    signal: str
    value: str
    continuously_disabled: bool
