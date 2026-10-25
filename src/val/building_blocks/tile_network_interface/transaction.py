"""Public port schema and independent cycle transactions."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

PORTS = {
    'i_clk': ('input', 1),
    'i_rstb': ('input', 1),
    'i_drain': ('input', 1),
    'i_flush': ('input', 1),
    'i_error_clear': ('input', 1),
    'i_config_valid': ('input', 1),
    'o_config_ready': ('output', 1),
    'i_config_tx_enable': ('input', 'TX'),
    'i_config_rx_enable': ('input', 'RX'),
    'i_config_context_check': ('input', 1),
    'i_config_context_id': ('input', 'CX'),
    'o_config_accepted': ('output', 1),
    'o_config_rejected': ('output', 1),
    'i_tile_tx_valid': ('input', 'TX'),
    'i_tile_tx_data': ('input', 'TX*TD'),
    'i_tile_tx_keep': ('input', 'TX*TB'),
    'i_tile_tx_last': ('input', 'TX'),
    'i_tile_tx_context_id': ('input', 'TX*CX'),
    'i_tile_tx_message_type': ('input', 'TX*MT'),
    'i_tile_tx_traffic_class': ('input', 'TX*TC'),
    'i_tile_tx_packet_id': ('input', 'TX*PI'),
    'i_tile_tx_user_metadata': ('input', 'TX*U'),
    'i_tile_tx_error': ('input', 'TX*ER'),
    'i_tile_tx_destination_node': ('input', 'TX*N'),
    'i_tile_tx_destination_endpoint': ('input', 'TX*EP'),
    'o_tile_tx_ready': ('output', 'TX'),
    'o_tile_rx_valid': ('output', 'RX'),
    'o_tile_rx_data': ('output', 'RX*TD'),
    'o_tile_rx_keep': ('output', 'RX*TB'),
    'o_tile_rx_last': ('output', 'RX'),
    'o_tile_rx_context_id': ('output', 'RX*CX'),
    'o_tile_rx_message_type': ('output', 'RX*MT'),
    'o_tile_rx_traffic_class': ('output', 'RX*TC'),
    'o_tile_rx_packet_id': ('output', 'RX*PI'),
    'o_tile_rx_user_metadata': ('output', 'RX*U'),
    'o_tile_rx_error': ('output', 'RX*ER'),
    'o_tile_rx_source_node': ('output', 'RX*N'),
    'o_tile_rx_source_endpoint': ('output', 'RX*EP'),
    'i_tile_rx_ready': ('input', 'RX'),
    'o_noc_tx_valid': ('output', 1),
    'o_noc_tx_data': ('output', 'FD'),
    'o_noc_tx_keep': ('output', 'FB'),
    'o_noc_tx_head': ('output', 1),
    'o_noc_tx_tail': ('output', 1),
    'o_noc_tx_fragment_index': ('output', 'F'),
    'o_noc_tx_vc': ('output', 'VW'),
    'o_noc_tx_source_node': ('output', 'N'),
    'o_noc_tx_source_endpoint': ('output', 'EP'),
    'o_noc_tx_destination_node': ('output', 'N'),
    'o_noc_tx_destination_endpoint': ('output', 'EP'),
    'o_noc_tx_context_id': ('output', 'CX'),
    'o_noc_tx_message_type': ('output', 'MT'),
    'o_noc_tx_traffic_class': ('output', 'TC'),
    'o_noc_tx_packet_id': ('output', 'PI'),
    'o_noc_tx_stream_last': ('output', 1),
    'o_noc_tx_user_metadata': ('output', 'U'),
    'o_noc_tx_error': ('output', 'ER'),
    'o_noc_tx_epoch': ('output', 'E'),
    'o_noc_tx_parity': ('output', 1),
    'i_noc_tx_ready': ('input', 1),
    'i_noc_rx_valid': ('input', 1),
    'i_noc_rx_data': ('input', 'FD'),
    'i_noc_rx_keep': ('input', 'FB'),
    'i_noc_rx_head': ('input', 1),
    'i_noc_rx_tail': ('input', 1),
    'i_noc_rx_fragment_index': ('input', 'F'),
    'i_noc_rx_vc': ('input', 'VW'),
    'i_noc_rx_source_node': ('input', 'N'),
    'i_noc_rx_source_endpoint': ('input', 'EP'),
    'i_noc_rx_destination_node': ('input', 'N'),
    'i_noc_rx_destination_endpoint': ('input', 'EP'),
    'i_noc_rx_context_id': ('input', 'CX'),
    'i_noc_rx_message_type': ('input', 'MT'),
    'i_noc_rx_traffic_class': ('input', 'TC'),
    'i_noc_rx_packet_id': ('input', 'PI'),
    'i_noc_rx_stream_last': ('input', 1),
    'i_noc_rx_user_metadata': ('input', 'U'),
    'i_noc_rx_error': ('input', 'ER'),
    'i_noc_rx_epoch': ('input', 'E'),
    'i_noc_rx_parity': ('input', 1),
    'o_noc_rx_ready': ('output', 1),
    'i_noc_tx_credit_valid': ('input', 1),
    'i_noc_tx_credit_vc': ('input', 'VW'),
    'i_noc_tx_credit_epoch': ('input', 'E'),
    'o_noc_rx_credit_valid': ('output', 1),
    'o_noc_rx_credit_vc': ('output', 'VW'),
    'o_noc_rx_credit_epoch': ('output', 'E'),
    'o_active_tx_enable': ('output', 'TX'),
    'o_active_rx_enable': ('output', 'RX'),
    'o_active_context_id': ('output', 'CX'),
    'o_link_epoch': ('output', 'E'),
    'o_tx_queue_occupancy': ('output', 'TX*TO'),
    'o_rx_vc_occupancy': ('output', 'V*VO'),
    'o_rx_queue_occupancy': ('output', 'RX*RO'),
    'o_tx_credit_count': ('output', 'V*CW'),
    'o_idle': ('output', 1),
    'o_quiescent': ('output', 1),
    'o_drain_done': ('output', 1),
    'o_flushed': ('output', 1),
    'o_error': ('output', 1),
    'o_error_code': ('output', 'tile_network_interface_pkg::NI_ERROR_WIDTH'),
    'o_event_tile_tx_accept': ('output', 'TX'),
    'o_event_tile_rx_transfer': ('output', 'RX'),
    'o_event_noc_tx_transfer': ('output', 1),
    'o_event_noc_rx_accept': ('output', 1),
    'o_event_tx_stall': ('output', 'TX'),
    'o_event_rx_stall': ('output', 'RX'),
    'o_event_tx_drop': ('output', 'TX'),
    'o_event_rx_drop': ('output', 1),
    'o_event_parity_error': ('output', 1),
}
FLIT_FIELDS = {
    'data': 'FD',
    'keep': 'FB',
    'head': 1,
    'tail': 1,
    'fragment_index': 'F',
    'vc': 'VW',
    'source_node': 'N',
    'source_endpoint': 'EP',
    'destination_node': 'N',
    'destination_endpoint': 'EP',
    'context_id': 'CX',
    'message_type': 'MT',
    'traffic_class': 'TC',
    'packet_id': 'PI',
    'stream_last': 1,
    'user_metadata': 'U',
    'error': 'ER',
    'epoch': 'E',
    'parity': 1,
}
TILE_FIELDS = {
    'data': 'TD',
    'keep': 'TB',
    'last': 1,
    'context_id': 'CX',
    'message_type': 'MT',
    'traffic_class': 'TC',
    'packet_id': 'PI',
    'user_metadata': 'U',
    'error': 'ER',
}
INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'input' and n != 'i_clk')
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'output')
TX_FIELDS = (*TILE_FIELDS, 'destination_node', 'destination_endpoint')
RX_FIELDS = (*TILE_FIELDS, 'source_node', 'source_endpoint')


class InterfaceItem(uvm_sequence_item):
    def __init__(self, label, offers, controls, *, packets=(), peer=None, edge=True, random=False):
        super().__init__(label)
        self.offers = offers
        self.controls = controls
        self.packets = packets
        self.peer = peer or {}
        self.edge = edge
        self.random = random
        self.pre = self.post = None
        self.peer_pending = 0


@dataclass(frozen=True)
class Observation:
    ports: dict
    storage: dict
    item: InterfaceItem
    stage: str
