"""Complete port schema and one real clock opportunity."""
from dataclasses import dataclass, field
from pyuvm import uvm_sequence_item

PORTS = {'i_clk': ('input', 1),
 'i_rstb': ('input', 1),
 'i_flush': ('input', 1),
 'i_error_clear': ('input', 1),
 'i_config_valid': ('input', 1),
 'o_config_ready': ('output', 1),
 'i_config_depth': ('input', 'DEPTH_WIDTH'),
 'i_config_level_mode': ('input', 'D*MODE_WIDTH'),
 'i_config_initial': ('input', 'INDEX_VECTOR_WIDTH'),
 'i_config_bound': ('input', 'INDEX_VECTOR_WIDTH'),
 'i_config_step': ('input', 'INDEX_VECTOR_WIDTH'),
 'i_config_trip_count': ('input', 'TRIP_VECTOR_WIDTH'),
 'i_config_compare': ('input', 'D*COMPARE_WIDTH'),
 'i_config_initiation_interval': ('input', 'P'),
 'i_config_context_id': ('input', 'C'),
 'i_config_completion_event_enable': ('input', 1),
 'i_config_completion_event_id': ('input', 'EVENT_ID_WIDTH'),
 'o_config_accepted': ('output', 1),
 'o_config_rejected': ('output', 1),
 'o_config_validating': ('output', 1),
 'i_start_valid': ('input', 1),
 'o_start_ready': ('output', 1),
 'i_start_context_id': ('input', 'C'),
 'i_start_run_id': ('input', 'R'),
 'o_start_accepted': ('output', 1),
 'o_start_rejected': ('output', 1),
 'i_control_valid': ('input', 1),
 'o_control_ready': ('output', 1),
 'i_control_command': ('input', 'CONTROL_WIDTH'),
 'i_control_context_id': ('input', 'C'),
 'i_control_run_id': ('input', 'R'),
 'o_control_accepted': ('output', 1),
 'o_control_rejected': ('output', 1),
 'i_execution_quiescent': ('input', 1),
 'o_quiesce_request': ('output', 1),
 'o_iteration_valid': ('output', 1),
 'i_iteration_ready': ('input', 1),
 'o_iteration_index': ('output', 'INDEX_VECTOR_WIDTH'),
 'o_iteration_ordinal': ('output', 'TRIP_VECTOR_WIDTH'),
 'o_iteration_first_mask': ('output', 'D'),
 'o_iteration_last_mask': ('output', 'D'),
 'o_iteration_active_mask': ('output', 'D'),
 'o_iteration_linear': ('output', 'L'),
 'o_iteration_context_id': ('output', 'C'),
 'o_iteration_run_id': ('output', 'R'),
 'o_iteration_epoch': ('output', 'E'),
 'o_completion_valid': ('output', 1),
 'i_completion_ready': ('input', 1),
 'o_completion_event_enable': ('output', 1),
 'o_completion_event_id': ('output', 'EVENT_ID_WIDTH'),
 'o_completion_context_id': ('output', 'C'),
 'o_completion_run_id': ('output', 'R'),
 'o_completion_status': ('output', 'loop_controller_pkg::COMPLETION_WIDTH'),
 'o_completion_iterations': ('output', 'L'),
 'o_configured': ('output', 1),
 'o_active': ('output', 1),
 'o_pause_pending': ('output', 1),
 'o_abort_pending': ('output', 1),
 'o_completion_pending': ('output', 1),
 'o_suspended': ('output', 1),
 'o_current_depth': ('output', 'DEPTH_WIDTH'),
 'o_current_context_id': ('output', 'C'),
 'o_current_run_id': ('output', 'R'),
 'o_current_epoch': ('output', 'E'),
 'o_total_iterations': ('output', 'L'),
 'o_pacing_count': ('output', 'P'),
 'o_idle': ('output', 1),
 'o_quiescent': ('output', 1),
 'o_error': ('output', 1),
 'o_fatal_error': ('output', 1),
 'o_error_code': ('output', 'loop_controller_pkg::ERROR_WIDTH'),
 'o_event_iteration_transfer': ('output', 1),
 'o_event_inner_wrap': ('output', 1),
 'o_event_outer_wrap': ('output', 'D'),
 'o_event_run_complete': ('output', 1),
 'o_event_iteration_stall': ('output', 1),
 'o_event_pause': ('output', 1),
 'o_event_resume': ('output', 1),
 'o_event_abort': ('output', 1)}
INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'input' and n != 'i_clk')
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'output')


class LoopControllerItem(uvm_sequence_item):
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
    item: LoopControllerItem
    stage: str
    internals: dict[str, str] = field(default_factory=dict)
