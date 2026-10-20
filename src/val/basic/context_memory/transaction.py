"""Masked configuration commands and immutable observations."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item
from mosaic_uvm.logic import bits


INPUTS = ("i_clk", "i_rstb", "i_read_enable", "i_read_raw", "i_read_address", "i_write_enable", "i_write_mask",
          "i_write_address", "i_write_data", "i_commit_enable", "i_commit_address", "i_invalidate_enable", "i_invalidate_address")
OUTPUTS = ("o_read_data", "o_read_valid")


def pack(words, width):
    return "".join(bits(word, width) for word in reversed(tuple(words)))


def unpack(word, width):
    assert len(word) % width == 0
    return tuple(word[len(word) - (index + 1) * width:len(word) - index * width] for index in range(len(word) // width))


class ContextMemoryItem(uvm_sequence_item):
    def __init__(self, label, ports, *, violations=(), hold_ps=10, random=False):
        super().__init__(label)
        assert hold_ps >= 2
        self.ports, self.violations = dict(ports), frozenset(violations)
        self.hold_ps, self.random = hold_ps, random


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    data: tuple[str, ...] | None
    valid: str | None
    item: ContextMemoryItem
    stage: str


@dataclass(frozen=True)
class Activity:
    signal: str
    before: str
    after: str
    quiet_mask: int
