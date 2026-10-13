"""Driven commands and immutable pre-edge, post-edge, and held observations."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item
from mosaic_uvm.logic import bits


class SequencerItem(uvm_sequence_item):
    def __init__(self, config, label, ports, *, violation=None, random=False, hold_ps=10):
        super().__init__(label)
        self.ports = {name: bits(value, config.widths[name]) for name, value in ports.items()}
        self.violation, self.random, self.hold_ps = violation, random, hold_ps
        assert hold_ps >= 2
        self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    internals: dict[str, str]
    item: SequencerItem
    stage: str


@dataclass(frozen=True)
class Activity:
    signal: str
    before: str
    after: str
    quiet: bool
