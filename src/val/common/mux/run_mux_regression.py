"""Run the mux specification matrix with real four-state PyUVM and coverage."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from mosaic_uvm.regression import (
    campaign_status, finish_summary, license_unavailable, parameter_guard, parse_args, passed_test, require_simulator, run_simulation, verification_hashes,
)

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


def check_invalid_parameters(args, build: Path, rtl: Path) -> list[dict]:
    return [parameter_guard(args, build, rtl, 'mux', name, parameters, expected)
            for name, parameters, expected in INVALID_PARAMETERS]


def main() -> int:
    args = parse_args('mux', __doc__, profiles=[profile[0] for profile in PROFILES], seed=20261011)
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
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary["status"] = "FAIL"
        for index, (name, inputs, width, default_class, default_value) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            parameters = {"NUM_INPUTS": inputs, "DATA_WIDTH": width, "DEFAULT_VALUE": default_value,
                          "SEL_WIDTH": max(1, (inputs - 1).bit_length())}
            case = build / name
            # Leave SEL_WIDTH derived, and preserve sized-literal apostrophes
            # through the Make recipe's shell without narrowing wide defaults.
            prefix = "-Pmux." if args.sim == "icarus" else "-pvalue+mux."
            compiler_parameters = {"NUM_INPUTS": str(inputs), "DATA_WIDTH": str(width),
                                   "DEFAULT_VALUE": f"{width}'h{default_value:x}"}
            overrides = " ".join(shlex.quote(f"{prefix}{key}={value}") for key, value in compiler_parameters.items())
            print(f'Running {name}: {parameters}, seed={args.seed + index}', flush=True)
            (result, log_file, results_file, coverage_file) = run_simulation(
                args, ROOT, TEST_DIR, 'mux', 'test_mux', 'MuxTest', case, rtl,
                environment={
                    'MUX_NUM_INPUTS': str(inputs), 'MUX_DATA_WIDTH': str(width),
                    'MUX_DEFAULT_VALUE': str(default_value), 'MUX_SEED': str(args.seed + index),
                    'MUX_RANDOM_CYCLES': str(args.random_cycles),
                },
                compile_args=f'{args.compile_args} {overrides}',
                parameters=parameters,
            )
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results_file, 'MuxTest', 'test_mux')
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
        summary["status"] = campaign_status(reports, complete)
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
        finish_summary(summary_file, summary, 'Mux')
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
