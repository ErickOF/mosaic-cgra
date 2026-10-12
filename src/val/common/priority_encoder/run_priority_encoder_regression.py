"""Run native PyUVM priority, four-state, and invalid-parameter checks."""

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
WIDTHS = (1, 2, 3, 4, 5, 8, 16, 32)
PROFILES = tuple((f"width{width}_{'lsb' if direction else 'msb'}", width, direction)
                 for width in WIDTHS for direction in (1, 0))
INVALID_PARAMETERS = (
    ("zero_width", {"WIDTH": "0"}, "priority_encoder_width_must_be_greater_than_zero"),
    ("undersized_index", {"WIDTH": "3", "INDEX_WIDTH": "1"}, "priority_encoder_index_width_must_match_width"),
    ("oversized_index", {"WIDTH": "4", "INDEX_WIDTH": "3"}, "priority_encoder_index_width_must_match_width"),
    ("minimum_zero_index", {"WIDTH": "1", "INDEX_WIDTH": "0"}, "priority_encoder_index_width_must_match_width"),
)


def license_unavailable(diagnostic: str) -> bool:
    """Recognize common checkout failures without crediting them as RTL results."""
    message = diagnostic.lower()
    return any(fragment in message for fragment in (
        "license checkout failed", "license check out failed", "no valid license",
        "cannot connect to license server", "unable to checkout a license",
    ))


