"""Checked command, address, lane, validity, alias and temporal coverage."""

from collections import Counter
from math import prod

from mosaic_uvm.components import CoverageCollector


class PredicateCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.observations = Counter()
        self.crosses = set()
        self.causes = Counter()
        self.addresses = set()
        self.aliases = set()
        self.address_use = set()
        self.source_validity = set()
        self.invalidate_prior = set()
        self.responses = set()
        self.atomic_causes = set()
        self.lanes = set()
        self.transitions = set()
        self.summaries = set()
        self.resets = set()
        self.stalls = set()
        self.context = set()
        self.exhaustive_commands = 0
        self.random_transactions = 0
        self.accepted = 0
        self.storage_checks = self.state_checks = self.isolation_checks = 0
        self.previous = None

    def record(self, event, item, out):
        c, kind = self.config, event["kind"]
        label = item.get_name().split(":", 1)[1]
        self.random_transactions += item.random
        self.exhaustive_commands += item.exhaustive
        if kind == "reset":
            n = event["population"]
            self.resets.add(
                "empty" if n == 0 else "full" if n == c.depth * c.lanes else "partial"
            )
        if kind == "stall" and label.startswith("stall_"):
            self.stalls.add(int(label.removeprefix("stall_")))
        if label.startswith("context_"):
            self.context.add(label)
        if "opcode" not in event:
            return
        op, mask, write = (event[key] for key in ("opcode", "mask", "write"))
        if op is not None and mask is not None and write is not None:
            self.crosses.add((op, mask.bit_count(), write))
        self.causes[event["cause"]] += 1
        self.source_validity.update(event["source_validity"])
        if kind == "illegal":
            self.atomic_causes.add(event["cause"])
        if kind in ("result", "invalidate"):
            self.responses.add((kind, write, bool(mask)))
        addresses = event["addresses"]
        for port, address in enumerate(addresses):
            address_class = (
                "unknown"
                if address is None
                else "unused"
                if address >= c.depth
                else "valid"
            )
            required = (
                bool(mask)
                and op is not None
                and (
                    3 <= op <= 7
                    if port == 0
                    else 5 <= op <= 7
                    if port == 1
                    else bool(write) and op <= 8
                )
            )
            self.address_use.add((port, required, address_class))
            if address is not None:
                self.addresses.add((port, address))
        if all(a is not None and a < c.depth for a in addresses):
            a, b, dest = addresses
            self.aliases.add((a == b, dest == a, dest == b))
        if self.previous is not None:
            self.transitions.add((self.previous, op))
        self.previous = op
        if kind in ("result", "invalidate"):
            for k in range(c.lanes):
                if not any(lane == k for _, lane, _, _ in event["updates"]):
                    self.lanes.add(("hold", k))
            for k in event["selected"]:
                self.lanes.add(("read" if op in range(3, 8) else "generate", k))
            for dest, k, valid, _ in event["updates"]:
                before = event["before_valid"][dest][k]
                if not valid:
                    self.invalidate_prior.add(bool(before))
                self.lanes.add(("write" if valid else "invalidate", k))
                self.lanes.add(
                    (
                        "invalid_to_valid"
                        if valid and not before
                        else "valid_to_invalid"
                        if before and not valid
                        else "hold_validity",
                        k,
                    )
                )
            if kind == "result":
                self.summaries.add(
                    (int(out["o_any"]), int(out["o_all"]), mask.bit_count())
                )

    def report(self):
        c = self.config
        expected_crosses = {
            (op, n, w) for op in range(16) for n in range(c.lanes + 1) for w in range(2)
        }
        expected_addresses = {
            (port, a) for port in range(3) for a in range(1 << c.address_width)
        }
        expected_causes = {
            "none",
            "controls",
            "opcode",
            "invalidate_write",
            "source_a_address",
            "source_b_address",
            "destination_address",
            "source_a_valid",
            "source_b_valid",
        }
        if c.depth == 1:
            expected_causes.remove("source_b_valid")
        expected_lanes = {
            (activity, k)
            for activity in (
                "read",
                "hold",
                "write",
                "invalidate",
                "invalid_to_valid",
                "valid_to_invalid",
            )
            for k in range(c.lanes)
        }
        expected_exhaustive = (
            prod(
                (
                    3 ** (c.depth * c.lanes),
                    16,
                    c.mask + 1,
                    (1 << c.address_width) ** 3,
                    c.mask + 1,
                    2,
                )
            )
            if c.depth * c.lanes <= 2
            else 0
        )
        expected_address_use = {
            (port, needed, kind)
            for port in range(3)
            for needed in (False, True)
            for kind in (
                ("valid", "unknown", "unused")
                if c.depth < 1 << c.address_width
                else ("valid", "unknown")
            )
        }
        expected_summaries = {(0, 0, 0)} | {
            (a, a, n) for n in range(1, c.lanes + 1) for a in range(2)
        }
        expected_summaries |= {(1, 0, n) for n in range(2, c.lanes + 1)}
        goals = {
            "opcode_population_write": expected_crosses <= self.crosses,
            "all_address_encodings_each_port": expected_addresses <= self.addresses,
            "every_illegal_cause": expected_causes <= self.causes.keys(),
            "atomic_no_update_by_illegal_cause": expected_causes - {"none"}
            <= self.atomic_causes,
            "address_class_required_ignored": expected_address_use <= self.address_use,
            "source_validity_by_port": {(p, v) for p in range(2) for v in (False, True)}
            <= self.source_validity,
            "invalidate_valid_and_invalid": {False, True} <= self.invalidate_prior,
            "compute_writeback_invalidate_empty_nonempty": {
                (kind, write, nonempty)
                for kind, write in (("result", 0), ("result", 1), ("invalidate", 1))
                for nonempty in (False, True)
            }
            <= self.responses,
            "dependent_opcode_pairs": {(a, b) for a in range(9) for b in range(9)}
            <= self.transitions,
            "summary_by_population": expected_summaries <= self.summaries,
            "lane_reads_writes_invalidation_transitions": expected_lanes <= self.lanes,
            "source_destination_alias_classes": len(self.aliases)
            == (1 if c.depth == 1 else 4 if c.depth == 2 else 5),
            "empty_and_partial_and_full_reset": {"empty", "full"} <= self.resets
            and (c.depth * c.lanes == 1 or "partial" in self.resets),
            "stall_durations": {1, 2, 5} <= self.stalls,
            "context_preservation_and_stale_rejection": {
                "context_preserve",
                "context_invalidate",
                "context_stale_read",
            }
            <= self.context,
            "empty_summary": (0, 0, 0) in self.summaries,
            "true_and_false_summary": (1, 1, c.lanes) in self.summaries
            and (0, 0, c.lanes) in self.summaries,
            "exhaustive_small_bank": self.exhaustive_commands == expected_exhaustive,
            "random_stream": self.random_transactions == c.random_cycles,
            "sample_stages": all(
                self.observations[s] for s in ("pre", "edge", "post", "held")
            ),
            "state_and_gating_checks": not c.check_internals
            or min(self.storage_checks, self.state_checks, self.isolation_checks) > 0,
        }
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": c.parameters,
            "seed": c.seed,
            "goals": goals,
            "random_transactions": self.random_transactions,
            "exhaustive_commands": self.exhaustive_commands,
            "accepted_commands": self.accepted,
            "native_hdl_assertions": "PASS" if c.hdl_assertions else "NOT_RUN",
            "opcode_population_write_bins": len(self.crosses),
            "address_bins": sorted(self.addresses),
            "illegal_causes": dict(self.causes),
            "alias_classes": sorted(self.aliases),
            "address_use_bins": sorted(self.address_use),
            "source_validity_bins": sorted(self.source_validity),
            "invalidation_prior_validity": sorted(self.invalidate_prior),
            "compute_writeback_response_bins": sorted(self.responses),
            "atomic_illegal_causes": sorted(self.atomic_causes),
            "lane_bins": sorted(self.lanes),
            "summary_bins": sorted(self.summaries),
            "reset_classes": sorted(self.resets),
            "stall_durations": sorted(self.stalls),
            "previous_next_opcode_bins": len(self.transitions),
            "storage_checks": self.storage_checks,
            "state_checks": self.state_checks,
            "isolation_checks": self.isolation_checks,
            "observations": dict(self.observations),
            "waivers": (
                ["Depth one cannot isolate invalid B from valid A."]
                if c.depth == 1
                else []
            )
            + (
                ["Power-of-two depths above one have no unused address encoding."]
                if c.depth > 1 and c.depth == 1 << c.address_width
                else []
            )
            + (
                ["A one-bit bank has no partial-valid reset population."]
                if c.depth * c.lanes == 1
                else []
            ),
        }
