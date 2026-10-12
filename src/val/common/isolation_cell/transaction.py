"""IsolationCell transaction components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from pyuvm import uvm_sequence_item
from mosaic_uvm.logic import bits


@dataclass(frozen=True)
class Inputs:
    isolate: int | str
    data: int | str

    def data_bits(self, width: int) -> str:
        return bits(self.data, width)


class IsolationCellItem(uvm_sequence_item):
    def __init__(self, label, inputs, *, unknown=None):
        super().__init__(label)
        self.inputs = inputs
        self.unknown = unknown


@dataclass(frozen=True)
class Observation:
    label: str
    isolate: str
    data: str
    output: str
    requested: Inputs
    expected_unknown: str | None
    continuously_isolated: bool


@dataclass(frozen=True)
class OutputActivity:
    value: str
    continuously_isolated: bool
