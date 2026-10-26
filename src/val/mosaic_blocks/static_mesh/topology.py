"""Executable v1 topology, route certificates, and byte-exact image schema."""

from collections import deque
from static_mesh.defaults import DEFAULTS


def bits(n):
    return max(1, (n - 1).bit_length())


def dimensions(p):
    r, c, h, tx, rx = (
        p[k]
        for k in (
            "MESH_ROWS",
            "MESH_COLS",
            "CHANNELS_PER_DIRECTION",
            "LOCAL_TX_PORTS",
            "LOCAL_RX_PORTS",
        )
    )
    n = r * c
    a = dict(
        R=r,
        C=c,
        H=h,
        TX=tx,
        RX=rx,
        N=n,
        I=tx + 4 * h,
        O=rx + 4 * h,
        D=p["LINK_DATA_WIDTH"],
        M=p["LINK_METADATA_WIDTH"],
        CD=p["CONTEXT_DEPTH"],
        W=p["CONFIG_DATA_WIDTH"],
        CI=p["CONTEXT_ID_WIDTH"],
        V=p["CONTEXT_VERSION_WIDTH"],
        K=p["KERNEL_ID_WIDTH"],
        EP=p["LINK_EPOCH_WIDTH"],
        P=p["ROUTE_PROOF_ID_WIDTH"],
        PM=p["SCHEDULE_PERIOD_MAX"],
    )
    a.update(
        B=2 * h * (r + c),
        IL=2 * h * (r * (c - 1) + (r - 1) * c),
        S=bits(a["I"]),
        OS=bits(a["O"]),
        NI=bits(n),
        RW=bits(n * a["I"]),
        AW=bits((n * a["I"] + 1) * (a["PM"] + 1) + 4),
        PW=bits(a["PM"] + 1),
    )
    a["L"] = a["IL"] + 2 * p["EXPOSE_BOUNDARY_PORTS"] * a["B"]
    a["LB"] = max(1, a["L"])
    a["LI"] = bits(a["L"])
    a["HEADER"] = 8 + 32 + a["V"] + a["K"] + a["P"] + a["PW"] + 1
    a["IMAGE"] = a["HEADER"] + n * a["O"] * (1 + a["S"]) + n * a["I"] * (a["RW"] + a["AW"])
    a["WORDS"] = (a["IMAGE"] + a["W"] - 1) // a["W"]
    a["IM"] = a["WORDS"] * a["W"]
    a["WI"] = bits(a["WORDS"])
    a["COUNTERS"] = 16 + 2 * n * (tx + rx) + 3 * a["LB"] + 4 * a["B"] + 4 * n
    a["CW"] = bits(a["COUNTERS"] + n + 1)
    return a


def links(p):
    a = dimensions(p)
    r, c, h = a["R"], a["C"], a["H"]
    result = []
    for row in range(r):
        for col in range(c - 1):
            for channel in range(h):
                left = row * c + col
                result.extend([(left, 2, channel, left + 1, 3), (left + 1, 3, channel, left, 2)])
    for row in range(r - 1):
        for col in range(c):
            for channel in range(h):
                north = row * c + col
                result.extend(
                    [(north, 1, channel, north + c, 0), (north + c, 0, channel, north, 1)]
                )
    return result


def boundary(p):
    a = dimensions(p)
    r, c, h = a["R"], a["C"], a["H"]
    return (
        [(col, 0, k) for col in range(c) for k in range(h)]
        + [((r - 1) * c + col, 1, k) for col in range(c) for k in range(h)]
        + [(row * c, 3, k) for row in range(r) for k in range(h)]
        + [(row * c + c - 1, 2, k) for row in range(r) for k in range(h)]
    )


