"""Run independent disabled/enabled startup simulations of ClockGateTest."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from mosaic_uvm.regression import (
    finish_summary, parse_args, passed_test, require_simulator, run_simulation, verification_hashes,
)

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent


def main() -> int:
    args = parse_args('clock_gate', __doc__, profiles=None, seed=20261010)
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    summary = {
        "status": "NOT_RUN", "framework": "PyUVM", "simulator": args.sim,
        "specification": "specs/common/mosaic-clock-gate/README.md",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "rtl": str(rtl), "profiles": [],
        "external_checks": dict.fromkeys((
            "hdl_sva", "formal",
            "commercial_static_checks", "technology_mapping", "logical_equivalence",
            "generated_clock_sta", "physical_power",
        ), "NOT_RUN"),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        for enabled in (False, True):
            name = "startup_enabled" if enabled else "startup_disabled"
            case_build = build / name
            print(f'Running {name}, seed={args.seed + int(enabled)}', flush=True)
            (result, log_file, results_file, coverage_file) = run_simulation(
                args, ROOT, TEST_DIR, 'clock_gate', 'test_clock_gate', 'ClockGateTest', case_build, rtl,
                environment={
                    'CLOCK_GATE_STARTUP_ENABLED': str(int(enabled)),
                    'CLOCK_GATE_SEED': str(args.seed + int(enabled)),
                    'CLOCK_GATE_RANDOM_CYCLES': str(args.random_cycles),
                },
                compile_args=args.compile_args,
            )
            report = {"status": "FAIL", "name": name, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results_file, 'ClockGateTest', 'test_clock_gate')
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["startup_enabled"] != enabled:
                    raise ValueError("Functional coverage or startup matching failed")
                if coverage["random_cycles"] != args.random_cycles or coverage["seed"] != args.seed + int(enabled):
                    raise ValueError("Random campaign settings did not match")
                report.update(coverage, name=name, coverage=str(coverage_file))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                report["error"] = str(error)
                print("\n".join(log_file.read_text(encoding="utf-8").splitlines()[-25:]), flush=True)
            summary["profiles"].append(report)
            print(f"{name}: {report['status']}", flush=True)
        summary["status"] = "PASS" if len(summary["profiles"]) == 2 and all(
            profile["status"] == "PASS" for profile in summary["profiles"]
        ) else "FAIL"
    except OSError as error:
        summary["error"] = str(error)
        print(f"Clock gate regression could not run: {error}", file=sys.stderr)
    finally:
        finish_summary(summary_file, summary, 'Clock gate')
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
