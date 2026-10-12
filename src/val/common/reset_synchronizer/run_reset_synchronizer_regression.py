"""Run PyUVM reset sequencing, stage assertions, and elaboration guards."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
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
PROFILES = tuple((f"stages{stages}", stages) for stages in (2, 3, 4))
INVALID_PARAMETERS = (
    ("zero_stages", {"STAGES": "0"}, "reset_synchronizer_stages_must_be_at_least_two"),
    ("one_stage", {"STAGES": "1"}, "reset_synchronizer_stages_must_be_at_least_two"),
)


def license_unavailable(diagnostic: str) -> bool:
    """Recognize common checkout failures without crediting them as RTL results."""
    message = diagnostic.lower()
    return any(fragment in message for fragment in (
        "license checkout failed", "license check out failed", "no valid license",
        "cannot connect to license server", "unable to checkout a license",
    ))


def check_unknown_resets(args, build: Path, rtl: Path) -> list[dict]:
    """Prove the live assertion rejects each unacknowledged unknown reset.

An expected test failure earns PASS only with the exact PyUVM test, a failing
JUnit record, and its unknown-reset diagnostic. Compilation errors cannot pass.
"""
    reports = []
    for state in "xz":
        case = build / "unknown_reset_checks" / state
        case.mkdir(parents=True, exist_ok=True)
        results_file, coverage_file = case / "results.xml", case / "coverage.json"
        results_file.unlink(missing_ok=True)
        coverage_file.unlink(missing_ok=True)
        parameter_file = case / "parameters.json"
        parameter_file.write_text('{"STAGES": 2}\n', encoding="utf-8")
        prefix = "-Preset_synchronizer." if args.sim == "icarus" else "-pvalue+reset_synchronizer."
        overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in {
            "STAGES": "2",
        }.items())
        command = [
            args.make, "--no-print-directory", "-C", str(ROOT), "-f", "Makefile", "pyuvm",
            f"SIM={args.sim}", f"PYTHON_BIN={sys.executable}", "COCOTB_TOPLEVEL=reset_synchronizer",
            "COCOTB_TEST_MODULES=test_reset_synchronizer", f"PYUVM_TEST_DIR={TEST_DIR}",
            r"COCOTB_TEST_FILTER=^test_reset_synchronizer\.ResetSynchronizerTest$", "COCOTB_TESTCASE=",
            f"VERILOG_SOURCES={rtl}", f"SIM_BUILD={case}", f"COCOTB_RESULTS_FILE={results_file}",
            f"CUSTOM_COMPILE_DEPS={parameter_file}", f"COMPILE_ARGS={args.compile_args} {overrides}",
            f"SIM_ARGS={args.sim_args}",
        ]
        if args.sim_bin_dir:
            variable = "VCS_BIN_DIR" if args.sim == "vcs" else "ICARUS_BIN_DIR"
            command.append(f"{variable}={args.sim_bin_dir}")
        environment = os.environ.copy()
        environment.update(
            RESET_SYNCHRONIZER_STAGES="2", RESET_SYNCHRONIZER_CHECK_STAGES="1",
            RESET_SYNCHRONIZER_UNKNOWN_PROBE=state, RESET_SYNCHRONIZER_SEED=str(args.seed),
            RESET_SYNCHRONIZER_RANDOM_CYCLES=str(args.random_cycles),
            RESET_SYNCHRONIZER_COVERAGE_FILE=str(coverage_file),
        )
        log_file = case / "simulation.log"
        with log_file.open("w", encoding="utf-8") as log:
            result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
        diagnostic = log_file.read_text(encoding="utf-8")
        detected = False
        try:
            cases = ET.parse(results_file).findall(".//testcase")
            detected = (
                len(cases) == 1 and cases[0].get("name") == "ResetSynchronizerTest"
                and cases[0].get("classname") == "test_reset_synchronizer"
                and cases[0].find("failure") is not None and cases[0].find("skipped") is None
                and f"AssertionError: Unknown-reset assertion failed: i_async_rstb={state}" in diagnostic
            )
        except (OSError, ET.ParseError):
            pass
        reports.append({
            "unknown_bit": state, "status": "PASS" if detected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
            "expected_test_failure": detected, "make_returncode": result.returncode, "log": str(log_file),
        })
        print(f"Unknown-reset assertion {state}: {reports[-1]['status']}", flush=True)
    return reports


def check_invalid_parameters(args, build: Path, rtl: Path) -> list[dict]:
    """Require intended elaboration guards, rather than unrelated compile failures."""
    compiler = shutil.which("vcs" if args.sim == "vcs" else "iverilog",
                            path=str(args.sim_bin_dir) if args.sim_bin_dir else None)
    reports = []
    for name, parameters, expected_guard in INVALID_PARAMETERS:
        case = build / "invalid_parameters" / name
        case.mkdir(parents=True, exist_ok=True)
        # Instantiate each illegal configuration so only the intended guard
        # can satisfy the elaboration rejection check.
        wrapper = case / "invalid_parameters.sv"
        overrides = ", ".join(f".{key}({value})" for key, value in parameters.items())
        wrapper.write_text(
            f"module reset_synchronizer_invalid_parameters;\nreset_synchronizer #({overrides}) dut ();\nendmodule\n",
            encoding="utf-8",
        )
        command = ([compiler, "-g2012", "-s", "reset_synchronizer_invalid_parameters", "-tnull"] if args.sim == "icarus" else
                   [compiler, "-full64", "-sverilog", "-top", "reset_synchronizer_invalid_parameters", "-o", str(case / "simv")])
        log_file = case / "elaboration.log"
        with log_file.open("w", encoding="utf-8") as log:
            result = subprocess.run([*command, *shlex.split(args.compile_args), str(rtl), str(wrapper)],
                                    cwd=case, stdout=log, stderr=subprocess.STDOUT)
        diagnostic = log_file.read_text(encoding="utf-8")
        rejected = result.returncode != 0 and expected_guard in diagnostic
        reports.append({
            "name": name, "parameters": parameters,
            "status": "PASS" if rejected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
            "expected_guard": expected_guard, "compiler_returncode": result.returncode,
            "stage": "elaboration" if rejected else None, "log": str(log_file),
        })
        print(f"Invalid parameters {name}: {reports[-1]['status']}", flush=True)
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim", choices=("vcs", "icarus"), default="vcs")
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--rtl", type=Path, default=ROOT / "src/rtl/common/reset_synchronizer.sv")
    parser.add_argument("--seed", type=int, default=20261011)
    parser.add_argument("--random-cycles", type=int, default=2000)
    parser.add_argument("--compile-args", default="")
    parser.add_argument("--sim-args", default="")
    parser.add_argument("--sim-bin-dir", type=Path)
    parser.add_argument("--make", default="make")
    parser.add_argument("--case", action="append", choices=[profile[0] for profile in PROFILES])
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
        "scope": "selected_profiles" if args.case else "synchronization_depth_matrix",
        "specification": "specs/common/mosaic-reset-synchronizer/README.md",
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "rtl": str(rtl),
        "profiles": [], "parameter_checks": [], "unknown_reset_checks": [],
        "external_checks": dict.fromkeys((
            "hdl_sva", "formal", "commercial_lint", "cdc", "rdc", "dft", "vc_lp",
            "synthesis", "logical_equivalence", "physical_timing", "physical_power",
            "metastability_mtbf", "recovery_removal", "physical_minimum_reset_pulse",
            "synchronizer_placement", "clock_gating_integration", "reset_reconvergence_integration",
        ), "NOT_RUN"),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = {
            name: hashlib.sha256((TEST_DIR / name).read_bytes()).hexdigest()
            for name in ("reset_synchronizer_env.py", "test_reset_synchronizer.py", "run_reset_synchronizer_regression.py")
        }
        binaries = ("vcs",) if args.sim == "vcs" else ("iverilog", "vvp")
        missing = [binary for binary in binaries if shutil.which(binary, path=str(args.sim_bin_dir) if args.sim_bin_dir else None) is None]
        if missing:
            raise FileNotFoundError(f"Simulator executable(s) missing: {', '.join(missing)}")
        summary["status"] = "FAIL"
        for index, (name, stages) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            parameters = {"STAGES": stages}
            case = build / name
            case.mkdir(parents=True, exist_ok=True)
            coverage_file, results_file = case / "coverage.json", case / "results.xml"
            log_file = case / "simulation.log"
            coverage_file.unlink(missing_ok=True)
            results_file.unlink(missing_ok=True)
            parameter_file = case / "parameters.json"
            parameter_file.write_text(json.dumps(parameters) + "\n", encoding="utf-8")
            # Each depth is a separate elaborated synchronization chain.
            prefix = "-Preset_synchronizer." if args.sim == "icarus" else "-pvalue+reset_synchronizer."
            compiler_parameters = {"STAGES": str(stages)}
            overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in compiler_parameters.items())
            command = [
                args.make, "--no-print-directory", "-C", str(ROOT), "-f", "Makefile", "pyuvm",
                f"SIM={args.sim}", f"PYTHON_BIN={sys.executable}", "COCOTB_TOPLEVEL=reset_synchronizer",
                "COCOTB_TEST_MODULES=test_reset_synchronizer", f"PYUVM_TEST_DIR={TEST_DIR}",
                r"COCOTB_TEST_FILTER=^test_reset_synchronizer\.ResetSynchronizerTest$", "COCOTB_TESTCASE=",
                f"VERILOG_SOURCES={rtl}", f"SIM_BUILD={case}", f"COCOTB_RESULTS_FILE={results_file}",
                f"CUSTOM_COMPILE_DEPS={parameter_file}", f"COMPILE_ARGS={args.compile_args} {overrides}",
                f"SIM_ARGS={args.sim_args}",
            ]
            if args.sim_bin_dir:
                variable = "VCS_BIN_DIR" if args.sim == "vcs" else "ICARUS_BIN_DIR"
                command.append(f"{variable}={args.sim_bin_dir}")
            environment = os.environ.copy()
            environment.update(
                RESET_SYNCHRONIZER_STAGES=str(stages), RESET_SYNCHRONIZER_CHECK_STAGES="1",
                RESET_SYNCHRONIZER_UNKNOWN_PROBE="",
                RESET_SYNCHRONIZER_SEED=str(args.seed + index), RESET_SYNCHRONIZER_RANDOM_CYCLES=str(args.random_cycles),
                RESET_SYNCHRONIZER_COVERAGE_FILE=str(coverage_file),
            )
            print(f"Running {name}: {parameters}, seed={args.seed + index}", flush=True)
            with log_file.open("w", encoding="utf-8") as log:
                result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                cases = ET.parse(results_file).findall(".//testcase")
                if len(cases) != 1 or cases[0].get("name") != "ResetSynchronizerTest" or cases[0].get("classname") != "test_reset_synchronizer":
                    raise ValueError("The expected PyUVM test did not run exactly once")
                if any(cases[0].find(tag) is not None for tag in ("failure", "error", "skipped")):
                    raise ValueError("The PyUVM test failed or was skipped")
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["parameters"] != parameters or coverage["portable_stage_assertions"] != "PASS" or not all(coverage["goals"].values()):
                    raise ValueError("Coverage or elaboration parameters did not match")
                if coverage["seed"] != args.seed + index or coverage["random_transactions"] != args.random_cycles:
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
        summary["unknown_reset_checks"] = check_unknown_resets(args, build, rtl)
        reports = (*summary["profiles"], *summary["parameter_checks"], *summary["unknown_reset_checks"])
        complete = len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary["parameter_checks"]) == len(INVALID_PARAMETERS) and len(summary["unknown_reset_checks"]) == 2
        summary["status"] = (
            "PASS" if complete and all(report["status"] == "PASS" for report in reports)
            else "NOT_RUN" if complete and any(report["status"] == "NOT_RUN" for report in reports)
            and all(report["status"] in ("PASS", "NOT_RUN") for report in reports)
            else "FAIL"
        )
        if not args.case:
            passed = [profile for profile in summary["profiles"] if profile["status"] == "PASS"]
            phases = {(profile["parameters"]["STAGES"], kind, phase) for profile in passed
                      for kind, phase in profile["bins"]["reset_transition_phases"]}
            expected_phases = ("low", "high", "before_rise", "after_rise", "before_fall", "after_fall", "on_rise", "on_fall")
            summary["matrix_goals"] = {
                "every_specified_depth": {profile["parameters"]["STAGES"] for profile in passed} == {stages for _, stages in PROFILES},
                "reset_phase_depth_cross": {(stages, kind, phase) for _, stages in PROFILES for kind in ("assert", "deassert") for phase in expected_phases} <= phases,
            }
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"

    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Reset synchronizer regression could not run: {error}", file=sys.stderr)
    finally:
        summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        summary_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"Reset synchronizer regression {summary['status']}: {summary_file}", flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
