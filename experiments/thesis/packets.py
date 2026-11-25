"""Recheck complete packet records before accepting extracted RTL evidence.

Metadata adaptation is intentional, but it must not conceal a malformed native
producer record, a stale context version, or a lost/reordered payload. These
checks use the saved public-port trace and submitted descriptors, so tables can
be regenerated without rerunning simulation.
"""

import sys

from cases import ROOT
sys.path.insert(0, str(ROOT / "src/val/mosaic_blocks"))
from mst.model import stream_beats


def validate(manifest, functional, trace):
    tiles = {t["id"]: t for t in manifest["tile_parameter_table"]}
    events = [e for e in trace if e["kind"] == "transfer"]

    def packets(tile, direction, port=0):
        return [e for e in events if e["tile"] == tile and e["direction"] == direction
                and e["port"] == port]

    def equal(actual, expected, label):
        if actual != expected:
            raise ValueError(f"Packet evidence mismatch: {label}")

    memory_packets = compute_packets = payloads = 0
    for ident, tile in tiles.items():
        p = tile["parameters"]
        if tile["module"] == "mst":
            for direction, transfer in (("output", 0), ("input", 1)):
                expected = []
                for entry in functional["descriptors"]:
                    d = entry["descriptor"]
                    if entry["tile"] == ident and d["mode"]["transfer"] == transfer:
                        count = d["control"]["inner_count"] * d["control"]["outer_count"]
                        expected += [meta for _, meta in stream_beats(p, d, [0] * count,
                                                                     source=transfer == 1)]
                actual = [e["metadata"] for e in packets(ident, direction)]
                equal(actual, expected, f"MST {ident} {direction} identity/format/keep/order")
                memory_packets += len(actual)
        elif tile["module"] in ("bct", "vct"):
            ci = max(1, (p["CONTEXT_DEPTH"] - 1).bit_length())
            mask = (1 << (ci + p["CONTEXT_VERSION_WIDTH"])) - 1
            tags = {side: [e["metadata"] & mask for e in packets(ident, side)]
                    for side in ("input", "output")}
            equal(tags["output"], tags["input"], f"tile {ident} context/version conservation")
            compute_packets += len(tags["output"])
    mapping = functional["schedule"]["mapping"]
    if functional["job"]["case"]["workload"] == "axpy":
        bct, vct = mapping["bct"], mapping["vct"]
        source, second = mapping["msts"]
        edges = [(source, bct, 0), (second, vct if vct is not None else bct, 1),
                 (vct if vct is not None else bct, source, 0)]
        if vct is not None:
            edges.append((bct, vct, 0))
        for producer, consumer, port in edges:
            produced = [e["data"] for e in packets(producer, "output")]
            consumed = [e["data"] for e in packets(consumer, "input", port)]
            equal(consumed, produced, f"payload/order {producer} → {consumer}:{port}")
            payloads += len(consumed)
    return dict(mst_packet_records=memory_packets, compute_packet_records=compute_packets,
                conserved_payloads=payloads)
