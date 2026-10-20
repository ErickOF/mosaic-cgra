"""Mandatory state graph, runtime, candidate, loop, error, and reset coverage."""

from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector
from context_sequencer.constants import COMMANDS, Error, Mode, State, legal_commands, reachable_states
from context_sequencer.model import integer


def legal_edges(config):
    """Required observable graph, including reset, waits, and legal runtime paths."""
    states = reachable_states(config)
    edges = {(state, state) for state in states} | {(state, State.IDLE) for state in states}
    edges |= {(state, State.ERROR) for state in states}
    edges |= {(state, target) for state in (State.IDLE, State.COMPLETED) for target in (State.START_WAIT, State.ACTIVE)}
    edges |= {(state, State.ACTIVE) for state in (State.START_WAIT, State.CONTEXT_WAIT)}
    edges |= {(State.ACTIVE, state) for state in (State.CONTEXT_WAIT, State.COMPLETED)}
    for state in states:
        if "i_stop_request" in legal_commands(state, config):
            edges.add((state, State.STOP_PENDING))
    if config.suspend:
        edges |= {(state, target) for state in (State.ACTIVE, State.CONTEXT_WAIT) for target in (State.SUSPEND_PENDING, State.SUSPENDED)}
        edges |= {(State.SUSPEND_PENDING, State.SUSPENDED), (State.SUSPENDED, State.ACTIVE), (State.SUSPENDED, State.CONTEXT_WAIT)}
    if config.switch:
        edges |= {(state, target) for state in (State.ACTIVE, State.CONTEXT_WAIT, *( (State.SUSPENDED,) if config.suspend else () ))
                  for target in (State.SWITCH_PENDING, State.SWITCH_WAIT, State.ACTIVE)}
        edges |= {(State.SWITCH_PENDING, State.SWITCH_WAIT), (State.SWITCH_PENDING, State.ACTIVE), (State.SWITCH_WAIT, State.ACTIVE)}
    return edges


