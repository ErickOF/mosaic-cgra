"""Repository-local packet ABI, descriptors and executable physical topology."""

from static_mesh.topology import crc32c, pack_fields
from configuration_network.defaults import DEFAULTS, TABLE_WIDTHS

ALIASES = {
    "NUM_MASTERS": "NM",
    "NUM_ENDPOINTS": "NE",
    "NUM_TILE_ENDPOINTS": "NT",
    "NUM_INFRA_ENDPOINTS": "NF",
    "TREE_BRANCH_FACTOR": "BF",
    "CONFIG_DATA_WIDTH": "D",
    "CONFIG_FLIT_WIDTH": "F",
    "ENDPOINT_ID_WIDTH": "EI",
    "ENDPOINT_TYPE_WIDTH": "ET",
    "COMMAND_WIDTH": "C",
    "CONTEXT_ID_WIDTH": "CI",
    "CONTEXT_VERSION_WIDTH": "V",
    "OWNER_ID_WIDTH": "OW",
    "KERNEL_ID_WIDTH": "K",
    "PACKAGE_ID_WIDTH": "P",
    "CONFIG_EPOCH_WIDTH": "EP",
    "TRANSACTION_ID_WIDTH": "TI",
    "TAG_WIDTH": "TG",
    "WORD_INDEX_WIDTH": "WI",
    "BYTE_STROBE_WIDTH": "BY",
    "COMMAND_QUEUE_DEPTH": "CQ",
    "RESPONSE_QUEUE_DEPTH": "RQ",
    "BRANCH_BUFFER_DEPTH": "BQ",
    "ENDPOINT_QUEUE_DEPTH": "EQ",
    "MAX_OUTSTANDING_TRANSACTIONS": "NS",
}
CMD = [
    ("command", "C"),
    ("transaction", "TI"),
    ("tag", "TG"),
    ("owner", "OW"),
    ("kernel", "K"),
    ("package_id", "P"),
    ("epoch", "EP"),
    ("context_id", "CI"),
    ("version", "V"),
    ("word_index", "WI"),
    ("write_data", "D"),
    ("strobe", "BY"),
    ("image_crc", "32"),
    ("destination", "NE"),
    ("master", "MI"),
    ("sequence_id", "32"),
    ("protocol", "8"),
    ("flags", "8"),
]
RSP = [
    ("command", "C"),
    ("transaction", "TI"),
    ("tag", "TG"),
    ("endpoint", "EI"),
    ("context_id", "CI"),
    ("version", "V"),
    ("read_data", "D"),
    ("image_crc", "32"),
    ("epoch", "EP"),
    ("status", "4"),
    ("error_code", "8"),
    ("sequence_id", "32"),
    ("protocol", "8"),
    ("prepared", "1"),
    ("committed", "1"),
]


def dimensions(p):
    a = {v: p[k] for k, v in ALIASES.items()}
    a.update(
        MI=max(1, (a["NM"] - 1).bit_length()),
        OC=a["NS"].bit_length(),
        SI=max(1, (a["NS"] - 1).bit_length()),
        CAP=1 << a["C"],
    )
    a["CB"] = sum(eval(w, {}, a) for _, w in CMD)
    a["RB"] = sum(eval(w, {}, a) for _, w in RSP)
    a["CP"] = (a["CB"] + 32 + a["F"] - 1) // a["F"] * a["F"]
    a["RP"] = (a["RB"] + 32 + a["F"] - 1) // a["F"] * a["F"]
    a["CF"], a["RF"] = a["CP"] // a["F"], a["RP"] // a["F"]
    a["CX"], a["RX"] = (
        max(1, (a["CF"] - 1).bit_length()),
        max(1, (a["RF"] - 1).bit_length()),
    )
    a["ENV"] = a["NE"] + a["TI"] + a["EP"] + 32 + a["MI"]
    a["FL"], a["RL"] = a["F"] + 3 + a["CX"] + a["ENV"], a["F"] + 3 + a["RX"] + a["ENV"]
    return a


def tables(p):
    if all(n in p for n in TABLE_WIDTHS):
        return {n: p[n] for n in TABLE_WIDTHS}
    a = dimensions(p)
    values = dict(
        ENDPOINT_PRESENT_MASK=(1 << a["NE"]) - 1,
        ENDPOINT_TYPE_TABLE=pack_fields(
            [(int(e >= a["NT"]), a["ET"]) for e in range(a["NE"])]
        ),
        ENDPOINT_ID_TABLE=pack_fields([(e, a["EI"]) for e in range(a["NE"])]),
        ENDPOINT_CAPABILITY_TABLE=pack_fields(
            [
                ((0x1FE if p["SUPPORT_READBACK"] else 0x1FA), a["CAP"])
                for _ in range(a["NE"])
            ]
        ),
        ENDPOINT_PERMISSION_TABLE=pack_fields(
            [(15 << a["OW"], a["OW"] + 4) for _ in range(a["NE"])]
        ),
        ENDPOINT_CLOCK_DOMAIN_TABLE=0,
        ENDPOINT_WORD_COUNT_TABLE=pack_fields([(4, 32) for _ in range(a["NE"])]),
        ENDPOINT_CONTEXT_DEPTH_TABLE=pack_fields([(4, 32) for _ in range(a["NE"])]),
        ENDPOINT_SCHEMA_TABLE=pack_fields([(4, 32) for _ in range(a["NE"])]),
        MULTICAST_GROUP_TABLE=(1 << (a["NE"] * a["NE"])) - 1,
        COMMIT_DOMAIN_TABLE=0,
    )
    return values | {n: p[n] for n in TABLE_WIDTHS if n in p}


