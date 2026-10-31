"""Immutable before/after public observations for one clock opportunity."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item

class ClusterItem(uvm_sequence_item):
    def __init__(self, name, ports, fault=None):
        super().__init__(name)
        self.ports = ports.copy()
        self.pre = self.post = None
        self.fault = fault

@dataclass
class Observation:
    ports: dict
    phase: str
    item: ClusterItem
