"""Complete request/response interface and explicit verification fault actions."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item

PORTS = {
    'i_clk': ('input', 1), 'i_rstb': ('input', 1), 'i_flush': ('input', 1),
    'i_error_clear': ('input', 1), 'i_req_valid': ('input', 1), 'o_req_ready': ('output', 1),
    'i_req_write': ('input', 1), 'i_req_address': ('input', 'A'),
    'i_req_size_log2': ('input', 'S'), 'i_req_wdata': ('input', 'D'),
    'i_req_wstrobe': ('input', 'B'), 'i_req_tag': ('input', 'T'),
    'o_rsp_valid': ('output', 1), 'i_rsp_ready': ('input', 1),
    'o_rsp_write': ('output', 1), 'o_rsp_rdata': ('output', 'D'), 'o_rsp_tag': ('output', 'T'),
    'o_rsp_error': ('output', 1), 'o_rsp_error_code': ('output', 4),
    'o_rsp_corrected': ('output', 1), 'o_rsp_uncorrectable': ('output', 1),
    'o_idle': ('output', 1), 'o_busy': ('output', 1), 'o_outstanding': ('output', 'O'),
    'o_request_accepted': ('output', 1), 'o_read_accepted': ('output', 1),
    'o_write_accepted': ('output', 1), 'o_response_accepted': ('output', 1),
    'o_corrected_event': ('output', 1), 'o_uncorrectable_event': ('output', 1),
    'o_scrub_completed': ('output', 1), 'o_flush_completed': ('output', 1),
    'o_error': ('output', 1), 'o_error_code': ('output', 4),
}
INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'input' and n != 'i_clk')
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'output')
REQUEST = tuple(n for n in INPUTS if n.startswith('i_req_') and n != 'i_req_valid')
RESPONSE = tuple(n for n in OUTPUTS if n.startswith('o_rsp_') and n != 'o_rsp_valid')
EVENTS = ('o_request_accepted', 'o_read_accepted', 'o_write_accepted', 'o_response_accepted',
          'o_corrected_event', 'o_uncorrectable_event', 'o_scrub_completed', 'o_flush_completed')


class ScratchpadBankItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False, fault=None, protocol=None):
        super().__init__(label)
        self.ports = ports
        self.edge = edge
        self.random = random
        self.fault = fault
        self.protocol = protocol
        self.pre = self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict
    storage: dict
    item: ScratchpadBankItem
    stage: str
