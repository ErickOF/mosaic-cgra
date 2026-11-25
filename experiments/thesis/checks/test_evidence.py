"""Gate-evidence integration checks using clearly synthetic report fixtures."""

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from attach_power import attach
from bundle import generate
from cases import architecture, digest, scenarios
from flavor.generate import digest as file_digest, verify_bundle


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        bundle, record = generate(architecture("H", rows=2, cols=2), self.path / "bundles")
        job = scenarios("E0")[0]
        self.row = dict(status=dict(rtl="PASS", energy="BLOCKED"), metrics={},
            artifacts=dict(bundle=str(bundle)), operating_point=None,
            build_id=record["build_id"], input_sha256=job["case"]["input_sha256"],
            scenario_id=digest(job))
        self.summary = self.path / "summary.json"
        self.summary.write_text(json.dumps(self.row))
        self.gate = dict(status="PASS", job=job, expected=[1], observed=[1],
            memory_sha256=dict(actual="synthetic-image", expected="synthetic-image"),
            windows=dict(kernel=dict(start_cycle=10, end_cycle=20, clock_period_ns=10)),
            metrics=dict(verified_outputs=1))
        fixtures = dict(netlist="// synthetic test netlist\n", sdc="# test constraints\n",
            saif="(SAIFILE (TIMESCALE 1 ns) (DURATION 100) (INSTANCE dut))",
            timing_report="synthetic setup slack 0.1 ns\n", activity_report="synthetic\n",
            unannotated_report="synthetic\n", gate_functional=json.dumps(self.gate))
        for name, text in fixtures.items():
            (self.path / name).write_text(text)
        power = dict(duration_s=1e-7, average_power_w=dict(total=0.002),
            saif_annotation=dict(file_annotated_nets=30, file_annotated_percent=95.5),
            analysis="mapped_netlist_estimate",
            inputs={name: str(self.path / name) for name in ("netlist", "sdc", "saif")})
        (self.path / "power_summary").write_text(json.dumps(power))
        self.proof = {key: self.row[key] for key in ("build_id", "input_sha256", "scenario_id")}
        self.proof.update(schema="mosaic-thesis-gate-evidence-v1",
            operating_point=dict(technology="SYNTHETIC_TEST_FIXTURE", library_corner="fixture",
                voltage_v=1, clock_period_ns=10, memory_model="fixture",
                simulator_version="fixture", power_tool_version="fixture"),
            timing=dict(status="PASS", worst_slack_ns=0.1),
            artifacts={name: dict(path=str(self.path / name), sha256=file_digest(self.path / name))
                       for name in (*fixtures, "power_summary")})
        self.evidence = self.path / "evidence.json"
        self.write_proof()

    def write_proof(self):
        self.evidence.write_text(json.dumps(self.proof))

    def test_adapter_export_is_immutable_and_opt_in(self):
        bundle = Path(self.row["artifacts"]["bundle"])
        verify_bundle(bundle)
        text = (bundle / "rtl/cluster.sv").read_text()
        self.assertIn("i_thesis_memory_stall", text)
        self.assertIn("_adapted", text)
        manifest = json.loads((bundle / "manifest.json").read_text())
        self.assertFalse(manifest["experiment"]["power_model"])
        self.assertTrue(all(t["parameters"].get("SUPPORT_POWER_OFF", 0) == 0
                            for t in manifest["tile_parameter_table"]))
        (bundle / "rtl/cluster.sv").write_text(text + "// tampered\n")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            verify_bundle(bundle)

    def test_valid_gate_report_attaches_si_energy(self):
        row = attach(self.summary, self.evidence)
        self.assertEqual(row["status"]["energy"], "PASS")
        self.assertAlmostEqual(row["metrics"]["energy_kernel_j"], 2e-10)
        self.assertEqual(row["operating_point"]["technology"], "SYNTHETIC_TEST_FIXTURE")

    def test_wrong_case_and_changed_files_are_rejected(self):
        original = self.summary.read_bytes()
        self.proof["input_sha256"] = "another-input"
        self.write_proof()
        with self.assertRaisesRegex(ValueError, "input_sha256"):
            attach(self.summary, self.evidence)
        self.assertEqual(self.summary.read_bytes(), original)
        self.proof["input_sha256"] = self.row["input_sha256"]
        self.write_proof()
        (self.path / "netlist").write_text("// changed netlist\n")
        with self.assertRaisesRegex(ValueError, "artifact changed"):
            attach(self.summary, self.evidence)

    def test_gate_functional_and_timing_failures_are_rejected(self):
        self.proof["timing"]["status"] = "FAIL"
        self.write_proof()
        with self.assertRaisesRegex(ValueError, "timing"):
            attach(self.summary, self.evidence)
        self.proof["timing"]["status"] = "PASS"
        self.gate["observed"] = [2]
        (self.path / "gate_functional").write_text(json.dumps(self.gate))
        self.proof["artifacts"]["gate_functional"]["sha256"] = file_digest(self.path / "gate_functional")
        self.write_proof()
        with self.assertRaisesRegex(ValueError, "output"):
            attach(self.summary, self.evidence)


if __name__ == "__main__":
    unittest.main()
