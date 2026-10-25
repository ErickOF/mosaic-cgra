"""Full interface schema and one controlled clock opportunity."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item

PORTS = {'i_clk': ('input', 1),
 'i_rstb': ('input', 1),
 'i_drain': ('input', 1),
 'i_flush': ('input', 1),
 'i_error_clear': ('input', 1),
 'i_lookup_valid': ('input', 1),
 'o_lookup_ready': ('output', 1),
 'i_lookup_coordinate': ('input', 'INDEX_WIDTH'),
 'i_lookup_bank': ('input', 'BANK_WIDTH'),
 'i_lookup_index_signed': ('input', 1),
 'i_lookup_output_signed': ('input', 1),
 'i_lookup_interpolate': ('input', 1),
 'i_lookup_round_mode': ('input', 1),
 'i_lookup_predicate': ('input', 1),
 'i_lookup_context_id': ('input', 'C'),
 'i_lookup_tag': ('input', 'G'),
 'o_result_valid': ('output', 1),
 'i_result_ready': ('input', 1),
 'o_result_data': ('output', 'W'),
 'o_result_bank': ('output', 'BANK_WIDTH'),
 'o_result_table_version': ('output', 'V'),
 'o_result_table_id': ('output', 'T'),
 'o_result_quality_id': ('output', 'Q'),
 'o_result_context_id': ('output', 'C'),
 'o_result_tag': ('output', 'G'),
 'o_result_clipped_low': ('output', 1),
 'o_result_clipped_high': ('output', 1),
 'o_result_interpolated': ('output', 1),
 'o_result_predicated': ('output', 1),
 'o_result_error': ('output', 1),
 'o_result_error_code': ('output', 'lut_unit_pkg::ERROR_WIDTH'),
 'i_program_valid': ('input', 1),
 'o_program_ready': ('output', 1),
 'i_program_command': ('input', 2),
 'i_program_bank': ('input', 'BANK_WIDTH'),
 'i_program_address': ('input', 'A'),
 'i_program_write_data': ('input', 'W'),
 'i_program_table_id': ('input', 'T'),
 'i_program_quality_id': ('input', 'Q'),
 'o_program_response_valid': ('output', 1),
 'i_program_response_ready': ('input', 1),
 'o_program_response_command': ('output', 2),
 'o_program_response_bank': ('output', 'BANK_WIDTH'),
 'o_program_response_address': ('output', 'A'),
 'o_program_response_read_data': ('output', 'W'),
 'o_program_response_version': ('output', 'V'),
 'o_program_response_table_id': ('output', 'T'),
 'o_program_response_quality_id': ('output', 'Q'),
 'o_program_response_bank_valid': ('output', 1),
 'o_program_response_error': ('output', 1),
 'o_program_response_error_code': ('output', 'lut_unit_pkg::ERROR_WIDTH'),
 'o_bank_valid': ('output', 'B'),
 'o_bank_version': ('output', 'B*V'),
 'o_bank_table_id': ('output', 'B*T'),
 'o_bank_quality_id': ('output', 'B*Q'),
 'o_bank_program_complete': ('output', 'B'),
 'o_lookup_queue_occupancy': ('output', 'LOOKUP_QUEUE_OCCUPANCY_WIDTH'),
 'o_program_queue_occupancy': ('output', 'PROGRAM_QUEUE_OCCUPANCY_WIDTH'),
 'o_idle': ('output', 1),
 'o_quiescent': ('output', 1),
 'o_drain_done': ('output', 1),
 'o_flushed': ('output', 1),
 'o_error': ('output', 1),
 'o_error_code': ('output', 'lut_unit_pkg::ERROR_WIDTH'),
 'o_fatal_error': ('output', 1),
 'o_event_lookup_accept': ('output', 1),
 'o_event_lookup_complete': ('output', 1),
 'o_event_lookup_stall': ('output', 1),
 'o_event_result_stall': ('output', 1),
 'o_event_clip_low': ('output', 1),
 'o_event_clip_high': ('output', 1),
 'o_event_interpolate': ('output', 1),
 'o_event_program_write': ('output', 1),
 'o_event_program_read': ('output', 1),
 'o_event_program_commit': ('output', 1),
 'o_event_program_invalidate': ('output', 1),
 'o_event_table_corrected': ('output', 1),
 'o_event_table_uncorrectable': ('output', 1)}
INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'input' and n != 'i_clk')
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'output')


class LutUnitItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False, fault=None):
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
    item: LutUnitItem
    stage: str
    storage: dict
