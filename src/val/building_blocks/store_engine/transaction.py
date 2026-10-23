"""Clock transactions and complete public-interface observations."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item

PORTS = {
    'i_clk': ('input', 1),
    'i_rstb': ('input', 1),
    'i_error_clear': ('input', 1),
    'i_config_valid': ('input', 1),
    'o_config_ready': ('output', 1),
    'i_mode': ('input', 2),
    'i_base_address': ('input', 'W'),
    'i_inner_count': ('input', 'C'),
    'i_outer_count': ('input', 'C'),
    'i_inner_stride': ('input', 'W'),
    'i_outer_stride': ('input', 'W'),
    'i_element_size_log2': ('input', 'ELEMENT_SIZE_WIDTH'),
    'i_address_space': ('input', 'S'),
    'i_channel_id': ('input', 'H'),
    'i_context_id': ('input', 'T'),
    'i_expect_end_of_stream': ('input', 1),
    'o_mem_req_valid': ('output', 1),
    'i_mem_req_ready': ('input', 1),
    'o_mem_req_address': ('output', 'W'),
    'o_mem_req_data': ('output', 'D'),
    'o_mem_req_strobe': ('output', 'DATA_BYTES'),
    'o_mem_req_size_log2': ('output', 'ELEMENT_SIZE_WIDTH'),
    'o_mem_req_tag': ('output', 'TAG_WIDTH'),
    'o_mem_req_address_space': ('output', 'S'),
    'o_mem_req_channel_id': ('output', 'H'),
    'o_mem_req_context_id': ('output', 'T'),
    'i_mem_rsp_valid': ('input', 1),
    'o_mem_rsp_ready': ('output', 1),
    'i_mem_rsp_tag': ('input', 'TAG_WIDTH'),
    'i_mem_rsp_error': ('input', 1),
    'i_stream_valid': ('input', 1),
    'o_stream_ready': ('output', 1),
    'i_stream_data': ('input', 'D'),
    'i_stream_keep': ('input', 'DATA_BYTES'),
    'i_stream_first': ('input', 1),
    'i_stream_last': ('input', 1),
    'i_stream_row_first': ('input', 1),
    'i_stream_row_last': ('input', 1),
    'i_stream_end_of_stream': ('input', 1),
    'i_stream_error': ('input', 1),
    'i_stream_channel_id': ('input', 'H'),
    'i_stream_context_id': ('input', 'T'),
    'o_idle': ('output', 1),
    'o_busy': ('output', 1),
    'o_command_started': ('output', 1),
    'o_request_accepted': ('output', 1),
    'o_response_accepted': ('output', 1),
    'o_stream_accepted': ('output', 1),
    'o_response_retired': ('output', 1),
    'o_command_completed': ('output', 1),
    'o_completed_with_error': ('output', 1),
    'o_command_failed': ('output', 1),
    'o_outstanding': ('output', 'OCCUPANCY_WIDTH'),
    'o_memory_error_seen': ('output', 1),
    'o_error': ('output', 1),
    'o_error_code': ('output', 5),
}
INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'input' and n != 'i_clk')
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'output')
DESCRIPTOR = ('i_mode', 'i_base_address', 'i_inner_count', 'i_outer_count',
              'i_inner_stride', 'i_outer_stride', 'i_element_size_log2', 'i_address_space',
              'i_channel_id', 'i_context_id', 'i_expect_end_of_stream')
STREAM = tuple(n for n in INPUTS if n.startswith('i_stream_') and n != 'i_stream_valid')
REQUEST = tuple(n for n in OUTPUTS if n.startswith('o_mem_req_') and n != 'o_mem_req_valid')
EVENTS = ('o_command_started', 'o_stream_accepted', 'o_request_accepted', 'o_response_accepted',
          'o_response_retired', 'o_command_completed', 'o_completed_with_error', 'o_command_failed')



class StoreEngineItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False, fault=False, release=False):
        super().__init__(label)
        self.ports = ports
        self.edge = edge
        self.random = random
        self.fault = fault
        self.release = release
        self.pre = None
        self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict
    storage: dict
    item: StoreEngineItem
    stage: str
