"""One clock opportunity, with immutable pre-edge and settled observations."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item
from static_mesh.defaults import PORTS

INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == "Input" and n != "i_clk")
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == "Output")


class MeshItem(uvm_sequence_item):
    def __init__(self, label, ports, fault=None):
        super().__init__(label)
        self.ports = ports.copy()
        self.pre = None
        self.post = None
        self.fault = fault


@dataclass
class Observation:
    ports: dict
    phase: str
    item: MeshItem
