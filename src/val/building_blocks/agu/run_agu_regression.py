"""Native PyUVM AGU profiles, strict parameter guards and hashed evidence."""

import hashlib
import json
import shlex
import sys
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
from mosaic_uvm.regression import (
    campaign_status,
    finish_summary,
    license_unavailable,
    parameter_guard,
    parse_args,
    passed_test,
    require_simulator,
    run_simulation,
    verification_hashes,
)

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = (
    ROOT / "src/rtl/building_blocks/agu_pkg.sv",
    *(
        ROOT / f"src/rtl/common/{name}.sv"
        for name in ("counter", "dff", "operand_isolation", "write_gate")
    ),
)


def geometry(w, c, e, s, h, t, a):
    return f"w{w}_c{c}_e{e}_s{s}_h{h}_t{t}_a{a}", {
        "ADDR_WIDTH": w,
        "COUNT_WIDTH": c,
        "MAX_ELEMENT_BYTES": e,
        "SPACE_ID_WIDTH": s,
        "CHANNEL_ID_WIDTH": h,
        "CONTEXT_ID_WIDTH": t,
        "ASYNC_RESET": a,
        "MODE_WIDTH": 2,
    }


GEOMETRIES = (
    (1, 1, 1, 1, 1, 1),
    (1, 2, 2, 1, 1, 1),
    (3, 2, 2, 1, 2, 3),
    (3, 3, 1, 2, 1, 2),
    (4, 3, 16, 1, 3, 2),
    (8, 1, 16, 1, 1, 1),
    (8, 4, 1, 2, 4, 8),
    (8, 4, 2, 2, 4, 8),
    (8, 4, 4, 2, 4, 8),
    (8, 4, 8, 2, 4, 8),
    (8, 4, 16, 2, 4, 8),
    (8, 8, 16, 2, 4, 8),
    (32, 8, 16, 2, 4, 8),
    (32, 16, 16, 2, 4, 8),
    (64, 8, 16, 2, 4, 8),
    (64, 16, 16, 2, 4, 8),
)
PROFILES = tuple(geometry(*g, a) for g, a in product(GEOMETRIES, (0, 1)))
INVALID = (
    *(
        (f"{name.lower()}_{label}", {name: value})
        for name, (label, value) in product(
            (
                "ADDR_WIDTH",
                "COUNT_WIDTH",
                "SPACE_ID_WIDTH",
                "CHANNEL_ID_WIDTH",
                "CONTEXT_ID_WIDTH",
            ),
            (("zero", 0), ("negative", -1), ("x", "32'bx"), ("z", "32'bz")),
        )
    ),
    *(
        (f"element_{label}", {"MAX_ELEMENT_BYTES": value})
        for label, value in (
            ("zero", 0),
            ("negative", -1),
            ("three", 3),
            ("six", 6),
            ("x", "32'bx"),
            ("z", "32'bz"),
        )
    ),
    ("element_exceeds_address", {"ADDR_WIDTH": 3, "MAX_ELEMENT_BYTES": 16}),
    *(
        (f"reset_{label}", {"ASYNC_RESET": value})
        for label, value in (
            ("two", 2),
            ("negative", -1),
            ("x", "32'bx"),
            ("z", "32'bz"),
        )
    ),
    *(
        (f"mode_{label}", {"MODE_WIDTH": value})
        for label, value in (
            ("zero", 0),
            ("one", 1),
            ("three", 3),
            ("negative", -1),
            ("x", "32'bx"),
            ("z", "32'bz"),
        )
    ),
)


