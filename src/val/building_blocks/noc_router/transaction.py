"""Four-state flit-link cycles and observations shared by UVM components."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

FIELDS = dict(
    data='D',
    keep='K',
    head=1,
    tail=1,
    fragment_index='F',
    vc='VW',
    source_node='N',
    source_endpoint='EP',
    destination_node='N',
    destination_endpoint='EP',
    context_id='CX',
    message_type='MT',
    traffic_class='TC',
    packet_id='PI',
    stream_last=1,
    user_metadata='U',
    error='ER',
    epoch='E',
)
EVENTS = (
    'input_accept',
    'output_transfer',
    'packet_head',
    'packet_tail',
    'input_stall',
    'output_stall',
    'vc_starved',
    'credit_starved',
    'route_error',
    'protocol_error',
    'parity_error',
    'buffer_corrected',
    'buffer_uncorrectable',
)
SCALARS = ('i_rstb', 'i_drain', 'i_flush', 'i_error_clear', 'i_config_valid')
INPUTS = (
    *SCALARS,
    'i_config_port_enable',
    'i_config_fault_port_mask',
    'i_in_valid',
    *(f'i_in_{name}' for name in FIELDS),
    'i_in_parity',
    'i_out_ready',
    'i_out_credit_valid',
    'i_out_credit_vc',
    'i_out_credit_epoch',
)
OUTPUTS = (
    'o_config_ready',
    'o_config_accepted',
    'o_config_rejected',
    'o_in_ready',
    'o_out_valid',
    *(f'o_out_{name}' for name in FIELDS),
    'o_out_parity',
    'o_in_credit_valid',
    'o_in_credit_vc',
    'o_in_credit_epoch',
    'o_active_port_enable',
    'o_active_fault_port_mask',
    'o_link_epoch',
    'o_input_vc_occupancy',
    'o_output_credit_count',
    'o_input_packet_locked',
    'o_output_packet_locked',
    'o_idle',
    'o_quiescent',
    'o_drain_done',
    'o_flushed',
    'o_error',
    'o_error_code',
    'o_fatal_error',
    *(f'o_event_{name}' for name in EVENTS),
)


class RouterItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, fault=None, random=False):
        super().__init__(label)
        self.ports = ports
        self.edge = edge
        self.fault = fault
        self.random = random
        self.pre = None
        self.observation = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    internal: dict[str, str]
    item: RouterItem
    stage: str
