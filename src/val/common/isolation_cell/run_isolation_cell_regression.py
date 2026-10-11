"""Run the isolation cell width/polarity/clamp matrix with real PyUVM tests."""

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
PROFILES = tuple(
    (f"width{width}_{'high' if polarity else 'low'}_{clamp_class}", width, polarity, clamp_class, clamp)
    for width, polarity in product(WIDTHS, (1, 0))
    for clamp_class, clamp in (
        ("zero", 0), ("one", (1 << width) - 1),
        *((("mixed", int(("10010110" * width)[:width], 2)),) if width > 1 else ()),
    )
)
INVALID_PARAMETERS = (
    ("zero_width", 0, "'0", 1, "WIDTH must be greater than or equal to one"),
    *tuple((f"clamp_{value}_{polarity}", 4, f"4'b10{value}1", polarity,
            "CLAMP_VALUE must contain only zero and one bits") for value, polarity in product(("x", "z"), (0, 1))),
)


def parameter_literal(name: str, value: int, width: int) -> str:
    if name == "CLAMP_VALUE":
        return f"{width}'h{value:x}"
    if name == "ISOLATE_ACTIVE_HIGH":
        return f"1'b{value}"
    return str(value)


def license_unavailable(diagnostic: str) -> bool:
    """Recognizable checkout failures describe an unavailable tool, not bad RTL."""
    message = diagnostic.lower()
    return any(fragment in message for fragment in (
        "license checkout failed", "license check out failed", "no valid license",
        "cannot connect to license server", "unable to checkout a license",
    ))


