"""Run the level-shifter width/direction matrix with real four-state PyUVM."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

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


def license_unavailable(diagnostic: str) -> bool:
    """Recognizable checkout failures indicate unavailable tools, not RTL results."""
    message = diagnostic.lower()
    return any(fragment in message for fragment in (
        "license checkout failed", "license check out failed", "no valid license",
        "cannot connect to license server", "unable to checkout a license",
    ))


def check_invalid_parameters(args, build: Path, rtl: Path) -> list[dict]:
    """Require the intended guard, and distinguish elaboration from startup."""
    search_path = str(args.sim_bin_dir) if args.sim_bin_dir else None
    compiler = shutil.which("vcs" if args.sim == "vcs" else "iverilog", path=search_path)
    reports = []
    for name, width, direction, expected_guard in INVALID_PARAMETERS:
        case = build / "invalid_parameters" / name
        case.mkdir(parents=True, exist_ok=True)
        wrapper = case / "invalid_parameters.sv"
        # WIDTH=0 declares [-1:0] in the unchanged RTL; avoid unrelated warnings.
        port_width = width if width else 2
        wrapper.write_text(
            '`timescale 1ns/1ps\nmodule level_shifter_invalid_parameters;\n'
            f'level_shifter #(.WIDTH({width}), .DIRECTION({direction})) dut '
            f'(.i_data({port_width}\'b0), .o_data());\n'
            'initial begin #1; $fatal(1, "Invalid level shifter parameters were accepted"); end\nendmodule\n',
            encoding="utf-8",
        )
        executable = case / ("simv" if args.sim == "vcs" else "sim.vvp")
        command = ([compiler, "-g2012", "-s", "level_shifter_invalid_parameters", "-o", str(executable)]
                   if args.sim == "icarus" else
                   [compiler, "-full64", "-sverilog", "-top", "level_shifter_invalid_parameters", "-o", str(executable)])
        log_file = case / "guard.log"
        with log_file.open("w", encoding="utf-8") as log:
            compiled = subprocess.run([*command, *shlex.split(args.compile_args), str(rtl), str(wrapper)],
                                      cwd=case, stdout=log, stderr=subprocess.STDOUT)
            runtime_code = None
            if compiled.returncode == 0:
                runtime = ([shutil.which("vvp", path=search_path), str(executable)]
                           if args.sim == "icarus" else [str(executable)])
                runtime_code = subprocess.run(runtime, cwd=case, stdout=log, stderr=subprocess.STDOUT).returncode
        diagnostic = log_file.read_text(encoding="utf-8")
        rejected = expected_guard in diagnostic and (
            compiled.returncode != 0 or runtime_code is not None and runtime_code != 0
        )
        reports.append({
            "name": name, "parameters": {"WIDTH": width, "DIRECTION": direction},
            "status": "PASS" if rejected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
            "expected_guard": expected_guard, "compiler_returncode": compiled.returncode,
            "runtime_returncode": runtime_code,
            "stage": "elaboration" if rejected and compiled.returncode != 0 else "simulation_startup" if rejected else None,
            "log": str(log_file),
        })
        print(f"Invalid parameters {name}: {reports[-1]['status']}", flush=True)
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim", choices=("vcs", "icarus"), default="vcs")
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--rtl", type=Path, default=ROOT / "src/rtl/common/level_shifter.sv")
    parser.add_argument("--seed", type=int, default=20261011)
    parser.add_argument("--random-cycles", type=int, default=2000)
    parser.add_argument("--compile-args", default="")
    parser.add_argument("--sim-args", default="")
    parser.add_argument("--sim-bin-dir", type=Path)
    parser.add_argument("--make", default="make")
    parser.add_argument("--case", action="append", choices=[name for name, _, _ in PROFILES])
    args = parser.parse_args()
    if args.random_cycles < 1000:
        parser.error("--random-cycles must be at least 1000")
    if args.sim_bin_dir:
        args.sim_bin_dir = args.sim_bin_dir.resolve()
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
        summary["verification_sha256"] = {
            name: hashlib.sha256((TEST_DIR / name).read_bytes()).hexdigest()
            for name in ("level_shifter_env.py", "test_level_shifter.py", "run_level_shifter_regression.py")
        }
        binaries = ("vcs",) if args.sim == "vcs" else ("iverilog", "vvp")
        missing = [binary for binary in binaries if shutil.which(binary, path=str(args.sim_bin_dir) if args.sim_bin_dir else None) is None]
        if missing:
            raise FileNotFoundError(f"Simulator executable(s) missing: {', '.join(missing)}")
        summary["status"] = "FAIL"
        for name, width, direction in PROFILES:
            if args.case and name not in args.case:
                continue
            parameters = {"WIDTH": width, "DIRECTION": direction}
            # The two directions receive identical input histories at each width.
            seed = args.seed + WIDTHS.index(width)
            case = build / name
            case.mkdir(parents=True, exist_ok=True)
            coverage_file, results_file = case / "coverage.json", case / "results.xml"
            log_file = case / "simulation.log"
            coverage_file.unlink(missing_ok=True)
            results_file.unlink(missing_ok=True)
            parameter_file = case / "parameters.json"
            parameter_file.write_text(json.dumps(parameters) + "\n", encoding="utf-8")
            prefix = "-Plevel_shifter." if args.sim == "icarus" else "-pvalue+level_shifter."
            overrides = " ".join(f"{prefix}{key}={value}" for key, value in parameters.items())
            command = [
                args.make, "--no-print-directory", "-C", str(ROOT), "-f", "Makefile", "pyuvm",
                f"SIM={args.sim}", f"PYTHON_BIN={sys.executable}", "COCOTB_TOPLEVEL=level_shifter",
                "COCOTB_TEST_MODULES=test_level_shifter", f"PYUVM_TEST_DIR={TEST_DIR}",
                r"COCOTB_TEST_FILTER=^test_level_shifter\.LevelShifterTest$", "COCOTB_TESTCASE=",
                f"VERILOG_SOURCES={rtl}", f"SIM_BUILD={case}", f"COCOTB_RESULTS_FILE={results_file}",
                f"CUSTOM_COMPILE_DEPS={parameter_file}", f"COMPILE_ARGS={args.compile_args} {overrides}",
                f"SIM_ARGS={args.sim_args}",
            ]
            if args.sim_bin_dir:
                variable = "VCS_BIN_DIR" if args.sim == "vcs" else "ICARUS_BIN_DIR"
                command.append(f"{variable}={args.sim_bin_dir}")
            environment = os.environ.copy()
            environment.update(
                LEVEL_SHIFTER_WIDTH=str(width), LEVEL_SHIFTER_DIRECTION=str(direction),
                LEVEL_SHIFTER_SEED=str(seed), LEVEL_SHIFTER_RANDOM_CYCLES=str(args.random_cycles),
                LEVEL_SHIFTER_COVERAGE_FILE=str(coverage_file),
            )
            print(f"Running {name}: {parameters}, seed={seed}", flush=True)
            with log_file.open("w", encoding="utf-8") as log:
                result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                cases = ET.parse(results_file).findall(".//testcase")
                if len(cases) != 1 or cases[0].get("name") != "LevelShifterTest" or cases[0].get("classname") != "test_level_shifter":
                    raise ValueError("The expected PyUVM test did not run exactly once")
                if any(cases[0].find(tag) is not None for tag in ("failure", "error", "skipped")):
                    raise ValueError("The PyUVM test failed or was skipped")
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
        summary["status"] = (
            "PASS" if complete and all(report["status"] == "PASS" for report in reports)
            else "NOT_RUN" if complete and any(report["status"] == "NOT_RUN" for report in reports)
            and all(report["status"] in ("PASS", "NOT_RUN") for report in reports)
            else "FAIL"
        )
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
        summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        summary_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"Level shifter regression {summary['status']}: {summary_file}", flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
