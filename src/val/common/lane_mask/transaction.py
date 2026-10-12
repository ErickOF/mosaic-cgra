"""LaneMask transaction components for specification-based PyUVM validation."""

from __future__ import annotations

from dataclasses import dataclass
from pyuvm import uvm_sequence_item
from mosaic_uvm.logic import bits


@dataclass(frozen=True)
class Inputs:
    operation_valid: int | str
    lane_valid: int | str
    lane_mask: int | str
    lane_predicate: int | str

    def ports(self, lanes: int) -> tuple[str, str, str, str]:
        return (bits(self.operation_valid, 1), bits(self.lane_valid, lanes),
                bits(self.lane_mask, lanes), bits(self.lane_predicate, lanes))


class LaneMaskItem(uvm_sequence_item):
    def __init__(self, label, inputs, *, expected_unknown=()):
        super().__init__(label)
        self.inputs = inputs
        self.expected_unknown = expected_unknown


@dataclass(frozen=True)
class Observation:
    label: str
    ports: tuple[str, str, str, str]
    outputs: tuple[str, str, str]
    requested: Inputs
    expected_unknown: tuple[str, ...]
