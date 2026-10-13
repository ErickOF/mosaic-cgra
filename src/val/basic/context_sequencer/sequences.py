"""Directed state graph, exact loop trips, runtime safety, and seeded traffic."""

from itertools import combinations
import random
from pyuvm import uvm_sequence
from context_sequencer.constants import COMMANDS, INPUTS, Mode, State, legal_commands, reachable_states
from context_sequencer.transaction import SequencerItem


class SequencerSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("specification_sequence")
        self.config = config
        self.last = None
        self.wait_origin = State.START_WAIT

    async def cycle(self, label, *, violation=None, random=False, hold_ps=10, **updates):
        previous_state = self.state() if self.last else State.IDLE
        ports = dict.fromkeys(INPUTS, 0)
        ports.update(i_rstb=1, i_active_context_valid=1, i_candidate_context_valid=1, i_loop_count=1)
        ports.update(updates)
        for clock in (0, 1):
            item = SequencerItem(self.config, label, ports | {"i_clk": clock},
                                 violation=violation if clock else None, random=random and bool(clock), hold_ps=hold_ps)
            await self.start_item(item)
            await self.finish_item(item)
            self.last = item.observation
        if self.last.ports["o_context_wait"] == "1" and self.last.ports["o_switch_pending"] == "0":
            if updates.get("i_start_enable") == 1:
                self.wait_origin = State.START_WAIT
            elif previous_state == State.ACTIVE and updates.get("i_step_accepted") == 1:
                self.wait_origin = State.CONTEXT_WAIT

    def state(self):
        ports = self.last.ports
        if ports["o_error"] == "1": return State.ERROR
        if ports["o_completed"] == "1": return State.COMPLETED
        if ports["o_switch_pending"] == "1": return State.SWITCH_WAIT if ports["o_context_wait"] == "1" else State.SWITCH_PENDING
        if ports["o_suspended"] == "1": return State.SUSPENDED
        if ports["o_suspend_pending"] == "1": return State.SUSPEND_PENDING
        if ports["o_stop_pending"] == "1": return State.STOP_PENDING
        if ports["o_active"] == "1": return State.ACTIVE
        if ports["o_idle"] == "1": return State.IDLE
        if self.config.check_internals:
            return State(int(self.last.internals["state"], 2))
        # START_WAIT and CONTEXT_WAIT share status. Track the validated command
        # origin across waits and suspension when private state is not observed.
        return self.wait_origin

    async def reset(self):
        await self.cycle("reset", i_rstb=0)
        await self.cycle("reset_release")

    async def start_context(self, address=0, *, valid=1):
        await self.cycle("start", i_start_enable=1, i_start_context=address, i_candidate_context_valid=valid)

    async def navigate(self, state):
        await self.reset()
        if state == State.IDLE:
            return
        if state == State.START_WAIT:
            await self.cycle("nav_start_wait", i_start_enable=1, i_candidate_context_valid=0)
            return
        if state == State.ERROR:
            await self.cycle("nav_error", i_resume_request=1, violation="command_state:i_resume_request")
            return
        await self.start_context()
        if state == State.ACTIVE:
            return
        if state == State.CONTEXT_WAIT:
            await self.cycle("nav_context_wait", i_step_accepted=1, i_transition_mode=Mode.JUMP, i_candidate_context_valid=0)
        elif state == State.STOP_PENDING:
            await self.cycle("nav_stop_pending", i_stop_request=1)
        elif state == State.SUSPEND_PENDING:
            await self.cycle("nav_suspend_pending", i_suspend_request=1)
        elif state == State.SUSPENDED:
            await self.cycle("nav_suspended", i_suspend_request=1, i_safe_point=1)
        elif state == State.SWITCH_PENDING:
            await self.cycle("nav_switch_pending", i_switch_request=1, i_switch_context=self.config.depth - 1, i_candidate_context_valid=0)
        elif state == State.SWITCH_WAIT:
            await self.cycle("nav_switch_wait", i_switch_request=1, i_switch_context=self.config.depth - 1, i_safe_point=1, i_candidate_context_valid=0)
        elif state == State.COMPLETED:
            await self.cycle("nav_completed", i_step_accepted=1, i_transition_mode=Mode.END)
        assert self.state() == state, f"Directed navigation did not reach {state.name}"

    async def runtime(self, state, command, latency, candidate_valid):
        await self.navigate(state)
        inputs = {command: 1, "i_safe_point": int(latency == 0), "i_candidate_context_valid": candidate_valid,
                  "i_switch_context": self.config.depth - 1}
        await self.cycle(f"runtime:{command}:{latency}", **inputs)
        for delay in range(1, latency + 1):
            await self.cycle("draining", i_safe_point=int(delay == latency), i_candidate_context_valid=candidate_valid)
        if self.state() in (State.START_WAIT, State.CONTEXT_WAIT, State.SWITCH_WAIT):
            for _ in range(3):
                await self.cycle("candidate_wait", i_candidate_context_valid=0)
            await self.cycle("candidate_commit", i_candidate_context_valid=1)

    async def state_graph(self):
        config = self.config
        for state in sorted(reachable_states(config)):
            for command in COMMANDS:
                if command in legal_commands(state, config):
                    if command in ("i_stop_request", "i_suspend_request", "i_switch_request"):
                        for latency in (0, 1, 5):
                            for valid in (0, 1):
                                await self.runtime(state, command, latency, valid)
                    else:
                        for valid in (0, 1):
                            await self.navigate(state)
                            await self.cycle("state_command", **{command: 1, "i_candidate_context_valid": valid})
                            if self.state() == State.START_WAIT:
                                await self.cycle("start_wait_stall", i_candidate_context_valid=0)
                                await self.cycle("start_commit", i_candidate_context_valid=1)
                else:
                    await self.navigate(state)
                    await self.cycle("illegal_state_command", violation="command_state:" + command, **{command: 1})
                    await self.cycle("sticky_error")
                    await self.cycle("error_clear", i_error_clear=1)
            await self.navigate(state)
            await self.cycle("reset_priority", i_rstb=0, **dict.fromkeys(COMMANDS, 1),
                             i_step_accepted=1, i_transition_mode="xxx", i_transition_target="x" * config.address_width,
                             i_loop_count="x" * config.count_width)
        if config.suspend:
            await self.navigate(State.CONTEXT_WAIT)
            await self.cycle("suspend_pending_candidate", i_suspend_request=1, i_candidate_context_valid=0)
            await self.cycle("suspend_drain", i_safe_point=0)
            await self.cycle("suspend_safe", i_safe_point=1)
            await self.cycle("suspended_hold", i_active_context_valid="x", i_candidate_context_valid="z")
            await self.cycle("resume_pending_candidate", i_resume_request=1, i_candidate_context_valid=0)
            await self.cycle("resume_wait", i_candidate_context_valid=0)
            await self.cycle("resume_commit", i_candidate_context_valid=1)

    async def scheduled(self):
        config = self.config
        for address in range(config.depth):
            await self.reset()
            await self.start_context(address)
            await self.cycle("hold", i_step_accepted=1)
            await self.cycle("event_clear")
        for mode in (Mode.INCREMENT, Mode.JUMP):
            pairs = [(0, 0)] if mode == Mode.JUMP else []
            if config.depth > 1:
                pairs += [(0, config.depth - 1), (config.depth - 1, 0)] if mode == Mode.JUMP else [(0, 1)]
            for source, target in pairs:
                for valid in (0, 1):
                    await self.reset()
                    await self.start_context(source)
                    await self.cycle("scheduled", i_step_accepted=1, i_transition_mode=mode, i_transition_target=target, i_candidate_context_valid=valid)
                    if not valid:
                        for _ in range(3):
                            await self.cycle("scheduled_wait", i_candidate_context_valid=0, i_active_context_valid="x",
                                             i_transition_mode="xxx", i_transition_target="z" * config.address_width,
                                             i_loop_count="x" * config.count_width)
                        await self.cycle("scheduled_commit")
        for length in range(33):
            await self.navigate(State.ACTIVE)
            for _ in range(length):
                await self.cycle("hold_stall", hold_ps=100)
            await self.cycle("hold_accept", i_step_accepted=1)
        await self.navigate(State.ACTIVE)
        await self.cycle("end", i_step_accepted=1, i_transition_mode=Mode.END)
        await self.cycle("completed_hold")
        await self.start_context(config.depth - 1)
        await self.cycle("restart_hold", i_step_accepted=1)

    async def loops(self):
        config = self.config
        if not config.loop:
            await self.navigate(State.ACTIVE)
            await self.cycle("loop_disabled", i_step_accepted=1, i_transition_mode=Mode.LOOP, violation="transition_mode")
            return
        counts = sorted({1, min(2, config.maximum_count), max(1, config.maximum_count // 2, min(3, config.maximum_count)), config.maximum_count})
        for count in counts:
            for stall in ((0, 1, 5) if count <= 32 else (0,)):
                await self.navigate(State.ACTIVE)
                for visit in range(count):
                    delay = stall if count <= 32 else (0, 1, 5)[visit] if visit < 3 else 0
                    for _ in range(delay):
                        await self.cycle("loop_stall")
                    expected = "fallthrough_address" if config.depth == 1 and visit == count - 1 else None
                    await self.cycle("loop_visit", i_step_accepted=1, i_transition_mode=Mode.LOOP, i_transition_target=0,
                                     i_loop_count=count if visit == 0 else "x" * config.count_width, violation=expected)
        if config.maximum_count == 1 and config.depth > 1:
            await self.navigate(State.ACTIVE)
            await self.cycle("one_visit_candidate_wait", i_step_accepted=1, i_transition_mode=Mode.LOOP,
                             i_loop_count=1, i_candidate_context_valid=0)
            await self.cycle("one_visit_wait", i_candidate_context_valid=0)
            await self.cycle("one_visit_commit")
        if config.maximum_count > 1:
            for valid in (0, 1):
                await self.navigate(State.ACTIVE)
                await self.cycle("loop_candidate", i_step_accepted=1, i_transition_mode=Mode.LOOP, i_loop_count=2, i_candidate_context_valid=valid)
                if not valid:
                    await self.cycle("loop_candidate_wait", i_candidate_context_valid=0)
                    await self.cycle("loop_candidate_commit")
            for action in ("stop", "end", *( ("suspend",) if config.suspend else () )):
                await self.navigate(State.ACTIVE)
                await self.cycle("live_loop", i_step_accepted=1, i_transition_mode=Mode.LOOP, i_loop_count=2)
                if action == "stop":
                    await self.cycle("stop_live_loop", i_stop_request=1, i_safe_point=1)
                elif action == "end":
                    await self.cycle("end_live_loop", i_step_accepted=1, i_transition_mode=Mode.END)
                else:
                    await self.cycle("suspend_live_loop", i_suspend_request=1)
                    await self.cycle("live_loop_draining")
                    await self.cycle("live_loop_safe", i_safe_point=1)
                    await self.cycle("resume_live_loop", i_resume_request=1)
                    await self.cycle("finish_resumed_loop", i_step_accepted=1, i_transition_mode=Mode.LOOP,
                                     i_loop_count="z" * config.count_width, violation="fallthrough_address" if config.depth == 1 else None)
            if config.depth > 1:
                await self.navigate(State.ACTIVE)
                await self.cycle("loop_to_body", i_step_accepted=1, i_transition_mode=Mode.LOOP, i_loop_count=2, i_transition_target=1)
                await self.cycle("loop_body", i_step_accepted=1, i_transition_mode=Mode.JUMP, i_transition_target=0)
                await self.cycle("loop_back", i_step_accepted=1, i_transition_mode=Mode.LOOP, i_loop_count="x" * config.count_width)

    async def failures(self):
        config = self.config
        cases = [(State.ACTIVE, "active_invalid", {"i_active_context_valid": 0}),
                 (State.IDLE, "step_without_execution", {"i_step_accepted": 1})]
        cases += [(State.ACTIVE, "transition_mode", {"i_step_accepted": 1, "i_transition_mode": mode}) for mode in (5, 6, 7)]
        for field in ("i_rstb", *COMMANDS, "i_step_accepted"):
            for unknown in "xz":
                cases.append((State.IDLE, field, {field: unknown}))
        for unknown in "xz":
            cases += [(State.ACTIVE, "i_active_context_valid", {"i_active_context_valid": unknown}),
                      (State.START_WAIT, "i_candidate_context_valid", {"i_candidate_context_valid": unknown}),
                      (State.STOP_PENDING, "i_safe_point", {"i_safe_point": unknown}),
                      (State.ACTIVE, "transition_mode", {"i_step_accepted": 1, "i_transition_mode": unknown * 3})]
        if config.loop:
            for count in (0, "x" * config.count_width, "z" * config.count_width):
                cases.append((State.ACTIVE, "loop_count", {"i_step_accepted": 1, "i_transition_mode": Mode.LOOP, "i_loop_count": count}))
        invalid_addresses = list(range(config.depth, 1 << config.address_width))
        invalid_addresses += [state * config.address_width for state in "xz"]
        invalid_addresses += ["0" * bit + state + "0" * (config.address_width - bit - 1) for bit in range(config.address_width) for state in "xz"]
        for value in sorted(set(invalid_addresses), key=lambda address: (isinstance(address, str), str(address))):
            cases.append((State.IDLE, "i_start_context", {"i_start_enable": 1, "i_start_context": value}))
            cases.append((State.ACTIVE, "transition_target", {"i_step_accepted": 1, "i_transition_mode": Mode.JUMP, "i_transition_target": value}))
            if config.switch:
                cases.append((State.ACTIVE, "i_switch_context", {"i_switch_request": 1, "i_switch_context": value}))
            if config.loop and config.maximum_count > 1:
                cases.append((State.ACTIVE, "transition_target", {"i_step_accepted": 1, "i_transition_mode": Mode.LOOP, "i_loop_count": 2, "i_transition_target": value}))
        for first, second in combinations(COMMANDS, 2):
            cases.append((State.ACTIVE, "command_conflict", {first: 1, second: 1}))
        for command in ("i_stop_request", *( ("i_suspend_request",) if config.suspend else () ), *( ("i_switch_request",) if config.switch else () )):
            cases.append((State.ACTIVE, "step_without_execution", {command: 1, "i_step_accepted": 1}))
        for state, reason, inputs in cases:
            await self.navigate(state)
            await self.cycle("expected_error:" + reason, violation=reason, **inputs)
            await self.cycle("sticky_error", i_candidate_context_valid="x", i_active_context_valid="z")
            await self.cycle("clear_error", i_error_clear=1)
        await self.reset()
        await self.start_context(config.depth - 1)
        await self.cycle("increment_boundary", i_step_accepted=1, i_transition_mode=Mode.INCREMENT, violation="fallthrough_address")
        if config.suspend:
            await self.navigate(State.SUSPENDED)
            await self.cycle("invalid_resume", i_resume_request=1, i_active_context_valid=0, violation="resume_invalid")
        if config.loop and config.maximum_count > 1:
            if config.depth > 1:
                await self.navigate(State.ACTIVE)
                await self.cycle("nested_setup", i_step_accepted=1, i_transition_mode=Mode.LOOP, i_loop_count=2, i_transition_target=1)
                await self.cycle("nested_loop", i_step_accepted=1, i_transition_mode=Mode.LOOP, violation="nested_loop")
            if config.switch:
                await self.navigate(State.ACTIVE)
                await self.cycle("switch_live_setup", i_step_accepted=1, i_transition_mode=Mode.LOOP, i_loop_count=2)
                await self.cycle("switch_live_loop", i_switch_request=1, violation="command_state:i_switch_request")
        await self.navigate(State.ACTIVE)
        await self.cycle("first_error", i_active_context_valid=0, violation="active_invalid")
        await self.cycle("secondary_command_error", i_start_enable=1, violation="command_state:i_start_enable")
        await self.cycle("secondary_protocol_error", i_step_accepted="x", violation="i_step_accepted")
        await self.cycle("secondary_conflict_error", i_start_enable=1, i_stop_request=1, violation="command_conflict")
        await self.cycle("clear_first_error", i_error_clear=1)

    async def ignored(self):
        config = self.config
        await self.reset()
        await self.cycle("ignored:idle", i_active_context_valid="x", i_candidate_context_valid="z", i_safe_point="x",
                         i_start_context="x" * config.address_width, i_switch_context="z" * config.address_width,
                         i_transition_mode="xxx", i_transition_target="x" * config.address_width, i_loop_count="z" * config.count_width)
        await self.navigate(State.CONTEXT_WAIT)
        await self.cycle("ignored:wait", i_candidate_context_valid=0, i_active_context_valid="x", i_transition_mode="zzz",
                         i_transition_target="x" * config.address_width, i_loop_count="z" * config.count_width)
        await self.navigate(State.ACTIVE)
        await self.cycle("ignored:stalled_mode", i_transition_mode="xxx", i_transition_target="z" * config.address_width, i_loop_count="x" * config.count_width)
        await self.cycle("ignored:safe_point", i_safe_point="z")

    async def randomized(self):
        config, rng = self.config, random.Random(self.config.seed)
        await self.reset()
        for _ in range(config.random_cycles):
            state = self.state()
            ports = self.last.ports
            active, live, owner, remaining = (int(ports[name], 2) for name in ("o_active_context", "o_loop_active", "o_loop_owner", "o_loop_remaining"))
            commands = legal_commands(state, config)
            if live:
                commands.discard("i_switch_request")
            updates = {"i_candidate_context_valid": rng.randrange(2)}
            violation = None
            if rng.random() < 0.04:
                command = rng.choice(sorted(set(COMMANDS) - commands))
                updates[command] = 1
                violation = "command_state:" + command
            elif commands and (state in (State.IDLE, State.COMPLETED, State.ERROR, State.SUSPENDED) or rng.random() < 0.2):
                command = rng.choice(sorted(commands))
                updates.update({command: 1, "i_start_context": rng.randrange(config.depth), "i_switch_context": rng.randrange(config.depth), "i_safe_point": rng.randrange(2)})
            elif state == State.ACTIVE:
                modes = [Mode.HOLD, Mode.JUMP, Mode.END]
                if active + 1 < config.depth: modes.append(Mode.INCREMENT)
                if config.loop and (not live or owner == active) and (active + 1 < config.depth or config.maximum_count > 1 and not (live and remaining == 1)):
                    modes.append(Mode.LOOP)
                mode = rng.choice(modes)
                count = rng.randint(1 if active + 1 < config.depth else 2, config.maximum_count) if mode == Mode.LOOP and not live else 1
                updates.update(i_step_accepted=int(rng.random() < 0.7), i_transition_mode=mode,
                               i_transition_target=rng.randrange(config.depth), i_loop_count=count)
            else:
                updates["i_safe_point"] = rng.randrange(2)
            await self.cycle("random", random=True, violation=violation, **updates)

    async def probe(self):
        config = self.config
        name, value = config.probe.split(":", 1)
        await self.navigate(State.ACTIVE if name in ("active_invalid", "active_valid", "active_start", "disabled_suspend", "disabled_switch", "transition_mode", "transition_target", "loop_count", "quiescing_step", "switch_address", "nested_loop", "live_switch") else State.STOP_PENDING if name == "i_safe_point" else State.START_WAIT if name == "candidate_valid" else State.SUSPENDED if name == "resume_invalid" else State.IDLE)
        updates = {}
        if name in ("transition_mode", "transition_target", "loop_count"):
            updates.update(i_step_accepted=1, i_transition_mode=Mode.LOOP if name == "loop_count" else Mode.JUMP if name == "transition_target" else value * 3 if value in "xz" else int(value))
            if name != "transition_mode": updates["i_" + name] = value * (config.count_width if name == "loop_count" else config.address_width) if value in "xz" else int(value)
        elif name == "start_address": updates.update(i_start_enable=1, i_start_context=value * config.address_width if value in "xz" else int(value))
        elif name == "switch_address": updates.update(i_switch_request=1, i_switch_context=value * config.address_width if value in "xz" else int(value))
        elif name == "active_invalid": updates["i_active_context_valid"] = 0
        elif name == "active_valid": updates["i_active_context_valid"] = value
        elif name == "active_start": updates["i_start_enable"] = 1
        elif name == "disabled_suspend": updates["i_suspend_request"] = 1
        elif name == "disabled_switch": updates["i_switch_request"] = 1
        elif name == "candidate_valid": updates["i_candidate_context_valid"] = value
        elif name == "resume_invalid": updates.update(i_resume_request=1, i_active_context_valid=0)
        elif name == "quiescing_step": updates.update(i_stop_request=1, i_step_accepted=1)
        elif name == "command_conflict": updates.update(i_start_enable=1, i_stop_request=1)
        elif name in ("nested_loop", "live_switch"):
            await self.cycle("probe_loop_setup", i_step_accepted=1, i_transition_mode=Mode.LOOP, i_loop_count=2, i_transition_target=1 if name == "nested_loop" else 0)
            updates = dict(i_step_accepted=1, i_transition_mode=Mode.LOOP) if name == "nested_loop" else dict(i_switch_request=1)
        else: updates[name] = value if value in "xz" else int(value)
        await self.cycle("untagged_assertion_probe", **updates)
        assert False, "Assertion probe was not detected"

    async def body(self):
        if self.config.probe:
            await self.probe()
            return
        await self.state_graph()
        await self.scheduled()
        await self.loops()
        await self.failures()
        await self.ignored()
        await self.randomized()
