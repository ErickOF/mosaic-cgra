"""Public port widths, power encodings and clock-opportunity transactions."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

PORTS = {
    'i_aon_clk': ('input', 1),
    'i_aon_rstb': ('input', 1),
    'i_error_clear': ('input', 1),
    'i_test_mode': ('input', 1),
    'i_test_clock_enable': ('input', 1),
    'i_config_valid': ('input', 1),
    'o_config_ready': ('output', 1),
    'i_config_auto_idle_enable': ('input', 1),
    'i_config_wake_enable': ('input', 'W'),
    'i_config_context_check': ('input', 1),
    'i_config_context_id': ('input', 'C'),
    'o_config_accepted': ('output', 1),
    'o_config_rejected': ('output', 1),
    'i_command_valid': ('input', 1),
    'o_command_ready': ('output', 1),
    'i_command': ('input', 'tile_power_controller_pkg::POWER_COMMAND_WIDTH'),
    'i_command_context_id': ('input', 'C'),
    'o_command_accepted': ('output', 1),
    'o_command_rejected': ('output', 1),
    'o_command_done': ('output', 1),
    'i_tile_busy': ('input', 1),
    'i_tile_quiescent': ('input', 1),
    'i_drain_done': ('input', 1),
    'i_stall_reason': ('input', 'S'),
    'i_clock_group_request': ('input', 'G'),
    'i_wakeup_event': ('input', 'W'),
    'i_power_good_async': ('input', 1),
    'i_retention_save_ack': ('input', 1),
    'i_retention_restore_ack': ('input', 1),
    'o_tile_accept_enable': ('output', 1),
    'o_drain_request': ('output', 1),
    'o_tile_clock_enable': ('output', 1),
    'o_clock_group_enable': ('output', 'G'),
    'o_operand_isolation_enable': ('output', 1),
    'o_write_disable': ('output', 1),
    'o_tile_reset_request': ('output', 1),
    'o_isolation_enable': ('output', 1),
    'o_retention_save': ('output', 1),
    'o_retention_restore': ('output', 1),
    'o_power_switch_enable': ('output', 1),
    'o_power_state': ('output', 'tile_power_controller_pkg::POWER_STATE_WIDTH'),
    'o_target_state': ('output', 'tile_power_controller_pkg::POWER_STATE_WIDTH'),
    'o_previous_stable_state': ('output', 'tile_power_controller_pkg::POWER_STATE_WIDTH'),
    'o_transition_active': ('output', 1),
    'o_power_good_sync': ('output', 1),
    'o_wakeup_pending': ('output', 'W'),
    'o_policy_valid': ('output', 1),
    'o_active_context_id': ('output', 'C'),
    'o_idle_count': ('output', 'IW'),
    'o_state_residency': ('output', 'tile_power_controller_pkg::POWER_RESIDENCY_WIDTH'),
    'o_idle': ('output', 1),
    'o_quiescent': ('output', 1),
    'o_error': ('output', 1),
    'o_fatal_error': ('output', 1),
    'o_error_code': ('output', 'tile_power_controller_pkg::POWER_ERROR_WIDTH'),
    'o_event_state_change': ('output', 1),
    'o_event_idle_entry': ('output', 1),
    'o_event_wakeup': ('output', 1),
    'o_event_stall_entry': ('output', 1),
    'o_event_retention_entry': ('output', 1),
    'o_event_off_entry': ('output', 1),
    'o_event_timeout': ('output', 1),
}
INPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'input' and n != 'i_aon_clk')
OUTPUTS = tuple(n for n, (d, _) in PORTS.items() if d == 'output')
STATES = {
    'RESET': 0,
    'ACTIVE': 1,
    'STALLED': 2,
    'IDLE': 3,
    'DRAINING': 4,
    'SAVING': 5,
    'ISOLATING': 6,
    'POWERING_DOWN': 7,
    'RETENTION': 8,
    'OFF': 9,
    'POWERING_UP': 10,
    'RESTORING': 11,
    'REINITIALIZING': 12,
    'WAKEUP': 13,
    'ERROR': 14,
}
ERRORS = {
    'NONE': 0,
    'COMMAND': 1,
    'CONTEXT': 2,
    'TRANSITION': 3,
    'UNKNOWN': 4,
    'DRAIN_TIMEOUT': 5,
    'SAVE_TIMEOUT': 6,
    'RESTORE_TIMEOUT': 7,
    'ACK': 8,
    'POWER_UP_TIMEOUT': 9,
    'POWER_DOWN_TIMEOUT': 10,
    'POWER_LOSS': 11,
    'TEST': 12,
    'CONFIG': 13,
    'SEQUENCE': 14,
}
STABLE = frozenset(STATES[n] for n in ('ACTIVE', 'STALLED', 'IDLE', 'RETENTION', 'OFF', 'ERROR'))


class PowerItem(uvm_sequence_item):
    def __init__(self, label, controls, *, edge=True, random=False):
        super().__init__(label)
        self.controls = controls
        self.edge = edge
        self.random = random
        self.pre = self.post = None


@dataclass(frozen=True)
class Observation:
    ports: dict
    storage: dict
    item: PowerItem
    stage: str
