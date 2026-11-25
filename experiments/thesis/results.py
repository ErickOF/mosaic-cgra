"""Validate evidence, preserve SI units, and regenerate thesis tables from JSON."""

import csv
import json
import math
from pathlib import Path
import sys

from cases import ROOT
sys.path.insert(0, str(ROOT / "flows/power"))
from summarize import saif_duration

FIELDS = ("experiment", "case_id", "workload", "case_role", "variant", "policy", "contrast", "build_id",
    "input_sha256", "seed", "rtl_status", "power_intent_status", "energy_status",
    "kernel_cycles", "kernel_time_s", "verified_outputs", "energy_kernel_j",
    "energy_per_output_j", "energy_config_j", "annotation_pct", "scenario_id", "report_path", "reason")
FIELDS += ("bct", "vct", "mst", "scratchpad_bytes", "data_width", "metadata_width",
           "wake_cycles", "off_cycles", "drain_cycles", "configuration_cycles", "reuses",
           "bank_conflict_cycles", "memory_wait_cycles", "route_hops", "domain_model")
FIELDS += ("timeline",)


def finite(value, name, *, positive=False):
    if (isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value)
            or value < 0 or positive and value == 0):
        raise ValueError(f"{name} must be finite and {'positive' if positive else 'nonnegative'}")
    return value


def energy(power, window, outputs, saif):
    """Reject full-simulation SAIFs and unannotated/invalid results, never invent joules."""
    if power["analysis"] not in ("post_route", "mapped_netlist_estimate"):
        raise ValueError("Unrecognized power analysis level")
    start, end = window["start_cycle"], window["end_cycle"]
    duration = (end - start) * finite(window["clock_period_ns"], "period", positive=True) * 1e-9
    finite(duration, "measurement window", positive=True)
    measured = saif_duration(Path(saif))
    if not math.isclose(measured, duration, rel_tol=1e-8, abs_tol=1e-15):
        raise ValueError("SAIF duration does not match the declared phase window")
    reported_duration = finite(power["duration_s"], "reported duration", positive=True)
    if not math.isclose(reported_duration, duration, rel_tol=1e-8, abs_tol=1e-15):
        raise ValueError("Power summary duration does not match the phase window")
    annotation = power["saif_annotation"]
    if finite(annotation["file_annotated_nets"], "annotated nets") == 0:
        raise ValueError("SAIF has no annotated nets")
    coverage = finite(annotation["file_annotated_percent"], "annotation percentage")
    if coverage > 100:
        raise ValueError("Annotation percentage exceeds 100")
    watts = finite(power["average_power_w"]["total"], "average power")
    joules = watts * duration
    finite(joules, "energy")
    finite(outputs, "verified useful outputs", positive=True)
    return dict(energy_kernel_j=joules, energy_per_output_j=joules / outputs,
                annotation_pct=coverage, duration_s=duration,
                analysis=power["analysis"])


def relative(reference, candidate):
    """Require equivalent work and operating conditions before forming a pair."""
    for key in ("input_sha256", "numeric_contract", "operating_point"):
        if not reference.get(key) or reference[key] != candidate.get(key):
            raise ValueError(f"Incomparable pair: {key}")
    for row in (reference, candidate):
        if row["status"]["rtl"] != "PASS" or row["status"]["energy"] != "PASS":
            raise ValueError("A comparison needs two validated functional/energy results")
    e0 = finite(reference["metrics"]["energy_kernel_j"], "reference energy", positive=True)
    t0 = finite(reference["metrics"]["kernel_time_s"], "reference time", positive=True)
    return dict(energy_saving_pct=100 * (e0 - candidate["metrics"]["energy_kernel_j"]) / e0,
                time_change_pct=100 * (candidate["metrics"]["kernel_time_s"] - t0) / t0)


