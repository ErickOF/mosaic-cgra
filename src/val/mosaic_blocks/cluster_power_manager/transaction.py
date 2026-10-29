"""Cycle items and independent public-port samples."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item
from cluster_power_manager.config import PORTS

INPUTS = tuple(n for n, (d, _) in PORTS.items()
               if d == 'input' and n not in ('i_aon_clk', 'i_functional_clk'))
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'output')


class PowerItem(uvm_sequence_item):
    def __init__(self, ports):
        super().__init__('power_cycle')
        self.ports = ports.copy()
        self.pre = None
        self.post = None


@dataclass
class Observation:
    ports: dict
    clock_edges: dict
