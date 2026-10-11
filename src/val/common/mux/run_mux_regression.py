"""Run the mux specification matrix with real four-state PyUVM and coverage."""

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
CONFIGURATIONS = ((1, 1), (2, 8), (3, 16), (4, 32), (5, 64), (8, 128))
PROFILES = tuple(
    (f"inputs{inputs}_width{width}_{default_class}", inputs, width, default_class, value)
    for inputs, width in CONFIGURATIONS
    for default_class, value in (
        ("zero", 0), ("one", (1 << width) - 1),
        *(((("mixed", int(("10100101" * width)[:width], 2)),)) if width > 1 else ()),
    )
)
INVALID_PARAMETERS = (
    ("zero_inputs", {"NUM_INPUTS": "0", "DATA_WIDTH": "8"}, "mux_num_inputs_must_be_greater_than_zero"),
    ("zero_data_width", {"NUM_INPUTS": "2", "DATA_WIDTH": "0"}, "mux_data_width_must_be_greater_than_zero"),
    ("undersized_selection", {"NUM_INPUTS": "3", "SEL_WIDTH": "1"}, "mux_sel_width_must_match_num_inputs"),
    ("oversized_selection", {"NUM_INPUTS": "4", "SEL_WIDTH": "3"}, "mux_sel_width_must_match_num_inputs"),
    ("minimum_zero_selection", {"NUM_INPUTS": "1", "SEL_WIDTH": "0"}, "mux_sel_width_must_match_num_inputs"),
    *((f"unknown_default_{state}", {"NUM_INPUTS": "2", "DATA_WIDTH": "4", "DEFAULT_VALUE": f"4'b10{state}1"},
       "mux_default_value_must_be_known") for state in "xz"),
)


