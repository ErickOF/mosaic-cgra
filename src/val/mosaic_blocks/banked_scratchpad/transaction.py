"""Public-cycle transactions and passive observations."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item
from banked_scratchpad.defaults import PORTS
INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'input' and n != 'i_clk')
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'output')


class ScratchpadItem(uvm_sequence_item):
    def __init__(self, name, ports, fault=None, edge=True):
        super().__init__(name)
        self.ports = ports
        self.fault = fault
        self.edge = edge
        self.pre = {}
        self.post = {}


@dataclass
class Observation:
    ports: dict
    banks: dict
    item: ScratchpadItem