def select_composition(baseline, candidates, expected_cases):
    """Equal-weight mean energy ratios, then time, VCT count and near placement."""
    valid, excluded = [], {}
    if set(baseline) != set(expected_cases):
        raise ValueError("H1 does not cover the frozen characterization set")
    for name, cases in candidates.items():
        try:
            if set(cases) != set(expected_cases):
                raise ValueError("Incomplete characterization coverage")
            energy_ratios, time_ratios = [], []
            for case_id in expected_cases:
                a, b = baseline[case_id], cases[case_id]
                relative(a, b)
                energy_ratios.append(b["metrics"]["energy_kernel_j"] /
                                     a["metrics"]["energy_kernel_j"])
                time_ratios.append(b["metrics"]["kernel_time_s"] / a["metrics"]["kernel_time_s"])
            count, placement = name.split("_")
            valid.append(dict(variant=name, mean_energy_ratio=sum(energy_ratios) / len(expected_cases),
                mean_time_ratio=sum(time_ratios) / len(expected_cases),
                vct_count=int(count[1:]), placement=placement, energy_ratios=energy_ratios,
                time_ratios=time_ratios))
        except (ValueError, KeyError) as error:
            excluded[name] = str(error)
    valid.sort(key=lambda row: (row["mean_energy_ratio"], row["mean_time_ratio"],
                               row["vct_count"], row["placement"] != "near"))
    # A missing candidate could win: incomplete coverage must not select M1*.
    return dict(status="PASS" if len(valid) == 6 and not excluded else "BLOCKED",
                selected=valid[0]["variant"] if len(valid) == 6 and not excluded else None,
                ranking=valid, excluded=excluded)