def check_invalid_parameters(args, build: Path, rtl: Path) -> list[dict]:
    """Require intended guard diagnostics and report the actual rejection stage."""
    search_path = str(args.sim_bin_dir) if args.sim_bin_dir else None
    compiler = shutil.which("vcs" if args.sim == "vcs" else "iverilog", path=search_path)
    reports = []
    for name, width, clamp, polarity, expected_guard in INVALID_PARAMETERS:
        case = build / "invalid_parameters" / name
        case.mkdir(parents=True, exist_ok=True)
        wrapper = case / "invalid_parameters.sv"
        port_width = width if width else 2  # WIDTH=0 declares [-1:0] in this RTL.
        wrapper.write_text(
            '`timescale 1ns/1ps\nmodule isolation_cell_invalid_parameters;\n'
            f'isolation_cell #(.WIDTH({width}), .CLAMP_VALUE({clamp}), '
            f'.ISOLATE_ACTIVE_HIGH(1\'b{polarity})) dut '
            f'(.i_data({port_width}\'b0), .i_isolate(1\'b0), .o_data());\n'
            'initial begin #1; $fatal(1, "Invalid isolation parameters were accepted"); end\nendmodule\n',
            encoding="utf-8",
        )
        executable = case / ("simv" if args.sim == "vcs" else "sim.vvp")
        command = ([compiler, "-g2012", "-s", "isolation_cell_invalid_parameters", "-o", str(executable)]
                   if args.sim == "icarus" else
                   [compiler, "-full64", "-sverilog", "-top", "isolation_cell_invalid_parameters", "-o", str(executable)])
        log_file = case / "guard.log"
        with log_file.open("w", encoding="utf-8") as log:
            compiled = subprocess.run([*command, *shlex.split(args.compile_args), str(rtl), str(wrapper)],
                                      cwd=case, stdout=log, stderr=subprocess.STDOUT)
            runtime_code = None
            if compiled.returncode == 0:
                runtime = ([shutil.which("vvp", path=search_path), str(executable)]
                           if args.sim == "icarus" else [str(executable)])
                result = subprocess.run(runtime, cwd=case, stdout=log, stderr=subprocess.STDOUT)
                runtime_code = result.returncode
        diagnostic = log_file.read_text(encoding="utf-8")
        rejected = expected_guard in diagnostic and (
            compiled.returncode != 0 or (runtime_code is not None and runtime_code != 0)
        )
        reports.append({
            "name": name, "status": "PASS" if rejected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
            "parameters": {"WIDTH": width, "CLAMP_VALUE": clamp, "ISOLATE_ACTIVE_HIGH": polarity},
            "expected_guard": expected_guard, "compiler_returncode": compiled.returncode,
            "runtime_returncode": runtime_code,
            "stage": "elaboration" if compiled.returncode != 0 and rejected else "simulation_startup" if rejected else None,
            "log": str(log_file),
        })
        print(f"Invalid parameters {name}: {reports[-1]['status']}", flush=True)
    return reports


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sim", choices=("vcs", "icarus"), default="vcs")
    parser.add_argument("--build-dir", type=Path, required=True)
    parser.add_argument("--rtl", type=Path, default=ROOT / "src/rtl/common/isolation_cell.sv")
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
        # Native guard checks change cwd; resolve executable searches first.
        args.sim_bin_dir = args.sim_bin_dir.resolve()
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = {
        "status": "NOT_RUN", "framework": "PyUVM", "simulator": args.sim,
        "scope": "selected_profiles" if args.case else "width_polarity_clamp_matrix",
        "specification": "specs/common/mosaic-isolation-cell/README.md",
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "rtl": str(rtl),
        "profiles": [], "parameter_checks": [],
        "specification_gaps": {
            "strict_elaboration_parameter_validation": "BLOCKED",
            "reason": "RTL guards use initial fatal; typed clamp/polarity parameters permit implicit resizing",
        },
        "external_checks": dict.fromkeys((
            "hdl_sva", "formal", "technology_equivalence", "upf_power_aware_simulation",
            "legal_power_state_coverage", "power_sequencing", "protocol_safe_clamp",
            "commercial_lint", "cdc", "rdc", "dft", "vc_lp", "synthesis",
            "physical_implementation", "physical_timing", "physical_power",
        ), "NOT_RUN"),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = {
            name: hashlib.sha256((TEST_DIR / name).read_bytes()).hexdigest()
            for name in ("isolation_cell_env.py", "test_isolation_cell.py", "run_isolation_cell_regression.py")
        }
        binaries = ("vcs",) if args.sim == "vcs" else ("iverilog", "vvp")
        missing = [binary for binary in binaries if shutil.which(
            binary, path=str(args.sim_bin_dir) if args.sim_bin_dir else None,
        ) is None]
        if missing:
            raise FileNotFoundError(f"Simulator executable(s) missing: {', '.join(missing)}")
        summary["status"] = "FAIL"
        for index, (name, width, polarity, clamp_class, clamp) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            assert width >= 1 and 0 <= clamp < 1 << width
            parameters = {"WIDTH": width, "CLAMP_VALUE": clamp, "ISOLATE_ACTIVE_HIGH": polarity}
            case = build / name
            case.mkdir(parents=True, exist_ok=True)
            coverage_file, results_file = case / "coverage.json", case / "results.xml"
            log_file = case / "simulation.log"
            coverage_file.unlink(missing_ok=True)
            results_file.unlink(missing_ok=True)
            parameter_file = case / "parameters.json"
            # Rewriting the dependency forces recompilation in a reused directory.
            parameter_file.write_text(json.dumps(parameters) + "\n", encoding="utf-8")
            prefix = "-Pisolation_cell." if args.sim == "icarus" else "-pvalue+isolation_cell."
            overrides = " ".join(shlex.quote(f"{prefix}{key}={parameter_literal(key, value, width)}")
                                 for key, value in parameters.items())
            command = [
                args.make, "--no-print-directory", "-C", str(ROOT), "-f", "Makefile", "pyuvm",
                f"SIM={args.sim}", f"PYTHON_BIN={sys.executable}", "COCOTB_TOPLEVEL=isolation_cell",
                "COCOTB_TEST_MODULES=test_isolation_cell", f"PYUVM_TEST_DIR={TEST_DIR}",
                r"COCOTB_TEST_FILTER=^test_isolation_cell\.IsolationCellTest$", "COCOTB_TESTCASE=",
                f"VERILOG_SOURCES={rtl}", f"SIM_BUILD={case}", f"COCOTB_RESULTS_FILE={results_file}",
                f"CUSTOM_COMPILE_DEPS={parameter_file}", f"COMPILE_ARGS={args.compile_args} {overrides}",
                f"SIM_ARGS={args.sim_args}",
            ]
            if args.sim_bin_dir:
                variable = "VCS_BIN_DIR" if args.sim == "vcs" else "ICARUS_BIN_DIR"
                command.append(f"{variable}={args.sim_bin_dir.resolve()}")
            environment = os.environ.copy()
            environment.update(
                ISOLATION_CELL_WIDTH=str(width), ISOLATION_CELL_CLAMP_VALUE=str(clamp),
                ISOLATION_CELL_ACTIVE_HIGH=str(polarity), ISOLATION_CELL_SEED=str(args.seed + index),
                ISOLATION_CELL_RANDOM_CYCLES=str(args.random_cycles), ISOLATION_CELL_COVERAGE_FILE=str(coverage_file),
            )
            print(f"Running {name}: {parameters}, seed={args.seed + index}", flush=True)
            with log_file.open("w", encoding="utf-8") as log:
                result = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT)
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                cases = ET.parse(results_file).findall(".//testcase")
                if len(cases) != 1 or cases[0].get("name") != "IsolationCellTest" or cases[0].get("classname") != "test_isolation_cell":
                    raise ValueError("The expected PyUVM test did not run exactly once")
                if any(cases[0].find(tag) is not None for tag in ("failure", "error", "skipped")):
                    raise ValueError("The PyUVM test failed or was skipped")
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["parameters"] != parameters or coverage["clamp_class"] != clamp_class:
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
        expected_profiles = len(set(args.case)) if args.case else len(PROFILES)
        summary["status"] = (
            "PASS" if len(summary["profiles"]) == expected_profiles and all(report["status"] == "PASS" for report in reports)
            else "NOT_RUN" if any(report["status"] == "NOT_RUN" for report in reports)
            and all(report["status"] in ("PASS", "NOT_RUN") for report in reports)
            else "FAIL"
        )
        if not args.case:
            crossed = {(report["parameters"]["WIDTH"], report["parameters"]["ISOLATE_ACTIVE_HIGH"], report["clamp_class"])
                       for report in summary["profiles"] if report["status"] == "PASS"}
            summary["matrix_goals"] = {"width_polarity_clamp_cross": crossed == {(width, polarity, clamp_class) for _, width, polarity, clamp_class, _ in PROFILES}}
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Isolation cell regression could not run: {error}", file=sys.stderr)
    finally:
        summary["finished_at_utc"] = datetime.now(timezone.utc).isoformat()
        summary_file.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(f"Isolation cell regression {summary['status']}: {summary_file}", flush=True)
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
