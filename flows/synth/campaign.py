#!/usr/bin/env python3
"""Plan, run, and collect MOSAIC Design Compiler synthesis campaigns."""

import argparse
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
import fnmatch
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/gen"))
sys.path.insert(0, str(ROOT / "src/gen/cluster"))

from flavor.generate import generate as generate_flavor  # noqa: E402
from flavor.model import SCHEMA as FLAVOR_SCHEMA  # noqa: E402
from flavor.model import dumps, parse, resolve  # noqa: E402


SCHEMA = "mosaic-synthesis-campaign-v1"
DEFAULT_SIZES = (2, 3, 4, 5, 6, 8, 10, 12, 16)
FAMILIES = ("bct", "vct", "sft", "mst", "cpt", "array")
APPLICATIONS = ("balanced", "ai", "scientific", "dsp_streaming", "control")

# One-factor-at-a-time sweeps keep PPA deltas attributable to one parameter.
# Every list includes the RTL default so each parameter has its own baseline.
SWEEPS = {
    "bct": {
        "DATA_WIDTH": (2, 4, 6, 8, 16, 32, 64, 128),
        "FU_PROFILE": (0, 1, 2),
        "RF_DEPTH": (4, 8, 16, 32),
        "MULTIPLY_OPERAND_WIDTH": (4, 8, 16),
        "INPUT_FIFO_DEPTH": (1, 2, 4, 8),
        "RESULT_QUEUE_DEPTH": (1, 2, 4, 8),
        "RF_PROTECTION": (0, 1, 2),
    },
    "vct": {
        "FU_PROFILE": (0, 1, 2),
        "NUM_LANES": (2, 4, 8),
        "ELEMENT_WIDTH": (4, 8, 16),
        "ACC_WIDTH": (32, 64, 128),
        "VRF_DEPTH": (2, 8, 32, 64),
        "INPUT_FIFO_DEPTH": (1, 2, 4, 8),
        "RESULT_QUEUE_DEPTH": (1, 2, 4, 8),
        "VRF_PROTECTION": (0, 1, 2),
    },
    "sft": {
        "FU_PROFILE": (0, 1, 2, 3),
        "INTERNAL_WIDTH": (24, 32, 48, 64),
        "LUT_ADDRESS_WIDTH": (4, 6, 8),
        "POLY_MAX_DEGREE": (1, 2, 3, 4),
        "REDUCTION_LANES": (1, 2, 4, 8),
        "LOCAL_RF_DEPTH": (2, 8, 16, 32),
        "TABLE_PROTECTION": (0, 1, 2),
    },
    "mst": {
        "READ_DATA_FIFO_DEPTH": (2, 4, 8, 16),
        "WRITE_DATA_FIFO_DEPTH": (2, 4, 8, 16),
        "SUPPORT_2D": (0, 1),
        "SUPPORT_UNALIGNED": (0, 1),
        "SUPPORT_ELEMENT_CONVERSION": (0, 1),
        "COMMAND_PROTECTION": (0, 1, 2),
        "FIFO_PROTECTION": (0, 1, 2),
    },
    "cpt": {
        "FU_PROFILE": (0, 1),
        "PREDICATE_LANES": (1, 4, 8, 16),
        "MAX_LOOP_DEPTH": (1, 2, 3, 4),
        "NUM_EVENTS": (1, 4, 8, 16),
        "NUM_BARRIERS": (1, 2, 3, 4),
        "MAX_OUTSTANDING_ACTIONS": (1, 2, 4, 8),
        "ACTION_QUEUE_DEPTH": (4, 8, 16),
        "CONTROL_REGISTER_DEPTH": (4, 8, 16),
        "EVENT_PROTECTION": (0, 1),
    },
}


