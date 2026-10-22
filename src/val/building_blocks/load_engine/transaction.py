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
    'i_emit_end_of_stream': ('input', 1),
    'o_mem_req_valid': ('output', 1),
    'i_mem_req_ready': ('input', 1),
    'o_mem_req_address': ('output', 'W'),
    'o_mem_req_size_log2': ('output', 'ELEMENT_SIZE_WIDTH'),
    'o_mem_req_tag': ('output', 'TAG_WIDTH'),
    'o_mem_req_address_space': ('output', 'S'),
    'o_mem_req_channel_id': ('output', 'H'),
    'o_mem_req_context_id': ('output', 'T'),
    'i_mem_rsp_valid': ('input', 1),
    'o_mem_rsp_ready': ('output', 1),
    'i_mem_rsp_tag': ('input', 'TAG_WIDTH'),
    'i_mem_rsp_data': ('input', 'D'),
    'i_mem_rsp_error': ('input', 1),
    'o_stream_valid': ('output', 1),
    'i_stream_ready': ('input', 1),
    'o_stream_data': ('output', 'D'),
    'o_stream_keep': ('output', 'DATA_BYTES'),
    'o_stream_first': ('output', 1),
    'o_stream_last': ('output', 1),
    'o_stream_row_first': ('output', 1),
    'o_stream_row_last': ('output', 1),
    'o_stream_end_of_stream': ('output', 1),
    'o_stream_error': ('output', 1),
    'o_stream_channel_id': ('output', 'H'),
    'o_stream_context_id': ('output', 'T'),
    'o_idle': ('output', 1),
    'o_busy': ('output', 1),
    'o_command_started': ('output', 1),
    'o_request_accepted': ('output', 1),
    'o_response_accepted': ('output', 1),
    'o_stream_accepted': ('output', 1),
    'o_command_completed': ('output', 1),
    'o_completed_with_error': ('output', 1),
    'o_command_failed': ('output', 1),
    'o_outstanding': ('output', 'OCCUPANCY_WIDTH'),
    'o_memory_error_seen': ('output', 1),
    'o_error': ('output', 1),
    'o_error_code': ('output', 4),
}
INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'input' and n != 'i_clk')
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'output')
DESCRIPTOR = tuple(n for n in INPUTS if n not in (
    'i_rstb', 'i_error_clear', 'i_config_valid', 'i_mem_req_ready', 'i_mem_rsp_valid',
    'i_mem_rsp_tag', 'i_mem_rsp_data', 'i_mem_rsp_error', 'i_stream_ready'))
REQUEST = tuple(n for n in OUTPUTS if n.startswith('o_mem_req_') and n != 'o_mem_req_valid')
STREAM = tuple(n for n in OUTPUTS if n.startswith('o_stream_') and n not in (
    'o_stream_valid', 'o_stream_accepted'))
EVENTS = ('o_command_started', 'o_request_accepted', 'o_response_accepted',
          'o_stream_accepted', 'o_command_completed', 'o_completed_with_error', 'o_command_failed')


class LoadEngineItem(uvm_sequence_item):
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
    item: LoadEngineItem
    stage: str
