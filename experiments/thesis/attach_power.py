"""Attach a validated gate measurement to an existing functional experiment.

The evidence JSON is a site-generated record, not an inference from an RTL
trace. All referenced files are hashed. A successful native power report alone
does not establish correct gate execution, timing closure or workload identity.
"""

import argparse
import json
from pathlib import Path

from cases import digest
from flavor.generate import digest as file_digest, verify_bundle
from results import energy, finite


def attach(summary_path, evidence_path, *, phase="kernel"):
    summary_path, evidence_path = Path(summary_path), Path(evidence_path)
    row = json.loads(summary_path.read_text())
    proof = json.loads(evidence_path.read_text())
    if row["status"]["rtl"] != "PASS":
        raise ValueError("Functional RTL execution must pass first")
    verify_bundle(row["artifacts"]["bundle"])
    if proof["schema"] != "mosaic-thesis-gate-evidence-v1":
        raise ValueError("Unsupported gate evidence schema")
    for key in ("build_id", "input_sha256", "scenario_id"):
        if proof[key] != row[key]:
            raise ValueError(f"Gate evidence differs from the run: {key}")
    conditions = proof["operating_point"]
    required = {"technology", "library_corner", "voltage_v", "clock_period_ns", "memory_model",
                "simulator_version", "power_tool_version"}
    if not required <= conditions.keys() or any(conditions[k] in (None, "") for k in required):
        raise ValueError("Incomplete operating point/tool identities")
    finite(conditions["voltage_v"], "voltage", positive=True)
    finite(conditions["clock_period_ns"], "clock period", positive=True)
    if row.get("operating_point") and row["operating_point"] != conditions:
        raise ValueError("Configuration and kernel measurements must use one operating point")
    timing = proof["timing"]
    if timing["status"] != "PASS" or finite(timing["worst_slack_ns"], "worst slack") < 0:
        raise ValueError("The compared operating point does not close timing")
    files = proof["artifacts"]
    for name in ("netlist", "sdc", "saif", "power_summary", "gate_functional", "timing_report",
                 "activity_report", "unannotated_report"):
        if name not in files:
            raise ValueError(f"Missing gate evidence: {name}")
    resolved = {}
    for name, entry in files.items():
        path = Path(entry["path"])
        path = path if path.is_absolute() else evidence_path.parent / path
        if file_digest(path) != entry["sha256"]:
            raise ValueError(f"Gate artifact changed: {name}")
        resolved[name] = path.resolve()
    gate = json.loads(resolved["gate_functional"].read_text())
    if gate["status"] != "PASS" or digest(gate["job"]) != row["scenario_id"]:
        raise ValueError("Gate execution failed or used different inputs/controls")
    if gate["expected"] != gate["observed"] or gate["memory_sha256"]["actual"] != (
            gate["memory_sha256"]["expected"]):
        raise ValueError("Gate output or SRAM guards do not match the reference")
    window = gate["windows"][phase]
    if window is None:
        raise ValueError("Repeated runs require separate segment captures; no single phase window")
    if conditions["clock_period_ns"] != window["clock_period_ns"]:
        raise ValueError("Gate markers and operating-point clock differ")
    power = json.loads(resolved["power_summary"].read_text())
    names = ["netlist", "sdc", "saif"] + [n for n in ("sdf", "spef") if power["inputs"].get(n)]
    for name in names:
        # Compare file contents, allowing a portable record to relocate artifacts.
        if name not in resolved:
            raise ValueError(f"Power input lacks hashed evidence: {name}")
        path = Path(power["inputs"][name])
        if file_digest(path) != file_digest(resolved[name]):
            raise ValueError(f"Power analysis used another {name}")
    if power["analysis"] == "post_route" and "spef" not in resolved:
        raise ValueError("Post-route analysis requires its SPEF evidence")
    result = energy(power, window, gate["metrics"]["verified_outputs"], resolved["saif"])
    row.setdefault("power_evidence", {})[phase] = dict(path=str(evidence_path.resolve()),
        sha256=file_digest(evidence_path), artifacts=files, measurement=result)
    row["operating_point"] = conditions
    if phase == "kernel":
        row["metrics"].update({k: result[k] for k in (
            "energy_kernel_j", "energy_per_output_j", "annotation_pct")})
        row["metrics"]["kernel_time_s"] = result["duration_s"]
        row["status"]["energy"] = "PASS"
        row["reason"] = None
    else:
        row["metrics"]["energy_config_j"] = result["energy_kernel_j"]
    row["artifacts"][f"power_{phase}_evidence"] = str(evidence_path.resolve())
    row.setdefault("artifact_sha256", {})[f"power_{phase}_evidence"] = file_digest(evidence_path)
    summary_path.write_text(json.dumps(row, indent=2, allow_nan=False) + "\n")
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--phase", choices=("kernel", "configuration"), default="kernel")
    args = parser.parse_args()
    try:
        attach(args.summary, args.evidence, phase=args.phase)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(2, f"Power evidence rejected: {error}\n")
    print(args.summary)


if __name__ == "__main__":
    main()