APPLICATION_RECIPES = {
    "balanced": {
        "cycle": ("MST", "BCT", "VCT", "CPT", "SFT", "BCT", "VCT", "BCT", "MST", "BCT"),
        "parameters": {},
    },
    "ai": {
        "cycle": ("MST", "VCT", "SFT", "CPT", "VCT", "VCT", "VCT", "MST", "VCT", "BCT"),
        "parameters": {
            "BCT": {"FU_PROFILE": 2},
            "MST": {"READ_DATA_FIFO_DEPTH": 16, "WRITE_DATA_FIFO_DEPTH": 16},
            "VCT": {"FU_PROFILE": 2, "NUM_LANES": 8, "ELEMENT_WIDTH": 8,
                    "ACC_WIDTH": 32, "VRF_DEPTH": 16},
            "SFT": {"FU_PROFILE": 3},
        },
    },
    "scientific": {
        "cycle": ("MST", "BCT", "VCT", "SFT", "CPT", "BCT", "VCT", "SFT", "BCT", "VCT"),
        "parameters": {
            "BCT": {"DATA_WIDTH": 64, "MULTIPLY_OPERAND_WIDTH": 32, "FU_PROFILE": 2},
            "MST": {"READ_DATA_FIFO_DEPTH": 16, "WRITE_DATA_FIFO_DEPTH": 16},
            "VCT": {"FU_PROFILE": 2, "NUM_LANES": 4, "ELEMENT_WIDTH": 16,
                    "ACC_WIDTH": 64, "VRF_DEPTH": 16},
            "SFT": {"FU_PROFILE": 3, "INTERNAL_WIDTH": 64},
        },
    },
    "dsp_streaming": {
        "cycle": ("MST", "SFT", "VCT", "BCT", "CPT", "MST", "SFT", "VCT", "BCT", "BCT"),
        "parameters": {
            "BCT": {"FU_PROFILE": 2, "INPUT_FIFO_DEPTH": 4, "RESULT_QUEUE_DEPTH": 4},
            "MST": {"READ_DATA_FIFO_DEPTH": 16, "WRITE_DATA_FIFO_DEPTH": 16},
            "VCT": {"FU_PROFILE": 2, "NUM_LANES": 8, "ELEMENT_WIDTH": 8,
                    "ACC_WIDTH": 32, "INPUT_FIFO_DEPTH": 4, "RESULT_QUEUE_DEPTH": 4},
            "SFT": {"FU_PROFILE": 1, "INPUT_FIFO_DEPTH": 8, "RESULT_QUEUE_DEPTH": 16},
        },
    },
    "control": {
        "cycle": ("CPT", "BCT", "MST", "CPT", "VCT", "BCT", "CPT", "BCT", "MST", "SFT"),
        "parameters": {
            "BCT": {"FU_PROFILE": 0},
            "VCT": {"FU_PROFILE": 0, "NUM_LANES": 2, "SUPPORT_MUL": 0, "SUPPORT_MAC": 0},
            "SFT": {"FU_PROFILE": 0, "ENABLE_MULTIPLIER": 0, "ENABLE_POLYNOMIAL": 0},
            "CPT": {"FU_PROFILE": 1, "NUM_EVENTS": 16, "NUM_BARRIERS": 4},
        },
    },
}


NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][-+]?\d+)?"


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def json_digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def file_digest(path):
    path = Path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


@lru_cache(maxsize=1)
def source_revision():
    files = sorted((ROOT / "src/rtl").rglob("*.sv"))
    files += [ROOT / "Makefile", ROOT / "flows/synth/run.tcl",
              ROOT / "flows/synth/campaign.py", ROOT / "src/constraints/timing.sdc"]
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(ROOT)).encode() + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def split_choices(text, valid, name):
    values = tuple(value.strip().lower() for value in text.split(",") if value.strip())
    if values == ("all",):
        return tuple(valid)
    unknown = sorted(set(values) - set(valid))
    if unknown:
        raise ValueError(f"Unknown {name}: {', '.join(unknown)}")
    return values


def parse_sizes(text):
    try:
        values = tuple(int(value) for value in text.split(",") if value.strip())
    except ValueError as error:
        raise ValueError("Sizes must be comma-separated integers") from error
    if not values or any(value < 1 for value in values):
        raise ValueError("Sizes must be positive integers")
    return values


