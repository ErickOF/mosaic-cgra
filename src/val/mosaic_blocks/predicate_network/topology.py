"""Executable predicate v1 contract built on the shared mesh geometry."""

from static_mesh.defaults import DEFAULTS as MESH_DEFAULTS
from static_mesh.topology import (
    physical as mesh_physical,
    dimensions as mesh_dimensions,
    crc32c,
    pack_fields,
)
from predicate_network.defaults import DEFAULTS


def mesh_parameters(p):
    q = MESH_DEFAULTS | dict(
        MESH_ROWS=p["NETWORK_ROWS"],
        MESH_COLS=p["NETWORK_COLS"],
        CHANNELS_PER_DIRECTION=p["CHANNELS_PER_DIRECTION"],
        LOCAL_TX_PORTS=p["LOCAL_TX_PORTS"],
        LOCAL_RX_PORTS=p["LOCAL_RX_PORTS"],
        LINK_DATA_WIDTH=2 * p["PREDICATE_WIDTH"],
        LINK_METADATA_WIDTH=p["PREDICATE_METADATA_WIDTH"],
        CONNECTIVITY_PROFILE=min(p["CONNECTIVITY_PROFILE"], 1),
        EXPOSE_BOUNDARY_PORTS=p["EXPOSE_BOUNDARY_PORTS"],
        BOUNDARY_BUFFER_DEPTH=1,
        SUPPORT_MULTICAST=p["SUPPORT_MULTICAST"],
        MAX_MULTICAST_FANOUT=p["MAX_MULTICAST_FANOUT"],
        SCHEDULE_PERIOD_MAX=p["SCHEDULE_PERIOD_MAX"],
        CONTEXT_ID_WIDTH=p["CONTEXT_ID_WIDTH"],
        CONTEXT_VERSION_WIDTH=p["CONTEXT_VERSION_WIDTH"],
        KERNEL_ID_WIDTH=p["KERNEL_ID_WIDTH"],
        LINK_EPOCH_WIDTH=p["PREDICATE_EPOCH_WIDTH"],
    )
    return q | {
        n: p[n]
        for n in ("NODE_PRESENT_MASK", "LINK_PRESENT_MASK", "NODE_CONNECTIVITY_MASKS")
        if n in p
    }


def physical(p):
    return mesh_physical(mesh_parameters(p))


def dimensions(p):
    a = mesh_dimensions(mesh_parameters(p))
    a.update(
        PV=p["PREDICATE_WIDTH"],
        T=p["ASSOCIATION_TAG_WIDTH"],
        PR=p["PRODUCER_ID_WIDTH"],
        CL=p["PREDICATE_CLASS_WIDTH"],
        ER=p["PREDICATE_ERROR_WIDTH"],
        P=p["ROUTE_PROOF_ID_WIDTH"],
    )
    a["RES"] = a["N"] * a["I"]
    a["RI"] = a["N"] * a["O"] * (1 + a["S"])
    a["HW"] = (a["RES"] + 2).bit_length()
    a["TW"] = (a["N"] * a["RX"]).bit_length()
    a["REQ"] = sum(a[k] for k in ("CI", "V", "K", "EP", "PR", "T", "CL", "ER"))
    a["BODY"] = a["RI"] + a["LB"] * (1 + a["PM"]) + a["PW"] + a["CI"] + a["V"] + a["K"] + a["EP"]
    a["IMAGE"] = a["BODY"] + a["P"]
    a["COUNTERS"] = (
        32 + 4 * a["N"] * (a["TX"] + a["RX"]) + 4 * a["LB"] + 4 * a["N"] + a["N"] * a["RX"]
    )
    a["CW"] = (a["COUNTERS"] + a["N"]).bit_length()
    return a


def topology_id(p):
    a, g = dimensions(p), physical(p)
    values = [p[n] for n in DEFAULTS]
    values += [(g["nodes"] >> i) & 1 for i in range(a["N"])]
    values += [(g["mask"] >> i) & 1 for i in range(a["L"])]
    values += [(g["connectivity"] >> i) & 1 for i in range(a["N"] * a["I"] * a["O"])]
    result = 0x504E0101
    for value in values:
        result = ((result ^ value) * 16777619) & 0xFFFFFFFF
    return result


def route_image(p, routes):
    a = dimensions(p)
    return pack_fields(
        [(int((n, o) in routes), 1) for n in range(a["N"]) for o in range(a["O"])]
        + [(routes.get((n, o), 0), a["S"]) for n in range(a["N"]) for o in range(a["O"])]
    )


