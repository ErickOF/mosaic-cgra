"""Requests, intentional fault transport and actual DUT observations."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item

INPUTS = ('i_rstb','i_flush','i_req_valid','i_req_write','i_req_addr','i_req_wdata','i_req_wmask','i_req_tag','i_rsp_ready')
OUTPUTS = ('o_req_ready','o_req_error','o_rsp_valid','o_rsp_rdata','o_rsp_tag','o_busy','o_outstanding_reads')
FIELDS = ('i_req_write','i_req_addr','i_req_wdata','i_req_wmask','i_req_tag')
BACKEND = ('backend_enable','backend_write','backend_addr','backend_wdata','backend_wmask','backend_rdata')
STATE = ('outstanding','queued','read_pointer','write_pointer','read_valid')


class SramItem(uvm_sequence_item):
    def __init__(self,label,ports,*,edge=True,random=False,fault_data=False,fault_tag=False,pulse=False):
        super().__init__(label)
        self.ports=dict(ports)
        self.edge,self.random,self.fault_data,self.fault_tag,self.pulse=edge,random,fault_data,fault_tag,pulse
        self.pre=self.observation=None
        self.start=None


@dataclass(frozen=True)
class Observation:
    ports: dict[str,str]
    internals: dict[str,str]
    item: SramItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    forbidden: bool
