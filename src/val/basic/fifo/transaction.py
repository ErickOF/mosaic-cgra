"""One clock opportunity and observations of real ports and storage."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

INPUTS = ('i_rstb', 'i_valid', 'i_data', 'i_ready')
OUTPUTS = ('o_ready', 'o_valid', 'o_data', 'o_full', 'o_empty',
           'o_almost_full', 'o_almost_empty', 'o_occupancy')
CONTROLS = ('i_rstb', 'i_valid', 'i_ready')


class FifoItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False):
        super().__init__(label)
        self.ports = dict(ports)
        self.edge = edge
        self.random = random
        self.pre = None
        self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    internals: dict[str, str]
    item: FifoItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    quiet: bool
