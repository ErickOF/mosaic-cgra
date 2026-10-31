"""Complete clock opportunities and immutable public observations."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item
from bct.defaults import PORTS

INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'Input' and n not in ('i_clk', 'i_cfg_clk'))
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'Output')

class BctItem(uvm_sequence_item):
    def __init__(self, label, ports, *, cfg_edge=True, core_edge=True, phase=0, fault=None):
        super().__init__(label)
        self.ports = ports
        self.cfg_edge = cfg_edge
        self.core_edge = core_edge
        self.phase = phase
        self.fault = fault
        self.edges = {}
        self.post = None

@dataclass
class Observation:
    ports: dict
    domain: str
    item: BctItem