def scratchpad_geometry(tile_count):
    if tile_count <= 16:
        return 8, 128
    if tile_count <= 36:
        return 8, 512
    if tile_count <= 100:
        return 16, 1024
    return 16, 2048


def flavor_document(application, size):
    recipe = APPLICATION_RECIPES[application]
    banks, words = scratchpad_geometry(size * size)
    tiles = []
    for tile_id in range(size * size):
        kind = recipe["cycle"][tile_id % len(recipe["cycle"])]
        tile = {
            "id": tile_id,
            "class": kind,
            "row": tile_id // size,
            "col": tile_id % size,
        }
        parameters = recipe["parameters"].get(kind)
        if parameters:
            tile["parameters"] = dict(parameters)
        tiles.append(tile)
    document = {
        "schema": FLAVOR_SCHEMA,
        "name": f"{application}_{size}x{size}",
        "cluster": {
            "schema": "mosaic-cluster-v1",
            "profile": "Configurable",
            "cluster_id": 0,
            "rows": size,
            "cols": size,
            "context_depth": 4,
            "scratchpad_banks": banks,
            "scratchpad_bank_words": words,
            "clock_gating": True,
            "lifecycle_timeout": 65535,
            "tiles": tiles,
        },
    }
    resolve(document)
    return document


def tile_cases(families):
    cases = []
    for family in families:
        if family == "array":
            continue
        for parameter, values in SWEEPS[family].items():
            for value in values:
                parameters = {parameter: value}
                companions = {}
                # Keep dependent geometry legal while the named parameter is swept.
                if family == "bct" and parameter == "DATA_WIDTH" and value < 32:
                    companions["MULTIPLY_OPERAND_WIDTH"] = value // 2
                if family == "vct" and parameter == "ELEMENT_WIDTH" and value == 4:
                    companions["WRITE_SLICE_WIDTH"] = 4
                if family == "cpt" and parameter == "PREDICATE_LANES":
                    companions["PREDICATE_WIDTH"] = value
                parameters.update(companions)
                cases.append({
                    "id": f"tile-{family}-{parameter.lower().replace('_', '-')}-{value}",
                    "scope": "tile",
                    "family": family,
                    "top": family,
                    "sweep_parameter": parameter,
                    "sweep_value": value,
                    "parameters": parameters,
                    "companion_parameters": companions,
                })
    return cases


def array_cases(families, applications, sizes):
    if "array" not in families:
        return []
    cases = []
    for application in applications:
        for size in sizes:
            document = flavor_document(application, size)
            resolved, _ = resolve(document)
            counts = {kind: 0 for kind in ("BCT", "VCT", "SFT", "MST", "CPT")}
            for tile in document["cluster"]["tiles"]:
                counts[tile["class"]] += 1
            cases.append({
                "id": f"array-{application.replace('_', '-')}-{size}x{size}",
                "scope": "array",
                "family": "array",
                "top": "cluster",
                "application": application,
                "rows": size,
                "cols": size,
                "tile_count": size * size,
                "tile_counts": counts,
                "flavor_name": document["name"],
                "architecture_id": json_digest(resolved),
            })
    return cases