def physical(p):
    a = dimensions(p)
    nodes = p.get("NODE_PRESENT_MASK", (1 << a["N"]) - 1)
    ins = {}
    outs = {}
    edges = []
    for index, (src, d, k, dst, arrival) in enumerate(links(p)):
        edges.append(
            dict(
                index=index,
                source_node=src,
                source_port=a["RX"] + d * a["H"] + k,
                destination_node=dst,
                destination_port=a["TX"] + arrival * a["H"] + k,
            )
        )
    if p["EXPOSE_BOUNDARY_PORTS"]:
        for b, (node, d, k) in enumerate(boundary(p)):
            edges.extend(
                [
                    dict(
                        index=a["IL"] + 2 * b,
                        boundary_input=b,
                        destination_node=node,
                        destination_port=a["TX"] + d * a["H"] + k,
                    ),
                    dict(
                        index=a["IL"] + 2 * b + 1,
                        source_node=node,
                        source_port=a["RX"] + d * a["H"] + k,
                        boundary_output=b,
                    ),
                ]
            )
    default = sum(
        1 << e["index"]
        for e in edges
        if all((nodes >> e[key]) & 1 for key in ("source_node", "destination_node") if key in e)
    )
    mask = p.get("LINK_PRESENT_MASK", default)
    for e in edges:
        if mask >> e["index"] & 1:
            if "source_node" in e:
                outs[e["source_node"], e["source_port"]] = e["index"]
            if "destination_node" in e:
                ins[e["destination_node"], e["destination_port"]] = e["index"]
    connectivity = 0
    for node in range(a["N"]):
        for out in range(a["O"]):
            for source in range(a["I"]):
                ip = source < a["TX"] or (node, source) in ins
                op = out < a["RX"] or (node, out) in outs
                incoming = (source - a["TX"]) // a["H"] if source >= a["TX"] else -1
                outgoing = (out - a["RX"]) // a["H"] if out >= a["RX"] else -1
                straight = incoming >= 0 and outgoing == (incoming ^ 1)
                turn = incoming >= 0 and outgoing >= 0 and outgoing != incoming
                legal = (
                    incoming < 0
                    or outgoing < 0
                    or straight
                    or (p["CONNECTIVITY_PROFILE"] >= 1 and turn)
                    or p["CONNECTIVITY_PROFILE"] == 2
                )
                if ((nodes >> node) & 1) and ip and op and legal:
                    connectivity |= 1 << (node * a["O"] * a["I"] + out * a["I"] + source)
    return dict(
        nodes=nodes,
        mask=mask,
        connectivity=p.get("NODE_CONNECTIVITY_MASKS", connectivity),
        edges=edges,
        inputs=ins,
        outputs=outs,
    )


def topology_id(p):
    a = dimensions(p)
    g = physical(p)
    value = 0x534D0101
    values = [p[k] for k in DEFAULTS]
    # The RTL consumes all mask bits in little-endian bit order.
    values += [(g["nodes"] >> k) & 1 for k in range(a["N"])]
    values += [(g["mask"] >> k) & 1 for k in range(a["L"])]
    values += [(g["connectivity"] >> k) & 1 for k in range(a["N"] * a["O"] * a["I"])]
    for v in values:
        value = ((value ^ v) * 16777619) & 0xFFFFFFFF
    return value


def crc32c(data):
    crc = 0xFFFFFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82F63B78 if crc & 1 else 0)
    return crc ^ 0xFFFFFFFF


def pack_fields(fields):
    value = shift = 0
    for number, width in fields:
        assert 0 <= number < 1 << width, (number, width)
        value |= number << shift
        shift += width
    return value


