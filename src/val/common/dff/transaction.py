"""Dff transaction components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from pyuvm import uvm_sequence_item
from mosaic_uvm.logic import bits


@dataclass(frozen=True)
class Inputs:
    clk: int
    rstb: int | str
    enable: int | str
    data: int | str

    def data_bits(self, width: int) -> str:
        return bits(self.data, width)


class DffItem(uvm_sequence_item):
    """One clock phase or off-edge control change, with optional illegal control."""

    def __init__(self, label, inputs, *, unknown=None):
        super().__init__(label)
        self.inputs = inputs
        self.unknown = unknown


@dataclass(frozen=True)
class Snapshot:
    time_ps: int
    clk: str
    rstb: str
    enable: str
    data: str
    q: str
    label: str
    expected_unknown: tuple[str, str] | None
    requested: Inputs | None


@dataclass(frozen=True)
class OutputChange:
    time_ps: int
    before: str
    after: str