def make_plan(args):
    families = split_choices(args.families, FAMILIES, "families")
    applications = split_choices(args.applications, APPLICATIONS, "applications")
    sizes = parse_sizes(args.sizes)
    cases = tile_cases(families) + array_cases(families, applications, sizes)
    if args.case_pattern:
        cases = [case for case in cases if fnmatch.fnmatch(case["id"], args.case_pattern)]
    if not cases:
        raise ValueError("The campaign filters selected no cases")
    for case in cases:
        case["case_fingerprint"] = json_digest(case)
    return {
        "schema": SCHEMA,
        "strategy": "one-factor-at-a-time tile sweeps plus application-oriented arrays",
        "families": list(families),
        "applications": list(applications),
        "sizes": list(sizes),
        "case_count": len(cases),
        "source_revision": source_revision(),
        "cases": cases,
    }


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def materialize_plan(plan, output):
    output.mkdir(parents=True, exist_ok=True)
    flavor_dir = output / "flavors"
    flavor_dir.mkdir(exist_ok=True)
    for case in plan["cases"]:
        if case["scope"] != "array":
            continue
        document = flavor_document(case["application"], case["rows"])
        flavor_path = flavor_dir / f"{case['id']}.toml"
        flavor_path.write_text(dumps(document))
        case["flavor_file"] = str(flavor_path.relative_to(output))
    write_json(output / "plan.json", plan)


def extract_number(text, patterns, flags=re.I | re.M):
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return float(match.group(1))
    return None


def extract_integer(text, patterns):
    value = extract_number(text, patterns)
    return int(value) if value is not None else None


def power_to_watts(value, unit):
    scale = {
        "w": 1.0,
        "mw": 1e-3,
        "uw": 1e-6,
        "nw": 1e-9,
        "pw": 1e-12,
        "fw": 1e-15,
    }
    return value * scale[unit.lower().replace("\u00b5", "u")]


def extract_power(text, label):
    match = re.search(rf"{label}\s*=\s*({NUMBER})\s*([munpf\u00b5]?W)\b", text, re.I)
    if not match:
        match = re.search(rf"{label}\s+({NUMBER})\s*([munpf\u00b5]?W)\b", text, re.I)
    return power_to_watts(float(match.group(1)), match.group(2)) if match else None


def read_report(report_dir, top, suffix):
    path = report_dir / f"{top}_{suffix}.rpt"
    return path.read_text(errors="replace") if path.is_file() else ""


def parse_reports(run_dir, top):
    report_dir = run_dir / "reports"
    area = read_report(report_dir, top, "area")
    timing = read_report(report_dir, top, "timing")
    power = read_report(report_dir, top, "power")
    qor = read_report(report_dir, top, "qor")
    units = read_report(report_dir, top, "units")

    metrics = {
        "area_total": extract_number(area, [rf"^\s*Total cell area:\s*({NUMBER})",
                                                   rf"^\s*Total area:\s*({NUMBER})"]),
        "area_combinational": extract_number(area, [rf"^\s*Combinational area:\s*({NUMBER})"]),
        "area_noncombinational": extract_number(area, [rf"^\s*Noncombinational area:\s*({NUMBER})"]),
        "cell_count": extract_integer(area, [r"^\s*Number of cells:\s*(\d+)",
                                                     r"^\s*Number of leaf cells:\s*(\d+)"]),
        "timing_wns": extract_number(qor, [rf"Critical Path Slack:\s*({NUMBER})",
                                                   rf"WNS[^\n:]*:\s*({NUMBER})"]),
        "timing_tns": extract_number(qor, [rf"Total Negative Slack:\s*({NUMBER})",
                                                   rf"TNS[^\n:]*:\s*({NUMBER})"]),
        "timing_violating_paths": extract_integer(qor, [r"No\. of Violating Paths:\s*(\d+)",
                                                               r"Violating Paths:\s*(\d+)"]),
        "critical_path_delay": extract_number(qor, [rf"Critical Path Length:\s*({NUMBER})"]),
        "power_dynamic_w": extract_power(power, "Total Dynamic Power"),
        "power_leakage_w": extract_power(power, "Cell Leakage Power"),
    }
    if metrics["timing_wns"] is None:
        slacks = re.findall(rf"slack\s*\((?:MET|VIOLATED)\)\s*({NUMBER})", timing, re.I)
        if slacks:
            metrics["timing_wns"] = min(float(value) for value in slacks)
    dynamic = metrics["power_dynamic_w"]
    leakage = metrics["power_leakage_w"]
    metrics["power_total_w"] = (dynamic or 0.0) + (leakage or 0.0) \
        if dynamic is not None or leakage is not None else None
    metrics["timing_met"] = metrics["timing_wns"] >= 0 \
        if metrics["timing_wns"] is not None else None

    time_match = re.search(r"Time(?:\s+unit|_unit)?\s*[:=]\s*([^\r\n]+)", units, re.I)
    metrics["time_unit"] = time_match.group(1).strip() if time_match \
        else "technology_library_unit"
    metrics["area_unit"] = "technology_library_area_unit"
    metrics["power_unit"] = "W"
    required = {
        "area": bool(area),
        "timing": bool(timing or qor),
        "power": bool(power),
    }
    parsed = {
        "area": metrics["area_total"] is not None,
        "timing": metrics["timing_wns"] is not None,
        "power": dynamic is not None or leakage is not None,
    }
    return metrics, required, parsed