def simulate(args, build, rtl, parameters, seed):
    prefix = "-Pagu." if args.sim == "icarus" else "-pvalue+agu."
    flags = " ".join(
        shlex.quote(f"{prefix}{name}={value}") for name, value in parameters.items()
    )
    return run_simulation(
        args,
        ROOT,
        TEST_DIR,
        "agu",
        "test_agu",
        "AguTest",
        build,
        " ".join(map(str, (*DEPENDENCIES, rtl))),
        parameters=parameters,
        compile_args=f"{args.compile_args} {flags}",
        environment={
            **{f"AGU_{name}": str(value) for name, value in parameters.items()},
            "AGU_SEED": str(seed),
            "AGU_RANDOM_CYCLES": str(args.random_cycles),
            "AGU_CHECK_INTERNALS": "1",
            "AGU_HDL_ASSERTIONS": "1",
        },
    )


def main():
    args = parse_args(
        "agu",
        __doc__,
        profiles=[name for name, _ in PROFILES],
        seed=20261020,
        rtl_category="building_blocks",
    )
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    report_file = build / "summary.json"
    report_file.unlink(missing_ok=True)
    summary = {
        "status": "NOT_RUN",
        "framework": "PyUVM",
        "simulator": args.sim,
        "specification": "specs/building-blocks/mosaic-agu/README.md",
        "rtl": str(rtl),
        "scope": "selected_profiles"
        if args.case
        else "representative_address_count_element_metadata_reset_profiles",
        "started_at_utc": datetime.now(UTC).isoformat(),
        "profiles": [],
        "parameter_checks": [],
        "external_checks": dict.fromkeys(
            (
                "formal",
                "commercial_lint",
                "cdc",
                "rdc",
                "dft",
                "vc_lp",
                "technology_synthesis",
                "sequential_equivalence",
                "physical_timing",
                "physical_power",
                "mosaic_contracts",
            ),
            "NOT_RUN",
        ),
    }
    try:
        summary["rtl_sha256"] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary["dependency_sha256"] = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in DEPENDENCIES
        }
        summary["verification_sha256"] = verification_hashes(TEST_DIR)
        require_simulator(args)
        for index, (name, parameters) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            print(f"Running {name}, seed={args.seed + index}", flush=True)
            result, log, results, coverage_file = simulate(
                args, build / name, rtl, parameters, args.seed + index
            )
            report = {
                "name": name,
                "status": "FAIL",
                "parameters": parameters,
                "log": str(log),
            }
            try:
                if result.returncode:
                    raise ValueError(f"make exited with status {result.returncode}")
                passed_test(results, "AguTest", "test_agu")
                coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
                if (
                    coverage["status"] != "PASS"
                    or coverage["parameters"] != parameters
                    or not coverage["goals"]
                    or not all(coverage["goals"].values())
                    or coverage["internal_storage_assertions"] != "PASS"
                    or coverage["hdl_handshake_assertions"] != "PASS"
                ):
                    raise ValueError("Coverage or elaborated geometry did not match")
                if (
                    coverage["seed"] != args.seed + index
                    or coverage["random_transactions"] != args.random_cycles
                ):
                    raise ValueError("Random campaign settings did not match")
                report.update(
                    coverage, name=name, log=str(log), coverage=str(coverage_file)
                )
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                report["error"] = str(error)
                if license_unavailable(log.read_text(encoding="utf-8")):
                    report["status"] = "NOT_RUN"
                print("\n".join(log.read_text().splitlines()[-22:]), flush=True)
            summary["profiles"].append(report)
            print(f"{name}: {report['status']}", flush=True)
        summary["parameter_checks"] = [
            parameter_guard(
                args,
                build,
                rtl,
                "agu",
                name,
                parameters,
                "agu_parameters_must_be_valid",
                dependencies=DEPENDENCIES,
            )
            for name, parameters in INVALID
        ]
        complete = len(summary["profiles"]) == (
            len(set(args.case)) if args.case else len(PROFILES)
        ) and len(summary["parameter_checks"]) == len(INVALID)
        summary["status"] = campaign_status(
            (*summary["profiles"], *summary["parameter_checks"]), complete
        )
    except (OSError, ValueError) as error:
        summary["error"] = str(error)
        print(f"AGU regression could not run: {error}", file=sys.stderr)
    finally:
        finish_summary(report_file, summary, "AGU")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
