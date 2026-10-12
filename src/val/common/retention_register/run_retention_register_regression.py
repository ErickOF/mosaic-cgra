"""Run portable PyUVM retention, protocol, and invalid-parameter checks."""

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
WIDTHS = (1, 8, 16, 32, 64, 128)
PROFILES = tuple(
    (f"width{width}_{'async' if asynchronous else 'sync'}_{'enable' if enabled else 'noenable'}_{reset_class}",
     width, reset_class, value, asynchronous, enabled)
    for width in WIDTHS
    for reset_class, value in (("zero", 0), ("one", (1 << width)-1),
                              *(((("mixed", int(("10100101" * width)[:width], 2)),)) if width > 1 else ()))
    for asynchronous in (0,1) for enabled in (0,1)
)
INVALID_PARAMETERS = (
    ("zero_width", {"WIDTH": "0"}, "retention_register_width_must_be_greater_than_zero"),
    *((f"unknown_reset_value_{state}", {"WIDTH": "4", "RESET_VALUE": f"4'b10{state}1"},
       "retention_register_reset_value_must_be_known") for state in "xz"),
    ("invalid_async_reset", {"ASYNC_RESET": "2"}, "retention_register_async_reset_must_be_boolean"),
    ("invalid_has_enable", {"HAS_ENABLE": "2"}, "retention_register_has_enable_must_be_boolean"),
    *((f"unknown_async_reset_{state}", {"ASYNC_RESET": f"1'b{state}"},
       "retention_register_async_reset_must_be_boolean") for state in "xz"),
    *((f"unknown_has_enable_{state}", {"HAS_ENABLE": f"1'b{state}"},
       "retention_register_has_enable_must_be_boolean") for state in "xz"),
)
PROTOCOL_PROBES = (
    *((f"unknown_{field}_{state}", f"unknown_{field}") for field in ("reset", "enable", "save", "restore") for state in "xz"),
    ("save_restore_conflict", "save_restore_conflict"),
    ("enable_save", "enable_during_retention"), ("enable_restore", "enable_during_retention"),
    ("restore_without_save", "restore_without_save"), ("repeat_save", "repeat_save"),
    ("repeat_restore", "repeat_restore,restore_without_save"),
)


def license_unavailable(diagnostic: str) -> bool:
    """Recognize common checkout failures without crediting them as RTL results."""
    message = diagnostic.lower()
    return any(fragment in message for fragment in (
        "license checkout failed", "license check out failed", "no valid license",
        "cannot connect to license server", "unable to checkout a license",
    ))


def check_protocol_probes(args, build: Path, rtl: Path) -> list[dict]:
    """Require exact failing PyUVM probes and their live protocol diagnostics."""
    reports = []
    for name, expected in PROTOCOL_PROBES:
        case = build / "protocol_checks" / name
        case.mkdir(parents=True, exist_ok=True)
        results_file, coverage_file = case / "results.xml", case / "coverage.json"
        results_file.unlink(missing_ok=True)
        coverage_file.unlink(missing_ok=True)
        parameters = {"WIDTH": 8, "RESET_VALUE": 0, "ASYNC_RESET": 1, "HAS_ENABLE": 1}
        parameter_file = case / "parameters.json"
        parameter_file.write_text(json.dumps(parameters) + "\n", encoding="utf-8")
        prefix = "-Pretention_register." if args.sim == "icarus" else "-pvalue+retention_register."
        overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in parameters.items())
        command = [
            args.make, "--no-print-directory", "-C", str(ROOT), "-f", "Makefile", "pyuvm",
            f"SIM={args.sim}", f"PYTHON_BIN={sys.executable}", "COCOTB_TOPLEVEL=retention_register",
            "COCOTB_TEST_MODULES=test_retention_register", f"PYUVM_TEST_DIR={TEST_DIR}",
            r"COCOTB_TEST_FILTER=^test_retention_register\.RetentionRegisterTest$", "COCOTB_TESTCASE=",
            f"VERILOG_SOURCES={rtl}", f"SIM_BUILD={case}", f"COCOTB_RESULTS_FILE={results_file}",
            f"CUSTOM_COMPILE_DEPS={parameter_file}", f"COMPILE_ARGS={args.compile_args} {overrides}",
            f"SIM_ARGS={args.sim_args}",
        ]
        if args.sim_bin_dir:
            command.append(f"{'VCS_BIN_DIR' if args.sim == 'vcs' else 'ICARUS_BIN_DIR'}={args.sim_bin_dir}")
        environment = os.environ.copy()
        environment.update(
            RETENTION_REGISTER_WIDTH="8", RETENTION_REGISTER_RESET_VALUE="0",
            RETENTION_REGISTER_ASYNC_RESET="1", RETENTION_REGISTER_HAS_ENABLE="1",
            RETENTION_REGISTER_CHECK_IMAGE="1", RETENTION_REGISTER_PROTOCOL_PROBE=name,
            RETENTION_REGISTER_SEED=str(args.seed), RETENTION_REGISTER_RANDOM_CYCLES=str(args.random_cycles),
            RETENTION_REGISTER_COVERAGE_FILE=str(coverage_file),
        )
        log_file = case / "simulation.log"
        with log_file.open("w", encoding="utf-8") as log:
            result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
        diagnostic = log_file.read_text(encoding="utf-8")
        detected = False
        try:
            cases = ET.parse(results_file).findall(".//testcase")
            detected = (len(cases) == 1 and cases[0].get("name") == "RetentionRegisterTest"
                        and cases[0].get("classname") == "test_retention_register"
                        and cases[0].find("failure") is not None and cases[0].find("skipped") is None
                        and f"AssertionError: Protocol assertion failed: {expected}" in diagnostic)
        except (OSError, ET.ParseError):
            pass
        reports.append({"name": name, "expected_diagnostic": expected,
                        "status": "PASS" if detected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
                        "expected_test_failure": detected, "make_returncode": result.returncode, "log": str(log_file)})
        print(f"Protocol assertion {name}: {reports[-1]['status']}", flush=True)
    return reports