def execution_identity(case, args, revision):
    def setup(path):
        if not path:
            return None
        resolved = Path(path).resolve()
        return {"path": str(resolved), "sha256": file_digest(resolved)}

    return json_digest({
        "case_fingerprint": case["case_fingerprint"],
        "source_revision": revision,
        "technology": setup(args.tech_setup),
        "dc_setup": setup(args.dc_setup),
        "constraints": setup(args.constraints),
        "dc_shell": args.dc_shell,
        "clock_period": args.clock_period,
    })


def synth_command(case, args, output, run_dir):
    command = shlex.split(args.make) + ["--no-print-directory", "-C", str(ROOT)]
    command += [
        f"COCOTB_TOPLEVEL={case['top']}",
        f"SYNTH_BUILD={run_dir}",
        f"TECH_SETUP_TCL={Path(args.tech_setup).resolve()}",
        f"DC_SHELL={args.dc_shell}",
        f"SYNTH_CLOCK_PERIOD={args.clock_period}",
        f"SYNTH_CPUS={args.synth_cpus}",
    ]
    if args.dc_setup:
        command.append(f"DC_SETUP_TCL={Path(args.dc_setup).resolve()}")
    if args.constraints:
        command.append(f"SYNTH_CONSTRAINTS={Path(args.constraints).resolve()}")
    if case["scope"] == "tile":
        assignments = ",".join(f"{name}={value}" for name, value in case["parameters"].items())
        command.append(f"SYNTH_PARAMETERS={assignments}")
    else:
        flavor_path = output / case["flavor_file"]
        document = parse(flavor_path.read_text())
        bundle, record = generate_flavor(document, output / "bundles")
        sources = [str((bundle / line.strip()).resolve())
                   for line in (bundle / "sources.f").read_text().splitlines() if line.strip()]
        command.append(f"VERILOG_SOURCES={' '.join(sources)}")
        case["bundle"] = str(bundle)
        case["architecture_id"] = record["architecture_id"]
        case["build_id"] = record["build_id"]
    command.append("synth")
    return command


def case_result(case, output, returncode=None, elapsed_seconds=None):
    run_dir = output / "runs" / case["id"]
    recorded_case = run_dir / "case.json"
    stale = False
    if recorded_case.is_file():
        previous = json.loads(recorded_case.read_text())
        stale = any(case.get(field) is not None and previous.get(field) != case.get(field)
                    for field in ("case_fingerprint", "execution_id"))
        if not stale:
            case = dict(case) | previous
    metrics, reports, parsed = parse_reports(run_dir, case["top"])
    state_path = run_dir / "run.json"
    state = json.loads(state_path.read_text()) if state_path.is_file() else {}
    if returncode is None:
        returncode = state.get("returncode")
    if elapsed_seconds is None:
        elapsed_seconds = state.get("elapsed_seconds")
    if stale:
        status = "stale"
    elif state.get("status") == "running":
        status = "incomplete"
    elif returncode not in (None, 0):
        status = "failed"
    elif not any(reports.values()) and returncode is None:
        status = "not_run"
    elif not all(reports.values()):
        status = "incomplete"
    elif not all(parsed.values()):
        status = "parse_error"
    else:
        status = "success"
    result = dict(case)
    result.update(metrics)
    result.update({
        "status": status,
        "returncode": returncode,
        "elapsed_seconds": elapsed_seconds,
        "run_dir": str(run_dir),
        "reports_present": reports,
        "metrics_parsed": parsed,
    })
    return result


