"""Run the required write gate widths and HDL destination integrations in PyUVM."""

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
WIDTHS = (1, 2, 4, 8, 16, 32, 64, 128)
PROFILES = tuple((f"width{width}_{kind}", width, kind == "integration")
                 for width in WIDTHS for kind in ("functional", "integration"))
PROBES = (
    ("write_x", False, "Known-control assertion failed: unknown_write_enable"),
    ("write_z", False, "Known-control assertion failed: unknown_write_enable"),
    ("suppress_x", False, "Known-control assertion failed: unknown_requested_suppression"),
    ("suppress_z", False, "Known-control assertion failed: unknown_requested_suppression"),
    ("unsafe_suppression", True, "Integration safety assertion failed: suppressed architecturally required write"),
)


def test_case(results: Path):
    cases = ET.parse(results).findall(".//testcase")
    if len(cases) != 1 or cases[0].get("name") != "WriteGateTest" or cases[0].get("classname") != "test_write_gate":
        raise ValueError("The expected PyUVM test did not run exactly once")
    return cases[0]


def simulate(args, case: Path, rtl: Path, width: int, integration: bool, seed: int, probe=""):
    """Invalidate stale reports and compile each profile with explicit parameters."""
    top = "write_gate_destinations" if integration else "write_gate"
    prefix = f"-P{top}." if args.sim == "icarus" else f"-pvalue+{top}."
    sources = str(rtl) + (f" {TEST_DIR / 'write_gate_destinations.sv'}" if integration else "")
    (result, log_file, results, coverage) = run_simulation(
        args, ROOT, TEST_DIR, top, 'test_write_gate', 'WriteGateTest', case, sources,
        environment={
            'WRITE_GATE_WIDTH': str(width), 'WRITE_GATE_INTEGRATION': str(int(integration)),
            'WRITE_GATE_SEED': str(seed), 'WRITE_GATE_RANDOM_CYCLES': str(args.random_cycles),
            'WRITE_GATE_CONTROL_PROBE': probe if not integration else '',
            'WRITE_GATE_INTEGRATION_PROBE': probe if integration else '',
        },
        compile_args=f"{args.compile_args} {shlex.quote(prefix + 'WIDTH=' + str(width))}",
        parameters=dict(WIDTH=width, integration=integration),
    )
    return result.returncode, log_file, results, coverage


def invalid_width(args, build: Path, rtl: Path) -> dict:
    return parameter_guard(args, build, rtl, 'write_gate', 'zero_width', {'WIDTH': 0},
                           'write_gate_width_must_be_greater_than_zero')


def assertion_probes(args, build: Path, rtl: Path) -> list[dict]:
    reports = []
    for name, integration, expected in PROBES:
        code, log_file, results, _ = simulate(args, build / "assertion_probes" / name, rtl, 8, integration, args.seed, name)
        diagnostic = log_file.read_text(encoding="utf-8")
        detected = False
        try:
            case = test_case(results)
            detected = (code != 0 and case.find("failure") is not None and case.find("skipped") is None
                        and f"AssertionError: {expected}" in diagnostic)
        except (OSError, ValueError, ET.ParseError):
            pass
        reports.append(dict(name=name, status="PASS" if detected else "NOT_RUN" if license_unavailable(diagnostic) else "FAIL",
                            expected_test_failure=detected, make_returncode=code, log=str(log_file)))
        print(f"Assertion {name}: {reports[-1]['status']}", flush=True)
    return reports


def main() -> int:
    args = parse_args('write_gate', __doc__, profiles=[profile[0] for profile in PROFILES], seed=20261011)
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = dict(
        status="NOT_RUN", framework="PyUVM", simulator=args.sim,
        scope="selected_profiles" if args.case else "width_destination_matrix",
        specification="specs/common/mosaic-write-gate/README.md", rtl=str(rtl),
        started_at_utc=datetime.now(timezone.utc).isoformat(), profiles=[], parameter_checks=[], assertion_probes=[],
        external_checks=dict.fromkeys((
            "hdl_sva", "formal", "formal_integration", "commercial_lint", "cdc", "rdc", "dft", "vc_lp",
            "technology_synthesis", "logical_equivalence", "physical_timing", "physical_power",
            "destination_energy_savings", "system_protocol_integration",
        ), "NOT_RUN"),
    )
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary["status"] = "FAIL"
        for index, (name, width, integration) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            print(f"Running {name}, seed={args.seed + index}", flush=True)
            code, log_file, results, coverage_file = simulate(args, build / name, rtl, width, integration, args.seed + index)
            report = dict(status="FAIL", name=name, parameters={"WIDTH": width}, integration=integration, log=str(log_file))
            try:
                if code:
                    raise ValueError(f"make exited with status {code}")
                passed_test(results, 'WriteGateTest', 'test_write_gate')
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if (coverage["status"] != "PASS" or coverage["parameters"] != {"WIDTH": width}
                        or coverage["integration"] != integration or not coverage["goals"] or not all(coverage["goals"].values())):
                    raise ValueError("Coverage or elaboration settings did not match")
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
        summary["parameter_checks"] = [invalid_width(args, build, rtl)]
        summary["assertion_probes"] = assertion_probes(args, build, rtl)
        reports = (*summary["profiles"], *summary["parameter_checks"], *summary["assertion_probes"])
        complete = (len(summary["profiles"]) == (len(set(args.case)) if args.case else len(PROFILES))
                    and len(summary["parameter_checks"]) == 1 and len(summary["assertion_probes"]) == len(PROBES))
        summary["status"] = campaign_status(reports, complete)
        if not args.case:
            crossed = {(report["parameters"]["WIDTH"], report["integration"])
                       for report in summary["profiles"] if report["status"] == "PASS"}
            summary["matrix_goals"] = {"width_functional_destination_cross": crossed == set(product_matrix())}
            if summary["status"] == "PASS" and not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"Write gate regression could not run: {error}", file=sys.stderr)
    finally:
        finish_summary(summary_file, summary, 'Write gate')
    return 0 if summary["status"] == "PASS" else 1


def product_matrix():
    return ((width, integration) for width in WIDTHS for integration in (False, True))


if __name__ == "__main__":
    sys.exit(main())
