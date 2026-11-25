"""Deterministic hardware, workloads and independent integer references."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/gen"))
from flavor.model import starter


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def campaign():
    return tomllib.loads(Path(__file__).with_name("campaign.toml").read_text())


def architecture(variant="M", *, rows=4, cols=4):
    """Rank VCT positions by distance to the nearest fixed MST, then row/column.

    H and every M candidate have identical memory and effective link widths.
    BCT payloads are explicitly 128 bits so a packed vector can traverse a BCT
    pass context without truncation. This differs from the preliminary 32-bit BCT.
    """
    plan = campaign()
    msts = [tuple(p) for p in plan["mst_positions"]] if (rows, cols) == (4, 4) else [
        (0, 0), (rows - 1, cols - 1)]
    if rows * cols < 4 or len(set(msts)) != 2:
        raise ValueError("The diagnostic grid needs at least four positions and two MSTs")
    positions = [(r, c) for r in range(rows) for c in range(cols) if (r, c) not in msts]
    count, placement = (0, "near") if variant == "H" else (4, "near") if variant == "M" else (
        int(variant.split("_")[0][1:]), variant.split("_")[1])
    if count > len(positions) - 1 or placement not in ("near", "far"):
        raise ValueError("Composition must retain at least one BCT and a valid placement")
    distance = lambda p: min(abs(p[0] - m[0]) + abs(p[1] - m[1]) for m in msts)
    ranked = sorted(positions, key=lambda p: (
        distance(p) if placement == "near" else -distance(p), *p))
    vectors = set(ranked[:count])
    document = starter()
    document["name"] = f"thesis_{variant.lower()}_{rows}x{cols}"
    d = document["cluster"]
    d.update(rows=rows, cols=cols, scratchpad_banks=plan["scratchpad_banks"],
             scratchpad_bank_words=plan["scratchpad_bank_words"])
    d["tiles"] = []
    for r in range(rows):
        for c in range(cols):
            kind = "MST" if (r, c) in msts else "VCT" if (r, c) in vectors else "BCT"
            params = dict(DATA_WIDTH=128, FU_PROFILE=2) if kind == "BCT" else (
                dict(FU_PROFILE=2) if kind == "VCT" else {})
            d["tiles"].append(dict(id=r * cols + c, row=r, col=c,
                                   **{"class": kind}, parameters=params))
    return document


def wrap(value, width):
    return value & ((1 << width) - 1)


def reference(workload, x, y=(), *, coefficient=-3, coefficients=(2, -1, 3)):
    """Unbounded integer arithmetic followed by declared 32-bit wrap semantics."""
    if workload == "axpy":
        if len(x) != len(y):
            raise ValueError("AXPY requires equally sized arrays")
        return [wrap(coefficient * a + b, 32) for a, b in zip(x, y, strict=True)]
    if workload == "copy":
        return [wrap(a, 32) for a in x]
    if workload == "dot":
        if len(x) != len(y):
            raise ValueError("Dot product requires equally sized arrays")
        return [wrap(sum(a * b for a, b in zip(x, y, strict=True)), 32)]
    if workload == "fir":
        return [wrap(sum(k * x[i - j] for j, k in enumerate(coefficients) if i >= j), 32)
                for i in range(len(x))]
    raise ValueError(f"Unknown workload: {workload}")


def workload(family, count, *, role="characterization", seed=None, lanes=4,
             source_stride=8, destination_stride=12):
    plan = campaign()
    seed = plan["seed"] if seed is None else seed
    rng = random.Random(seed)
    x = [rng.randrange(-16, 16) for _ in range(count)]
    y = [rng.randrange(-1000, 1000) for _ in range(count)]
    spec = plan["workloads"][family]
    result = dict(case_id=f"{family}_{count}", workload=family, case_role=role, seed=seed,
        count=count, x=x, y=y if family in ("axpy", "dot") else [], lanes=lanes,
        element_width=spec.get("element_width", 32), signed=True, accumulator_width=32,
        overflow="wrap", coefficient=spec.get("coefficient", -3),
        coefficients=spec.get("coefficients", [2, -1, 3]),
        memory=dict(x_base=64, y_base=512, output_base=1024, sentinel=0xA5,
                    source_stride=source_stride, destination_stride=destination_stride))
    result["expected"] = reference(family, x, y, coefficient=result["coefficient"],
                                    coefficients=result["coefficients"])
    # Input identity excludes hardware, policy, placement and observed results.
    result["input_sha256"] = digest(result)
    return result


def scenarios(experiment, *, lanes=4):
    full = workload("axpy", 2 * lanes, lanes=lanes)
    tail = workload("axpy", 2 * lanes + 1, lanes=lanes)
    copy = workload("copy", 8, lanes=lanes)
    if experiment == "E0":
        return [dict(case=deepcopy(case), policy="always_on", backpressure=stalled)
                for case in (full, tail, copy) for stalled in (False, True)]
    if experiment == "D0":
        return [dict(case=deepcopy(case), policy=policy, backpressure=True)
                for case in (copy, tail) for policy in ("always_on", "phase_aware")]
    if experiment == "E3":
        return [dict(case=case, policy="always_on", backpressure=False) for case in (full, tail)]
    if experiment == "E4":
        # bank = floor(byte_address / 8) mod 8 for this physical SRAM geometry.
        return [dict(case=workload("copy", 8, source_stride=stride,
                                  destination_stride=stride), policy="always_on",
                     bank_pattern=label, backpressure=True)
                for label, stride in (("distributed", 8), ("concentrated", 64))]
    if experiment == "E5":
        return [dict(case=deepcopy(tail), policy="always_on", route=route, backpressure=True)
                for route in ("short", "detour")]
    if experiment == "E6":
        return [dict(case=deepcopy(tail), policy="always_on", monitor=enabled,
                     backpressure=False) for enabled in (False, True)]
    if experiment == "E7":
        return [dict(case=deepcopy(tail), policy="always_on", residency=mode,
                     repetitions=3, backpressure=False) for mode in ("reload", "resident")]
    return []
