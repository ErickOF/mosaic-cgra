"""Self-contained checks for the MOSAIC synthesis campaign driver."""

import argparse
import json
from pathlib import Path
import tempfile
import unittest

import campaign


class CampaignPlanTest(unittest.TestCase):
    def args(self, **overrides):
        values = dict(families="all", applications="all",
                      sizes="2,3,4,5,6,8,10,12,16", case_pattern=None)
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_complete_matrix_has_expected_cases(self):
        plan = campaign.make_plan(self.args())
        self.assertEqual(plan["case_count"], 177)
        arrays = [case for case in plan["cases"] if case["scope"] == "array"]
        self.assertEqual(len(arrays), 45)
        self.assertEqual({case["application"] for case in arrays}, set(campaign.APPLICATIONS))
        self.assertEqual({case["rows"] for case in arrays}, set(campaign.DEFAULT_SIZES))

    def test_dependent_parameter_sweeps_remain_legal(self):
        plan = campaign.make_plan(self.args(families="bct,vct,cpt", applications="ai", sizes="2"))
        cases = {case["id"]: case for case in plan["cases"]}
        self.assertEqual(cases["tile-bct-data-width-2"]["parameters"],
                         {"DATA_WIDTH": 2, "MULTIPLY_OPERAND_WIDTH": 1})
        self.assertEqual(cases["tile-bct-data-width-6"]["parameters"],
                         {"DATA_WIDTH": 6, "MULTIPLY_OPERAND_WIDTH": 3})
        self.assertEqual(cases["tile-bct-data-width-16"]["parameters"],
                         {"DATA_WIDTH": 16, "MULTIPLY_OPERAND_WIDTH": 8})
        self.assertEqual(cases["tile-vct-element-width-4"]["parameters"],
                         {"ELEMENT_WIDTH": 4, "WRITE_SLICE_WIDTH": 4})
        self.assertEqual(cases["tile-cpt-predicate-lanes-16"]["parameters"],
                         {"PREDICATE_LANES": 16, "PREDICATE_WIDTH": 16})
        document = campaign.flavor_document("balanced", 2)
        bct = next(tile for tile in document["cluster"]["tiles"] if tile["class"] == "BCT")
        bct["parameters"] = {"DATA_WIDTH": 2, "MULTIPLY_OPERAND_WIDTH": 1}
        campaign.resolve(document)

    def test_every_application_flavor_validates(self):
        for application in campaign.APPLICATIONS:
            for size in campaign.DEFAULT_SIZES:
                document = campaign.flavor_document(application, size)
                resolved, geometry = campaign.resolve(document)
                self.assertEqual(len(resolved["cluster"]["tiles"]), size * size)
                self.assertGreater(geometry["capacity"], 0)


class CampaignReportTest(unittest.TestCase):
    def write_reports(self, run_dir, top="bct"):
        reports = run_dir / "reports"
        reports.mkdir(parents=True)
        (reports / f"{top}_area.rpt").write_text(
            "Number of cells: 120\nCombinational area: 123.5\n"
            "Noncombinational area: 42.0\nTotal cell area: 165.5\n")
        (reports / f"{top}_qor.rpt").write_text(
            "Critical Path Length: 3.75\nCritical Path Slack: 0.25\n"
            "Total Negative Slack: 0.00\nNo. of Violating Paths: 0\n")
        (reports / f"{top}_timing.rpt").write_text("slack (MET) 0.25\n")
        (reports / f"{top}_power.rpt").write_text(
            "Total Dynamic Power = 12.0 mW\nCell Leakage Power = 340.0 uW\n")
        (reports / f"{top}_units.rpt").write_text("Time unit : 1ns\n")

    def test_report_parser_normalizes_power(self):
        with tempfile.TemporaryDirectory() as directory:
            run_dir = Path(directory)
            self.write_reports(run_dir)
            metrics, reports, parsed = campaign.parse_reports(run_dir, "bct")
        self.assertTrue(all(reports.values()))
        self.assertTrue(all(parsed.values()))
        self.assertEqual(metrics["area_total"], 165.5)
        self.assertEqual(metrics["timing_wns"], 0.25)
        self.assertAlmostEqual(metrics["power_dynamic_w"], 0.012)
        self.assertAlmostEqual(metrics["power_total_w"], 0.01234)
        self.assertTrue(metrics["timing_met"])

    def test_fake_make_run_produces_collectable_result(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            output = temporary / "campaign"
            technology = temporary / "technology.tcl"
            technology.write_text("# fake technology setup\n")
            fake_make = temporary / "fake_make.py"
            fake_make.write_text(
                "#!/usr/bin/env python3\n"
                "import pathlib, sys\n"
                "values = dict(a.split('=', 1) for a in sys.argv[1:] if '=' in a)\n"
                "run = pathlib.Path(values['SYNTH_BUILD'])\n"
                "top = values['COCOTB_TOPLEVEL']\n"
                "r = run / 'reports'\n"
                "r.mkdir(parents=True, exist_ok=True)\n"
                "(r / f'{top}_area.rpt').write_text('Total cell area: 10.0\\n')\n"
                "(r / f'{top}_qor.rpt').write_text('Critical Path Slack: 0.1\\n')\n"
                "(r / f'{top}_timing.rpt').write_text('slack (MET) 0.1\\n')\n"
                "(r / f'{top}_power.rpt').write_text('Total Dynamic Power = 2 mW\\n')\n")
            fake_make.chmod(0o755)
            plan_args = argparse.Namespace(families="array", applications="ai", sizes="2",
                                           case_pattern=None)
            plan = campaign.make_plan(plan_args)
            campaign.materialize_plan(plan, output)
            run_args = argparse.Namespace(
                make=str(fake_make), tech_setup=technology, dc_shell="dc_shell",
                clock_period=4.0, synth_cpus=1, dc_setup=None, constraints=None, force=False)
            result = campaign.run_case(dict(plan["cases"][0]), run_args, output)
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["area_total"], 10.0)
            self.assertTrue((output / "bundles").is_dir())
            state = json.loads((output / "runs" / result["id"] / "run.json").read_text())
            self.assertEqual(state["returncode"], 0)
            changed = dict(plan["cases"][0], execution_id="different-synthesis-context")
            self.assertEqual(campaign.case_result(changed, output)["status"], "stale")


if __name__ == "__main__":
    unittest.main()