def check_ambiguous_requests(args, build: Path, rtl: Path) -> list[dict]:
    """Prove the live assertion rejects each unacknowledged ambiguous request.

An expected test failure earns PASS only with the exact PyUVM test, a failing
JUnit record, and its ambiguous-request diagnostic. Compilation errors cannot pass.
"""
    reports = []
    for state in "xz":
        case = build / "ambiguous_request_checks" / state
        case.mkdir(parents=True, exist_ok=True)
        results_file, coverage_file = case / "results.xml", case / "coverage.json"
        results_file.unlink(missing_ok=True)
        coverage_file.unlink(missing_ok=True)
        parameter_file = case / "parameters.json"
        parameter_file.write_text('{"WIDTH": 4, "LSB_HIGH_PRIORITY": 1}\n', encoding="utf-8")
        prefix = "-Ppriority_encoder." if args.sim == "icarus" else "-pvalue+priority_encoder."
        overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in {
            "WIDTH": "4", "LSB_HIGH_PRIORITY": "1",
        }.items())
        command = [
            args.make, "--no-print-directory", "-C", str(ROOT), "-f", "Makefile", "pyuvm",
            f"SIM={args.sim}", f"PYTHON_BIN={sys.executable}", "COCOTB_TOPLEVEL=priority_encoder",
            "COCOTB_TEST_MODULES=test_priority_encoder", f"PYUVM_TEST_DIR={TEST_DIR}",
            r"COCOTB_TEST_FILTER=^test_priority_encoder\.PriorityEncoderTest$", "COCOTB_TESTCASE=",
            f"VERILOG_SOURCES={rtl}", f"SIM_BUILD={case}", f"COCOTB_RESULTS_FILE={results_file}",
            f"CUSTOM_COMPILE_DEPS={parameter_file}", f"COMPILE_ARGS={args.compile_args} {overrides}",
            f"SIM_ARGS={args.sim_args}",
        ]
        if args.sim_bin_dir:
            variable = "VCS_BIN_DIR" if args.sim == "vcs" else "ICARUS_BIN_DIR"
            command.append(f"{variable}={args.sim_bin_dir}")
        environment = os.environ.copy()
        environment.update(
            PRIORITY_ENCODER_WIDTH="4", PRIORITY_ENCODER_LSB_HIGH_PRIORITY="1",
            PRIORITY_ENCODER_AMBIGUITY_PROBE=state, PRIORITY_ENCODER_SEED=str(args.seed),
            PRIORITY_ENCODER_RANDOM_CYCLES=str(args.random_cycles),
            PRIORITY_ENCODER_COVERAGE_FILE=str(coverage_file),
        )
        log_file = case / "simulation.log"
        with log_file.open("w", encoding="utf-8") as log:
            result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
        diagnostic = log_file.read_text(encoding="utf-8")
        detected = False
        try:
            cases = ET.parse(results_file).findall(".//testcase")
            detected = (
                len(cases) == 1 and cases[0].get("name") == "PriorityEncoderTest"
                and cases[0].get("classname") == "test_priority_encoder"
                and cases[0].find("failure") is not None and cases[0].find("skipped") is None
                and f"AssertionError: Ambiguous-request assertion failed: i_request=001{state}" in diagnostic
            )
        except (OSError, ET.ParseError):
            pass
        reports.append({
            "unknown_bit": state, "status": "PASS" if detected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
            "expected_test_failure": detected, "make_returncode": result.returncode, "log": str(log_file),
        })
        print(f"Ambiguous-request assertion {state}: {reports[-1]['status']}", flush=True)
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
            f"module priority_encoder_invalid_parameters;\npriority_encoder #({overrides}) dut ();\nendmodule\n",
            encoding="utf-8",
        )
        command = ([compiler, "-g2012", "-s", "priority_encoder_invalid_parameters", "-tnull"] if args.sim == "icarus" else
                   [compiler, "-full64", "-sverilog", "-top", "priority_encoder_invalid_parameters", "-o", str(case / "simv")])
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
    parser.add_argument("--rtl", type=Path, default=ROOT / "src/rtl/common/priority_encoder.sv")
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
        "scope": "selected_profiles" if args.case else "width_priority_matrix",
        "specification": "specs/common/mosaic-priority-encoder/README.md",
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "rtl": str(rtl),
        "profiles": [], "parameter_checks": [], "ambiguous_request_checks": [],
        "external_checks": dict.fromkeys((
            "hdl_sva", "formal", "commercial_lint", "cdc", "rdc", "dft", "vc_lp",
            "synthesis", "logical_equivalence", "physical_timing", "physical_power",
            "request_coherence_integration", "acknowledgement_retention_integration",
        ), "NOT_RUN"),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = {
            name: hashlib.sha256((TEST_DIR / name).read_bytes()).hexdigest()
            for name in ("priority_encoder_env.py", "test_priority_encoder.py", "run_priority_encoder_regression.py")
        }
        binaries = ("vcs",) if args.sim == "vcs" else ("iverilog", "vvp")
        missing = [binary for binary in binaries if shutil.which(binary, path=str(args.sim_bin_dir) if args.sim_bin_dir else None) is None]
        if missing:
            raise FileNotFoundError(f"Simulator executable(s) missing: {', '.join(missing)}")
        summary["status"] = "FAIL"
        for index, (name, width, direction) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            parameters = {"WIDTH": width, "LSB_HIGH_PRIORITY": direction,
                          "INDEX_WIDTH": max(1, (width - 1).bit_length())}
            case = build / name
            case.mkdir(parents=True, exist_ok=True)
            coverage_file, results_file = case / "coverage.json", case / "results.xml"
            log_file = case / "simulation.log"
            coverage_file.unlink(missing_ok=True)
            results_file.unlink(missing_ok=True)
            parameter_file = case / "parameters.json"
            parameter_file.write_text(json.dumps(parameters) + "\n", encoding="utf-8")
            # Leave INDEX_WIDTH derived and audit the actual binary index port.
            # Static priority direction is an elaboration-time parameter.
            prefix = "-Ppriority_encoder." if args.sim == "icarus" else "-pvalue+priority_encoder."
            compiler_parameters = {"WIDTH": str(width), "LSB_HIGH_PRIORITY": str(direction)}
            overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in compiler_parameters.items())
            command = [
                args.make, "--no-print-directory", "-C", str(ROOT), "-f", "Makefile", "pyuvm",
                f"SIM={args.sim}", f"PYTHON_BIN={sys.executable}", "COCOTB_TOPLEVEL=priority_encoder",
                "COCOTB_TEST_MODULES=test_priority_encoder", f"PYUVM_TEST_DIR={TEST_DIR}",
                r"COCOTB_TEST_FILTER=^test_priority_encoder\.PriorityEncoderTest$", "COCOTB_TESTCASE=",
                f"VERILOG_SOURCES={rtl}", f"SIM_BUILD={case}", f"COCOTB_RESULTS_FILE={results_file}",
                f"CUSTOM_COMPILE_DEPS={parameter_file}", f"COMPILE_ARGS={args.compile_args} {overrides}",
                f"SIM_ARGS={args.sim_args}",
            ]
            if args.sim_bin_dir:
                variable = "VCS_BIN_DIR" if args.sim == "vcs" else "ICARUS_BIN_DIR"
                command.append(f"{variable}={args.sim_bin_dir}")
            environment = os.environ.copy()
            environment.update(
                PRIORITY_ENCODER_WIDTH=str(width), PRIORITY_ENCODER_LSB_HIGH_PRIORITY=str(direction),
                PRIORITY_ENCODER_AMBIGUITY_PROBE="",
                PRIORITY_ENCODER_SEED=str(args.seed + index), PRIORITY_ENCODER_RANDOM_CYCLES=str(args.random_cycles),
                PRIORITY_ENCODER_COVERAGE_FILE=str(coverage_file),
            )
            print(f"Running {name}: {parameters}, seed={args.seed + index}", flush=True)
            with log_file.open("w", encoding="utf-8") as log:
                result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                cases = ET.parse(results_file).findall(".//testcase")
                if len(cases) != 1 or cases[0].get("name") != "PriorityEncoderTest" or cases[0].get("classname") != "test_priority_encoder":
                    raise ValueError("The expected PyUVM test did not run exactly once")
                if any(cases[0].find(tag) is not None for tag in ("failure", "error", "skipped")):
                    raise ValueError("The PyUVM test failed or was skipped")
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["parameters"] != parameters or not all(coverage["goals"].values()):
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
        summary["ambiguous_request_checks"] = check_ambiguous_requests(args, build, rtl)
        reports = (*summary["profiles"], *summary["parameter_checks"], *summary["ambiguous_request_checks"])
        complete = len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary["parameter_checks"]) == len(INVALID_PARAMETERS) and len(summary["ambiguous_request_checks"]) == 2
        summary["status"] = (
            "PASS" if complete and all(report["status"] == "PASS" for report in reports)
            else "NOT_RUN" if complete and any(report["status"] == "NOT_RUN" for report in reports)
            and all(report["status"] in ("PASS", "NOT_RUN") for report in reports)
            else "FAIL"
        )
        if not args.case:
            crossed = {(profile["parameters"]["WIDTH"], profile["parameters"]["LSB_HIGH_PRIORITY"])
                       for profile in summary["profiles"] if profile["status"] == "PASS"}
            selected = {(profile["parameters"]["WIDTH"], profile["parameters"]["LSB_HIGH_PRIORITY"], index)
                        for profile in summary["profiles"] if profile["status"] == "PASS"
                        for index in profile["bins"]["selected_indices"]}
            summary["matrix_goals"] = {
                "width_priority_direction_cross": crossed == {(width, direction) for _, width, direction in PROFILES},
                "selected_index_priority_direction_cross": selected == {(width, direction, index) for _, width, direction in PROFILES for index in range(width)},
            }
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"

    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Priority encoder regression could not run: {error}", file=sys.stderr)
    finally:
        summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        summary_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"Priority encoder regression {summary['status']}: {summary_file}", flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
