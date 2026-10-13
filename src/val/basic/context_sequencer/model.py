"""Behavioral sequence position and loop-visit reference, independent of RTL."""

from context_sequencer.constants import COMMANDS, Error, Mode, State, legal_commands


def integer(value):
    return int(value, 2) if set(value) <= {"0", "1"} else None


class SequencerModel:
    def __init__(self, config):
        self.config = config
        self.clock = "0"
        self.reset()

    def reset(self):
        self.state = State.IDLE
        self.active = self.pending = 0
        self.pending_scheduled = False
        self.owner = None
        self.total_visits = self.visits = 0
        self.error = Error.NONE
        self.activated = self.changed = self.completed = False

    @property
    def remaining(self):
        return self.total_visits - self.visits if self.owner is not None else 0

    def valid_address(self, value):
        parsed = integer(value)
        return parsed is not None and parsed < self.config.depth

    def transition(self, ports):
        """Resolve the next sequence position using total visits, not a counter."""
        mode = integer(ports["i_transition_mode"])
        if mode not in set(Mode) or mode == Mode.LOOP and not self.config.loop:
            return None, (Error.TRANSITION, "transition_mode"), None
        if mode in (Mode.HOLD, Mode.END):
            return None, None, None
        finish = mode == Mode.INCREMENT
        action = None
        if mode == Mode.LOOP:
            if self.owner is not None:
                if self.owner != self.active:
                    return None, (Error.LOOP, "nested_loop"), None
                action = "visit"
                finish = self.visits + 1 >= self.total_visits
            else:
                count = integer(ports["i_loop_count"])
                if count is None or count == 0:
                    return None, (Error.LOOP, "loop_count"), None
                action = "start"
                finish = count == 1
        if finish:
            destination = self.active + 1
            if destination >= self.config.depth:
                return None, (Error.ADDRESS, "fallthrough_address"), None
        else:
            if not self.valid_address(ports["i_transition_target"]):
                return None, (Error.ADDRESS, "transition_target"), None
            destination = integer(ports["i_transition_target"])
        return destination, None, "clear" if mode == Mode.LOOP and finish else action

    def reads(self, ports):
        active_read = self.state == State.ACTIVE or self.state == State.SUSPENDED and self.config.suspend and ports["i_resume_request"] == "1"
        candidate = None
        if self.state in (State.IDLE, State.COMPLETED) and ports["i_start_enable"] == "1" and self.valid_address(ports["i_start_context"]):
            candidate = integer(ports["i_start_context"])
        elif self.config.switch and self.owner is None and self.state in (State.ACTIVE, State.CONTEXT_WAIT, State.SUSPENDED) and ports["i_switch_request"] == "1" and self.valid_address(ports["i_switch_context"]):
            candidate = integer(ports["i_switch_context"])
        elif self.state in (State.START_WAIT, State.CONTEXT_WAIT, State.SWITCH_PENDING, State.SWITCH_WAIT):
            candidate = self.pending
        elif self.state == State.ACTIVE and all(ports[name] == "0" for name in COMMANDS):
            candidate, _, _ = self.transition(ports)
        if ports["i_rstb"] != "1":
            return False, None
        return active_read, candidate

    def outputs(self, ports):
        active_read, candidate = self.reads(ports)
        quiescing = self.state in (State.STOP_PENDING, State.SUSPEND_PENDING, State.SWITCH_PENDING, State.SWITCH_WAIT)
        requesting = ports["i_stop_request"] == "1" or self.config.suspend and ports["i_suspend_request"] == "1" or self.config.switch and ports["i_switch_request"] == "1"
        quiescing |= self.state in (State.ACTIVE, State.CONTEXT_WAIT, State.START_WAIT, State.SUSPENDED) and requesting
        result = dict(o_active_read_enable=active_read, o_active_context=self.active,
                      o_candidate_read_enable=candidate is not None, o_candidate_context=candidate or 0,
                      o_context_enable=ports["i_rstb"] == "1" and self.state == State.ACTIVE and ports["i_active_context_valid"] == "1" and all(ports[name] == "0" for name in COMMANDS),
                      o_quiesce_request=ports["i_rstb"] == "1" and quiescing,
                      o_context_wait=self.state in (State.START_WAIT, State.CONTEXT_WAIT, State.SWITCH_WAIT),
                      o_switch_pending=self.state in (State.SWITCH_PENDING, State.SWITCH_WAIT),
                      o_error_code=self.error, o_context_activated=self.activated, o_context_changed=self.changed,
                      o_sequence_completed=self.completed, o_loop_active=self.owner is not None,
                      o_loop_owner=self.owner or 0, o_loop_remaining=self.remaining)
        for output, state in (("o_idle", State.IDLE), ("o_active", State.ACTIVE), ("o_stop_pending", State.STOP_PENDING),
                              ("o_suspend_pending", State.SUSPEND_PENDING), ("o_suspended", State.SUSPENDED),
                              ("o_completed", State.COMPLETED), ("o_error", State.ERROR)):
            result[output] = self.state == state
        return result

    def fault(self, ports):
        if ports["i_rstb"] == "0":
            return None
        for name in ("i_rstb", *COMMANDS, "i_step_accepted"):
            if integer(ports[name]) is None:
                return Error.PROTOCOL, name
        asserted = [name for name in COMMANDS if ports[name] == "1"]
        if len(asserted) > 1:
            return Error.COMMAND, "command_conflict"
        if asserted and (asserted[0] not in legal_commands(self.state, self.config) or asserted[0] == "i_switch_request" and self.owner is not None):
            return Error.COMMAND, "command_state:" + asserted[0]
        active_read, candidate = self.reads(ports)
        for enabled, name in ((active_read, "i_active_context_valid"), (candidate is not None, "i_candidate_context_valid")):
            if enabled and integer(ports[name]) is None:
                return Error.PROTOCOL, name
        safe_required = self.state in (State.STOP_PENDING, State.SUSPEND_PENDING, State.SWITCH_PENDING) or bool(set(asserted) & {"i_stop_request", "i_suspend_request", "i_switch_request"})
        if safe_required and integer(ports["i_safe_point"]) is None:
            return Error.PROTOCOL, "i_safe_point"
        if self.state == State.ACTIVE and ports["i_active_context_valid"] == "0":
            return Error.ACTIVE_INVALID, "active_invalid"
        if ports["i_step_accepted"] == "1" and not self.outputs(ports)["o_context_enable"]:
            return Error.PROTOCOL, "step_without_execution"
        for command, field in (("i_start_enable", "i_start_context"), ("i_switch_request", "i_switch_context")):
            if ports[command] == "1" and not self.valid_address(ports[field]):
                return Error.ADDRESS, field
        if ports["i_resume_request"] == "1" and ports["i_active_context_valid"] == "0":
            return Error.ACTIVE_INVALID, "resume_invalid"
        if self.state == State.ACTIVE and ports["i_step_accepted"] == "1":
            return self.transition(ports)[1]
        return None

    def clear_loop(self):
        self.owner = None
        self.total_visits = self.visits = 0

    def activate(self, address):
        self.changed = address != self.active
        self.active = address
        self.state = State.ACTIVE
        self.pending_scheduled = False
        self.activated = True

    def step(self, ports):
        rising = self.clock == "0" and ports["i_clk"] == "1"
        self.clock = ports["i_clk"]
        if ports["i_rstb"] == "0" and (self.config.async_reset or rising):
            self.reset()
        elif rising:
            self.activated = self.changed = self.completed = False
            if self.state == State.ERROR:
                if ports["i_error_clear"] == "1" and all(ports[name] == "0" for name in COMMANDS if name != "i_error_clear") and ports["i_step_accepted"] == "0" and ports["i_rstb"] == "1":
                    self.reset()
                return rising
            fault = self.fault(ports)
            if fault:
                self.state, self.error = State.ERROR, fault[0]
                return rising
            command = next((name for name in COMMANDS if ports[name] == "1"), None)
            if command == "i_start_enable":
                self.clear_loop()
                self.pending, self.pending_scheduled = integer(ports["i_start_context"]), False
                self.state = State.START_WAIT
                if ports["i_candidate_context_valid"] == "1":
                    self.activate(self.pending)
            elif command == "i_stop_request" or self.state == State.STOP_PENDING:
                self.state = State.STOP_PENDING
                if ports["i_safe_point"] == "1":
                    self.reset()
            elif command == "i_suspend_request" or self.state == State.SUSPEND_PENDING:
                self.state = State.SUSPENDED if ports["i_safe_point"] == "1" else State.SUSPEND_PENDING
            elif command == "i_switch_request":
                self.pending, self.pending_scheduled = integer(ports["i_switch_context"]), False
                self.state = State.SWITCH_PENDING
                if ports["i_safe_point"] == "1":
                    self.state = State.SWITCH_WAIT
                    if ports["i_candidate_context_valid"] == "1":
                        self.clear_loop()
                        self.activate(self.pending)
            elif command == "i_resume_request":
                self.state = State.CONTEXT_WAIT if self.pending_scheduled else State.ACTIVE
                self.activated = not self.pending_scheduled
            elif self.state in (State.START_WAIT, State.CONTEXT_WAIT, State.SWITCH_WAIT):
                if ports["i_candidate_context_valid"] == "1":
                    if self.state == State.SWITCH_WAIT:
                        self.clear_loop()
                    self.activate(self.pending)
            elif self.state == State.SWITCH_PENDING:
                if ports["i_safe_point"] == "1":
                    self.state = State.SWITCH_WAIT
                    if ports["i_candidate_context_valid"] == "1":
                        self.clear_loop()
                        self.activate(self.pending)
            elif self.state == State.ACTIVE and ports["i_step_accepted"] == "1":
                mode = integer(ports["i_transition_mode"])
                if mode == Mode.END:
                    self.state, self.completed = State.COMPLETED, True
                    self.pending, self.pending_scheduled = 0, False
                    self.clear_loop()
                else:
                    destination, _, action = self.transition(ports)
                    if destination is not None:
                        if action == "start":
                            self.owner, self.total_visits, self.visits = self.active, integer(ports["i_loop_count"]), 1
                        elif action == "visit":
                            self.visits += 1
                        elif action == "clear":
                            self.clear_loop()
                        self.pending, self.pending_scheduled = destination, True
                        self.state = State.CONTEXT_WAIT
                        if ports["i_candidate_context_valid"] == "1":
                            self.activate(destination)
        return rising
