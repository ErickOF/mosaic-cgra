"""Cycle transactions and complete public-interface observations."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item

PORTS = {
    'i_clk': ('input', 1),
    'i_rstb': ('input', 1),
    'i_flush': ('input', 1),
    'i_error_clear': ('input', 1),
    'i_config_valid': ('input', 1),
    'o_config_ready': ('output', 1),
    'i_config_output_enable': ('input', 'O'),
    'i_config_output_select': ('input', 'OUTPUT_SELECT_WIDTH'),
    'i_config_context_id': ('input', 'C'),
    'o_config_accepted': ('output', 1),
    'o_config_rejected': ('output', 1),
    'i_input_valid': ('input', 'I'),
    'o_input_ready': ('output', 'I'),
    'i_input_data': ('input', 'INPUT_DATA_WIDTH'),
    'i_input_metadata': ('input', 'INPUT_METADATA_WIDTH'),
    'o_output_valid': ('output', 'O'),
    'i_output_ready': ('input', 'O'),
    'o_output_data': ('output', 'OUTPUT_DATA_WIDTH'),
    'o_output_metadata': ('output', 'OUTPUT_METADATA_WIDTH'),
    'o_active_output_enable': ('output', 'O'),
    'o_active_output_select': ('output', 'OUTPUT_SELECT_WIDTH'),
    'o_active_context_id': ('output', 'C'),
    'o_input_buffered': ('output', 'I'),
    'o_pending_delivery': ('output', 'PENDING_WIDTH'),
    'o_idle': ('output', 1),
    'o_quiescent': ('output', 1),
    'o_error': ('output', 1),
    'o_error_code': ('output', 3),
    'o_flushed': ('output', 1),
    'o_event_input_accept': ('output', 'I'),
    'o_event_output_transfer': ('output', 'O'),
    'o_event_input_stall': ('output', 'I'),
    'o_event_output_stall': ('output', 'O'),
    'o_event_multicast_accept': ('output', 'I'),
    'o_event_item_complete': ('output', 'I'),
}
INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'input' and n != 'i_clk')
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'output')
EVENTS = tuple(n for n in OUTPUTS if n.startswith('o_event_')) + (
    'o_config_accepted', 'o_config_rejected', 'o_flushed')
CONFIG = ('i_config_output_enable', 'i_config_output_select', 'i_config_context_id')


class LocalSwitchItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False, fault=None, release=False):
        super().__init__(label)
        self.ports = ports
        self.edge = edge
        self.random = random
        self.fault = fault
        self.pre = None
        self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict
    storage: dict
    item: LocalSwitchItem
    stage: str
