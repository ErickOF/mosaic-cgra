"""Packed interface stimulus, sample records, and continuous output activity."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

from mosaic_uvm.logic import bits


INPUTS = ("i_clk", "i_rstb", "i_source_data", "i_source_valid", "i_destination_enable", "i_select", "i_capture_enable", "i_flush")
OUTPUTS = ("o_destination_data", "o_destination_valid", "o_selection_error")


def pack(words, width: int) -> str:
    """Element zero occupies the least significant packed position."""
    return "".join(bits(word, width) for word in reversed(tuple(words)))


def unpack(word: str, width: int) -> tuple[str, ...]:
    assert len(word) % width == 0
    return tuple(word[len(word) - (index + 1) * width:len(word) - index * width]
                 for index in range(len(word) // width))


class BypassNetworkItem(uvm_sequence_item):
    def __init__(self, label, ports, *, violations=(), hold_ps=10, random=False):
        super().__init__(label)
        assert hold_ps >= 2
        self.ports = dict(ports)
        self.violations = frozenset(violations)
        self.hold_ps, self.random = hold_ps, random


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    stored_data: tuple[str, ...] | None
    stored_valid: tuple[str, ...] | None
    item: BypassNetworkItem
    stage: str


@dataclass(frozen=True)
class Activity:
    signal: str
    before: str
    after: str
    quiet_mask: int
