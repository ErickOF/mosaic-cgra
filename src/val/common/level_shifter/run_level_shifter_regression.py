"""Run the level-shifter width/direction matrix with real four-state PyUVM."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from mosaic_uvm.regression import (
    campaign_status, finish_summary, license_unavailable, parameter_guard, parse_args, passed_test, require_simulator, run_simulation, verification_hashes,
)

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
WIDTHS = (1, 2, 4, 8, 16, 32, 64)
PROFILES = tuple((f"width{width}_{'l2h' if direction == 0 else 'h2l'}", width, direction)
                 for width, direction in product(WIDTHS, (0, 1)))
INVALID_PARAMETERS = (
    *((f"zero_width_{direction}", 0, direction, "WIDTH must be greater than or equal to one") for direction in (0, 1)),
    *((f"direction_{direction}_width{width}", width, direction, "DIRECTION must be zero or one")
      for width, direction in product((1, 4), (2, -1))),
)


def check_invalid_parameters(args, build: Path, rtl: Path) -> list[dict]:
    reports = []
    for (name, width, direction, expected_guard) in INVALID_PARAMETERS:
        port_width = width if width else 2
        reports.append(parameter_guard(args, build, rtl, 'level_shifter', name, {'WIDTH': width, 'DIRECTION': direction}, expected_guard,
                                       wrapper_source=(
        '`timescale 1ns/1ps\nmodule level_shifter_invalid_parameters;\n'
        f'level_shifter #(.WIDTH({width}), .DIRECTION({direction})) dut '
        f'(.i_data({port_width}\'b0), .o_data());\n'
        'initial begin #1; $fatal(1, "Invalid level shifter parameters were accepted"); end\nendmodule\n'
    ), allow_startup=True))
    return reports


def main() -> int:
    args = parse_args('level_shifter', __doc__, profiles=[name for name, _, _ in PROFILES], seed=20261011)
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = {
        "status": "NOT_RUN", "framework": "PyUVM", "simulator": args.sim,
        "scope": "selected_profiles" if args.case else "width_direction_matrix",
        "specification": "specs/common/mosaic-level-shifter/README.md",
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "rtl": str(rtl),
        "profiles": [], "parameter_checks": [], "specification_gaps": {},
        "external_checks": dict.fromkeys((
            "hdl_sva", "formal", "technology_equivalence", "upf_power_aware_simulation",
            "power_state_table", "illegal_power_states", "source_destination_power_transitions",
            "voltage_pairs_and_dvfs", "separate_combined_isolation", "isolation_sequencing",
            "invalid_output_consumption", "commercial_lint", "cdc", "rdc", "dft", "vc_lp",
            "synthesis_and_cell_insertion", "physical_supplies_and_placement", "drc_lvs",
            "cross_voltage_timing_and_skew", "multi_supply_power", "multi_voltage_energy_tradeoff",
        ), "NOT_RUN"),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary["status"] = "FAIL"
        for name, width, direction in PROFILES:
            if args.case and name not in args.case:
                continue
            parameters = {"WIDTH": width, "DIRECTION": direction}
            # The two directions receive identical input histories at each width.
            seed = args.seed + WIDTHS.index(width)
            case = build / name
            prefix = "-Plevel_shifter." if args.sim == "icarus" else "-pvalue+level_shifter."
            overrides = " ".join(f"{prefix}{key}={value}" for key, value in parameters.items())
            print(f'Running {name}: {parameters}, seed={seed}', flush=True)
            (result, log_file, results_file, coverage_file) = run_simulation(
                args, ROOT, TEST_DIR, 'level_shifter', 'test_level_shifter', 'LevelShifterTest', case, rtl,
                environment={
                    'LEVEL_SHIFTER_WIDTH': str(width), 'LEVEL_SHIFTER_DIRECTION': str(direction),
                    'LEVEL_SHIFTER_SEED': str(seed), 'LEVEL_SHIFTER_RANDOM_CYCLES': str(args.random_cycles),
                },
                compile_args=f'{args.compile_args} {overrides}',
                parameters=parameters,
            )
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results_file, 'LevelShifterTest', 'test_level_shifter')
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["parameters"] != parameters or not all(coverage["goals"].values()):
                    raise ValueError("Coverage or elaboration parameters did not match")
                if coverage["seed"] != seed or coverage["random_transactions"] != args.random_cycles:
                    raise ValueError("Random campaign settings did not match")
                report.update(coverage, name=name, coverage=str(coverage_file))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                report["error"] = str(error)
                diagnostic = log_file.read_text(encoding="utf-8")
                if license_unavailable(diagnostic):
                    report["status"] = "NOT_RUN"
                print("\n".join(diagnostic.splitlines()[-25:]), flush=True)
            summary["profiles"].append(report)
            print(f"{name}: {report['status']}", flush=True)
        summary["parameter_checks"] = check_invalid_parameters(args, build, rtl)
        if any(report["stage"] == "simulation_startup" for report in summary["parameter_checks"]):
            summary["specification_gaps"]["strict_elaboration_parameter_validation"] = {
                "status": "BLOCKED", "reason": "RTL guards reject invalid parameters with initial fatal at simulation startup",
            }
        reports = (*summary["profiles"], *summary["parameter_checks"])
        complete = len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary["parameter_checks"]) == len(INVALID_PARAMETERS)
        summary["status"] = campaign_status(reports, complete)
        if not args.case:
            passed = [report for report in summary["profiles"] if report["status"] == "PASS"]
            crossed = {(report["parameters"]["WIDTH"], report["parameters"]["DIRECTION"]) for report in passed}
            class_cross = {(report["parameters"]["DIRECTION"], pattern) for report in passed for pattern in report["bins"]["pattern_classes"]}
            classes = {"zero", "one", "walking_one", "walking_zero", "alternating", "all_x", "all_z",
                       "mixed_known", "mixed_unknown_known", "mixed_x_z"}
            paired_histories = all(
                len(pair := [report for report in passed if report["parameters"]["WIDTH"] == width]) == 2
                and pair[0]["seed"] == pair[1]["seed"] and pair[0]["stimulus_sha256"] == pair[1]["stimulus_sha256"]
                for width in WIDTHS
            )
            summary["matrix_goals"] = {
                "width_direction_cross": crossed == set(product(WIDTHS, (0, 1))),
                "direction_data_pattern_cross": set(product((0, 1), classes)) <= class_cross,
                "identical_stimulus_in_both_directions": paired_histories,
            }
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Level shifter regression could not run: {error}", file=sys.stderr)
    finally:
        finish_summary(summary_file, summary, 'Level shifter')
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