def check_invalid_parameters(args, build: Path, rtl: Path) -> list[dict]:
    """Require intended elaboration guards, rather than unrelated compile failures."""
    compiler = shutil.which("vcs" if args.sim == "vcs" else "iverilog",
                            path=str(args.sim_bin_dir) if args.sim_bin_dir else None)
    reports = []
    for name, parameters, expected_guard in INVALID_PARAMETERS:
        case = build / "invalid_parameters" / name
        case.mkdir(parents=True, exist_ok=True)
        # Icarus command-line defparams reject X/Z digits and can still exit
        # successfully. Put literals in source so the RTL's own guards run.
        wrapper = case / "invalid_parameters.sv"
        overrides = ", ".join(f".{key}({value})" for key, value in parameters.items())
        wrapper.write_text(
            f"module retention_register_invalid_parameters;\nretention_register #({overrides}) dut ();\nendmodule\n",
            encoding="utf-8",
        )
        command = ([compiler, "-g2012", "-s", "retention_register_invalid_parameters", "-tnull"] if args.sim == "icarus" else
                   [compiler, "-full64", "-sverilog", "-top", "retention_register_invalid_parameters", "-o", str(case / "simv")])
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
    parser.add_argument("--rtl", type=Path, default=ROOT / "src/rtl/common/retention_register.sv")
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
        "scope": "selected_profiles" if args.case else "width_reset_enable_matrix",
        "specification": "specs/common/mosaic-retention-register/README.md",
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "rtl": str(rtl),
        "profiles": [], "parameter_checks": [], "protocol_checks": [],
        "external_checks": dict.fromkeys((
            "hdl_sva", "formal", "commercial_lint", "cdc", "rdc", "dft", "vc_lp",
            "synthesis", "logical_equivalence", "physical_timing", "physical_power",
            "power_aware_simulation", "retention_supply_loss", "legal_power_state_cross",
            "approved_retention_cell_mapping", "power_sequence_integration", "physical_supply_connectivity",
        ), "NOT_RUN"),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = {
            name: hashlib.sha256((TEST_DIR / name).read_bytes()).hexdigest()
            for name in ("retention_register_env.py", "test_retention_register.py", "run_retention_register_regression.py")
        }
        binaries = ("vcs",) if args.sim == "vcs" else ("iverilog", "vvp")
        missing = [binary for binary in binaries if shutil.which(binary, path=str(args.sim_bin_dir) if args.sim_bin_dir else None) is None]
        if missing:
            raise FileNotFoundError(f"Simulator executable(s) missing: {', '.join(missing)}")
        summary["status"] = "FAIL"
        for index, (name, width, reset_class, reset_value, asynchronous, enabled) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            parameters = {"WIDTH": width, "RESET_VALUE": reset_value, "ASYNC_RESET": asynchronous, "HAS_ENABLE": enabled}
            case = build / name
            case.mkdir(parents=True, exist_ok=True)
            coverage_file, results_file = case / "coverage.json", case / "results.xml"
            log_file = case / "simulation.log"
            coverage_file.unlink(missing_ok=True)
            results_file.unlink(missing_ok=True)
            parameter_file = case / "parameters.json"
            parameter_file.write_text(json.dumps(parameters) + "\n", encoding="utf-8")
            # Sized reset literals preserve the complete value through WIDTH=128.
            # Quote apostrophes for the Make recipe shell.
            prefix = "-Pretention_register." if args.sim == "icarus" else "-pvalue+retention_register."
            compiler_parameters = {"WIDTH": str(width), "RESET_VALUE": f"{width}'h{reset_value:x}",
                                   "ASYNC_RESET": str(asynchronous), "HAS_ENABLE": str(enabled)}
            overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in compiler_parameters.items())
            command = [
                args.make, "--no-print-directory", "-C", str(ROOT), "-f", "Makefile", "pyuvm",
                f"SIM={args.sim}", f"PYTHON_BIN={sys.executable}", "COCOTB_TOPLEVEL=retention_register",
                "COCOTB_TEST_MODULES=test_retention_register", f"PYUVM_TEST_DIR={TEST_DIR}",
                r"COCOTB_TEST_FILTER=^test_retention_register\.RetentionRegisterTest$", "COCOTB_TESTCASE=",
                f"VERILOG_SOURCES={rtl}", f"SIM_BUILD={case}", f"COCOTB_RESULTS_FILE={results_file}",
                f"CUSTOM_COMPILE_DEPS={parameter_file}", f"COMPILE_ARGS={args.compile_args} {overrides}",
                f"SIM_ARGS={args.sim_args}",
            ]
            if args.sim_bin_dir:
                variable = "VCS_BIN_DIR" if args.sim == "vcs" else "ICARUS_BIN_DIR"
                command.append(f"{variable}={args.sim_bin_dir}")
            environment = os.environ.copy()
            environment.update(
                RETENTION_REGISTER_WIDTH=str(width), RETENTION_REGISTER_RESET_VALUE=str(reset_value),
                RETENTION_REGISTER_ASYNC_RESET=str(asynchronous), RETENTION_REGISTER_HAS_ENABLE=str(enabled),
                RETENTION_REGISTER_CHECK_IMAGE="1",
                RETENTION_REGISTER_PROTOCOL_PROBE="",
                RETENTION_REGISTER_SEED=str(args.seed + index), RETENTION_REGISTER_RANDOM_CYCLES=str(args.random_cycles),
                RETENTION_REGISTER_COVERAGE_FILE=str(coverage_file),
            )
            print(f"Running {name}: {parameters}, seed={args.seed + index}", flush=True)
            with log_file.open("w", encoding="utf-8") as log:
                result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                cases = ET.parse(results_file).findall(".//testcase")
                if len(cases) != 1 or cases[0].get("name") != "RetentionRegisterTest" or cases[0].get("classname") != "test_retention_register":
                    raise ValueError("The expected PyUVM test did not run exactly once")
                if any(cases[0].find(tag) is not None for tag in ("failure", "error", "skipped")):
                    raise ValueError("The PyUVM test failed or was skipped")
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["parameters"] != parameters or coverage["reset_class"] != reset_class or coverage["portable_image_assertions"] != "PASS" or not all(coverage["goals"].values()):
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
        summary["protocol_checks"] = check_protocol_probes(args, build, rtl)
        reports = (*summary["profiles"], *summary["parameter_checks"], *summary["protocol_checks"])
        complete = len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary["parameter_checks"]) == len(INVALID_PARAMETERS) and len(summary["protocol_checks"]) == len(PROTOCOL_PROBES)
        summary["status"] = (
            "PASS" if complete and all(report["status"] == "PASS" for report in reports)
            else "NOT_RUN" if complete and any(report["status"] == "NOT_RUN" for report in reports)
            and all(report["status"] in ("PASS", "NOT_RUN") for report in reports)
            else "FAIL"
        )
        if not args.case:
            crossed = {(profile["parameters"]["WIDTH"], profile["reset_class"], profile["parameters"]["ASYNC_RESET"], profile["parameters"]["HAS_ENABLE"])
                       for profile in summary["profiles"] if profile["status"] == "PASS"}
            summary["matrix_goals"] = {"width_reset_class_reset_style_enable_cross": crossed == {(width, reset_class, asynchronous, enabled) for _, width, reset_class, _, asynchronous, enabled in PROFILES}}
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"

    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Retention register regression could not run: {error}", file=sys.stderr)
    finally:
        summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        summary_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"Retention register regression {summary['status']}: {summary_file}", flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
