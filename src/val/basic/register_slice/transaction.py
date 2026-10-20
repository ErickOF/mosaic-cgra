"""Clock opportunities, intentional four-state payloads and actual observations."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

INPUTS = ('i_rstb', 'i_valid', 'i_data', 'i_ready')
OUTPUTS = ('o_ready', 'o_valid', 'o_data')
CONTROLS = ('i_rstb', 'i_valid', 'i_ready')


class RegisterSliceItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False, four_state_data=False, pulse=False):
        super().__init__(label)
        self.ports = dict(ports)
        self.edge, self.random, self.four_state_data, self.pulse = edge, random, four_state_data, pulse
        self.pre = None
        self.observation = None
        self.start_count = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    internals: dict[str, str]
    item: RegisterSliceItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    forbidden: bool
