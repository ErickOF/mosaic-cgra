"""Run the MOSAIC decoder matrix and rejected-parameter elaboration checks."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from mosaic_uvm.regression import (
    finish_summary, parameter_guard, parse_args, passed_test, require_simulator, run_simulation, verification_hashes,
)

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
    return [parameter_guard(args, build, rtl, 'decoder', name,
                            {'NUM_OUTPUTS': outputs, **({'SELECT_WIDTH': width} if width is not None else {})}, expected)
            for name, outputs, width, expected in INVALID_PARAMETERS]


def main() -> int:
    args = parse_args('decoder', __doc__, profiles=[name for name, _ in PROFILES], seed=20261010)
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
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        for index, (name, outputs) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            case_build = build / name
            parameters = {"NUM_OUTPUTS": outputs, "SELECT_WIDTH": max(1, (outputs - 1).bit_length())}
            # Override only NUM_OUTPUTS: the RTL must derive SELECT_WIDTH.
            override = f"-Pdecoder.NUM_OUTPUTS={outputs}" if args.sim == "icarus" else f"-pvalue+decoder.NUM_OUTPUTS={outputs}"
            print(f'Running {name}: {parameters}, seed={args.seed + index}', flush=True)
            (result, log_file, results_file, coverage_file) = run_simulation(
                args, ROOT, TEST_DIR, 'decoder', 'test_decoder', 'DecoderTest', case_build, rtl,
                environment={
                    'DECODER_NUM_OUTPUTS': str(outputs), 'DECODER_SEED': str(args.seed + index),
                    'DECODER_RANDOM_CYCLES': str(args.random_cycles),
                },
                compile_args=f'{args.compile_args} {override}',
                parameters=parameters,
            )
            report = {"status": "FAIL", "name": name, "log": str(log_file)}
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results_file, 'DecoderTest', 'test_decoder')
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
        finish_summary(summary_file, summary, 'Decoder')
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