def run_case(case, args, output):
    run_dir = output / "runs" / case["id"]
    if "execution_id" not in case:
        case["execution_id"] = execution_identity(case, args, source_revision())
    existing = case_result(case, output)
    if existing["status"] == "success" and not args.force:
        return existing
    run_dir.mkdir(parents=True, exist_ok=True)
    write_json(run_dir / "case.json", case)
    command = synth_command(case, args, output, run_dir)
    write_json(run_dir / "case.json", case)
    started_at = utc_now()
    write_json(run_dir / "command.json", {"argv": command, "started_at": started_at})
    write_json(run_dir / "run.json", {"status": "running", "started_at": started_at})
    started = datetime.now(timezone.utc)
    with (run_dir / "run.log").open("w") as log:
        completed = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                                   check=False, text=True)
    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    state = {
        "status": "finished",
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
        "finished_at": utc_now(),
    }
    write_json(run_dir / "run.json", state)
    result = case_result(case, output, completed.returncode, elapsed)
    write_json(run_dir / "result.json", result)
    return result


def csv_value(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return value


def write_results(output, results):
    write_json(output / "results.json", {"schema": SCHEMA, "results": results})
    preferred = [
        "id", "status", "scope", "family", "application", "rows", "cols", "tile_count",
        "sweep_parameter", "sweep_value", "parameters", "area_total", "area_combinational",
        "area_noncombinational", "area_unit", "cell_count", "timing_wns", "timing_tns",
        "timing_violating_paths", "critical_path_delay", "time_unit", "timing_met",
        "power_dynamic_w", "power_leakage_w", "power_total_w", "power_unit",
        "elapsed_seconds", "returncode", "run_dir",
    ]
    all_fields = set().union(*(result.keys() for result in results)) if results else set()
    fields = [field for field in preferred if field in all_fields]
    fields += sorted(all_fields - set(fields) - {"reports_present", "metrics_parsed"})
    with (output / "results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for result in results:
            writer.writerow({key: csv_value(value) for key, value in result.items()})
    write_summary(output / "summary.md", results)


def range_text(values, digits=6):
    numbers = [value for value in values if isinstance(value, (int, float)) and math.isfinite(value)]
    return "-" if not numbers else f"{min(numbers):.{digits}g} .. {max(numbers):.{digits}g}"


def write_summary(path, results):
    statuses = {}
    for result in results:
        statuses[result["status"]] = statuses.get(result["status"], 0) + 1
    lines = ["# MOSAIC synthesis campaign", "", f"Cases: {len(results)}", "",
             "## Status", "", "| Status | Cases |", "|---|---:|"]
    for status, count in sorted(statuses.items()):
        lines.append(f"| {status} | {count} |")
    lines += ["", "## PPA ranges", "",
              "| Group | Successful | Area | WNS | Total power (W) |",
              "|---|---:|---:|---:|---:|"]
    groups = {}
    for result in results:
        if result["status"] != "success":
            continue
        group = result.get("application") or result["family"].upper()
        groups.setdefault(group, []).append(result)
    for group, members in sorted(groups.items()):
        lines.append("| {} | {} | {} | {} | {} |".format(
            group, len(members), range_text([item.get("area_total") for item in members]),
            range_text([item.get("timing_wns") for item in members]),
            range_text([item.get("power_total_w") for item in members])))
    lines += ["", "Area and timing use the units reported by the target technology library.",
              "Power is normalized to watts. DC power is vectorless unless the technology setup supplies activity.", ""]
    path.write_text("\n".join(lines))


def collect(plan, output):
    results = [case_result(case, output) for case in plan["cases"]]
    write_results(output, results)
    return results


def common_arguments(parser):
    parser.add_argument("--output", type=Path, default=ROOT / "build/synth/campaign",
                        help="Campaign output directory")
    parser.add_argument("--families", default="all",
                        help="Comma-separated bct,vct,sft,mst,cpt,array or all")
    parser.add_argument("--applications", default="all",
                        help="Comma-separated application flavors or all")
    parser.add_argument("--sizes", default=",".join(str(value) for value in DEFAULT_SIZES),
                        help="Comma-separated square array dimensions")
    parser.add_argument("--case-pattern", help="Shell-style case ID filter")


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan", help="Validate and write the campaign without running DC")
    common_arguments(plan)

    run = commands.add_parser("run", help="Plan, synthesize, and collect the selected cases")
    common_arguments(run)
    run.add_argument("--tech-setup", required=True, type=Path,
                     help="Readable Tcl file that configures target_library/link_library")
    run.add_argument("--dc-setup", type=Path, help="Optional site-specific DC setup Tcl")
    run.add_argument("--constraints", type=Path, help="Optional synthesis constraints Tcl/SDC")
    run.add_argument("--dc-shell", default="dc_shell")
    run.add_argument("--make", default="make", help="Make executable or command")
    run.add_argument("--clock-period", type=float, default=4.0)
    run.add_argument("--synth-cpus", type=int, default=4)
    run.add_argument("--jobs", type=int, default=1,
                     help="Concurrent DC jobs. Keep at one unless licenses permit more")
    run.add_argument("--force", action="store_true", help="Rerun successful cases")

    collect_parser = commands.add_parser("collect", help="Reparse reports for an existing plan")
    collect_parser.add_argument("--output", type=Path, default=ROOT / "build/synth/campaign")
    return parser


def validate_run_arguments(args):
    if not args.tech_setup.is_file():
        raise ValueError(f"Technology setup is not readable: {args.tech_setup}")
    for name in ("dc_setup", "constraints"):
        path = getattr(args, name)
        if path and not path.is_file():
            raise ValueError(f"{name.replace('_', ' ').title()} is not readable: {path}")
    if args.jobs < 1 or args.synth_cpus < 1 or args.clock_period <= 0:
        raise ValueError("jobs, synth-cpus, and clock-period must be positive")


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        if args.command == "collect":
            plan_path = output / "plan.json"
            if not plan_path.is_file():
                raise ValueError(f"Campaign plan not found: {plan_path}")
            plan = json.loads(plan_path.read_text())
            results = collect(plan, output)
            print(f"Collected {len(results)} cases into {output / 'results.csv'}")
            return 1 if any(result["status"] in ("failed", "incomplete", "parse_error")
                            for result in results) else 0

        plan = make_plan(args)
        if args.command == "plan":
            materialize_plan(plan, output)
            print(f"Planned {plan['case_count']} cases in {output / 'plan.json'}")
            return 0

        validate_run_arguments(args)
        for case in plan["cases"]:
            case["execution_id"] = execution_identity(case, args, plan["source_revision"])
        materialize_plan(plan, output)
        results = []
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = {executor.submit(run_case, dict(case), args, output): case
                       for case in plan["cases"]}
            for future in as_completed(futures):
                case = futures[future]
                try:
                    result = future.result()
                except Exception as error:  # Preserve the rest of a long campaign.
                    result = dict(case, status="failed", error=str(error), returncode=-1)
                    run_dir = output / "runs" / case["id"]
                    write_json(run_dir / "run.json", {
                        "returncode": -1,
                        "finished_at": utc_now(),
                        "error": str(error),
                    })
                    write_json(run_dir / "result.json", result)
                results.append(result)
                print(f"[{result['status']}] {case['id']}", flush=True)
        results = collect(plan, output)
        failures = [result for result in results if result["status"] != "success"]
        print(f"Collected {len(results)} cases into {output / 'results.csv'}")
        return 1 if failures else 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    raise SystemExit(main())