def collect(root):
    root = Path(root)
    rows = []
    for path in sorted(root.glob("runs/*/*/summary.json")):
        summary = json.loads(path.read_text())
        status = summary["status"]
        metrics = summary["metrics"]
        row = {name: summary.get(name) for name in FIELDS}
        row.update(rtl_status=status["rtl"], power_intent_status=status["power_intent"],
                   energy_status=status["energy"], report_path=str(path.relative_to(root)))
        row.update({name: metrics.get(name) for name in FIELDS if name in metrics})
        row.update(summary.get("composition", {}))
        geometry = summary.get("geometry", {})
        row.update(scratchpad_bytes=geometry.get("capacity"), data_width=geometry.get("data_width"),
                   metadata_width=geometry.get("metadata_width"))
        functional = summary.get("artifacts", {}).get("functional")
        if functional:
            try:
                if status["rtl"] != "PASS":
                    raise ValueError(summary.get("reason") or "Functional run was not accepted")
                from flavor.generate import digest as file_digest, verify_bundle
                for name, expected in summary.get("artifact_sha256", {}).items():
                    if file_digest(summary["artifacts"][name]) != expected:
                        raise ValueError(f"Artifact changed: {name}")
                verify_bundle(summary["artifacts"]["bundle"])
                raw = json.loads(Path(functional).read_text())
                if raw["status"] != "PASS":
                    raise ValueError(f"Functional phase {raw['phase']} failed")
                if raw["expected"] != raw["observed"]:
                    raise ValueError("Expected/observed output mismatch")
                if raw["memory_sha256"]["actual"] != raw["memory_sha256"]["expected"]:
                    raise ValueError("SRAM/sentinel image mismatch")
                from cases import digest
                if digest(raw["job"]) != summary["scenario_id"]:
                    raise ValueError("Workload/mapping controls differ from the run identity")
                if raw["job"]["case"]["input_sha256"] != summary["input_sha256"]:
                    raise ValueError("Input identity differs from functional evidence")
                bundle = Path(summary["artifacts"]["bundle"])
                if json.loads((bundle / "generation.json").read_text())["build_id"] != summary["build_id"]:
                    raise ValueError("Hardware bundle differs from the run identity")
                from packets import validate
                validate(json.loads((bundle / "manifest.json").read_text()), raw,
                         json.loads(Path(summary["artifacts"]["trace"]).read_text()))
                for key in FIELDS:
                    if key in raw["metrics"]:
                        row[key] = raw["metrics"][key]
                row["rtl_status"] = "PASS"
                if summary.get("experiment") == "D0":
                    from timeline import render
                    timeline = path.parent / "timeline.svg"
                    render(summary["artifacts"]["trace"], timeline,
                           f"{summary['case_id']} / {summary['policy']}")
                    row["timeline"] = str(timeline.relative_to(root))
            except (OSError, ValueError, KeyError) as error:
                row.update(rtl_status="FAIL", energy_status="BLOCKED", reason=str(error))
                for key in ("energy_kernel_j", "energy_per_output_j", "energy_config_j"):
                    row[key] = None
        if row["rtl_status"] == "PASS" and summary.get("power_evidence"):
            try:
                from flavor.generate import digest as file_digest
                for phase, entry in summary["power_evidence"].items():
                    evidence = Path(entry["path"])
                    if file_digest(evidence) != entry["sha256"]:
                        raise ValueError("Power evidence identity changed")
                    proof = json.loads(evidence.read_text())
                    paths = {}
                    for name, artifact in proof["artifacts"].items():
                        p = Path(artifact["path"])
                        p = p if p.is_absolute() else evidence.parent / p
                        if file_digest(p) != artifact["sha256"]:
                            raise ValueError(f"Power artifact changed: {name}")
                        paths[name] = p
                    power = json.loads(paths["power_summary"].read_text())
                    gate = json.loads(paths["gate_functional"].read_text())
                    values = energy(power, gate["windows"][phase],
                                    gate["metrics"]["verified_outputs"], paths["saif"])
                    if phase == "kernel":
                        row.update({k: values[k] for k in (
                            "energy_kernel_j", "energy_per_output_j", "annotation_pct")})
                        row["kernel_time_s"] = values["duration_s"]
                    else:
                        row["energy_config_j"] = values["energy_kernel_j"]
            except (OSError, ValueError, KeyError) as error:
                row.update(energy_status="BLOCKED", reason=str(error))
                for key in ("energy_kernel_j", "energy_per_output_j", "energy_config_j"):
                    row[key] = None
        rows.append(row)
    root.mkdir(parents=True, exist_ok=True)
    with (root / "results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    def cell(value):
        return "" if value is None else str(value).replace("|", "\\|").replace("\n", " ")
    lines = ["# Thesis experiment evidence", "",
        "RTL cycles and events are functional evidence. Joules require a validated, "
        "phase-matched gate-level power report. Missing measurements remain empty.", ""]
    for title, columns in (
        ("Composition and integration", ("experiment", "case_id", "variant", "bct", "vct", "mst",
            "scratchpad_bytes", "data_width", "contrast", "rtl_status",
            "verified_outputs", "kernel_cycles", "report_path")),
        ("Domains and scheduling", ("experiment", "case_id", "policy", "power_intent_status",
            "domain_model", "wake_cycles", "off_cycles", "drain_cycles", "rtl_status", "timeline", "report_path")),
        ("Energy and time (J, s)", ("experiment", "case_id", "variant", "policy",
            "energy_kernel_j", "energy_per_output_j", "energy_config_j", "kernel_time_s",
            "energy_status", "report_path")),
        ("Coverage and pending work", ("experiment", "case_id", "variant", "rtl_status",
            "energy_status", "reason", "report_path"))):
        lines += [f"## {title}", "", "| " + " | ".join(columns) + " |",
                  "| " + " | ".join("---" for _ in columns) + " |"]
        for row in rows:
            lines.append("| " + " | ".join(cell(row.get(c)) for c in columns) + " |")
        lines.append("")
    plan = root / "plan.json"
    if plan.exists():
        definitions = json.loads(plan.read_text())["experiments"]
        lines += ["## Recorded coverage and experiment prerequisites", "",
            "| Experiment | Recorded | RTL PASS | RTL FAIL | RTL BLOCKED/NOT_RUN | Energy PASS | Requirements |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
        for definition in definitions:
            selected = [r for r in rows if r["experiment"] == definition["id"]]
            counts = [sum(r["rtl_status"] == state for r in selected) for state in ("PASS", "FAIL")]
            energy_count = sum(r["energy_status"] == "PASS" for r in selected)
            lines.append("| " + " | ".join(map(cell, (definition["id"], len(selected), *counts,
                len(selected) - sum(counts), energy_count, "; ".join(definition.get("requires", []))))) + " |")
        lines.append("")
    (root / "thesis-summary.md").write_text("\n".join(lines))
    return rows
