"""Run the isolation cell width/polarity/clamp matrix with real PyUVM tests."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from mosaic_uvm.regression import (
    finish_summary, license_unavailable, parameter_guard, parse_args, passed_test, require_simulator, run_simulation, verification_hashes,
)

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


def check_invalid_parameters(args, build: Path, rtl: Path) -> list[dict]:
    reports = []
    for (name, width, clamp, polarity, expected_guard) in INVALID_PARAMETERS:
        port_width = width if width else 2
        reports.append(parameter_guard(args, build, rtl, 'isolation_cell', name, {'WIDTH': width, 'CLAMP_VALUE': clamp, 'ISOLATE_ACTIVE_HIGH': polarity}, expected_guard,
                                       wrapper_source=(
        '`timescale 1ns/1ps\nmodule isolation_cell_invalid_parameters;\n'
        f'isolation_cell #(.WIDTH({width}), .CLAMP_VALUE({clamp}), '
        f'.ISOLATE_ACTIVE_HIGH(1\'b{polarity})) dut '
        f'(.i_data({port_width}\'b0), .i_isolate(1\'b0), .o_data());\n'
        'initial begin #1; $fatal(1, "Invalid isolation parameters were accepted"); end\nendmodule\n'
    ), allow_startup=True))
    return reports


def main() -> int:
    args = parse_args('isolation_cell', __doc__, profiles=[profile[0] for profile in PROFILES], seed=20261011)
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
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary["status"] = "FAIL"
        for index, (name, width, polarity, clamp_class, clamp) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            assert width >= 1 and 0 <= clamp < 1 << width
            parameters = {"WIDTH": width, "CLAMP_VALUE": clamp, "ISOLATE_ACTIVE_HIGH": polarity}
            case = build / name
            # Rewriting the dependency forces recompilation in a reused directory.
            prefix = "-Pisolation_cell." if args.sim == "icarus" else "-pvalue+isolation_cell."
            overrides = " ".join(shlex.quote(f"{prefix}{key}={parameter_literal(key, value, width)}")
                                 for key, value in parameters.items())
            print(f'Running {name}: {parameters}, seed={args.seed + index}', flush=True)
            (result, log_file, results_file, coverage_file) = run_simulation(
                args, ROOT, TEST_DIR, 'isolation_cell', 'test_isolation_cell', 'IsolationCellTest', case, rtl,
                environment={
                    'ISOLATION_CELL_WIDTH': str(width), 'ISOLATION_CELL_CLAMP_VALUE': str(clamp),
                    'ISOLATION_CELL_ACTIVE_HIGH': str(polarity), 'ISOLATION_CELL_SEED': str(args.seed + index),
                    'ISOLATION_CELL_RANDOM_CYCLES': str(args.random_cycles),
                },
                compile_args=f'{args.compile_args} {overrides}',
                parameters=parameters,
            )
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results_file, 'IsolationCellTest', 'test_isolation_cell')
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
        finish_summary(summary_file, summary, 'Isolation cell')
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
