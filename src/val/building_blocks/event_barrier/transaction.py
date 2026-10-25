"""Driver transactions and passive observations of the complete interface."""
from dataclasses import dataclass
from pyuvm import uvm_sequence_item

PORTS = {'i_clk': ['input', 1],
 'i_rstb': ['input', 1],
 'i_flush': ['input', 1],
 'i_error_clear': ['input', 1],
 'i_config_valid': ['input', 1],
 'i_post_valid': ['input', 1],
 'i_ack_valid': ['input', 1],
 'i_wait_valid': ['input', 1],
 'i_wait_cancel_valid': ['input', 1],
 'i_wait_result_ready': ['input', 1],
 'i_barrier_config_valid': ['input', 1],
 'i_barrier_config_enable': ['input', 1],
 'i_barrier_release_event_enable': ['input', 1],
 'i_barrier_arrival_valid': ['input', 1],
 'i_barrier_release_ready': ['input', 1],
 'i_wait_consume': ['input', 1],
 'i_config_context_id': ['input', 'C'],
 'i_post_context_id': ['input', 'C'],
 'i_ack_context_id': ['input', 'C'],
 'i_wait_context_id': ['input', 'C'],
 'i_wait_cancel_context_id': ['input', 'C'],
 'i_barrier_context_id': ['input', 'C'],
 'i_barrier_arrival_context_id': ['input', 'C'],
 'i_config_event_enable': ['input', 'E'],
 'i_wait_event_mask': ['input', 'E'],
 'i_post_event_id': ['input', 'EI'],
 'i_ack_event_id': ['input', 'EI'],
 'i_barrier_release_event_id': ['input', 'EI'],
 'i_ack_mode': ['input', 2],
 'i_wait_mode': ['input', 2],
 'i_wait_slot': ['input', 'WI'],
 'i_wait_cancel_slot': ['input', 'WI'],
 'i_wait_tag': ['input', 'WT'],
 'i_wait_cancel_tag': ['input', 'WT'],
 'i_barrier_config_id': ['input', 'BI'],
 'i_barrier_arrival_id': ['input', 'BI'],
 'i_barrier_expected_mask': ['input', 'P'],
 'i_barrier_tag': ['input', 'BT'],
 'i_barrier_participant_id': ['input', 'PI'],
 'i_barrier_arrival_generation': ['input', 'G'],
 'o_config_ready': ['output', 1],
 'o_config_accepted': ['output', 1],
 'o_config_rejected': ['output', 1],
 'o_post_ready': ['output', 1],
 'o_post_accepted': ['output', 1],
 'o_post_rejected': ['output', 1],
 'o_ack_ready': ['output', 1],
 'o_ack_accepted': ['output', 1],
 'o_ack_rejected': ['output', 1],
 'o_wait_ready': ['output', 1],
 'o_wait_armed': ['output', 1],
 'o_wait_rejected': ['output', 1],
 'o_wait_cancel_ready': ['output', 1],
 'o_wait_canceled': ['output', 1],
 'o_wait_cancel_not_found': ['output', 1],
 'o_wait_result_valid': ['output', 1],
 'o_wait_result_status': ['output', 1],
 'o_barrier_config_ready': ['output', 1],
 'o_barrier_configured': ['output', 1],
 'o_barrier_config_rejected': ['output', 1],
 'o_barrier_arrival_ready': ['output', 1],
 'o_barrier_arrival_accepted': ['output', 1],
 'o_barrier_arrival_rejected': ['output', 1],
 'o_barrier_release_valid': ['output', 1],
 'o_barrier_release_event_enable': ['output', 1],
 'o_policy_valid': ['output', 1],
 'o_idle': ['output', 1],
 'o_quiescent': ['output', 1],
 'o_flushed': ['output', 1],
 'o_error': ['output', 1],
 'o_fatal_error': ['output', 1],
 'o_event_post': ['output', 1],
 'o_event_ack': ['output', 1],
 'o_event_wait_complete': ['output', 1],
 'o_event_barrier_arrival': ['output', 1],
 'o_event_barrier_release': ['output', 1],
 'o_event_duplicate_arrival': ['output', 1],
 'o_event_mutation_stall': ['output', 1],
 'o_active_context_id': ['output', 'C'],
 'o_wait_result_context_id': ['output', 'C'],
 'o_barrier_release_context_id': ['output', 'C'],
 'o_event_pending': ['output', 'E'],
 'o_event_saturated': ['output', 'E'],
 'o_wait_result_matched_mask': ['output', 'E'],
 'o_wait_result_consumed_mask': ['output', 'E'],
 'o_event_count': ['output', 'E*K'],
 'o_wait_slot_active': ['output', 'W'],
 'o_barrier_enable': ['output', 'B'],
 'o_barrier_arrived': ['output', 'B*P'],
 'o_barrier_generation': ['output', 'B*G'],
 'o_wait_result_occupancy': ['output', 'QW'],
 'o_barrier_release_occupancy': ['output', 'QR'],
 'o_wait_result_slot': ['output', 'WI'],
 'o_wait_result_mode': ['output', 2],
 'o_wait_result_tag': ['output', 'WT'],
 'o_barrier_release_id': ['output', 'BI'],
 'o_barrier_release_generation': ['output', 'G'],
 'o_barrier_release_tag': ['output', 'BT'],
 'o_barrier_release_participants': ['output', 'P'],
 'o_barrier_release_event_id': ['output', 'EI'],
 'o_error_code': ['output', 4]}

INPUTS = tuple(name for name, (direction, _) in PORTS.items() if direction == 'input' and name != 'i_clk')
OUTPUTS = tuple(name for name, (direction, _) in PORTS.items() if direction == 'output')
VALIDS = tuple(name for name in INPUTS if name.endswith('_valid'))


class EventBarrierItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False, fault=''):
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
    item: EventBarrierItem
    stage: str
