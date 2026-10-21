"""Clock opportunities with independently controlled backend scenarios."""
from dataclasses import dataclass,field
from pyuvm import uvm_sequence_item


class DmaItem(uvm_sequence_item):
    def __init__(self,label,ports=None,*,options=None,edge=True,random=False):
        super().__init__(label)
        self.ports=ports or {}
        self.options=options or {}
        self.edge,self.random=edge,random
        self.pre=self.observation=None


@dataclass(frozen=True)
class Observation:
    ports: dict[str,str]
    item: DmaItem
    stage: str
    internals: dict[str,tuple[str,...]]=field(default_factory=dict)