def count_classes(count, maximum):
    result = set()
    if count == 1:
        result.add("one")
    if maximum >= 2 and count == 2:
        result.add("two")
    if maximum >= 3 and count == max(3, maximum // 2):
        result.add("middle")
    if count == maximum:
        result.add("maximum")
    return result


class SequencerCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.checks = self.pre_checks = self.held_checks = self.random_checks = 0
        self.states, self.exited, self.edges, self.commands, self.resets, self.clear_sources = set(), set(), set(), set(), set(), set()
        self.errors, self.error_sources, self.modes, self.addresses, self.events = set(), set(), set(), set(), set()
        self.candidates, self.relations, self.validities = set(), set(), set()
        self.stalls, self.loop_counts, self.loop_stalls, self.loop_outcomes, self.safe_latencies = set(), set(), set(), set(), set()
        self.ignored, self.labels = set(), set()
        self.waveforms, self.assertions = Counter(), Counter()
        self.stall_run = 0
        self.runtime = None
        self.scheduled_mode = None

    def sample(self, observation, before, model, rising, reset):
        state = before["state"]
        if reset:
            self.resets.add(state)
            self.edges.add((state, model.state))
            self.exited.add(state)
        self.states.update((state, model.state))
        if observation.stage == "pre":
            self.pre_checks += 1
            return
        if observation.stage == "held":
            self.held_checks += 1
            return
        self.checks += 1
        self.random_checks += observation.item.random
        ports, item = observation.ports, observation.item
        label = item.get_name()
        self.labels.add(label.split(":")[0])
        if label.startswith("ignored:"):
            self.ignored.add(label.split(":")[1])
        if not rising:
            return
        self.edges.add((state, model.state))
        if state != model.state:
            self.exited.add(state)
        if reset:
            self.runtime = self.scheduled_mode = None
            self.stall_run = 0
            return
        for name in COMMANDS:
            if ports[name] == "1":
                self.commands.add((state, name))
                if name == "i_error_clear":
                    self.clear_sources.add(state)
        self.errors.add(model.error)
        if model.state == State.ERROR and state != State.ERROR:
            self.error_sources.add((state, model.error))
        if model.activated:
            self.addresses.add(model.active)
            self.events.add("activation")
        if model.changed:
            self.events.add("change")
        if model.completed:
            self.events.add("completion")
        for enabled, name in ((before["reads"][0], "i_active_context_valid"),
                              (before["reads"][1] is not None, "i_candidate_context_valid")):
            if enabled:
                self.validities.add((state, name, ports[name]))
        mode = integer(ports["i_transition_mode"])
        if state == State.ACTIVE and ports["i_step_accepted"] == "1":
            if mode in set(Mode):
                self.modes.add(mode)
            if mode in (Mode.INCREMENT, Mode.JUMP, Mode.LOOP) and model.state != State.ERROR:
                timing = "immediate" if ports["i_candidate_context_valid"] == "1" else "delayed"
                self.candidates.add((mode, timing))
                self.scheduled_mode = mode if timing == "delayed" else None
                target = model.active if timing == "immediate" else model.pending
                self.relations.add((mode, "self" if target == before["active"] else "forward" if target > before["active"] else "backward"))
            if mode == Mode.LOOP and self.config.loop:
                count = before["total_visits"] if before["owner"] is not None else integer(ports["i_loop_count"])
                classes = count_classes(count, self.config.maximum_count)
                self.loop_counts |= classes
                self.loop_stalls.update((kind, min(self.stall_run, 5)) for kind in classes)
                if model.state != State.ERROR:
                    self.loop_outcomes.add("taken" if model.owner is not None else "fallthrough")
            self.stalls.add(min(self.stall_run, 32))
            self.stall_run = 0
        elif state == State.ACTIVE and all(ports[name] == "0" for name in COMMANDS):
            self.stall_run += 1
        else:
            self.stall_run = 0
        if state == State.CONTEXT_WAIT and model.activated and self.scheduled_mode is not None:
            self.candidates.add((self.scheduled_mode, "delayed"))
            self.scheduled_mode = None
        runtime = next((name for name in ("i_stop_request", "i_suspend_request", "i_switch_request") if ports[name] == "1"), None)
        if runtime and runtime in legal_commands(state, self.config) and model.state != State.ERROR:
            self.runtime = (runtime, 0)
        elif self.runtime and state in (State.STOP_PENDING, State.SUSPEND_PENDING, State.SWITCH_PENDING):
            self.runtime = (self.runtime[0], self.runtime[1] + 1)
        if self.runtime and ports["i_safe_point"] == "1" and model.state != State.ERROR:
            self.safe_latencies.add(self.runtime)
            self.runtime = None
        if model.state == State.ERROR:
            self.runtime = self.scheduled_mode = None

    def report(self):
        config = self.config
        states = reachable_states(config)
        errors = set(Error) - ({Error.LOOP} if not config.loop else set())
        modes_with_candidates = {Mode.JUMP} | ({Mode.INCREMENT} if config.depth > 1 else set())
        if config.loop and (config.depth > 1 or config.maximum_count > 1):
            modes_with_candidates.add(Mode.LOOP)
        relations = {(Mode.JUMP, "self")}
        if config.depth > 1:
            relations |= {(Mode.JUMP, "forward"), (Mode.JUMP, "backward"), (Mode.INCREMENT, "forward")}
        counts = {"one", "maximum"} | ({"two"} if config.maximum_count >= 2 else set()) | ({"middle"} if config.maximum_count >= 3 else set())
        runtime = {"i_stop_request"} | ({"i_suspend_request"} if config.suspend else set()) | ({"i_switch_request"} if config.switch else set())
        required_events = {"activation", "completion"} | ({"change"} if config.depth > 1 else set())
        validity_states = {(State.ACTIVE, "i_active_context_valid")}
        validity_states |= {(state, "i_candidate_context_valid") for state in
                            (State.IDLE, State.COMPLETED, State.ACTIVE, State.START_WAIT, State.CONTEXT_WAIT)}
        if config.suspend:
            validity_states.add((State.SUSPENDED, "i_active_context_valid"))
        if config.switch:
            validity_states |= {(state, "i_candidate_context_valid") for state in (State.SWITCH_PENDING, State.SWITCH_WAIT)}
            if config.suspend: validity_states.add((State.SUSPENDED, "i_candidate_context_valid"))
        goals = dict(
            reachable_states_entered=states <= self.states,
            reachable_states_exited=states <= self.exited,
            legal_state_graph=legal_edges(config) <= self.edges,
            commands_in_every_state=set(product(states, COMMANDS)) <= self.commands,
            reset_from_every_state=states <= self.resets,
            error_clear_from_every_state=states <= self.clear_sources,
            applicable_error_classes=errors <= self.errors,
            all_transition_modes=set(Mode) <= self.modes,
            every_address_activated=set(range(config.depth)) <= self.addresses,
            immediate_and_delayed_candidates=set(product(modes_with_candidates, ("immediate", "delayed"))) <= self.candidates,
            jump_and_increment_address_relations=relations <= self.relations,
            enabled_read_state_validity_cross={(state, name, valid) for state, name in validity_states for valid in "01"} <= self.validities,
            stall_lengths_zero_through_32=set(range(33)) <= self.stalls,
            loop_count_classes=not config.loop or counts <= self.loop_counts,
            loop_stall_cross=not config.loop or set(product(counts, (0, 1, 5))) <= self.loop_stalls,
            loop_taken_and_fallthrough=not config.loop or (({"taken"} if config.maximum_count > 1 else set()) | ({"fallthrough"} if config.depth > 1 else set())) <= self.loop_outcomes,
            runtime_safe_point_latencies=set(product(runtime, (0, 1, 5))) <= self.safe_latencies,
            activation_change_and_completion_events=required_events <= self.events,
            ignored_inactive_metadata={"idle", "wait", "stalled_mode", "safe_point"} <= self.ignored,
            pre_post_and_held_per_item=self.pre_checks == self.held_checks == self.checks,
            random_cycles=self.random_checks == config.random_cycles,
        )
        serialize = lambda values: sorted(tuple(int(value) if isinstance(value, (State, Error, Mode)) else value for value in row) if isinstance(row, tuple) else int(row) if isinstance(row, (State, Error, Mode)) else row for row in values)
        return dict(status="PASS" if all(goals.values()) else "FAIL", parameters=config.parameters, interface_version=1, seed=config.seed,
                    checked_transactions=self.checks, pre_edge_checks=self.pre_checks, held_checks=self.held_checks, random_transactions=self.random_checks,
                    structural_assertions="PASS" if config.check_internals else "NOT_RUN", goals=goals,
                    bins={name: serialize(getattr(self, name)) for name in ("states", "exited", "edges", "commands", "resets", "clear_sources", "errors", "error_sources", "modes", "addresses", "events", "candidates", "relations", "validities", "stalls", "loop_counts", "loop_stalls", "loop_outcomes", "safe_latencies", "ignored")},
                    expected_assertions=dict(self.assertions), waveform_transitions=dict(self.waveforms),
                    missing_edges=serialize(legal_edges(config) - self.edges),
                    waivers=dict(disabled_suspend=not config.suspend, disabled_switch=not config.switch, disabled_loop=not config.loop,
                                 depth_one_forward_backward=config.depth == 1, depth_one_loop_fallthrough=config.depth == 1,
                                 one_bit_count_multiple_visits=config.maximum_count == 1, physical_safe_point="NOT_RUN"))
