"""Connectivity-aware mandatory bins collected after functional checks."""

from collections import Counter
from itertools import combinations, product

from mosaic_uvm.components import CoverageCollector
from mosaic_uvm.patterns import pattern_classes


class BypassNetworkCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.checks = self.pre_checks = self.held_checks = self.random_checks = 0
        self.transitions, self.violations, self.actions = Counter(), Counter(), Counter()
        self.edges, self.disconnected, self.out_of_range, self.unknown_selects = set(), set(), set(), set()
        self.control_cross, self.patterns, self.data_bits = set(), set(), set()
        self.fanouts, self.distinct, self.pairs, self.enables = set(), set(), set(), set()
        self.unselected, self.invalid_payloads, self.hold_lengths = set(), set(), set()
        self.priorities, self.contexts, self.ignored = set(), set(), set()
        self.small_words = set()

    def sample(self, observation, routes, rising, valid_state):
        config, item, ports = self.config, observation.item, observation.ports
        if observation.stage == "pre":
            self.pre_checks += 1
            return
        if observation.stage == "held":
            self.held_checks += 1
            self.hold_lengths.add("long" if item.hold_ps >= 1000 else "short")
            return
        self.checks += 1
        self.random_checks += item.random
        active = []
        for route in routes:
            destination = route.destination
            self.enables.add((destination, route.enabled))
            if route.kind == "legal" and route.source_valid in ("0", "1"):
                self.control_cross.add((destination, route.source, route.enabled, route.capture, route.source_valid))
            if not route.consumed or config.registered and not rising:
                continue
            if route.kind == "legal":
                self.edges.add((destination, route.source))
                active.append(route)
                if route.source_valid == "1":
                    self.patterns.update((destination, route.source, name) for name in pattern_classes(route.data))
                    self.data_bits.update((destination, route.source, bit, value) for bit, value in enumerate(reversed(route.data)))
                    if config.width <= 2:
                        self.small_words.add((destination, route.source, route.data))
                elif set(route.data) in ({"x"}, {"z"}):
                    self.invalid_payloads.add((destination, route.source, route.data[0]))
            elif route.kind == "disconnected":
                self.disconnected.add((destination, route.source))
            elif route.kind == "out_of_range":
                self.out_of_range.add((destination, route.source))
            else:
                self.unknown_selects.add((destination, route.select))
        for source in {route.source for route in active}:
            selected = [route for route in active if route.source == source]
            self.fanouts.add((len(selected), selected[0].source_valid))
        if active:
            self.distinct.add(len({route.source for route in active}))
        self.pairs.update((first.destination, first.source, second.destination, second.source)
                          for first, second in combinations(active, 2))
        label = item.get_name()
        if label.startswith("unselected:"):
            _, destination, source, other, value = label.split(":")[:5]
            self.unselected.add((int(destination), int(source), int(other), value))
        if label.startswith("ignored:"):
            self.ignored.add(label.removeprefix("ignored:"))
        if config.registered:
            if rising:
                if routes[0].enabled == "1" and routes[0].capture in ("0", "1"):
                    self.priorities.add((ports["i_rstb"], ports["i_flush"], routes[0].capture))
                if ports["i_rstb"] == "0":
                    self.actions["reset"] += 1
                elif ports["i_flush"] == "1":
                    self.actions["flush"] += 1
                else:
                    self.actions["capture"] += sum(route.consumed for route in routes)
                    self.actions["hold"] += sum(not route.consumed for route in routes)
            if label.startswith("context:") and rising:
                state = "valid" if set(valid_state) == {"1"} else "invalid" if set(valid_state) == {"0"} else "mixed"
                assert label.split(":")[1] == state, "Context-flush state did not match coverage label"
                self.contexts.add(state)

    def report(self):
        config = self.config
        illegal = set(product(range(config.destinations), range(config.sources, 1 << config.select_width)))
        controls = {(*edge, enabled, capture, valid) for edge in config.edges for enabled, capture, valid in product("01", repeat=3)}
        pairs = {(first, source1, second, source2) for first, second in combinations(range(config.destinations), 2)
                 for source1 in config.connected(first) for source2 in config.connected(second)}
        unselected = {(destination, source, other, value) for destination, source in config.edges
                      for other in range(config.sources) if other != source for value in "01xz"}
        classes = {"zero", "one", "walking_one", "walking_zero", "alternating"}
        goals = dict(
            every_connected_edge_selected=self.edges == config.edges,
            every_disconnected_edge_rejected=self.disconnected == config.disconnected,
            every_out_of_range_encoding_rejected=self.out_of_range == illegal,
            every_unknown_consumed_selection=self.unknown_selects == set(product(range(config.destinations), config.unknown_selects)),
            every_destination_enable=self.enables == set(product(range(config.destinations), "01")),
            edge_enable_capture_valid_cross=controls <= self.control_cross,
            every_legal_destination_selection_pair=pairs <= self.pairs,
            reachable_fanout_population_by_valid=set(product(range(1, config.maximum_fanout + 1), "01")) <= self.fanouts,
            reachable_distinct_source_populations=set(range(1, len(config.distinct_assignment()) + 1)) <= self.distinct,
            data_pattern_class_by_connected_edge={(*edge, name) for edge in config.edges for name in classes} <= self.patterns,
            every_forwarded_data_bit_zero_and_one={(*edge, bit, value) for edge in config.edges for bit, value in product(range(config.width), "01")} <= self.data_bits,
            unselected_four_state_activity_ignored=unselected <= self.unselected,
            invalid_source_unknown_payloads_ignored={(*edge, value) for edge in config.edges for value in "xz"} <= self.invalid_payloads,
            short_and_long_stable_intervals=self.hold_lengths == {"short", "long"},
            every_item_checked_before_edge_and_after_hold=self.pre_checks == self.held_checks == self.checks,
            random_transactions=self.random_checks == config.random_cycles,
        )
        if config.registered:
            goals.update(
                reset_flush_capture_priority_cross=self.priorities == set(product("01", repeat=3)),
                registered_capture_hold_reset_flush=all(self.actions[action] > 0 for action in ("capture", "hold", "reset", "flush")),
                context_flush_valid_invalid_and_mixed=({"valid", "invalid", "mixed"} if config.destinations > 1 else {"valid", "invalid"}) <= self.contexts,
                unconsumed_unknown_select_and_capture_ignored={"held_select", "disabled_capture"} <= self.ignored,
            )
        else:
            goals["inactive_registered_controls_ignored"] = {"rstb", "flush", "capture"} <= self.ignored
        if config.width <= 2:
            goals["exhaustive_small_width_known_words"] = {(*edge, f"{value:0{config.width}b}") for edge in config.edges for value in range(1 << config.width)} <= self.small_words
        return dict(status="PASS" if all(goals.values()) else "FAIL", parameters=config.parameters, graph=config.graph,
                    seed=config.seed, checked_transactions=self.checks, pre_edge_checks=self.pre_checks, held_checks=self.held_checks,
                    random_transactions=self.random_checks, structural_assertions="PASS" if config.check_internals else "NOT_RUN",
                    goals=goals, bins=dict(connected_edges=sorted(self.edges), disconnected_edges=sorted(self.disconnected),
                    out_of_range_selections=sorted(self.out_of_range), unknown_selects=sorted(self.unknown_selects),
                    edge_enable_capture_valid=sorted(self.control_cross), destination_pairs=sorted(self.pairs),
                    fanout_valid=sorted(self.fanouts), distinct_source_populations=sorted(self.distinct), patterns=sorted(self.patterns),
                    unselected_activity=sorted(self.unselected), invalid_source_payloads=sorted(self.invalid_payloads),
                    hold_lengths=sorted(self.hold_lengths), reset_flush_capture=sorted(self.priorities), context_flushes=sorted(self.contexts),
                    ignored_controls=sorted(self.ignored), expected_protocol_assertions=dict(self.violations),
                    registered_actions=dict(self.actions), waveform_transitions=dict(self.transitions)),
                    waivers=dict(maximum_fanout=config.maximum_fanout, maximum_distinct_sources=len(config.distinct_assignment()),
                                 reason="Larger populations are unreachable in this connectivity graph."))