def image(
    p, routes, *, version=1, kernel=3, period=1, pause=0, proof=None, ranks=None, arrivals=None
):
    """Build a route certificate, rejecting physical holes, dangling paths and cycles."""
    a = dimensions(p)
    g = physical(p)
    selected = {(n, o): s for (n, o), s in routes.items()}
    used = {(n, s) for (n, _), s in selected.items()}
    graph = {node: [] for node in used}
    indegree = {node: 0 for node in used}
    for (node, out), source in selected.items():
        assert (g["connectivity"] >> (node * a["O"] * a["I"] + out * a["I"] + source)) & 1, (
            "Absent connection"
        )
        if out >= a["RX"]:
            link = g["edges"][g["outputs"][node, out]]
            if "destination_node" in link:
                target = link["destination_node"], link["destination_port"]
                assert target in used, "Dangling output"
                graph[node, source].append(target)
                indegree[target] += 1
        if source >= a["TX"]:
            link = g["edges"][g["inputs"][node, source]]
            if "source_node" in link:
                assert (link["source_node"], link["source_port"]) in selected, "Orphan input"
    queue = deque(sorted(node for node, degree in indegree.items() if not degree))
    rank = {node: 0 for node in used}
    arrival = {node: 0 for node in used}
    visited = []
    for node, source in used:
        if source >= a["TX"]:
            link = g["edges"][g["inputs"][node, source]]
            if "boundary_input" in link:
                arrival[node, source] = int(p["BOUNDARY_BUFFER_DEPTH"] > 0)
    while queue:
        node = queue.popleft()
        visited.append(node)
        for dst in graph[node]:
            rank[dst] = max(rank[dst], rank[node] + 1)
            arrival[dst] = max(arrival[dst], arrival[node] + 1)
            indegree[dst] -= 1
            if indegree[dst] == 0:
                queue.append(dst)
    assert len(visited) == len(used), "Cyclic channel dependencies"
    rank.update(ranks or {})
    arrival.update(arrivals or {})
    header = [
        (1, 8),
        (topology_id(p), 32),
        (version, a["V"]),
        (kernel, a["K"]),
        (0, a["P"]),
        (period, a["PW"]),
        (pause, 1),
    ]
    body = [(int((n, o) in selected), 1) for n in range(a["N"]) for o in range(a["O"])]
    body += [(selected.get((n, o), 0), a["S"]) for n in range(a["N"]) for o in range(a["O"])]
    body += [(rank.get((n, i), 0), a["RW"]) for n in range(a["N"]) for i in range(a["I"])]
    body += [(arrival.get((n, i), 0), a["AW"]) for n in range(a["N"]) for i in range(a["I"])]
    raw = pack_fields(header + body)
    proof_value = crc32c(raw.to_bytes(a["IM"] // 8, "little")) ^ topology_id(p)
    if proof_value == 0:
        raise ValueError("Reserved zero proof ID")
    raw |= ((proof_value if proof is None else proof) & ((1 << a["P"]) - 1)) << (
        40 + a["V"] + a["K"]
    )
    return (
        raw,
        proof_value,
        dict(routes=selected, ranks=rank, arrivals=arrival, period=period, pause=pause),
    )


def metadata(p, context, version, kernel, epoch, *, data=0, keep=None, **flags):
    a = dimensions(p)
    y = a["D"] // 8
    return pack_fields(
        [
            (context, a["CI"]),
            (version, a["V"]),
            (kernel, a["K"]),
            (epoch, a["EP"]),
            ((1 << y) - 1 if keep is None else keep, y),
        ]
        + [(flags.get(n, 0), 1) for n in ("first", "last", "row_first", "row_last", "eos", "error")]
        + [(flags.get("datatype", 0), 2)]
    )


def manifest(p):
    a = dimensions(p)
    g = physical(p)
    return dict(
        schema="mosaic-static-mesh-v1",
        parameters=p,
        dimensions=a,
        topology_id=topology_id(p),
        nodes=g["nodes"],
        links=g["mask"],
        connectivity=g["connectivity"],
        directed_edges=g["edges"],
        latency="neighbor_hops + 1 node stages; one per queued boundary",
        reverse_ready_nodes=1,
        late_stall_entries_per_internal_link=1,
        proof="strictly increasing input-resource ranks; exact scheduled arrival offsets",
        synthesis="Design Compiler (deferred)",
        physical_timing="NOT_CHARACTERIZED",
        energy="NOT_CHARACTERIZED",
    )
