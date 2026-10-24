"""One driver-controlled clock opportunity and independently observed signals."""
from dataclasses import dataclass, field
from pyuvm import uvm_sequence_item


class PolynomialItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False, fault=None):
        super().__init__(label)
        self.ports = ports
        self.edge = edge
        self.random = random
        self.fault = fault
        self.pre = self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    item: PolynomialItem
    stage: str
    internals: dict = field(default_factory=dict)
