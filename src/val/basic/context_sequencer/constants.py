"""Repository-local version-one interface encodings and port names."""

from enum import IntEnum


class Mode(IntEnum):
    HOLD = 0
    INCREMENT = 1
    JUMP = 2
    LOOP = 3
    END = 4


class Error(IntEnum):
    NONE = 0
    ACTIVE_INVALID = 1
    ADDRESS = 2
    TRANSITION = 3
    LOOP = 4
    COMMAND = 5
    PROTOCOL = 6


class State(IntEnum):
    IDLE = 0
    START_WAIT = 1
    ACTIVE = 2
    CONTEXT_WAIT = 3
    STOP_PENDING = 4
    SUSPEND_PENDING = 5
    SUSPENDED = 6
    SWITCH_PENDING = 7
    SWITCH_WAIT = 8
    COMPLETED = 9
    ERROR = 10


COMMANDS = ("i_start_enable", "i_stop_request", "i_suspend_request", "i_resume_request", "i_switch_request", "i_error_clear")
INPUTS = ("i_clk", "i_rstb", *COMMANDS, "i_start_context", "i_switch_context", "i_step_accepted", "i_safe_point",
          "i_transition_mode", "i_transition_target", "i_loop_count", "i_active_context_valid", "i_candidate_context_valid")
OUTPUTS = ("o_active_read_enable", "o_active_context", "o_candidate_read_enable", "o_candidate_context", "o_context_enable",
           "o_quiesce_request", "o_idle", "o_active", "o_context_wait", "o_stop_pending", "o_suspend_pending", "o_suspended",
           "o_switch_pending", "o_completed", "o_error", "o_error_code", "o_context_activated", "o_context_changed",
           "o_sequence_completed", "o_loop_active", "o_loop_owner", "o_loop_remaining")
COMBINATIONAL = {"o_active_read_enable", "o_candidate_read_enable", "o_candidate_context", "o_context_enable", "o_quiesce_request"}
REGISTERED = set(OUTPUTS) - COMBINATIONAL
INTERNALS = ("state", "pending_context", "pending_scheduled")


def legal_commands(state, config):
    """Table from the specification; pending requests are single-cycle commands."""
    result = set()
    if state in (State.IDLE, State.COMPLETED):
        result.add("i_start_enable")
    if state in (State.START_WAIT, State.ACTIVE, State.CONTEXT_WAIT, State.SUSPEND_PENDING,
                 State.SUSPENDED, State.SWITCH_PENDING, State.SWITCH_WAIT):
        result.add("i_stop_request")
    if config.suspend and state in (State.ACTIVE, State.CONTEXT_WAIT):
        result.add("i_suspend_request")
    if config.suspend and state == State.SUSPENDED:
        result.add("i_resume_request")
    if config.switch and state in (State.ACTIVE, State.CONTEXT_WAIT, State.SUSPENDED):
        result.add("i_switch_request")
    if state == State.ERROR:
        result.add("i_error_clear")
    return result


def reachable_states(config):
    states = {State.IDLE, State.START_WAIT, State.ACTIVE, State.CONTEXT_WAIT,
              State.STOP_PENDING, State.COMPLETED, State.ERROR}
    if config.suspend:
        states.update((State.SUSPEND_PENDING, State.SUSPENDED))
    if config.switch:
        states.update((State.SWITCH_PENDING, State.SWITCH_WAIT))
    return states
