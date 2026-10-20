"""A schedule opportunity and real port/storage observations."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

INPUTS = ('i_rstb', 'i_advance', 'i_channel_enable', 'i_delay', 'i_input_data', 'i_input_valid', 'i_flush')
OUTPUTS = ('o_output_data', 'o_output_valid', 'o_output_transfer', 'o_channel_empty', 'o_all_empty', 'o_config_error')


class RduItem(uvm_sequence_item):
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
    item: RduItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    quiet_change: bool
