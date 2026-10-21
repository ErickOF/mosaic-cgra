"""Clock opportunities and immutable four-state interface/storage observations."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

INPUTS = ('i_rstb', 'i_clock_enable', 'i_valid', 'i_command', 'i_lane_mask', 'i_data', 'i_signed', 'i_saturate')
PERSISTENT = ('o_data', 'o_state_valid', 'o_state_signed')
RESPONSE = ('o_valid', 'o_illegal_operation', 'o_updated_mask', 'o_carry', 'o_borrow',
    'o_overflow', 'o_saturated', 'o_zero', 'o_negative')
OUTPUTS = (*PERSISTENT, *RESPONSE)
RAW = ('state_data', 'state_signed')


class AccumulatorItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False, pulse=''):
        super().__init__(label)
        self.ports = dict(ports)
        self.edge, self.random, self.pulse = edge, random, pulse
        self.pre = self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    internals: dict[str, str]
    item: AccumulatorItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    forbidden_bits: tuple[int, ...]