def license_unavailable(diagnostic: str) -> bool:
    """Recognize common checkout failures without crediting them as RTL results."""
    message = diagnostic.lower()
    return any(fragment in message for fragment in (
        "license checkout failed", "license check out failed", "no valid license",
        "cannot connect to license server", "unable to checkout a license",
    ))


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
            f"module mux_invalid_parameters;\nmux #({overrides}) dut ();\nendmodule\n",
            encoding="utf-8",
        )
        command = ([compiler, "-g2012", "-s", "mux_invalid_parameters", "-tnull"] if args.sim == "icarus" else
                   [compiler, "-full64", "-sverilog", "-top", "mux_invalid_parameters", "-o", str(case / "simv")])
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
    parser.add_argument("--rtl", type=Path, default=ROOT / "src/rtl/common/mux.sv")
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
        "scope": "selected_profiles" if args.case else "input_count_width_default_matrix",
        "specification": "specs/common/mosaic-mux/README.md",
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "rtl": str(rtl),
        "profiles": [], "parameter_checks": [],
        "external_checks": dict.fromkeys((
            "hdl_sva", "formal", "commercial_lint", "cdc", "dft", "vc_lp",
            "synthesis", "logical_equivalence", "physical_timing", "physical_power",
            "operand_isolation_integration",
        ), "NOT_RUN"),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = {
            name: hashlib.sha256((TEST_DIR / name).read_bytes()).hexdigest()
            for name in ("mux_env.py", "test_mux.py", "run_mux_regression.py")
        }
        binaries = ("vcs",) if args.sim == "vcs" else ("iverilog", "vvp")
        missing = [binary for binary in binaries if shutil.which(binary, path=str(args.sim_bin_dir) if args.sim_bin_dir else None) is None]
        if missing:
            raise FileNotFoundError(f"Simulator executable(s) missing: {', '.join(missing)}")
        summary["status"] = "FAIL"
        for index, (name, inputs, width, default_class, default_value) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            parameters = {"NUM_INPUTS": inputs, "DATA_WIDTH": width, "DEFAULT_VALUE": default_value,
                          "SEL_WIDTH": max(1, (inputs - 1).bit_length())}
            case = build / name
            case.mkdir(parents=True, exist_ok=True)
            coverage_file, results_file = case / "coverage.json", case / "results.xml"
            log_file = case / "simulation.log"
            coverage_file.unlink(missing_ok=True)
            results_file.unlink(missing_ok=True)
            parameter_file = case / "parameters.json"
            parameter_file.write_text(json.dumps(parameters) + "\n", encoding="utf-8")
            # Leave SEL_WIDTH derived, and preserve sized-literal apostrophes
            # through the Make recipe's shell without narrowing wide defaults.
            prefix = "-Pmux." if args.sim == "icarus" else "-pvalue+mux."
            compiler_parameters = {"NUM_INPUTS": str(inputs), "DATA_WIDTH": str(width),
                                   "DEFAULT_VALUE": f"{width}'h{default_value:x}"}
            overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in compiler_parameters.items())
            command = [
                args.make, "--no-print-directory", "-C", str(ROOT), "-f", "Makefile", "pyuvm",
                f"SIM={args.sim}", f"PYTHON_BIN={sys.executable}", "COCOTB_TOPLEVEL=mux",
                "COCOTB_TEST_MODULES=test_mux", f"PYUVM_TEST_DIR={TEST_DIR}",
                r"COCOTB_TEST_FILTER=^test_mux\.MuxTest$", "COCOTB_TESTCASE=",
                f"VERILOG_SOURCES={rtl}", f"SIM_BUILD={case}", f"COCOTB_RESULTS_FILE={results_file}",
                f"CUSTOM_COMPILE_DEPS={parameter_file}", f"COMPILE_ARGS={args.compile_args} {overrides}",
                f"SIM_ARGS={args.sim_args}",
            ]
            if args.sim_bin_dir:
                variable = "VCS_BIN_DIR" if args.sim == "vcs" else "ICARUS_BIN_DIR"
                command.append(f"{variable}={args.sim_bin_dir}")
            environment = os.environ.copy()
            environment.update(
                MUX_NUM_INPUTS=str(inputs), MUX_DATA_WIDTH=str(width), MUX_DEFAULT_VALUE=str(default_value),
                MUX_SEED=str(args.seed + index), MUX_RANDOM_CYCLES=str(args.random_cycles),
                MUX_COVERAGE_FILE=str(coverage_file),
            )
            print(f"Running {name}: {parameters}, seed={args.seed + index}", flush=True)
            with log_file.open("w", encoding="utf-8") as log:
                result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                cases = ET.parse(results_file).findall(".//testcase")
                if len(cases) != 1 or cases[0].get("name") != "MuxTest" or cases[0].get("classname") != "test_mux":
                    raise ValueError("The expected PyUVM test did not run exactly once")
                if any(cases[0].find(tag) is not None for tag in ("failure", "error", "skipped")):
                    raise ValueError("The PyUVM test failed or was skipped")
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["parameters"] != parameters or coverage["default_class"] != default_class or not all(coverage["goals"].values()):
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
        reports = (*summary["profiles"], *summary["parameter_checks"])
        complete = len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary["parameter_checks"]) == len(INVALID_PARAMETERS)
        summary["status"] = (
            "PASS" if complete and all(report["status"] == "PASS" for report in reports)
            else "NOT_RUN" if complete and any(report["status"] == "NOT_RUN" for report in reports)
            and all(report["status"] in ("PASS", "NOT_RUN") for report in reports)
            else "FAIL"
        )
        if not args.case:
            crossed = {(report["parameters"]["NUM_INPUTS"], report["parameters"]["DATA_WIDTH"], report["default_class"])
                       for report in summary["profiles"] if report["status"] == "PASS"}
            summary["matrix_goals"] = {"input_count_width_default_cross": crossed == {(inputs, width, default_class) for _, inputs, width, default_class, _ in PROFILES}}
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Mux regression could not run: {error}", file=sys.stderr)
    finally:
        summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        summary_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"Mux regression {summary['status']}: {summary_file}", flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
