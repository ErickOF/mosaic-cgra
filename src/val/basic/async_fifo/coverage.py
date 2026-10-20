"""Mandatory coverage collected only after functional assertions pass."""

from collections import Counter
from itertools import product

from mosaic_uvm.components import CoverageCollector


RELATIONS = ("write_faster", "read_faster", "equal_drift", "relatively_prime", "random_periods")


class AsyncFifoCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.checks = self.random_checks = self.simultaneous = 0
        self.transitions = Counter()
        self.boundaries, self.address_pairs, self.reset_states = set(), set(), set()
        self.addresses = {domain: set() for domain in "wr"}
        self.phases = {domain: set() for domain in "wr"}
        self.wraps = Counter()
        self.stalls = {domain: set() for domain in "wr"}
        self.thresholds = {domain: set() for domain in "wr"}
        self.stage_activity, self.injected = set(), set()
        self.payload_states = set()
        self.unknown_bits = set()
        self.stopped, self.init_orders, self.reset_skews = set(), set(), set()
        self.burst = Counter()
        self.longest = Counter()
        self.accounting = {}

    def sample(self, observation, model, push, pop, rises, old_counts, new_reset, was_occupancy, stalled_output):
        config, item, after = self.config, observation.item, observation.after
        self.checks += 1
        self.random_checks += item.random
        self.simultaneous += bool(push and pop)
        occupancy = len(model.records)
        boundary = "empty" if occupancy == 0 else "full" if occupancy == config.depth else "partial"
        if model.epoch and after.integer("o_w_init_done") and after.integer("o_r_init_done"):
            self.boundaries.add((item.relation, boundary))
            self.address_pairs.add((model.w.count % config.depth, model.r.count % config.depth))
        for domain, transfer, prior in zip("wr", (push, pop), old_counts):
            history = getattr(model, domain)
            if transfer:
                self.addresses[domain].add(prior % config.depth)
                self.wraps[domain] += history.count // config.depth > prior // config.depth
                peer = history.visible(config.stages)[0]
                self.phases[domain].add((history.count // config.depth % 2, peer // config.depth % 2))
            if rises[domain]:
                self.burst[domain] = self.burst[domain] + 1 if transfer else 0
                self.longest[domain] = max(self.longest[domain], self.burst[domain])
            initialized = after.integer(f"o_{domain}_init_done")
            flag = after.integer("o_w_almost_full" if domain == "w" else "o_r_almost_empty")
            if initialized:
                self.thresholds[domain].add(flag)
                stalled = (after.integer("i_w_valid") and not after.integer("o_w_ready")) if domain == "w" else (after.integer("o_r_valid") and not after.integer("i_r_ready"))
                if stalled:
                    self.stalls[domain].add(history.level)
        if push:
            data = observation.before.ports["i_w_data"]
            self.payload_states.update(set(data))
            self.unknown_bits.update(index for index, bit in enumerate(data) if bit in "xz")
        if new_reset:
            state = "empty" if was_occupancy == 0 else "full" if was_occupancy == config.depth else "partial"
            self.reset_states.add(state)
            if stalled_output:
                self.reset_states.add("stalled_valid")
        if item.get_name().startswith("stopped_"):
            self.stopped.add(item.get_name().split("_")[1])
        if item.get_name() in ("release_w", "release_r"):
            self.init_orders.add(item.get_name().split("_")[1])
        if item.get_name().startswith("reset_skew_"):
            self.reset_skews.add(item.get_name().removeprefix("reset_skew_"))
        if config.check_internals:
            for name, stages in after.chains.items():
                for index, value in enumerate(stages):
                    if set(value) <= {"0", "1"} and int(value, 2):
                        self.stage_activity.add((name, index))
        if item.fault:
            self.injected.add((item.fault[0], item.fault[2]))
        self.accounting = dict(pushed=model.pushed, popped=model.popped, canceled=model.canceled, pending=occupancy)

    def report(self):
        config = self.config
        goals = {
            "clock_relationship_empty_full_cross": set(product(RELATIONS, ("empty", "full"))) <= self.boundaries,
            "every_storage_write_and_read_address": all(self.addresses[domain] == set(range(config.depth)) for domain in "wr"),
            "every_write_address_by_every_read_address": self.address_pairs == set(product(range(config.depth), repeat=2)),
            "both_pointer_wrap_phases_with_remote_phase": all(self.phases[domain] == set(product((0, 1), repeat=2)) for domain in "wr"),
            "repeated_pointer_wrapping": all(self.wraps[domain] >= 8 for domain in "wr"),
            "simultaneous_push_and_pop": self.simultaneous > 0,
            "almost_threshold_entry_and_exit": all(self.thresholds[domain] == {0, 1} for domain in "wr"),
            "source_full_stall": config.depth in self.stalls["w"],
            "destination_stall_at_every_visible_level": set(range(1, config.depth + 1)) <= self.stalls["r"],
            "reset_empty_partial_full_and_stalled_output": {"empty", "partial", "full", "stalled_valid"} <= self.reset_states,
            "stop_and_restart_both_clocks": self.stopped == {"w", "r"},
            "initialization_with_either_domain_stopped": self.init_orders == {"w", "r"},
            "skewed_assert_release_and_unilateral_recovery": {"assert_w", "assert_r", "release_w", "release_r", "unexpected_w", "unexpected_r"} <= self.reset_skews,
            "full_rate_write_and_read_bursts": all(self.longest[domain] >= config.depth for domain in "wr"),
            "four_state_payload_and_every_unknown_bit": self.payload_states == set("01xz") and self.unknown_bits == set(range(config.width)),
            "seeded_random_clock_events": self.random_checks == config.random_cycles,
            "every_synchronizer_stage_active": not config.check_internals or self.stage_activity == set(product(CHAINS_FOR_COVERAGE, range(config.stages))),
            "first_stage_unknowns_do_not_feed_logic": not config.check_internals or self.injected == set(product(CHAINS_FOR_COVERAGE, "xz")),
            "all_records_consumed_or_canceled": bool(self.accounting) and self.accounting["pending"] == 0 and self.accounting["pushed"] == self.accounting["popped"] + self.accounting["canceled"],
        }
        return dict(status="PASS" if all(goals.values()) else "FAIL", parameters=config.parameters,
                    seed=config.seed, checked_transactions=self.checks, random_transactions=self.random_checks,
                    structural_assertions="PASS" if config.check_internals else "NOT_RUN", goals=goals,
                    records=self.accounting, bins=dict(clock_boundary=sorted(self.boundaries),
                    address_pairs=sorted(self.address_pairs), addresses={key: sorted(value) for key, value in self.addresses.items()},
                    wrap_remote_phases={key: sorted(value) for key, value in self.phases.items()}, pointer_wraps=dict(self.wraps),
                    stall_levels={key: sorted(value) for key, value in self.stalls.items()},
                    threshold_values={key: sorted(value) for key, value in self.thresholds.items()}, reset_states=sorted(self.reset_states),
                    reset_skews=sorted(self.reset_skews), stopped_clocks=sorted(self.stopped), initialization_orders=sorted(self.init_orders),
                    longest_bursts=dict(self.longest), simultaneous_transfers=self.simultaneous,
                    payload_states=sorted(self.payload_states), unknown_bit_positions=sorted(self.unknown_bits),
                    synchronizer_stages=sorted(self.stage_activity), first_stage_injections=sorted(self.injected),
                    waveform_transitions=dict(self.transitions)))


CHAINS_FOR_COVERAGE = ("r_gray_sync", "w_gray_sync", "r_up_sync", "w_up_sync")
