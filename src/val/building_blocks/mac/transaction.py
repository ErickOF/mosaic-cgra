"""Clock opportunities and passive observations, including four-state values."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item

INPUTS = ('i_rstb', 'i_clock_enable', 'i_valid', 'i_operand_a', 'i_operand_b',
          'i_accumulator', 'i_signed', 'i_saturate')
OUTPUTS = ('o_valid', 'o_result', 'o_carry', 'o_overflow', 'o_saturated',
           'o_zero', 'o_negative', 'o_illegal_operation')
CONTROLS = ('i_signed', 'i_saturate')


class MacItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False):
        super().__init__(label)
        self.ports = ports
        self.edge = edge
        self.random = random
        self.pre = None
        self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    internals: dict[str, str]
    item: MacItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    value: str
