"""Run the lane-mask specification matrix with native four-state PyUVM tests."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from mosaic_uvm.regression import (
    campaign_status, finish_summary, license_unavailable, parse_args, passed_test, require_simulator, run_simulation, verification_hashes,
)

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
# Five required sizes plus a non-power-of-two configuration.
PROFILES = tuple((f"lanes{lanes}", lanes) for lanes in (1, 2, 3, 4, 8, 16))


def check_invalid_parameters(args, build: Path, rtl: Path) -> dict:
    """Distinguish explicit guard rejection from a known structural rejection."""
    case = build / "invalid_parameters" / "zero_lanes"
    case.mkdir(parents=True, exist_ok=True)
    wrapper = case / "invalid_parameters.sv"
    wrapper.write_text(
        '`timescale 1ns/1ps\nmodule lane_mask_invalid_parameters;\n'
        'lane_mask #(.LANES(0)) dut (.i_operation_valid(1\'b0), '
        '.i_lane_valid(2\'b0), .i_lane_mask(2\'b0), .i_lane_predicate(2\'b0), '
        '.o_lane_active(), .o_lane_isolate(), .o_lane_write_mask());\n'
        'initial begin #1; $fatal(1, "Invalid lane parameters were accepted"); end\nendmodule\n',
        encoding="utf-8",
    )
    search_path = str(args.sim_bin_dir) if args.sim_bin_dir else None
    compiler = shutil.which("vcs" if args.sim == "vcs" else "iverilog", path=search_path)
    executable = case / ("simv" if args.sim == "vcs" else "sim.vvp")
    command = ([compiler, "-g2012", "-s", "lane_mask_invalid_parameters", "-o", str(executable)]
               if args.sim == "icarus" else
               [compiler, "-full64", "-sverilog", "-top", "lane_mask_invalid_parameters", "-o", str(executable)])
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
    intended = "LANES must be greater than or equal to one"
    explicit_rejection = intended in diagnostic and (
        compiled.returncode != 0 or runtime_code is not None and runtime_code != 0
    )
    structural_rejection = args.sim == "icarus" and compiled.returncode != 0 and (
        "Concatenation repeat may not be zero in this context" in diagnostic
    )
    rejected = explicit_rejection or structural_rejection
    report = {
        "name": "zero_lanes", "parameters": {"LANES": 0},
        "status": "PASS" if rejected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
        "expected_guard": intended, "compiler_returncode": compiled.returncode,
        "runtime_returncode": runtime_code, "log": str(log_file),
        "stage": "elaboration" if rejected and compiled.returncode != 0 else "simulation_startup" if rejected else None,
        "rejection_kind": "explicit_guard" if explicit_rejection else "structural_replication" if structural_rejection else None,
        "explicit_guard_coverage": "PASS" if explicit_rejection else "BLOCKED" if structural_rejection else "NOT_RUN",
    }
    print(f"Invalid LANES=0: {report['status']} ({report['rejection_kind']})", flush=True)
    return report


def main() -> int:
    args = parse_args('lane_mask', __doc__, profiles=[name for name, _ in PROFILES], seed=20261011)
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = {
        "status": "NOT_RUN", "framework": "PyUVM", "simulator": args.sim,
        "scope": "selected_profiles" if args.case else "lane_count_matrix",
        "specification": "specs/common/mosaic-lane-mask/README.md",
        "started_at_utc": datetime.now(timezone.utc).isoformat(), "rtl": str(rtl),
        "profiles": [], "parameter_checks": [], "specification_gaps": {},
        "external_checks": dict.fromkeys((
            "hdl_sva", "formal", "lane_data_and_state_integration", "reductions",
            "stall_alignment", "operation_class_cross", "datatype_precision_cross", "clock_gating_policy",
            "commercial_lint", "cdc", "rdc", "dft", "vc_lp", "synthesis",
            "logical_equivalence", "physical_timing", "physical_power", "net_lane_energy_savings",
        ), "NOT_RUN"),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary["status"] = "FAIL"
        for index, (name, lanes) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            parameters = {"LANES": lanes}
            case = build / name
            # A changed elaboration parameter must rebuild an existing simulator.
            override = f"-Plane_mask.LANES={lanes}" if args.sim == "icarus" else f"-pvalue+lane_mask.LANES={lanes}"
            print(f'Running {name}: {parameters}, seed={args.seed + index}', flush=True)
            (result, log_file, results_file, coverage_file) = run_simulation(
                args, ROOT, TEST_DIR, 'lane_mask', 'test_lane_mask', 'LaneMaskTest', case, rtl,
                environment={
                    'LANE_MASK_LANES': str(lanes), 'LANE_MASK_SEED': str(args.seed + index),
                    'LANE_MASK_RANDOM_CYCLES': str(args.random_cycles),
                },
                compile_args=f'{args.compile_args} {override}',
                parameters=parameters,
            )
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results_file, 'LaneMaskTest', 'test_lane_mask')
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
        parameter_report = check_invalid_parameters(args, build, rtl)
        summary["parameter_checks"].append(parameter_report)
        if parameter_report["explicit_guard_coverage"] == "BLOCKED":
            summary["specification_gaps"]["explicit_parameter_guard_coverage"] = {
                "status": "BLOCKED", "reason": "Icarus rejects the zero-lane replication before the explicit RTL guard can execute",
            }
        if parameter_report["stage"] == "simulation_startup":
            summary["specification_gaps"]["strict_elaboration_parameter_validation"] = {
                "status": "BLOCKED", "reason": "The explicit RTL parameter guard uses initial fatal at simulation startup",
            }
        reports = (*summary["profiles"], *summary["parameter_checks"])
        expected_profiles = len(set(args.case)) if args.case else len(PROFILES)
        complete = len(summary["profiles"]) == expected_profiles and len(summary["parameter_checks"]) == 1
        summary["status"] = campaign_status(reports, complete)
        if not args.case:
            passed_lanes = {report["parameters"]["LANES"] for report in summary["profiles"] if report["status"] == "PASS"}
            summary["matrix_goals"] = {"all_required_and_additional_lane_counts": passed_lanes == {lanes for _, lanes in PROFILES}}
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Lane mask regression could not run: {error}", file=sys.stderr)
    finally:
        finish_summary(summary_file, summary, 'Lane mask')
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
