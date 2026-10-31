"""One complete clock opportunity and immutable observations."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item
from global_noc.dependencies import PORTS
INPUTS=tuple(n for n,(d,_) in PORTS.items() if d=='Input' and n!='i_noc_clk')
OUTPUTS=tuple(n for n,(d,_) in PORTS.items() if d=='Output')

class NocItem(uvm_sequence_item):
    def __init__(self,ports,label='cycle'):
        super().__init__(label)
        self.ports=ports.copy()
        self.pre={}
        self.post={}

@dataclass
class Observation:
    ports: dict
    item: NocItem
    transfers: list
    credit_events: list
