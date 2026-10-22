"""Clock transactions and observations of the complete exp-unit interface."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item

PORTS = {'i_clk': ['input', 1],
 'i_rstb': ['input', 1],
 'i_drain': ['input', 1],
 'i_flush': ['input', 1],
 'i_error_clear': ['input', 1],
 'i_request_valid': ['input', 1],
 'i_request_base': ['input', 1],
 'i_request_output_signed': ['input', 1],
 'i_request_interpolate': ['input', 1],
 'i_request_round_mode': ['input', 1],
 'i_request_predicate': ['input', 1],
 'i_result_ready': ['input', 1],
 'i_request_operand': ['input', 'IW'],
 'i_request_context_id': ['input', 'C'],
 'i_request_tag': ['input', 'T'],
 'o_request_ready': ['output', 1],
 'o_result_valid': ['output', 1],
 'o_result_base': ['output', 1],
 'o_result_output_signed': ['output', 1],
 'o_result_interpolated': ['output', 1],
 'o_result_overflow': ['output', 1],
 'o_result_underflow': ['output', 1],
 'o_result_saturated': ['output', 1],
 'o_result_rounded': ['output', 1],
 'o_result_approximate': ['output', 1],
 'o_result_predicated': ['output', 1],
 'o_result_error': ['output', 1],
 'o_busy': ['output', 1],
 'o_idle': ['output', 1],
 'o_quiescent': ['output', 1],
 'o_drain_done': ['output', 1],
 'o_flushed': ['output', 1],
 'o_error': ['output', 1],
 'o_fatal_error': ['output', 1],
 'o_event_request_accept': ['output', 1],
 'o_event_result_complete': ['output', 1],
 'o_event_request_stall': ['output', 1],
 'o_event_result_stall': ['output', 1],
 'o_event_base_e': ['output', 1],
 'o_event_base_2': ['output', 1],
 'o_event_table_lookup': ['output', 1],
 'o_event_interpolation': ['output', 1],
 'o_event_overflow': ['output', 1],
 'o_event_underflow': ['output', 1],
 'o_event_table_corrected': ['output', 1],
 'o_event_table_uncorrectable': ['output', 1],
 'o_result_data': ['output', 'OW'],
 'o_result_reduced_exponent': ['output', 'EW'],
 'o_result_quality_id': ['output', 32],
 'o_table_image_id': ['output', 32],
 'o_table_checksum': ['output', 32],
 'o_log2e_constant_id': ['output', 32],
 'o_log2e_checksum': ['output', 32],
 'o_result_context_id': ['output', 'C'],
 'o_result_tag': ['output', 'T'],
 'o_result_error_code': ['output', 4],
 'o_error_code': ['output', 4],
 'o_output_queue_occupancy': ['output', 'QW']}
INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'input' and n != 'i_clk')
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'output')
REQUEST = tuple(n for n in INPUTS if n.startswith('i_request_') and n != 'i_request_valid')


class ExpUnitItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False, fault=None, release=False):
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
    item: ExpUnitItem
    stage: str
