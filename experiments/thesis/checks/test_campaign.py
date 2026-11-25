"""Independent checks of experiment contracts, extraction and exclusion rules."""

from copy import deepcopy
import csv
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cases import architecture, campaign, digest, reference, scenarios, workload
from results import collect, energy, relative, select_composition
from packets import validate as validate_packets
from schedule import domains, grouping_candidates, schedule
from flavor.model import resolve


class CampaignTests(unittest.TestCase):
    def test_inventory_covers_all_experiments(self):
        self.assertEqual({e["id"] for e in campaign()["experiments"]},
                         {"D0", *(f"E{i}" for i in range(11))})

    def test_compositions_and_memory_are_comparable(self):
        for variant, counts in (("H", (14, 0, 2)), ("M", (10, 4, 2)),
                                ("M6_far", (8, 6, 2))):
            resolved, g = resolve(architecture(variant))
            tiles = resolved["cluster"]["tiles"]
            self.assertEqual(tuple(sum(t["class"] == c for t in tiles)
                                   for c in ("BCT", "VCT", "MST")), counts)
            self.assertEqual(g["capacity"], 2048)
            self.assertEqual(g["data_width"], 128)
            self.assertEqual(g["metadata_width"], 256)
            self.assertEqual([(t["row"], t["col"]) for t in tiles if t["class"] == "MST"],
                             [(0, 1), (3, 2)])

    def test_near_far_tie_break_and_fixed_mst(self):
        for count in (2, 4, 6):
            for placement in ("near", "far"):
                document = architecture(f"M{count}_{placement}")
                tiles = document["cluster"]["tiles"]
                msts = [(0, 1), (3, 2)]
                key = lambda p: ((1 if placement == "near" else -1) * min(
                    abs(p[0] - m[0]) + abs(p[1] - m[1]) for m in msts), *p)
                candidates = sorted(((r, c) for r in range(4) for c in range(4)
                                     if (r, c) not in msts), key=key)
                self.assertEqual({(t["row"], t["col"]) for t in tiles if t["class"] == "VCT"},
                                 set(candidates[:count]))

    def test_axpy_wrap_and_negative_values(self):
        self.assertEqual(reference("axpy", [-128, 127], [-1, 2**31 - 1], coefficient=-3),
                         [383, (2**31 - 1 - 381) & 0xFFFFFFFF])
        with self.assertRaises(ValueError):
            reference("axpy", [1], [])

    def test_dot_and_fir_independent_references(self):
        self.assertEqual(reference("dot", [-2, 3], [4, -5]), [(-23) & 0xFFFFFFFF])
        self.assertEqual(reference("fir", [1, 2, -3], coefficients=[2, -1, 3]),
                         [2, 3, (-5) & 0xFFFFFFFF])

    def test_inputs_reproducible_and_held_out(self):
        a = workload("axpy", 9)
        self.assertEqual(a, workload("axpy", 9))
        b = workload("axpy", 13, role="reserved")
        self.assertNotEqual(a["input_sha256"], b["input_sha256"])
        self.assertEqual(len(a["expected"]), 9)
        jobs = scenarios("E0")
        self.assertEqual(jobs[0]["case"]["input_sha256"], jobs[1]["case"]["input_sha256"])

    def test_domain_reference_uses_same_work(self):
        jobs = scenarios("D0")
        self.assertEqual(len(jobs), 4)
        for a, b in ((jobs[0], jobs[1]), (jobs[2], jobs[3])):
            self.assertEqual(a["case"], b["case"])
            self.assertNotEqual(a["policy"], b["policy"])
        d = domains(architecture()["cluster"])
        self.assertEqual(len(d["compute"]["tiles"]), 14)
        self.assertFalse(d["retention"])
        self.assertEqual(d["power_intent_status"], "NOT_RUN")

    def test_schedule_is_offline_with_drain_before_off(self):
        result = schedule(workload("axpy", 9), "phase_aware", {})
        actions = [x["action"] for x in result["actions"]]
        self.assertLess(actions.index("drain"), actions.index("power_off"))
        self.assertLess(actions.index("wake"), actions.index("execute_axpy"))
        self.assertEqual(result["decision_mode"], "offline_phase_schedule_v1")

    def test_grouping_rules_keep_composition_and_group_sizes_fixed(self):
        candidates = grouping_candidates(architecture()["cluster"])
        self.assertEqual(len(candidates), 2)
        a, b = candidates
        self.assertNotEqual(a["criterion"], b["criterion"])
        self.assertEqual(sorted(map(len, a["groups"])), [7, 7])
        self.assertEqual({x for group in a["groups"] for x in group},
                         {x for group in b["groups"] for x in group})
        self.assertEqual(b["status"], "NOT_RUN")

    def test_packet_extraction_rejects_stale_compute_context(self):
        manifest = dict(tile_parameter_table=[dict(id=0, module="bct",
            parameters=dict(CONTEXT_DEPTH=4, CONTEXT_VERSION_WIDTH=16))])
        functional = dict(descriptors=[], schedule=dict(mapping={}),
                          job=dict(case=dict(workload="copy")))
        trace = [dict(kind="transfer", tile=0, direction=side, port=0, data=41, metadata=20)
                 for side in ("input", "output")]
        self.assertEqual(validate_packets(manifest, functional, trace)["compute_packet_records"], 1)
        trace[1]["metadata"] = 24
        with self.assertRaisesRegex(ValueError, "context/version"):
            validate_packets(manifest, functional, trace)


class ResultsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.saif = self.path / "kernel.saif"
        self.saif.write_text("(SAIFILE (TIMESCALE 1 ns) (DURATION 100) (INSTANCE dut))")
        self.window = dict(start_cycle=10, end_cycle=20, clock_period_ns=10)
        self.power = dict(duration_s=1e-7, average_power_w=dict(total=0.002),
            saif_annotation=dict(file_annotated_nets=30, file_annotated_percent=95.5),
            analysis="mapped_netlist_estimate")

    def test_known_si_conversion(self):
        result = energy(self.power, self.window, 4, self.saif)
        self.assertAlmostEqual(result["energy_kernel_j"], 2e-10)
        self.assertAlmostEqual(result["energy_per_output_j"], 5e-11)

    def test_whole_simulation_saif_is_rejected(self):
        self.saif.write_text("(SAIFILE (TIMESCALE 1 ns) (DURATION 1000) (INSTANCE dut))")
        with self.assertRaisesRegex(ValueError, "SAIF duration"):
            energy(self.power, self.window, 4, self.saif)

    def test_incomplete_power_reports_are_rejected(self):
        for field, value in (("file_annotated_nets", 0), ("file_annotated_percent", 101)):
            bad = deepcopy(self.power)
            bad["saif_annotation"][field] = value
            with self.assertRaises(ValueError):
                energy(bad, self.window, 4, self.saif)
        for value in (-1, float("inf"), float("nan")):
            bad = deepcopy(self.power)
            bad["average_power_w"]["total"] = value
            with self.assertRaises(ValueError):
                energy(bad, self.window, 4, self.saif)
        with self.assertRaises(ValueError):
            energy(self.power, self.window, 0, self.saif)

    @staticmethod
    def row(energy_j=10, time_s=20):
        return dict(input_sha256="a", numeric_contract=dict(width=32),
            operating_point=dict(technology="test_fixture", voltage=1),
            status=dict(rtl="PASS", energy="PASS"),
            metrics=dict(energy_kernel_j=energy_j, kernel_time_s=time_s))

    def test_pairs_require_identical_inputs_and_conditions(self):
        a, b = self.row(), self.row(5, 22)
        self.assertEqual(relative(a, b), dict(energy_saving_pct=50, time_change_pct=10))
        b["input_sha256"] = "different"
        with self.assertRaisesRegex(ValueError, "input_sha256"):
            relative(a, b)
        b = self.row()
        b["operating_point"] = None
        with self.assertRaisesRegex(ValueError, "operating_point"):
            relative(a, b)

    def test_complete_selection_and_near_tie_break(self):
        baseline = {"axpy": self.row(), "copy": self.row()}
        candidates = {f"M{n}_{p}": deepcopy(baseline)
                      for n in (2, 4, 6) for p in ("near", "far")}
        result = select_composition(baseline, candidates, list(baseline))
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["selected"], "M2_near")
        candidates["M6_far"].pop("copy")
        result = select_composition(baseline, candidates, list(baseline))
        self.assertEqual(result["status"], "BLOCKED")
        self.assertIsNone(result["selected"])
        self.assertIn("M6_far", result["excluded"])

    def test_missing_candidate_never_selects_m1star(self):
        baseline = {"axpy": self.row()}
        result = select_composition(baseline, {"M2_near": baseline}, ["axpy"])
        self.assertEqual(result["status"], "BLOCKED")

    def test_csv_and_markdown_regenerate_and_keep_blockers(self):
        path = self.path / "runs/E1/M_pending/summary.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(dict(experiment="E1", variant="M", case_id="pending",
            status=dict(rtl="BLOCKED", power_intent="NOT_RUN", energy="BLOCKED"),
            metrics={}, reason="licensed tools unavailable")))
        collect(self.path)
        original = (self.path / "results.csv").read_bytes()
        collect(self.path)
        self.assertEqual(original, (self.path / "results.csv").read_bytes())
        with (self.path / "results.csv").open() as stream:
            row = list(csv.DictReader(stream))[0]
        self.assertEqual(row["energy_kernel_j"], "")
        self.assertEqual(row["rtl_status"], "BLOCKED")
        self.assertIn("licensed tools unavailable", (self.path / "thesis-summary.md").read_text())


if __name__ == "__main__":
    unittest.main()
