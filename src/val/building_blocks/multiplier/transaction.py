"""Clock opportunities and passive observations, including four-state values."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item

INPUTS = ('i_rstb', 'i_clock_enable', 'i_valid', 'i_operand_a', 'i_operand_b',
          'i_signed_a', 'i_signed_b')
OUTPUTS = ('o_valid', 'o_product', 'o_product_signed', 'o_zero', 'o_negative')
CONTROLS = ('i_signed_a', 'i_signed_b')


class MultiplierItem(uvm_sequence_item):
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
    item: MultiplierItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    value: str
