"""Run the counter specification matrix through the existing PyUVM Make flow."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from mosaic_uvm.regression import (
    finish_summary, parse_args, passed_test, require_simulator, run_simulation, verification_hashes,
)


# src/val/<category>/counter is four directory levels below the project root.
# Resolve from the script so direct invocations work from any directory.
ROOT = Path(__file__).resolve().parents[4]
PROFILES = (
    ("minimum_saturating", 1, 1, 0, 0),
    ("minimum_wrapping", 1, 0, 0, 0),
    ("fifo_pointer", 4, 0, 0, 0),
    ("small_event", 8, 1, 0, 0),
    ("performance", 32, 1, 0, 0),
    ("extended", 64, 1, 0, 0),
    ("async_reset", 32, 1, 1, 0),
    ("nonzero_reset", 16, 1, 0, 0x35A7),
)


def main() -> int:
    args = parse_args('counter', __doc__, profiles=[profile[0] for profile in PROFILES], seed=20261010)
    build = args.build_dir.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary_file = build / "summary.json"
    summary_file.unlink(missing_ok=True)
    rtl = args.rtl.resolve()
    summary = {
        "status": "NOT_RUN",
        "framework": "PyUVM",
        "simulator": args.sim,
        "scope": "selected_profiles" if args.case else "recommended_matrix",
        "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "specification": "specs/common/mosaic-counter/README.md",
        "rtl": str(rtl),
        "rtl_sha256": None,
        "profiles": [],
        "external_checks": {
            "formal": "NOT_RUN", "hdl_sva": "NOT_RUN",
            "commercial_static_checks": "NOT_RUN", "physical_power": "NOT_RUN",
        },
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["verification_sha256"] = verification_hashes(Path(__file__).resolve().parent)
        # Missing tools are NOT_RUN, rather than successful verification or
        # an RTL failure. Respect the same executable directory as cocotb.
        require_simulator(args)
        for index, (name, width, saturate, async_reset, reset_value) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            case_build = build / name
            parameters = {
                "WIDTH": width, "SATURATE": saturate,
                "ASYNC_RESET": async_reset, "RESET_VALUE": reset_value,
            }
            # Rewriting this dependency forces recompilation when parameter
            # overrides change, even if the same build directory is reused.
            overrides = " ".join(
                f"-Pcounter.{key}={value}" if args.sim == "icarus"
                else f"-pvalue+counter.{key}={value}"
                for key, value in parameters.items()
            )
            print(f'Running {name}: {parameters}, seed={args.seed + index}', flush=True)
            (result, log_file, results_file, coverage_file) = run_simulation(
                args, ROOT, Path(__file__).resolve().parent, 'counter', 'test_counter_spec', 'CounterSpecTest', case_build, rtl,
                environment={
                    'COUNTER_WIDTH': str(width), 'COUNTER_RESET_VALUE': str(reset_value),
                    'COUNTER_SATURATE': str(saturate), 'COUNTER_ASYNC_RESET': str(async_reset),
                    'COUNTER_SEED': str(args.seed + index), 'COUNTER_RANDOM_CYCLES': str(args.random_cycles),
                },
                compile_args=f'{args.compile_args} {overrides}',
                parameters=parameters,
            )
            report = {"status": "FAIL", "name": name, "parameters": parameters, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results_file, 'CounterSpecTest', 'test_counter_spec')
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if coverage["status"] != "PASS" or coverage["parameters"] != parameters:
                    raise ValueError("Functional coverage or parameter matching failed")
                report.update(coverage, name=name, log=str(log_file), coverage=str(coverage_file))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                report["error"] = str(error)
                print("\n".join(log_file.read_text(encoding="utf-8").splitlines()[-25:]), flush=True)
            summary["profiles"].append(report)
            print(f'{name}: {report["status"]}', flush=True)
        summary["status"] = (
            "PASS" if summary["profiles"] and all(
                report["status"] == "PASS" for report in summary["profiles"]
            ) else "FAIL"
        )
        if summary["status"] == "PASS" and not args.case:
            # The remaining specification crosses span elaborations rather
            # than cycles within one statically configured counter instance.
            boundaries = {
                (report["parameters"]["SATURATE"], boundary)
                for report in summary["profiles"]
                for boundary in ("overflow", "underflow")
                if report["events"][boundary] > 0
            }
            reset_commands = {
                (report["parameters"]["ASYNC_RESET"], command)
                for report in summary["profiles"]
                for command in report["bins"]["commands"]
            }
            width_boundaries = {
                (report["parameters"]["WIDTH"], boundary)
                for report in summary["profiles"]
                for boundary in ("overflow", "underflow")
                if report["events"][boundary] > 0
            }
            summary["matrix_goals"] = {
                "recommended_profiles": len(summary["profiles"]) == len(PROFILES),
                "boundary_saturation_cross": set(product((0, 1), ("overflow", "underflow"))) <= boundaries,
                "reset_mode_active_command_cross": set(product((0, 1), ("clear", "load", "increment", "decrement"))) <= reset_commands,
                "width_boundary_cross": set(product({profile[1] for profile in PROFILES}, ("overflow", "underflow"))) <= width_boundaries,
            }
            if not all(summary["matrix_goals"].values()):
                summary["status"] = "FAIL"
    except OSError as error:
        summary["error"] = str(error)
        print(f"Counter regression could not run: {error}", file=sys.stderr)
    finally:
        finish_summary(summary_file, summary, 'Counter')
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
