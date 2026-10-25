"""Mandatory opcode, predication, format, status, timing and conservation goals."""

from collections import Counter
from itertools import product

from mosaic_uvm.components import CoverageCollector

from vector_lane.model import known


class LaneCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.labels = Counter()
        self.observations = Counter()
        self.op_modes = set()
        self.predication = set()
        self.op_formats = set()
        self.comparisons = set()
        self.selects = set()
        self.causes = set()
        self.suppression = set()
        self.status = set()
        self.pairs = set()
        self.reset_occupancies = set()
        self.stalls = set()
        self.banks = set()
        self.frozen_banks = set()
        self.formats = set()
        self.previous = None
        self.stall_run = 0
        self.random_transactions = self.exhaustive = 0
        self.storage_checks = self.isolation_checks = 0
        self.accounting = {}

    def record(self, event, item):
        kind, p = event["kind"], item.ports
        self.events[kind] += 1
        self.labels[item.get_name()] += 1
        self.random_transactions += item.random
        self.exhaustive += item.get_name() == "exhaustive"
        self.stall_run = self.stall_run + 1 if kind == "stall" else 0
        if kind == "stall":
            self.stalls.add((event["occupancy"], self.stall_run))
        if kind == "reset":
            self.reset_occupancies.add(event["occupancy"])
        if kind in ("reset", "bubble"):
            self.previous = None
        if kind not in ("legal", "illegal", "suppressed"):
            return
        if known(p["i_opcode"]):
            op = int(p["i_opcode"], 2)
            if self.previous is not None:
                self.pairs.add((self.previous, op))
            self.previous = op
            keys = ("i_lane_enable", "i_predicate_enable", "i_execute_predicate")
            if all(known(p[k]) for k in keys):
                self.predication.add((op, *(int(p[k]) for k in keys)))
            if (
                p["i_lane_enable"] == "1"
                and p["i_predicate_enable"] == "0"
                and known(p["i_signed"])
                and known(p["i_saturate"])
            ):
                self.op_modes.add((op, int(p["i_signed"]), int(p["i_saturate"])))
        if kind == "suppressed":
            self.suppression.add((event["cause"], event["response"]["o_write_enable"]))
        if kind == "illegal":
            self.causes.add(event["cause"])
        if kind != "legal":
            return
        r, op = event["response"], event["opcode"]
        fmt = int(r["o_result_format"], 2)
        self.formats.add(fmt)
        self.op_formats.add((op, fmt))
        self.status.update(
            k
            for k in ("o_carry", "o_borrow", "o_overflow", "o_saturated", "o_zero", "o_negative")
            if r[k] == "1"
        )
        if 9 <= op <= 14:
            self.comparisons.add((op, int(r["o_predicate"])))
        if op == 15:
            self.selects.add((int(p["i_select_predicate"]), event["a"] == event["b"]))

    def report(self):
        c = self.config
        legal = set(range(20)) - ({18, 19} if not c.minmax else set())
        legal |= {20} if c.mul else set()
        legal |= {21} if c.mac else set()
        formats = {(op, 0 if 9 <= op <= 14 else 1 if op < 20 else op - 18) for op in legal}
        causes = {
            "lane_enable",
            "predicate_enable",
            "execute_predicate",
            "opcode",
            "signed",
            "saturate",
            "reserved",
            "select_predicate",
            "unsupported_saturation",
        }
        causes |= {name + "_disabled" for name in ("mul", "mac", "minmax") if not getattr(c, name)}
        status = {"o_carry", "o_borrow", "o_overflow", "o_zero", "o_negative"}
        if c.saturation:
            status.add("o_saturated")
        goals = {
            "opcode_signedness_saturation": set(product(range(32), range(2), range(2)))
            <= self.op_modes,
            "opcode_mask_predication": set(product(range(32), range(2), range(2), range(2)))
            <= self.predication,
            "opcode_result_format": formats <= self.op_formats,
            "comparison_predicate": set(product(range(9, 15), range(2))) <= self.comparisons,
            "select_predicate_equality": set(product(range(2), (False, True))) <= self.selects,
            "suppression_never_writes": {("mask", "0"), ("predicate", "0")} <= self.suppression,
            "every_illegal_cause": causes <= self.causes,
            "every_applicable_status": status <= self.status,
            "mixed_opcode_pairs": set(product(range(32), repeat=2)) <= self.pairs,
            "configured_random_campaign": self.random_transactions == c.random_cycles,
            "exact_response_conservation": bool(self.accounting)
            and self.accounting["accepted"]
            == self.accounting["emitted"] + self.accounting["reset_discarded"],
            "complete_observation_windows": self.observations["pre"]
            == self.observations["post"]
            == self.observations["held"]
            > 0,
            "real_pre_nba_edges": self.observations["edge"] > 0,
            "isolated_functional_units": not c.check_internals or self.isolation_checks > 0,
            "exhaustive_small_operands": c.element > 2
            or self.exhaustive == 22 * 4 * (1 << (2 * c.element)),
            "ignored_fields_xz": self.labels["ignored_unknowns"] >= 12,
        }
        if c.latency:
            goals.update(
                reset_every_occupancy=set(range(c.latency + 1)) <= self.reset_occupancies,
                occupancy_stall_duration=set(product({0, 1, c.latency}, (1, 3, 32))) <= self.stalls,
                every_dff_checked=not c.check_internals or bool(self.banks),
                every_dff_held=not c.check_internals or self.banks <= self.frozen_banks,
                clockless_reset=self.labels["clockless_reset"] > 0,
            )
        else:
            goals["ignored_clock_reset_enable"] = self.labels["ignored_clock_controls"] >= 6
        return {
            "status": "PASS" if all(goals.values()) else "FAIL",
            "parameters": c.parameters,
            "seed": c.seed,
            "random_transactions": self.random_transactions,
            "goals": goals,
            "events": dict(self.events),
            "observations": dict(self.observations),
            "illegal_causes": sorted(self.causes),
            "formats": sorted(self.formats),
            "status_observed": sorted(self.status),
            "opcode_pairs": len(self.pairs),
            "reset_occupancies": sorted(self.reset_occupancies),
            "occupancy_stall_duration": sorted(self.stalls),
            "dff_banks": len(self.banks),
            "dff_checks": self.storage_checks,
            "isolation_checks": self.isolation_checks,
            "response_accounting": self.accounting,
            "native_hdl_assertions": "PASS" if c.hdl_assertions else "NOT_RUN",
            "waivers": {
                "full_operand_enumeration": "Only ELEMENT_WIDTH <= 2 is exhaustive",
                "saturation": "Disabled saturation has no saturated response"
                if not c.saturation
                else "Enabled",
                "physical_checks": "NOT_RUN: technology/server tools required",
            },
        }
