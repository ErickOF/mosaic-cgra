"""Port stimuli and observations at the verification harness's sampling edges."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

INPUTS = ('i_valid', 'i_data', 'i_required', 'i_ready')
OUTPUTS = ('o_ready', 'o_valid', 'o_data', 'o_required')


class StreamJoinItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False, four_state_data=False, quiet=False, pulse=None):
        super().__init__(label)
        self.ports = dict(ports)
        self.edge, self.random, self.four_state_data = edge, random, four_state_data
        self.quiet, self.pulse = quiet, pulse
        self.pre = self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    item: StreamJoinItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    forbidden: bool