def endpoint(p, e):
    a = dimensions(p)
    t = tables(p)
    return dict(
        present=bool(t["ENDPOINT_PRESENT_MASK"] >> e & 1),
        id=t["ENDPOINT_ID_TABLE"] >> (e * a["EI"]) & ((1 << a["EI"]) - 1),
        type=t["ENDPOINT_TYPE_TABLE"] >> (e * a["ET"]) & ((1 << a["ET"]) - 1),
        capabilities=t["ENDPOINT_CAPABILITY_TABLE"] >> (e * a["CAP"])
        & ((1 << a["CAP"]) - 1),
        permission=t["ENDPOINT_PERMISSION_TABLE"] >> (e * (a["OW"] + 4))
        & ((1 << (a["OW"] + 4)) - 1),
        words=t["ENDPOINT_WORD_COUNT_TABLE"] >> (e * 32) & 0xFFFFFFFF,
        contexts=t["ENDPOINT_CONTEXT_DEPTH_TABLE"] >> (e * 32) & 0xFFFFFFFF,
        schema=t["ENDPOINT_SCHEMA_TABLE"] >> (e * 32) & 0xFFFFFFFF,
    )


def packet(p, values, response=False):
    a = dimensions(p)
    fields = RSP if response else CMD
    width = a["RP" if response else "CP"]
    body = pack_fields([(values.get(n, 0), eval(w, {}, a)) for n, w in fields])
    crc = (
        crc32c(body.to_bytes((width - 32) // 8, "little"))
        if p["ENABLE_PACKET_CRC"]
        else 0
    )
    return body | crc << (width - 32)


def topology(p):
    """Actual parent, child, route and pipeline tables; no software-visible tree IDs."""
    a = dimensions(p)
    n = a["NE"]
    b = a["BF"]
    capacity = b
    while capacity < n:
        capacity *= b
    if p["TOPOLOGY_PROFILE"] == 0:
        capacity = n
        internal = max(1, n - 1)

        def parent(node):
            return node - 1 if node < internal else min(node - internal, internal - 1)
    else:
        internal = (capacity - 1) // (b - 1)

        def parent(node):
            return (node - 1) // b

    total = internal + capacity
    parents = [-1] + [parent(j) for j in range(1, total)]
    children = [[] for _ in range(total)]
    for node in range(1, total):
        children[parents[node]].append(node)
    routes = [0] * total
    depths = []
    for e in range(n):
        node = internal + e
        depth = 0
        while True:
            if endpoint(p, e)["present"]:
                routes[node] |= 1 << e
            if node == 0:
                break
            node = parents[node]
            depth += 1
        depths.append(depth)
    return dict(
        parents=parents,
        children=children,
        routes=routes,
        pipeline=[int(j != 0 and bool(routes[j])) for j in range(total)],
        depths=depths,
        internal=internal,
        diameter=max(depths),
    )


def preflight(p, r, epoch, safe):
    a = dimensions(p)
    mask = r["destination_mask"]
    cmd = r["command"]
    selected = mask.bit_count()
    if r["protocol"] != 1 or r["flags"] & 0xFE:
        return 1
    if r["epoch"] != epoch:
        return 10
    if cmd > 10 or cmd == 8:
        return 2
    if 1 <= cmd <= 7 and not mask:
        return 3
    if cmd in (2, 5) and selected != 1:
        return 3
    groups = tables(p)["MULTICAST_GROUP_TABLE"]
    compatible = any(
        not mask & ~(groups >> (g * a["NE"]) & ((1 << a["NE"]) - 1))
        for g in range(a["NE"])
    )
    if selected > 1 and (not p["SUPPORT_MULTICAST"] or not compatible):
        return 3
    if cmd == 2 and not p["SUPPORT_READBACK"]:
        return 4
    if (cmd == 0 or cmd >= 9) and mask:
        return 3
    schemas = set()
    for e in range(a["NE"]):
        d = endpoint(p, e)
        if not mask >> e & 1 or not d["present"]:
            continue
        if not d["capabilities"] >> cmd & 1:
            return 4
        rights = d["permission"] >> a["OW"]
        owner = d["permission"] & ((1 << a["OW"]) - 1)
        if r["owner_id"] != owner and not (
            r["flags"] & 1 and rights & 8 and r["owner_id"] == 0
        ):
            return 5
        if (
            cmd == 1
            and not rights & 2
            or cmd == 2
            and not rights & 1
            or cmd >= 3
            and not rights & 4
        ):
            return 5
        if not safe >> e & 1:
            return 19
        if r["context_id"] >= d["contexts"]:
            return 8
        if cmd in (1, 2) and r["word_index"] >= d["words"]:
            return 7
        if cmd == 1:
            schemas.add(d["schema"])
            if len(schemas) > 1:
                return 6
    return 0


def published_parameters(parameters):
    """Keep generated tables portable without Python's decimal digit limit."""
    from configuration_network.defaults import TABLE_WIDTHS

    return {
        name: hex(value) if name in TABLE_WIDTHS else value
        for name, value in parameters.items()
    }
