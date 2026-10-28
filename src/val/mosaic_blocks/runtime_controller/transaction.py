"""Cycle items and passive public-port observations."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item
from runtime_controller.config import PORTS

INPUTS = tuple(n for n, (direction, _) in PORTS.items() if direction == 'input' and n != 'i_clk')
OUTPUTS = tuple(n for n, (direction, _) in PORTS.items() if direction == 'output')


class RuntimeItem(uvm_sequence_item):
    def __init__(self, ports):
        super().__init__('runtime_cycle')
        self.ports = ports.copy()
        self.pre = None
        self.post = None


@dataclass
class Observation:
    ports: dict
    item: RuntimeItem
