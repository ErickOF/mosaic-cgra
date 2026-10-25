"""Profile-aware numerical, mask, legality, extension and pipeline coverage goals."""

from collections import Counter
from itertools import product

from mosaic_uvm.components import CoverageCollector

from vector_reduction.model import known


class ReductionCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.labels = Counter()
        self.observations = Counter()
        self.op_modes_counts = set()
        self.empty_operations = set()
        self.formats = set()
        self.extensions = set()
        self.causes = set()
        self.masks = set()
        self.winners = set()
        self.duplicate_extrema = set()
        self.sum_signs = set()
        self.sum_mix = set()
        self.pairs = set()
        self.reset_occupancies = set()
        self.reset_families = set()
        self.stalls = set()
        self.banks = set()
        self.frozen_banks = set()
        self.valid_states = set()
        self.previous = None
        self.fill_family = None
        self.stall_run = 0
        self.random_transactions = self.exhaustive = 0
        self.storage_checks = self.isolation_checks = 0
        self.accounting = {}

    def record(self, event, item):
        c, p, kind = self.config, item.ports, event["kind"]
        self.events[kind] += 1
        self.labels[item.get_name()] += 1
        self.random_transactions += item.random
        self.exhaustive += item.get_name() == "exhaustive"
        self.stall_run = self.stall_run + 1 if kind == "stall" else 0
        if kind == "stall":
            self.stalls.add((event["occupancy"], self.stall_run))
        if item.get_name() == "fill_before_reset":
            self.fill_family = int(p["i_opcode"], 2)
        if kind == "reset":
            self.reset_occupancies.add(event["occupancy"])
            if self.fill_family is not None:
                self.reset_families.add(self.fill_family)
        if kind in ("reset", "bubble"):
            self.previous = None
        if kind not in ("legal", "illegal"):
            return
        if known(p["i_opcode"]):
            op = int(p["i_opcode"], 2)
            if self.previous is not None:
                self.pairs.add((self.previous, op))
            self.previous = op
            if known(p["i_signed"]) and known(p["i_element_mask"]):
                mask = int(p["i_element_mask"], 2)
                self.masks.add(mask)
                self.op_modes_counts.add((op, int(p["i_signed"]), mask.bit_count()))
                if mask == 0:
                    self.empty_operations.add((op, int(p["i_signed"]), kind))
        if kind == "illegal":
            self.causes.add(event["cause"])
            return
        r, op, signed = event["response"], event["opcode"], event["signed"]
        fmt = int(r["o_result_format"], 2)
        self.formats.add((fmt, signed))
        width = c.sum_width if op == 0 else c.element
        extension = (
            "none"
            if c.accumulator == width
            else "sign"
            if signed and event["value"] < 0
            else "zero"
        )
        self.extensions.add((fmt, extension))
        if op in (1, 2):
            self.winners.add((op, signed, event["value"] % (1 << c.element)))
            if event["values"].count(event["value"]) > 1:
                self.duplicate_extrema.add((op, signed))
        if op == 0 and signed:
            value, selected = event["value"], event["values"]
            self.sum_signs.add((value > 0) - (value < 0))
            negative, positive = any(v < 0 for v in selected), any(v > 0 for v in selected)
            self.sum_mix.add(
                "mixed"
                if negative and positive
                else "negative"
                if negative
                else "positive"
                if positive
                else "zero"
            )

    def report(self):
        c = self.config
        causes = {"opcode", "mask", "signed", "reserved"}
        if len(c.enabled_opcodes) < 5:
            causes.add("feature_disabled")
        if c.minmax:
            causes.add("empty_extrema")
        formats = {(3 if op == 0 else 1, s) for op in c.enabled_opcodes for s in range(2)}
        extensions = set()
        for fmt in {f for f, _ in formats}:
            width = c.sum_width if fmt == 3 else c.element
            extensions |= (
                {(fmt, "none")} if c.accumulator == width else {(fmt, "sign"), (fmt, "zero")}
            )
        boundaries = {0, 1, c.mask, 1 << (c.element - 1), (1 << (c.element - 1)) - 1}
        empty = {
            (op, signed, "legal" if op in c.enabled_opcodes and op not in (1, 2) else "illegal")
            for op, signed in product(range(8), range(2))
        }
        expected_exhaustive = (
            16 * (1 << (c.element * c.count + c.count))
            if c.element * c.count <= 6 and c.count <= 3
            else 0
        )
        sum_mix = {"negative", "zero"} | ({"positive"} if c.element > 1 else set())
        if c.element > 1 and c.count > 1:
            sum_mix.add("mixed")
        goals = {
            "opcode_signedness_population": set(product(range(8), range(2), range(c.count + 1)))
            <= self.op_modes_counts,
            "every_element_selected_and_masked": all(
                any(mask & (1 << k) for mask in self.masks)
                and any(not mask & (1 << k) for mask in self.masks)
                for k in range(c.count)
            ),
            "empty_mask_opcode_legality": empty <= self.empty_operations,
            "every_result_format_and_mode": formats <= self.formats,
            "exact_extension_categories": extensions <= self.extensions,
            "every_illegal_cause": causes <= self.causes,
            "extrema_boundaries": not c.minmax
            or set(product((1, 2), range(2), boundaries)) <= self.winners,
            "duplicate_extrema": not c.minmax
            or c.count == 1
            or set(product((1, 2), range(2))) <= self.duplicate_extrema,
            "signed_sum_sign_and_mix": not c.sum
            or sum_mix <= self.sum_mix
            and {-1, 0, *([1] if c.element > 1 else [])} <= self.sum_signs,
            "every_opcode_pair": set(product(range(8), repeat=2)) <= self.pairs,
            "exhaustive_small_vectors": self.exhaustive == expected_exhaustive,
            "ignored_and_masked_unknowns": self.labels["ignored_unknowns"] >= 18
            and self.labels["masked_unknowns"] == 10 * c.count,
            "configured_random_campaign": self.random_transactions == c.random_cycles,
            "complete_observation_windows": self.observations["pre"]
            == self.observations["post"]
            == self.observations["held"]
            > 0,
            "real_pre_nba_edges": self.observations["edge"] > 0,
            "operand_isolation": not c.check_internals or self.isolation_checks > 0,
            "response_conservation": bool(self.accounting)
            and self.accounting["accepted"]
            == self.accounting["emitted"] + self.accounting["reset_discarded"],
        }
        if c.latency:
            goals.update(
                reset_every_occupancy=set(range(c.latency + 1)) <= self.reset_occupancies,
                reset_every_operation=set(range(5)) <= self.reset_families,
                occupancy_stall_duration=set(product({0, 1, c.latency}, (1, 3, 32))) <= self.stalls,
                every_dff_capture_hold=not c.check_internals
                or bool(self.banks)
                and self.banks <= self.frozen_banks,
                every_stage_valid_bubble=not c.check_internals
                or set(product(range(c.latency), ("0", "1"))) <= self.valid_states,
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
            "result_formats": sorted(self.formats),
            "extensions": sorted(self.extensions),
            "opcode_pairs": len(self.pairs),
            "reset_occupancies": sorted(self.reset_occupancies),
            "reset_operations": sorted(self.reset_families),
            "exhaustive_vectors": self.exhaustive,
            "expected_exhaustive": expected_exhaustive,
            "response_accounting": self.accounting,
            "dff_banks": len(self.banks),
            "dff_checks": self.storage_checks,
            "isolation_checks": self.isolation_checks,
            "native_hdl_assertions": "PASS" if c.hdl_assertions else "NOT_RUN",
            "waivers": {
                "full_enumeration": "Exhaustive when E*N <= 6 and N <= 3",
                "signed_positive": "Impossible for signed one-bit elements"
                if c.element == 1
                else "Reachable",
                "duplicate_extrema": "Needs at least two selected elements"
                if c.count == 1
                else "Reachable",
            },
        }
