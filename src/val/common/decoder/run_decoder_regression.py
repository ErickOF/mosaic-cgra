"""Run the MOSAIC decoder matrix and rejected-parameter elaboration checks."""

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
PROFILES = (
    ("minimum", 1), ("binary", 2), ("non_power_of_two", 3),
    ("directional_ports", 4), ("non_power_of_two_extended", 5),
    ("register_selection", 8), ("context_selection", 16), ("large_decode", 32),
)
INVALID_PARAMETERS = (
    ("zero_outputs", 0, None, "decoder_num_outputs_must_be_greater_than_zero"),
    ("undersized_selection", 3, 1, "decoder_select_width_must_match_num_outputs"),
    ("oversized_selection", 4, 3, "decoder_select_width_must_match_num_outputs"),
    ("minimum_zero_width", 1, 0, "decoder_select_width_must_match_num_outputs"),
)


def check_invalid_parameters(args, build: Path, rtl: Path) -> list[dict]:
    """Require the intended elaboration guard, not an unrelated compile error."""
    compiler = shutil.which("vcs" if args.sim == "vcs" else "iverilog",
                            path=str(args.sim_bin_dir) if args.sim_bin_dir else None)
    reports = []
    for name, outputs, width, expected_guard in INVALID_PARAMETERS:
        case_build = build / "invalid_parameters" / name
        case_build.mkdir(parents=True, exist_ok=True)
        log_file = case_build / "elaboration.log"
        parameters = {"NUM_OUTPUTS": outputs}
        if width is not None:
            parameters["SELECT_WIDTH"] = width
        flags = [f"-Pdecoder.{key}={value}" if args.sim == "icarus"
                 else f"-pvalue+decoder.{key}={value}" for key, value in parameters.items()]
        command = (
            [compiler, "-g2012", "-s", "decoder", "-tnull"] if args.sim == "icarus"
            else [compiler, "-full64", "-sverilog", "-top", "decoder", "-o", str(case_build / "simv")]
        )
        command.extend([*shlex.split(args.compile_args), *flags, str(rtl)])
        with log_file.open("w", encoding="utf-8") as log:
            result = subprocess.run(command, cwd=case_build, stdout=log, stderr=subprocess.STDOUT)
        diagnostic = log_file.read_text(encoding="utf-8")
        rejected = result.returncode != 0 and expected_guard in diagnostic
        reports.append({
            "name": name, "status": "PASS" if rejected else "FAIL",
            "parameters": parameters, "expected_guard": expected_guard,
            "compiler_returncode": result.returncode, "log": str(log_file),
        })
        print(f"Invalid parameters {name}: {reports[-1]['status']}", flush=True)
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim", choices=("vcs", "icarus"), default="vcs")
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--rtl", type=Path, default=ROOT / "src/rtl/common/decoder.sv")
    parser.add_argument("--seed", type=int, default=20261010)
    parser.add_argument("--random-cycles", type=int, default=2000)
    parser.add_argument("--compile-args", default="")
    parser.add_argument("--sim-args", default="")
    parser.add_argument("--sim-bin-dir", type=Path)
    parser.add_argument("--make", default="make")
    parser.add_argument("--case", action="append", choices=[name for name, _ in PROFILES])
    args = parser.parse_args()
    if args.random_cycles < 1000:
        parser.error("--random-cycles must be at least 1000")
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = {
        "status": "NOT_RUN", "framework": "PyUVM", "simulator": args.sim,
        "scope": "selected_profiles" if args.case else "recommended_matrix",
        "specification": "specs/common/mosaic-decoder/README.md",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "rtl": str(rtl), "profiles": [], "parameter_checks": [],
        "external_checks": dict.fromkeys((
            "formal", "hdl_sva", "commercial_static_checks", "synthesis",
            "physical_timing", "physical_power",
        ), "NOT_RUN"),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = {
            name: hashlib.sha256((TEST_DIR / name).read_bytes()).hexdigest()
            for name in ("decoder_env.py", "test_decoder.py", "run_decoder_regression.py")
        }
        binaries = ("vcs",) if args.sim == "vcs" else ("iverilog", "vvp")
        missing = [binary for binary in binaries if shutil.which(
            binary, path=str(args.sim_bin_dir) if args.sim_bin_dir else None,
        ) is None]
        if missing:
            raise FileNotFoundError(f"Simulator executable(s) missing: {', '.join(missing)}")
        for index, (name, outputs) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            case_build = build / name
            case_build.mkdir(parents=True, exist_ok=True)
            coverage_file, results_file = case_build / "coverage.json", case_build / "results.xml"
            log_file = case_build / "simulation.log"
            coverage_file.unlink(missing_ok=True)
            results_file.unlink(missing_ok=True)
            parameters = {"NUM_OUTPUTS": outputs, "SELECT_WIDTH": max(1, (outputs - 1).bit_length())}
            parameter_file = case_build / "parameters.json"
            parameter_file.write_text(json.dumps(parameters) + "\n", encoding="utf-8")
            # Override only NUM_OUTPUTS: the RTL must derive SELECT_WIDTH.
            override = f"-Pdecoder.NUM_OUTPUTS={outputs}" if args.sim == "icarus" else f"-pvalue+decoder.NUM_OUTPUTS={outputs}"
            command = [
                args.make, "--no-print-directory", "-C", str(ROOT), "-f", "Makefile", "pyuvm",
                f"SIM={args.sim}", f"PYTHON_BIN={sys.executable}",
                "COCOTB_TOPLEVEL=decoder", "COCOTB_TEST_MODULES=test_decoder",
                f"PYUVM_TEST_DIR={TEST_DIR}", r"COCOTB_TEST_FILTER=^test_decoder\.DecoderTest$",
                "COCOTB_TESTCASE=", f"VERILOG_SOURCES={rtl}", f"SIM_BUILD={case_build}",
                f"COCOTB_RESULTS_FILE={results_file}", f"CUSTOM_COMPILE_DEPS={parameter_file}",
                f"COMPILE_ARGS={args.compile_args} {override}", f"SIM_ARGS={args.sim_args}",
            ]
            if args.sim_bin_dir:
                variable = "VCS_BIN_DIR" if args.sim == "vcs" else "ICARUS_BIN_DIR"
                command.append(f"{variable}={args.sim_bin_dir.resolve()}")
            environment = os.environ.copy()
            environment.update(
                DECODER_NUM_OUTPUTS=str(outputs), DECODER_SEED=str(args.seed + index),
                DECODER_RANDOM_CYCLES=str(args.random_cycles), DECODER_COVERAGE_FILE=str(coverage_file),
            )
            print(f"Running {name}: {parameters}, seed={args.seed + index}", flush=True)
            with log_file.open("w", encoding="utf-8") as log:
                result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
            report = {"status": "FAIL", "name": name, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                cases = ET.parse(results_file).findall(".//testcase")
                if len(cases) != 1 or cases[0].get("name") != "DecoderTest" or cases[0].get("classname") != "test_decoder":
                    raise ValueError("The expected PyUVM test did not run exactly once")
                if any(cases[0].find(tag) is not None for tag in ("failure", "error", "skipped")):
                    raise ValueError("The PyUVM test failed or was skipped")
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["parameters"] != parameters:
                    raise ValueError("Coverage or elaboration parameters did not match")
                if coverage["random_transactions"] != args.random_cycles or coverage["seed"] != args.seed + index:
                    raise ValueError("Random campaign settings did not match")
                report.update(coverage, name=name, coverage=str(coverage_file))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                report["error"] = str(error)
                print("\n".join(log_file.read_text(encoding="utf-8").splitlines()[-25:]), flush=True)
            summary["profiles"].append(report)
            print(f"{name}: {report['status']}", flush=True)
        summary["parameter_checks"] = check_invalid_parameters(args, build, rtl)
        expected_profiles = len(set(args.case)) if args.case else len(PROFILES)
        summary["status"] = "PASS" if len(summary["profiles"]) == expected_profiles and all(
            report["status"] == "PASS" for report in (*summary["profiles"], *summary["parameter_checks"])
        ) else "FAIL"
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Decoder regression could not run: {error}", file=sys.stderr)
    finally:
        summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        summary_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"Decoder regression {summary['status']}: {summary_file}", flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