def graph(p, routes):
    """DFS rejects cycles, incomplete paths, and excess copies independently of RTL DP."""
    a, g = dimensions(p), physical(p)
    children = {}
    terminals = {}
    parents = {}
    for (n, o), source in routes.items():
        assert (
            0 <= source < a["I"]
            and (g["connectivity"] >> (n * a["O"] * a["I"] + o * a["I"] + source)) & 1
        ), "physical"
        u = n, source
        children.setdefault(u, [])
        terminals.setdefault(u, [])
        if o < a["RX"]:
            terminals[u].append(("tile", n * a["RX"] + o))
        else:
            edge = g["edges"][g["outputs"][n, o]]
            if "boundary_output" in edge:
                terminals[u].append(("boundary", edge["boundary_output"]))
            else:
                v = edge["destination_node"], edge["destination_port"]
                children[u].append(v)
                parents[v] = u
    done = {}
    visiting = set()

    def visit(u):
        assert u in children, "dangling"
        assert u not in visiting, "cycle"
        if u in done:
            return done[u]
        visiting.add(u)
        destinations = list(terminals[u])
        for v in children[u]:
            destinations += visit(v)
        visiting.remove(u)
        done[u] = destinations
        assert len(destinations) <= p["MAX_TREE_DESTINATIONS"], "tree"
        assert len(children[u]) + len(terminals[u]) <= p["MAX_MULTICAST_FANOUT"], "fanout"
        assert p["SUPPORT_MULTICAST"] or len(children[u]) + len(terminals[u]) <= 1, "multicast"
        return destinations

    for u in children:
        visit(u)
    for n, source in children:
        if source >= a["TX"]:
            edge = g["edges"][g["inputs"][n, source]]
            if "source_node" in edge:
                assert (n, source) in parents, "orphan"
    depths = {}

    def depth(u):
        if u in depths:
            return depths[u]
        if u in parents:
            value = depth(parents[u]) + 1
        else:
            value = int(u[1] >= a["TX"])
        depths[u] = value
        return value

    for u in children:
        depth(u)
    used_links = set()
    link_depth = {}
    for (n, o), source in routes.items():
        if o >= a["RX"]:
            l = g["outputs"][n, o]
            used_links.add(l)
            link_depth[l] = depths[n, source] + (1 if l < a["IL"] else 2)
        if source >= a["TX"]:
            l = g["inputs"][n, source]
            used_links.add(l)
            if l >= a["IL"]:
                link_depth[l] = 0
    return dict(destinations=done, depths=depths, links=used_links, link_depth=link_depth)


def image(
    p,
    routes,
    *,
    context=1,
    version=1,
    kernel=3,
    epoch=1,
    period=1,
    scheduled=False,
    slot=0,
    check=True,
):
    a = dimensions(p)
    cert = graph(p, routes) if check else None
    enable = sum(1 << l for l in cert["links"]) if scheduled else 0
    slots = (
        sum(
            1 << (l * a["PM"] + (slot + offset) % period)
            for l, offset in cert["link_depth"].items()
        )
        if scheduled
        else 0
    )
    fields = [
        (route_image(p, routes), a["RI"]),
        (enable, a["LB"]),
        (slots, a["LB"] * a["PM"]),
        (period, a["PW"]),
        (context, a["CI"]),
        (version, a["V"]),
        (kernel, a["K"]),
        (epoch, a["EP"]),
    ]
    body = pack_fields(fields)
    proof = crc32c(((body << 32) | topology_id(p)).to_bytes((a["BODY"] + 32 + 7) // 8, "little"))
    assert proof != 0
    return dict(
        route=fields[0][0],
        schedule_enable=enable,
        slots=slots,
        period=period,
        context=context,
        version=version,
        kernel=kernel,
        epoch=epoch,
        proof=proof,
        certificate=cert,
    )


def metadata(p, context, version, kernel, epoch, producer, tag, kind=1, error=0, opaque=0):
    a = dimensions(p)
    return pack_fields(
        [
            (context, a["CI"]),
            (version, a["V"]),
            (kernel, a["K"]),
            (epoch, a["EP"]),
            (producer, a["PR"]),
            (tag, a["T"]),
            (kind, a["CL"]),
            (error, a["ER"]),
            (opaque, a["M"] - a["REQ"]),
        ]
    )


def proof_id(p, fields):
    """Hash the complete configuration body and topology, excluding the proof itself."""
    a = dimensions(p)
    packed = pack_fields(
        [
            (fields["i_cfg_route_image"], a["RI"]),
            (fields["i_cfg_schedule_enable"], a["LB"]),
            (fields["i_cfg_schedule_slot_image"], a["LB"] * a["PM"]),
            (fields["i_cfg_schedule_period"], a["PW"]),
            (fields["i_cfg_context_id"], a["CI"]),
            (fields["i_cfg_context_version"], a["V"]),
            (fields["i_cfg_kernel_id"], a["K"]),
            (fields["i_cfg_epoch"], a["EP"]),
        ]
    )
    return crc32c(((packed << 32) | topology_id(p)).to_bytes((a["BODY"] + 39) // 8, "little"))
