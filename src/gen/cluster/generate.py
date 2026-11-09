"""Generate the synchronous, cluster-exclusive BCT/MST integration boundary.

Python 3.12's TOML reader consumes an explicit placement, never a class-by-coordinate
convention. Public widths are checked against the real SystemVerilog port headers.
Generated manifests are architecture artifacts, not simulator dependency loaders.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import tomllib

from sources import SOURCES
from tile_parameters import tile_parameters

ROOT = Path(__file__).resolve().parents[3]
RTL = ROOT / "src/rtl"
HERE = Path(__file__).resolve().parent


def bits(count: int) -> int:
    return max(1, (count - 1).bit_length())


def arithmetic(expression: str, names: dict[str, int]) -> int:
    """Evaluate only integer arithmetic from trusted RTL width expressions."""
    node = ast.parse(expression, mode="eval").body
    def visit(value):
        match value:
            case ast.Constant(value=int(number)):
                return number
            case ast.Name(id=name):
                return names[name]
            case ast.BinOp(left=left, op=op, right=right):
                lhs, rhs = visit(left), visit(right)
                match op:
                    case ast.Add(): return lhs + rhs
                    case ast.Sub(): return lhs - rhs
                    case ast.Mult(): return lhs * rhs
                    case ast.Div() | ast.FloorDiv(): return lhs // rhs
                    case _: raise ValueError("Unsupported width operator")
            case _: raise ValueError("Unsupported width expression")
    return visit(node)


def ports(module: str, aliases: dict[str, int]) -> dict[str, tuple[str, int]]:
    source = (RTL / f"mosaic_blocks/{module}.sv").read_text()
    header = source.split(") (", 1)[1].split(");", 1)[0]
    found = re.findall(r"\b(input|output)\s+(?:wire|logic)\s*"
                       r"(?:\[([^\]]+)\]\s*)?(\w+)", header)
    result = {}
    for direction, extent, name in found:
        if extent:
            high, low = extent.split(":")
            width = arithmetic(high, aliases) - arithmetic(low, aliases) + 1
        else:
            width = 1
        if width <= 0:
            raise ValueError(f"Invalid public width {module}.{name}")
        result[name] = direction, width
    if not result:
        raise ValueError(f"No public ports in {module}")
    return result


def geometry(descriptor):
    rows, cols = descriptor["rows"], descriptor["cols"]
    n = rows * cols
    c = descriptor["context_depth"]
    if c != 4:
        raise ValueError("MVP v1's explicit stream codec requires four contexts")
    b = descriptor["scratchpad_banks"]
    words = descriptor["scratchpad_bank_words"]
    capacity = b * words * 8
    a = bits(capacity)
    mesh = dict(R=rows, C=cols, N=n, H=1, TX=2, RX=2, I=6, O=6, D=32,
                M=512, CD=c, W=64, CI=8, V=16, K=16, EP=4, P=32, PM=16)
    mesh.update(B=2 * (rows + cols), IL=2 * (rows * (cols - 1) + (rows - 1) * cols),
                NI=bits(n), S=3, OS=3, RW=bits(n * 6), AW=bits((n * 6 + 1) * 17 + 4), PW=5)
    mesh["L"] = mesh["IL"] + 2 * mesh["B"]
    mesh.update(LB=max(1, mesh["L"]), LI=bits(mesh["L"]))
    mesh["IMAGE"] = 110 + n * 6 * 4 + n * 6 * (mesh["RW"] + mesh["AW"])
    mesh["WORDS"] = (mesh["IMAGE"] + 63) // 64
    mesh["WI"] = bits(mesh["WORDS"])
    mesh["COUNTERS"] = 16 + 8 * n + 3 * mesh["LB"] + 4 * mesh["B"] + 4 * n
    mesh["CW"] = bits(mesh["COUNTERS"] + n + 1)
    common = dict(TI=8, AV=16, CP=32, D=32, M=256, NI=2, NO=2, BI=1, BO=1,
                  P=1, PM=16, PI=1, PO=1, E=256, EI=1, EO=1, C=c, NC=c,
                  W=64, Q=4, O=16, K=16, V=16, T=16, S=8, ER=8, TR=64, CI=2, BY=8)
    bct = common | dict(N=8, WI=3, IM=512, E=32)
    mst = common | dict(N=16, WI=4, IM=1024, A=32, MD=64, NL=1, NS=1, NM=1,
                       NDI=1, NDO=1, NR=8, NB=2, NE=16, RI=4, BU=8, PK=32,
                       J=16, DG=16, AL=16, EP=4, SP=4, ST=8, DT=6, PR=3, C=16,
                       SY=4, MY=8, H=2, HCI=1, LCI=1, SCI=1, CH=1, IDW=134,
                       MOW=8, ENW=146, FOW=16, EVW=88, CTW=52, RGW=142, BUW=175,
                       MT=76, MSZ=2, MBW=4, BC=37, OC=3, INE=1)
    sp = dict(D=64, B=b, C=4, N=8, R=8, T=76, O=16, K=16, G=16, BG=4,
              A=a, Y=8, Z=4, RI=3, CI=2, BI=bits(b), SI=3, CO=4, RO=6, BO=4)
    sp["DW"] = 1 + a + a + 1 + 16 + 16 + 3 + 1 + 8 + 16 + 4 + 2 + 2
    root = dict(NM=1, NE=n + 2, NT=n, NF=2, D=64, F=64, EI=8, ET=4,
                C=5, CI=8, V=16, OW=16, K=16, P=32, EP=4, TI=8, TG=16,
                WI=16, BY=8, OC=3)
    return dict(n=n, contexts=c, capacity=capacity, bct=bct, mst=mst,
                mesh=mesh, sp=sp, root=root)


def validate(d):
    allowed = {"schema", "profile", "cluster_id", "rows", "cols", "context_depth",
               "scratchpad_banks", "scratchpad_bank_words", "clock_gating",
               "lifecycle_timeout", "tiles"}
    if set(d) != allowed:
        raise ValueError(f"Unknown/missing descriptor fields: {set(d) ^ allowed}")
    if d["schema"] != "mosaic-cluster-v1" or d["profile"] != "Cluster-MVP":
        raise ValueError("Only the released synchronous Cluster-MVP profile is supported")
    for name in ("cluster_id", "rows", "cols", "context_depth", "lifecycle_timeout"):
        if type(d[name]) is not int:
            raise ValueError(f"{name} must be an integer")
    if d["rows"] not in (2, 4) or d["cols"] != d["rows"]:
        raise ValueError("MVP requires a 2 by 2 or 4 by 4 square")
    if type(d["clock_gating"]) is not bool or not 16 <= d["lifecycle_timeout"] <= 16777215:
        raise ValueError("Invalid clock-gating or timeout contract")
    if not 0 <= d["cluster_id"] < 256:
        raise ValueError("Cluster ID does not fit the published ABI")
    for name in ("scratchpad_banks", "scratchpad_bank_words"):
        value = d[name]
        if type(value) is not int or value <= 0 or value & (value - 1):
            raise ValueError("Scratchpad geometry must be positive powers of two")
    if d["scratchpad_banks"] > 16 or not 16 <= d["scratchpad_banks"] * d[
            "scratchpad_bank_words"] * 8 <= 1048576:
        raise ValueError("Scratchpad geometry exceeds the MVP address codec")
    tiles = d["tiles"]
    if not isinstance(tiles, list):
        raise ValueError("tiles must be an explicit list")
    if len(tiles) != d["rows"] * d["cols"]:
        raise ValueError("Each grid position must have one explicit released tile")
    ids, coordinates = set(), set()
    for tile in tiles:
        required = {"id", "class", "row", "col"}
        if not isinstance(tile, dict) or not required <= set(tile) or set(tile) - required - {
                "parameters"}:
            raise ValueError("Tile entries require id, class, row and col; parameters are optional")
        if any(type(tile[key]) is not int for key in ("id", "row", "col")):
            raise ValueError("Tile identity and coordinates must be integers")
        if not isinstance(tile["class"], str):
            raise ValueError("Tile class must be a string")
        if tile["class"] not in ("BCT", "MST"):
            raise ValueError(f"Unsupported Cluster-MVP tile class or adapter: {tile['class']}")
        coordinate = tile["row"], tile["col"]
        if (not 0 <= tile["id"] < 240 or tile["id"] in ids or
            coordinate in coordinates or not 0 <= tile["row"] < d["rows"] or
            not 0 <= tile["col"] < d["cols"]):
            raise ValueError("Duplicate or out-of-range tile identity/coordinate")
        ids.add(tile["id"])
        coordinates.add(coordinate)
        tile_parameters(tile)
    if sum(t["class"] == "MST" for t in tiles) != 1:
        raise ValueError("MVP v1 qualifies exactly one MST and its dedicated scratchpad client")
    return geometry(d)


class Wrapper:
    port_catalog = staticmethod(ports)

    def __init__(self):
        self.public = {}
        self.wires = {}
        self.statements = []
        self.instances = []
        self.ties = {}

    def wire(self, name, width=1):
        if name in self.wires and self.wires[name] != width:
            raise ValueError(f"Conflicting wire width: {name}")
        self.wires[name] = width
        return name

    def port(self, name, direction, width=1):
        if name in self.public and self.public[name] != (direction, width):
            raise ValueError(f"Conflicting public port: {name}")
        self.public[name] = direction, width
        return name

    def assign(self, left, right):
        self.statements.append(f"    assign {left} = {right};")

    def instance(self, module, prefix, aliases, parameters=None, bindings=None, expose=None):
        bindings = bindings or {}
        expose = expose or {}
        catalog = self.port_catalog(module, aliases)
        unknown = set(bindings) - set(catalog)
        if unknown:
            raise ValueError(f"Unknown {module} binding: {unknown}")
        mapping = {}
        ties = {}
        for name, (direction, width) in catalog.items():
            if name in expose:
                mapping[name] = self.port(expose[name], direction, width)
            elif name in bindings:
                mapping[name] = bindings[name]
            else:
                mapping[name] = self.wire(f"{prefix}_{name}", width)
                if direction == "input":
                    self.assign(mapping[name], "'0")
                    ties[name] = "0 (feature absent from this descriptor)"
        params = ",\n".join(f"        .{key}({value})" for key, value in (parameters or {}).items())
        connections = ",\n".join(f"        .{name}({value})" for name, value in mapping.items())
        module_name = module.rsplit("/", 1)[-1]
        self.instances.append(f"    {module_name} #(\n{params}\n    ) u_{prefix} (\n{connections}\n    );")
        self.ties[prefix] = ties
        return mapping

    def render(self, manifest_hash):
        header = ["`timescale 1ns / 1ps", "`default_nettype none",
                  "// GENERATED by src/gen/cluster/generate.py; edit the descriptor/generator.",
                  f"// Architecture identity: {manifest_hash}", "module cluster ("]
        header.append(",\n".join(f"    {direction} wire " +
                      (f"[{width - 1}:0] " if width > 1 else "") + name
                      for name, (direction, width) in self.public.items()))
        header.append(");")
        header += ["    wire " + (f"[{width - 1}:0] " if width > 1 else "") + name + ";"
                   for name, width in self.wires.items()]
        # Preserve readable boundaries in generated procedural blocks and
        # between instances, so formatting survives architecture regeneration.
        statements = []
        for line in self.statements:
            previous = statements[-1] if statements else ""
            begins_block = line.startswith(("    always", "    // Capture"))
            follows_block = previous == "    end"
            begins_condition = line.lstrip().startswith("if (") and not previous.endswith("begin")
            if previous and not previous.lstrip().startswith("//") and (
                    begins_block or follows_block or begins_condition):
                statements.append("")
            statements.append(line)
        instances = "\n\n".join(self.instances)
        return "\n".join(header + statements + ["", instances,
                         "endmodule", "`default_nettype wire", ""])


def packed(values, width):
    return f"{len(values) * width}'h{sum(v << (i * width) for i, v in enumerate(values)):x}"


def build(d, g):
    w = Wrapper()
    n, ne = g["n"], g["n"] + 2
    for name in ("i_clk", "i_rstb", "i_test_mode", "i_scan_enable"):
        w.port(name, "input")
    def wire(name, width=1): return w.wire(name, width)
    for name, width in dict(allocated=1, running=1, boundary_enable=1, configuration_enable=1,
        owner=16, kernel=16, package_id=32, context_id=8, epoch=4, allocation_generation=16,
        cfg_flush=1, cfg_release=1, error_clear=1, snapshot=1, counter_clear=1,
        memory_release=1, memory_release_done=1, memory_release_error=1,
        package_clear=1, package_compatible=1, package_suspend_safe=1, package_idle=1,
        completion_mask=n, event_empty=1, terminal_event=1, terminal_ready=1,
        fault_event=1, fault_event_ready=1, first_error_code=8, first_error_source=8,
        fault=1, fault_code=8, fault_source=8, metadata_error=n*2,
        tile_runtime_valid=n, tile_runtime_ready=n, tile_response_valid=n,
        tile_response_ready=n, tile_response_error=n, tile_response_command=n*3,
        tile_response_tag=n*16, tile_runtime_command=3, tile_state=n*4,
        tile_busy=n, tile_idle=n, tile_quiescent=n, tile_error=n, tile_fatal=n,
        tile_stalls=n*8, tile_events=n, tile_events_ready=n, tile_event_payload=n*256,
        tile_versions=n*16, duplicate_completion=1, transport_idle=1,
        all_quiescent=1, cfg_idle=1, cfg_hold=1, cfg_flushed=1, cfg_commit_complete=1,
        cfg_commit_error=1, cfg_fail_stop=1, cfg_ack_mask=ne, gclk=1, commit_inflight=1).items():
        wire(name, width)
    tiles = sorted(d["tiles"], key=lambda t: (t["row"], t["col"]))
    tile_ids = [t["id"] for t in tiles]
    words = [8 if t["class"] == "BCT" else 16 for t in tiles] + [g["mesh"]["WORDS"], 2]
    root_public = {name: name for name in ports("configuration_network", g["root"])
                   if name.startswith(("i_cfg_", "o_cfg_"))}
    # Gate offers without rewriting owner or package identity. Ready follows exactly
    # the same eligibility condition, so no hidden acceptance can occur.
    root_public.pop("i_cfg_request_valid")
    root_public.pop("o_cfg_request_ready")
    w.port("i_cfg_request_valid", "input")
    w.port("o_cfg_request_ready", "output")
    w.port("i_cfg_commit_valid", "input")
    w.port("o_cfg_commit_ready", "output")
    for name in ports("configuration_network", g["root"]):
        if name.startswith("i_commit_") and name != "i_commit_valid":
            root_public[name] = name.replace("i_commit_", "i_cfg_commit_")
    common_context = "i_cfg_commit_context_ids[7:0]"
    contexts_equal = " && ".join(f"i_cfg_commit_context_ids[{e * 8}+:8] == {common_context}"
                                  for e in range(ne))
    commit_allowed = wire("commit_allowed")
    w.assign(commit_allowed, f"configuration_enable && package_compatible && i_cfg_commit_destination_mask == "
             f"{ne}'h{(1 << ne) - 1:x} && i_cfg_commit_owner_id == owner && "
             "i_cfg_commit_kernel_id == kernel && "
             "i_cfg_commit_epoch == mesh_o_active_epoch + 4'd1 && " + contexts_equal)
    root = w.instance("configuration_network", "cfg", g["root"], dict(
        NUM_ENDPOINTS=ne, NUM_TILE_ENDPOINTS=n, NUM_INFRA_ENDPOINTS=2,
        ENDPOINT_TYPE_TABLE=packed([0]*n + [1, 4], 4),
        ENDPOINT_ID_TABLE=packed(tile_ids + [240, 241], 8),
        ENDPOINT_WORD_COUNT_TABLE=packed(words, 32),
        MULTICAST_GROUP_TABLE=packed([sum(1 << k for k,t in enumerate(tiles)
            if t["class"] == "BCT") if e < n and tiles[e]["class"] == "BCT"
            else 1 << e for e in range(ne)], ne),
        ENDPOINT_CONTEXT_DEPTH_TABLE=packed([4]*ne, 32),
        ENDPOINT_SCHEMA_TABLE=packed([1]*ne, 32), USE_ALLOCATION_OWNER=1,
        ENDPOINT_PERMISSION_TABLE=packed([7 << 16]*ne, 20),
        COMMIT_TIMEOUT_CYCLES=4096), bindings=dict(
        i_clk="gclk", i_reset_n="i_rstb", i_test_enable="i_test_mode",
        i_scan_enable="i_scan_enable", i_allocation_owner_valid="allocated",
        i_allocation_owner_id="owner", i_flush="cfg_flush", i_resume="cfg_release || !allocated",
        i_error_clear="error_clear", i_execution_release="cfg_release", i_release_safe="transport_idle",
        i_cfg_request_valid="i_cfg_request_valid && configuration_enable",
        o_cfg_request_ready=wire("cfg_ingress_ready"),
        i_commit_valid="i_cfg_commit_valid && commit_allowed",
        o_commit_ready=wire("cfg_native_commit_ready"),
        o_idle="cfg_idle", o_execution_hold="cfg_hold", o_flushed="cfg_flushed",
        o_commit_complete="cfg_commit_complete", o_commit_error="cfg_commit_error",
        o_fail_stop="cfg_fail_stop", o_commit_ack_mask="cfg_ack_mask",
        i_endpoint_power_safe=f"{ne}'h{(1 << ne) - 1:x}"), expose=root_public)
    w.assign("o_cfg_request_ready", "cfg_ingress_ready && configuration_enable")
    w.assign("o_cfg_commit_ready", "cfg_native_commit_ready && commit_allowed")
    for name, signal, width in (("o_cfg_execution_hold", "cfg_hold", 1),
        ("o_cfg_commit_complete", "cfg_commit_complete", 1),
        ("o_cfg_commit_error", "cfg_commit_error", 1),
        ("o_cfg_commit_ack_mask", "cfg_ack_mask", ne),
        ("o_cfg_commit_failure_mask", root["o_commit_failure_mask"], ne),
        ("o_cfg_configuration_epoch", root["o_configuration_epoch"], 4)):
        w.port(name, "output", width)
        w.assign(name, signal)
    # The instance helper intentionally ties absent features. These endpoint buses
    # are driven below by real adapters, so remove their automatic zero ties.
    endpoint_inputs = [p for p in root if p.startswith("i_endpoint_") and
                       p != "i_endpoint_power_safe"]
    for p in endpoint_inputs:
        w.statements.remove(f"    assign {root[p]} = '0;")
        w.ties["cfg"].pop(p, None)

    mesh_params = dict(CONTROL_PROTECTION=1, MESH_ROWS=d["rows"], MESH_COLS=d["cols"], LINK_METADATA_WIDTH=512,
                       LINK_EPOCH_WIDTH=4, SCHEDULE_PERIOD_MAX=16)
    mesh_bind = dict(i_clk="gclk", i_reset_n="i_rstb", i_enable="running",
        i_error_clear="error_clear", i_test_enable="i_test_mode", i_scan_enable="i_scan_enable")
    mesh = w.instance("static_mesh", "mesh", g["mesh"], mesh_params, mesh_bind)
    # Endpoint proxy drives these native configuration pins, not the host.
    for p in list(mesh):
        if p.startswith(("i_cfg_", "i_tile_", "i_boundary_")) and p != "i_boundary_isolate":
            w.statements.remove(f"    assign {mesh[p]} = '0;")
            w.ties["mesh"].pop(p, None)
    # Data boundaries retain the full canonical envelope under backpressure.
    b = g["mesh"]["B"]
    for name, direction, width in (("i_boundary_valid", "input", b),
        ("o_boundary_ready", "output", b), ("i_boundary_data", "input", b*32),
        ("i_boundary_metadata", "input", b*512), ("o_boundary_valid", "output", b),
        ("i_boundary_ready", "input", b), ("o_boundary_data", "output", b*32),
        ("o_boundary_metadata", "output", b*512), ("o_boundary_error", "output", b)):
        w.port(name, direction, width)
    wire("boundary_bad", b)
    for p in range(b):
        low = p * 512
        wire(f"boundary_ok_{p}")
        m = f"i_boundary_metadata[{low}+:512]"
        w.assign(f"boundary_ok_{p}", f"(^{m} !== 1'bx) && "
            f"(^{m} !== 1'bx) && i_boundary_metadata[{low}+:8] == context_id && "
            f"i_boundary_metadata[{low+8}+:16] == mesh_o_active_context_version && "
            f"i_boundary_metadata[{low+24}+:16] == kernel && "
            f"i_boundary_metadata[{low+40}+:4] == epoch && "
            f"i_boundary_metadata[{low+320}+:16] == owner && "
            f"i_boundary_metadata[{low+336}+:32] == package_id && "
            f"i_boundary_metadata[{low+376}+:136] == 0 && "
            f"i_boundary_metadata[{low+56}+:8] == 0")
        w.assign(f"boundary_bad[{p}]", f"boundary_enable && i_boundary_valid[{p}] === 1'b1 "
                 f"&& !boundary_ok_{p}")
        w.assign(f"{mesh['i_boundary_rx_valid']}[{p}]", f"boundary_enable && "
                 f"i_boundary_valid[{p}] && boundary_ok_{p}")
        w.assign(f"o_boundary_ready[{p}]", f"boundary_enable && {mesh['o_boundary_rx_ready']}"
                 f"[{p}] && boundary_ok_{p}")
    w.assign(mesh["i_boundary_rx_data"], "i_boundary_data")
    w.assign(mesh["i_boundary_rx_metadata"], "i_boundary_metadata")
    w.assign(mesh["i_boundary_rx_parity"], "'0")
    # Accepted output traffic remains visible while an orderly suspend/drain runs.
    w.assign(mesh["i_boundary_tx_ready"], "i_boundary_ready")
    w.assign("o_boundary_valid", mesh["o_boundary_tx_valid"])
    w.assign("o_boundary_data", mesh["o_boundary_tx_data"])
    w.assign("o_boundary_metadata", mesh["o_boundary_tx_metadata"])
    w.assign("o_boundary_error", "boundary_bad")

    sp = w.instance("banked_scratchpad", "sp", g["sp"], dict(
        NUM_BANKS=d["scratchpad_banks"], BANK_DEPTH_WORDS=d["scratchpad_bank_words"],
        CLIENT_TAG_WIDTH=76, CONTROL_PROTECTION=1), dict(i_clk="gclk", i_reset_n="i_rstb", i_enable="1'b1",
        i_error_clear="error_clear", i_bank_power_ack=f"{g['sp']['B']}'h{(1 << g['sp']['B'])-1:x}"))
    for p in list(sp):
        if p.startswith(("i_client_", "i_region_")) or p == "i_event_ready":
            w.statements.remove(f"    assign {sp[p]} = '0;")
            w.ties["sp"].pop(p, None)
    # Region zero is the only MVP region. There are no unprogrammed permission
    # bypasses; every native client still passes owner/kernel/generation checks.
    for p in ("i_region_cmd_a", "i_region_cmd_b", "i_region_expected_generation_b",
              "i_region_expected_state_b", "i_region_buffer_group", "i_region_buffer_role"):
        w.assign(sp[p], "'0")
    for p, value in dict(i_region_owner_id="owner", i_region_kernel_id="kernel",
        i_region_contents_valid="1'b1", i_region_state="3'd5",
        i_region_expected_state_a="3'd5").items(): w.assign(sp[p], value)

    native_tiles = []
    proxies = []
    for index, tile in enumerate(tiles):
        module = tile["class"].lower()
        params = dict(TILE_ID=tile["id"], TILE_ID_WIDTH=8, RUNTIME_TAG_WIDTH=16,
                      EVENT_WIDTH=256, DATA_METADATA_WIDTH=256, CONTROL_PROTECTION=1)
        if module == "bct": params.update(DATA_INPUT_PORTS=2, DATA_OUTPUT_PORTS=2, EVENT_WIDTH=32)
        else: params.update(SHELL_DATA_WIDTH=32, EXECUTION_EPOCH_WIDTH=4, MAX_ELEMENT_BYTES=8)
        params.update(tile_parameters(tile))
        bind = dict(i_clk="gclk", i_rstb="i_rstb", i_cfg_clk="gclk", i_cfg_rstb="i_rstb",
            i_test_enable="i_test_mode", i_scan_enable="i_scan_enable",
            i_runtime_request_valid=f"tile_runtime_valid[{index}]",
            o_runtime_request_ready=f"tile_runtime_ready[{index}]",
            i_runtime_request_command="tile_runtime_command", i_runtime_request_owner_id="owner",
            i_runtime_request_kernel_id="kernel", i_runtime_request_context_id="context_id[1:0]",
            i_runtime_request_tag="control_o_runtime_response_tag",
            o_runtime_response_valid=f"tile_response_valid[{index}]",
            i_runtime_response_ready=f"tile_response_ready[{index}]",
            o_runtime_response_error=f"tile_response_error[{index}]",
            o_runtime_response_command=f"tile_response_command[{index*3}+:3]",
            o_runtime_response_tag=f"tile_response_tag[{index*16}+:16]",
            o_status_execution_state=f"tile_state[{index*4}+:4]",
            o_status_busy=f"tile_busy[{index}]", o_status_idle=f"tile_idle[{index}]",
            o_status_quiescent=f"tile_quiescent[{index}]", o_status_error=f"tile_error[{index}]",
            o_status_fatal_error=f"tile_fatal[{index}]", o_status_stall_reasons=f"tile_stalls[{index*8}+:8]",
            o_status_context_version=f"tile_versions[{index*16}+:16]",
            o_event_out_valid=f"tile_events[{index}]", i_event_out_ready=f"tile_events_ready[{index}]",
            o_event_out_payload=f"tile_event_payload[{index*256}+:{32 if module == 'bct' else 256}]",
            i_body_power_good="1'b1", i_body_save_done="1'b1", i_body_restore_done="1'b1",
            i_power_response_ready="1'b1", i_trace_ready="1'b1")
        # The one MST exposes its released descriptor, region, DMA, cancellation,
        # rejection and completion interfaces. It does not expose scratchpad wires.
        expose = {}
        if module == "mst":
            common_ports = set(ports("bct", g["bct"]))
            for p in ports("mst", g["mst"]):
                if p not in common_ports and "scratchpad" not in p:
                    expose[p] = p if p.startswith(("o_mst_", "i_mst_")) else p[:2] + "mst_" + p[2:]
            for p in ("i_drain", "i_flush", "i_error_clear", "i_descriptor_valid",
                      "o_descriptor_ready", "o_descriptor_accepted", "o_descriptor_rejected"):
                expose.pop(p, None)
            # Native management writes are configuration traffic. Freeze new offers
            # during the retained commit safe point; response paths stay live.
            for guarded in ("i_region_valid", "i_buffer_valid"):
                public = expose.pop(guarded)
                w.port(public, "input")
                bind[guarded] = public + " && configuration_enable && !commit_inflight"
            w.port("i_mst_descriptor_valid", "input")
            w.port("o_mst_descriptor_ready", "output")
            w.port("o_mst_descriptor_accepted", "output")
            w.port("o_mst_descriptor_rejected", "output")
            bind.update(i_error_clear="error_clear", i_descriptor_valid=
                "i_mst_descriptor_valid && running && !descriptor_pending && "
                "(!descriptor_is_store || !store_bound)")
            wire("descriptor_pending")
            wire("descriptor_is_store")
            wire("store_bound")
            wire("store_identity", 134)
            wire("store_format", 16)
            wire("store_channel")
            w.assign("descriptor_is_store", "i_mst_descriptor_mode[2:0] == 1 || "
                     "i_mst_descriptor_mode[2:0] == 4")
        native = w.instance(module, f"tile{index}", g[module], params, bind, expose)
        for p in list(native):
            if p.startswith(("i_cfg_", "i_data_")) and p not in ("i_cfg_clk", "i_cfg_rstb"):
                w.statements.remove(f"    assign {native[p]} = '0;")
                w.ties[f"tile{index}"].pop(p, None)
        native_tiles.append(native)
        if module == "bct":
            w.assign(f"tile_event_payload[{index*256+32}+:224]", "224'd0")
        if module == "mst":
            mst = native
            mst_index = index
    # Native shared-resource proxies have the exact shell configuration ABI used
    # by the same released network adapter as the four execution tiles.
    for kind, ep in enumerate((n, n+1)):
        count = words[ep]
        a = dict(N=count, C=4, CI=2, WI=bits(count), A=g["sp"]["A"], P=4)
        bind = dict(i_clk="gclk", i_rstb="i_rstb", i_owner_id="owner", i_kernel_id="kernel",
            i_activation_epoch=f"{root['o_endpoint_commit_epoch']}[{ep*4}+:4]",
            i_quiescent="transport_idle", i_release="memory_release" if kind else "1'b0")
        if kind:
            bind.update(o_release_done="memory_release_done", o_release_error="memory_release_error")
            for p, sp_port in dict(o_region_cmd_valid="i_region_cmd_valid",
                i_region_cmd_ready="o_region_cmd_ready", o_region_cmd_opcode="i_region_cmd_opcode",
                o_region_expected_generation="i_region_expected_generation_a",
                o_region_base="i_region_base", o_region_limit="i_region_limit",
                o_region_read_mask="i_region_read_mask", o_region_write_mask="i_region_write_mask",
                i_region_rsp_valid="o_region_rsp_valid", o_region_rsp_ready="i_region_rsp_ready",
                i_region_rsp_error="o_region_rsp_error").items(): bind[p] = sp[sp_port]
        else:
            for p, mesh_port in dict(o_mesh_cfg_valid="i_cfg_valid", i_mesh_cfg_ready="o_cfg_ready",
                o_mesh_cfg_opcode="i_cfg_opcode", o_mesh_cfg_context_id="i_cfg_context_id",
                o_mesh_cfg_context_version="i_cfg_context_version", o_mesh_cfg_word_index="i_cfg_word_index",
                o_mesh_cfg_write_data="i_cfg_write_data", o_mesh_cfg_kernel_id="i_cfg_kernel_id",
                o_mesh_cfg_proof_id="i_cfg_proof_id", o_mesh_cfg_checksum="i_cfg_checksum",
                i_mesh_cfg_rsp_valid="o_cfg_rsp_valid", o_mesh_cfg_rsp_ready="i_cfg_rsp_ready",
                i_mesh_cfg_rsp_error="o_cfg_rsp_error", i_mesh_active_context_id="o_active_context_id",
                i_mesh_active_context_version="o_active_context_version", i_mesh_active_epoch="o_active_epoch",
                i_mesh_active_valid="o_active_context_valid").items(): bind[p] = mesh[mesh_port]
            w.assign(mesh["i_cfg_write_strobe"], "8'hff")
        proxy = w.instance("cluster_infrastructure", f"infra{kind}", a, dict(
            RESOURCE_KIND=kind, CONFIG_WORD_COUNT=count, SCRATCHPAD_ADDR_WIDTH=g["sp"]["A"]), bind)
        for p in list(proxy):
            if p.startswith("i_cfg_"):
                w.statements.remove(f"    assign {proxy[p]} = '0;")
                w.ties[f"infra{kind}"].pop(p, None)
        proxies.append(proxy)
    for ep, native in enumerate(native_tiles + proxies):
        count = words[ep]
        a = dict(D=64, C=5, CI=8, V=16, OW=16, K=16, P=32, EP=4, TI=8,
                 TG=16, WI=16, CTX=4, WORDS=count, ST=16, ID=8, BY=8, SC=2, SW=bits(count))
        bind = dict(i_clk="gclk", i_reset_n="i_rstb", i_power_safe="1'b1",
                    i_quiescent=f"commit_inflight || tile_quiescent[{ep}]" if ep < n else "commit_inflight || transport_idle")
        for p, (_, width) in ports("configuration_network_tile_adapter", a).items():
            root_port = None
            if p in ("i_cancel", "o_cancel_ack", "o_prepared_retained", "o_commit_ready",
                     "o_commit_ack_valid", "o_commit_error"):
                root_port = p.replace("i_", "o_endpoint_", 1) if p.startswith("i_") else (
                    p.replace("o_", "i_endpoint_", 1))
            elif p.startswith(("i_request_", "i_commit_")):
                root_port = "o_endpoint_" + p[2:]
            elif p.startswith(("o_response_", "o_active_")):
                root_port = "i_endpoint_" + p[2:]
            elif p == "i_response_ready": root_port = "o_endpoint_response_ready"
            elif p == "i_commit_ack_ready": root_port = "o_endpoint_commit_ack_ready"
            elif p == "o_request_ready": root_port = "i_endpoint_request_ready"
            if root_port in root:
                bind[p] = f"{root[root_port]}[{ep*width}+:{width}]"
        # Scalar handshake names are not covered by the field-prefix mapping.
        for p, rp in dict(o_response_valid="i_endpoint_response_valid",
            i_commit_valid="o_endpoint_commit_valid", o_commit_ready="i_endpoint_commit_ready",
            i_request_valid="o_endpoint_request_valid").items(): bind[p] = f"{root[rp]}[{ep}]"
        for p in ports("configuration_network_tile_adapter", a):
            if p.startswith("o_shell_request_"):
                np = "i_cfg_request_" + p.removeprefix("o_shell_request_")
                if np in native: bind[p] = native[np]
            elif p.startswith("i_shell_response_"):
                np = "o_cfg_response_" + p.removeprefix("i_shell_response_")
                if np in native: bind[p] = native[np]
        bind["o_shell_response_ready"] = native["i_cfg_response_ready"]
        bind["i_shell_request_ready"] = native["o_cfg_request_ready"]
        if ep < n:
            bind.update(i_shell_active_valid=f"tile_versions[{ep*16}+:16] != 0",
                i_shell_context_id=native["o_status_active_context"],
                i_shell_context_version=native["o_status_context_version"],
                i_shell_owner_id=native["o_status_owner_id"],
                i_shell_kernel_id=native["o_status_kernel_id"],
                i_shell_validated=native["o_status_context_valid"])
        else:
            bind.update(i_shell_active_valid=native["o_active_valid"],
                i_shell_context_id=native["o_active_context_id"],
                i_shell_context_version=native["o_active_context_version"],
                i_shell_owner_id="owner", i_shell_kernel_id="kernel",
                i_shell_validated=native["o_context_valid"])
        adapter = w.instance("configuration_network_tile_adapter", f"adapter{ep}", a,
            dict(CONFIG_WORD_COUNT=count, SHELL_TAG_WIDTH=16, TILE_ID_WIDTH=8,
                 TILE_ID=tile_ids[ep] if ep < n else 240 + ep - n), bind)
    # All remaining integration logic is generated from these concrete public maps.
    finish(w, d, g, root, mesh, sp, native_tiles, proxies, mst, mst_index)
    return w, tiles, words


def finish(w, d, g, root, mesh, sp, tiles, proxies, mst, mst_index):
    n, ne = g["n"], g["n"] + 2
    wire = w.wire
    for name, width in dict(commit_owner=16, commit_kernel=16, commit_context=8,
        commit_epoch=4, commit_versions=ne*16, commit_package=32).items(): wire(name, width)
    captures = dict(commit_owner="i_cfg_commit_owner_id", commit_kernel="i_cfg_commit_kernel_id",
        commit_context="i_cfg_commit_context_ids[7:0]", commit_epoch="i_cfg_commit_epoch",
        commit_versions="i_cfg_commit_context_versions", commit_package="i_cfg_commit_package_id")
    w.statements += ["    // Capture the accepted commit tuple; the source may change its payload next edge.",
        "    always_ff @(posedge gclk) begin", "        if (!i_rstb) begin"]
    for name in captures:
        w.statements.append(f"            {name} <= '0;")
    w.statements += ["        end else if (i_cfg_commit_valid && o_cfg_commit_ready) begin"]
    for name, value in captures.items(): w.statements.append(f"            {name} <= {value};")
    w.statements += ["        end", "    end"]
    # The manifest authenticates the architecture, epoch and exact image set.
    # The CRC directory observes successful native PREPARE retirement records.
    wire("prepared_crcs", ne*32)
    wire("next_prepared_crcs", ne*32)
    wire("prepared_crc_bad")
    w.registers = {"next_prepared_crcs"}
    w.statements += ["    always @* begin", "        next_prepared_crcs = prepared_crcs;",
        "        if (counter_clear || package_clear || cfg_flush) next_prepared_crcs = '0;"]
    endpoint_ids = [t["id"] for t in sorted(d["tiles"], key=lambda t: (t["row"],t["col"]))]+[240,241]
    for e, logical in enumerate(endpoint_ids):
        w.statements += ["        if (o_cfg_response_valid && i_cfg_response_ready &&",
            "            o_cfg_response_prepared && o_cfg_response_status == 0 &&",
            f"            o_cfg_response_endpoint_id == 8'd{logical})",
            f"            next_prepared_crcs[{e*32}+:32] = o_cfg_response_crc;"]
    w.statements += ["    end"]
    w.instances.append(f"""    tile_shell_state #(.WIDTH({ne*32}), .PROTECTION(1)) u_prepared_crcs (
        .i_clk(gclk),
        .i_rstb(i_rstb),
        .i_enable(1'b1),
        .i_data(next_prepared_crcs),
        .o_data(prepared_crcs),
        .o_bad(prepared_crc_bad),
        .o_corrected()
    );""")
    package_public = {p:p for p in ports("cluster_package",dict(N=n,E=ne))
                      if p.startswith(("i_package_","o_package_")) or p=="i_package_id"}
    package = w.instance("cluster_package", "package",dict(N=n,E=ne),dict(
        NUM_TILES=n,NUM_ENDPOINTS=ne,ARCHITECTURE_HASH="256'hMANIFEST_HASH"),dict(
        i_clk="gclk",i_rstb="i_rstb",i_clear="counter_clear || package_clear || cfg_flush",
        i_enable="configuration_enable && !commit_inflight && control_o_state == 4'd2",
        i_commit_fire="i_cfg_commit_valid && o_cfg_commit_ready",i_owner_id="owner",
        i_kernel_id="kernel",i_allocation_generation="allocation_generation",
        i_topology_id=mesh["o_topology_id"],i_next_epoch="mesh_o_active_epoch + 4'd1",
        i_commit_package_id="i_cfg_commit_package_id",i_commit_context_id="i_cfg_commit_context_ids[7:0]",
        i_commit_context_versions="i_cfg_commit_context_versions",i_commit_epoch="i_cfg_commit_epoch",
        i_prepared_image_crcs="prepared_crcs",o_commit_compatible="package_compatible",
        o_suspend_safe="package_suspend_safe",o_idle="package_idle"),package_public)
    # These are registers, not nets, in the final generated declarations.
    w.registers |= set(captures) | {"commit_inflight"}
    w.statements += ["    always_ff @(posedge gclk) begin",
        "        if (!i_rstb || cfg_commit_complete || cfg_commit_error || cfg_flush)",
        "            commit_inflight <= 1\'b0;",
        "        else if (i_cfg_commit_valid && o_cfg_commit_ready) commit_inflight <= 1\'b1;",
        "    end"]
    control_bind = dict(i_clk="i_clk", i_rstb="i_rstb", i_transport_idle="transport_idle",
        i_events_empty="event_empty && !(|tile_events) && !sp_o_event_valid",
        i_all_quiescent="all_quiescent",
        i_cfg_idle="cfg_idle && package_idle", i_suspend_allowed="package_suspend_safe",
        i_cfg_hold="cfg_hold", i_cfg_commit_complete="cfg_commit_complete",
        i_cfg_commit_error="cfg_commit_error", i_cfg_package_id="commit_package",
        i_cfg_owner_id="commit_owner", i_cfg_kernel_id="commit_kernel",
        i_cfg_context_id="commit_context", i_cfg_epoch="commit_epoch",
        i_completion_mask="completion_mask", i_fault="fault", i_fault_code="fault_code",
        i_fault_source="fault_source", i_memory_release_done="memory_release_done",
        i_memory_release_error="memory_release_error", i_cfg_flushed="cfg_flushed",
        o_memory_release="memory_release", o_cfg_flush="cfg_flush", o_cfg_release="cfg_release",
        o_snapshot="snapshot", o_counter_clear="counter_clear", o_error_clear="error_clear",
        o_package_clear="package_clear", o_launch_clear="snapshot_clear_completion",
        o_terminal_event="terminal_event", i_terminal_ready="terminal_ready",
        o_fault_event="fault_event", i_fault_event_ready="fault_event_ready",
        o_allocated="allocated", o_running="running", o_boundary_enable="boundary_enable",
        o_configuration_enable="configuration_enable", o_owner_id="owner", o_kernel_id="kernel",
        o_package_id="package_id", o_context_id="context_id", o_epoch="epoch",
        o_allocation_generation="allocation_generation", o_first_error_code="first_error_code",
        o_first_error_source="first_error_source", o_tile_runtime_valid="tile_runtime_valid",
        i_tile_runtime_ready="tile_runtime_ready", o_tile_runtime_command="tile_runtime_command",
        i_tile_response_valid="tile_response_valid", o_tile_response_ready="tile_response_ready",
        i_tile_response_error="tile_response_error", i_tile_response_command="tile_response_command",
        i_tile_response_tag="tile_response_tag", i_tile_state="tile_state")
    expose = {p: p for p in ports("cluster_control", dict(N=n)) if p.startswith(
        ("i_runtime_", "o_runtime_"))}
    expose.pop("i_runtime_valid")
    expose.pop("o_runtime_ready")
    wire("runtime_native_ready")
    control_bind.update(i_runtime_valid="i_runtime_valid && i_test_mode === 1'b0 && i_scan_enable === 1'b0",
                        o_runtime_ready="runtime_native_ready")
    w.port("i_runtime_valid", "input")
    w.port("o_runtime_ready", "output")
    w.assign("o_runtime_ready", "runtime_native_ready && i_test_mode === 1'b0 && i_scan_enable === 1'b0")
    control = w.instance("cluster_control", "control", dict(N=n), dict(
        NUM_TILES=n, TIMEOUT_CYCLES=d["lifecycle_timeout"]), control_bind, expose)
    # Registered response tag is the native fanout correlation ID as well.
    for tile in tiles:
        assert tile["i_runtime_request_tag"] == "control_o_runtime_response_tag"
    for k, inst in enumerate(w.instances):
        w.instances[k] = inst.replace("control_o_runtime_response_tag", "o_runtime_response_tag")
    wire("fabrics_enable")
    w.assign("fabrics_enable", f"allocated && !cfg_hold && !{control['o_fatal']}")
    # Replace the preliminary mesh enable with the accepted-work permission.
    for k, inst in enumerate(w.instances):
        if "u_mesh (" in inst: w.instances[k] = inst.replace(".i_enable(running)", ".i_enable(fabrics_enable)")
    w.port("o_cluster_clock_enable", "output")
    w.port("o_boundary_isolation_enable", "output")
    w.assign("o_cluster_clock_enable", "1'b1" if not d["clock_gating"] else
        "i_rstb !== 1'b1 || allocated || i_runtime_valid === 1'b1 || o_runtime_response_valid || "
        "!cfg_idle || !event_empty || i_test_mode === 1'b1 || i_scan_enable === 1'b1")
    w.assign("o_boundary_isolation_enable", "!boundary_enable")
    w.instances.append("""    clock_gate u_clock_gate (
        .i_clk(i_clk),
        .i_enable(o_cluster_clock_enable),
        .i_test_enable(i_test_mode === 1'b1 || i_scan_enable === 1'b1),
        .o_gclk(gclk));""")

    # Store bindings are explicit one-command directories. An accepted descriptor
    # is remembered across the native admission pulse; failed admissions do not bind.
    for name, width in dict(candidate_identity=134, candidate_format=16,
                           candidate_channel=1, candidate_store=1).items(): wire(name, width)
    w.registers.update(("descriptor_pending", "store_bound", "store_identity", "store_format",
                        "store_channel", "candidate_identity", "candidate_format",
                        "candidate_channel", "candidate_store"))
    w.assign("o_mst_descriptor_ready", f"{mst['o_descriptor_ready']} && running && "
        "!descriptor_pending && (!descriptor_is_store || !store_bound)")
    w.assign("o_mst_descriptor_accepted", mst["o_descriptor_accepted"])
    w.assign("o_mst_descriptor_rejected", mst["o_descriptor_rejected"])
    w.statements += ["    always_ff @(posedge gclk) begin",
        "        if (!i_rstb || counter_clear) begin",
        "            descriptor_pending <= 1'b0;", "            store_bound <= 1'b0;",
        "            store_identity <= '0;", "            store_format <= '0;",
        "            store_channel <= 1'b0;", "            candidate_identity <= '0;",
        "            candidate_format <= '0;", "            candidate_channel <= 1'b0;",
        "            candidate_store <= 1'b0;", "        end else begin",
        "            if (i_mst_descriptor_valid && o_mst_descriptor_ready) begin",
        "                descriptor_pending <= 1'b1;",
        "                candidate_identity <= i_mst_descriptor_identity;",
        "                candidate_format <= i_mst_descriptor_format;",
        "                candidate_channel <= i_mst_descriptor_source[4];",
        "                candidate_store <= descriptor_is_store;", "            end",
        "            if (o_mst_descriptor_accepted || o_mst_descriptor_rejected)",
        "                descriptor_pending <= 1'b0;",
        "            if (o_mst_descriptor_accepted && candidate_store) begin",
        "                store_bound <= 1'b1;", "                store_identity <= candidate_identity;",
        "                store_format <= candidate_format;", "                store_channel <= candidate_channel;",
        "            end",
        "            if (o_mst_completion_valid && i_mst_completion_ready === 1'b1 &&",
        "                o_mst_completion_identity == store_identity) store_bound <= 1'b0;",
        "        end", "    end"]
    for t, tile in enumerate(tiles):
        is_mst = int(t == mst_index)
        for p in range(2):
            idx = t * 2 + p
            bind = dict(i_enable="fabrics_enable", i_context_id="context_id",
                i_native_version=f"tile_versions[{t*16}+:16]",
                i_route_version=mesh["o_active_context_version"], i_owner_id="owner",
                i_kernel_id="kernel", i_package_id="package_id",
                i_allocation_generation="allocation_generation", i_epoch="epoch",
                i_mst_epoch=mst["o_execution_epoch"],
                i_native_tx_valid=f"{tile['o_data_out_valid']}[{p}]",
                o_native_tx_ready=f"{tile['i_data_out_ready']}[{p}]",
                i_native_tx_data=f"{tile['o_data_out_payload']}[{p*32}+:32]",
                i_native_tx_metadata=f"{tile['o_data_out_metadata']}[{p*256}+:256]",
                o_mesh_tx_valid=f"{mesh['i_tile_tx_valid']}[{idx}]",
                i_mesh_tx_ready=f"{mesh['o_tile_tx_ready']}[{idx}]",
                o_mesh_tx_data=f"{mesh['i_tile_tx_data']}[{idx*32}+:32]",
                o_mesh_tx_metadata=f"{mesh['i_tile_tx_metadata']}[{idx*512}+:512]",
                i_mesh_rx_valid=f"{mesh['o_tile_rx_valid']}[{idx}]",
                o_mesh_rx_ready=f"{mesh['i_tile_rx_ready']}[{idx}]",
                i_mesh_rx_data=f"{mesh['o_tile_rx_data']}[{idx*32}+:32]",
                i_mesh_rx_metadata=f"{mesh['o_tile_rx_metadata']}[{idx*512}+:512]",
                o_native_rx_valid=f"{tile['i_data_in_valid']}[{p}]",
                i_native_rx_ready=f"{tile['o_data_in_ready']}[{p}]",
                o_native_rx_data=f"{tile['i_data_in_payload']}[{p*32}+:32]",
                o_native_rx_metadata=f"{tile['i_data_in_metadata']}[{p*256}+:256]",
                i_store_valid=f"store_bound && store_channel == 1'd{p}" if is_mst else "1'b0",
                i_store_identity="store_identity", i_store_format="store_format",
                o_error=f"metadata_error[{idx}]")
            w.instance("cluster_stream_adapter", f"stream{idx}", {},
                       dict(IS_MST=is_mst, TILE_ID=sorted(d["tiles"], key=lambda t: (t["row"], t["col"]))[t]["id"]), bind)

    bridge_bind = dict(i_clk="gclk", i_rstb="i_rstb")
    for kind in ("read", "write"):
        for short, native in dict(valid="valid", address="address", size_log2="size_log2",
                                  tag="tag", identity="identity", region="region_id",
                                  generation="generation").items():
            bridge_bind[f"i_{kind}_{short}"] = mst[f"o_scratchpad_{kind}_{native}"]
        bridge_bind[f"o_{kind}_ready"] = mst[f"i_scratchpad_{kind}_ready"]
        bridge_bind[f"o_{kind}_rsp_valid"] = mst[f"i_scratchpad_{kind}_response_valid"]
        bridge_bind[f"i_{kind}_rsp_ready"] = mst[f"o_scratchpad_{kind}_response_ready"]
    bridge_bind.update(i_write_data=mst["o_scratchpad_write_data"],
        i_write_strobe=mst["o_scratchpad_write_strobe"],
        o_read_data=mst["i_scratchpad_read_response_data"],
        o_write_bytes_committed=mst["i_scratchpad_write_response_bytes_committed"])
    for p, native in dict(o_request_valid="i_client_req_valid", i_request_ready="o_client_req_ready",
        o_request_opcode="i_client_req_opcode", o_request_address="i_client_req_addr",
        o_request_size="i_client_req_size", o_request_data="i_client_req_wdata",
        o_request_strobe="i_client_req_wstrb", o_request_owner="i_client_req_owner_id",
        o_request_kernel="i_client_req_kernel_id", o_request_region="i_client_req_region_id",
        o_request_generation="i_client_req_generation", o_request_tag="i_client_req_tag",
        i_response_valid="o_client_rsp_valid", o_response_ready="i_client_rsp_ready",
        i_response_error="o_client_rsp_error", i_response_data="o_client_rsp_rdata",
        i_response_tag="o_client_rsp_tag", i_response_opcode="o_client_rsp_opcode",
        i_response_region="o_client_rsp_region_id", i_response_generation="o_client_rsp_generation").items():
        direction, total = ports("banked_scratchpad", g["sp"])[native]
        width = total // 4
        bridge_bind[p] = f"{sp[native]}[{2*width}+:{width}]"
    bridge = w.instance("cluster_memory_bridge", "memory_bridge", dict(
        ADDRESS_WIDTH=g["sp"]["A"], TAG_WIDTH=76, IDENTITY_WIDTH=134), dict(
        ADDRESS_WIDTH=g["sp"]["A"], TAG_WIDTH=76, IDENTITY_WIDTH=134), bridge_bind)
    for p in ("error", "tag", "identity"):
        for kind in ("read", "write"):
            w.assign(mst[f"i_scratchpad_{kind}_response_{p}"], bridge[f"o_rsp_{p}"])
    w.assign(mst["i_scratchpad_conflict"], "|sp_o_bank_conflict")
    # Three host/system-memory clients share the same permission-checked banks.
    for p, (direction, total) in ports("banked_scratchpad", g["sp"]).items():
        if not p.startswith(("i_client_", "o_client_")) or p == "o_client_outstanding": continue
        width = total // 4
        name = p[:2] + "memory_" + p[2:].removeprefix("client_")
        w.port(name, direction, 3*width)
        for host, physical_client in enumerate((0, 1, 3)):
            native_slice = f"{sp[p]}[{physical_client*width}+:{width}]"
            public_slice = f"{name}[{host*width}+:{width}]"
            if direction == "input":
                value = public_slice
                if p == "i_client_req_valid":
                    value += " && configuration_enable && !commit_inflight"
                w.assign(native_slice, value)
            else:
                value = native_slice
                if p == "o_client_req_ready":
                    value += " && configuration_enable && !commit_inflight"
                w.assign(public_slice, value)
    # Per-client corrected/permission outputs are status only; the native response
    # retains each request's error/opcode/tag and identity generation.
    for p in mst:
        if p.startswith("i_scratchpad_") and p != "i_scratchpad_conflict":
            statement = f"    assign {mst[p]} = '0;"
            if statement in w.statements:
                w.statements.remove(statement)
                w.ties[f"tile{mst_index}"].pop(p, None)

    event_bind = dict(i_clk="i_clk", i_rstb="i_rstb", i_clear_completion=
        "counter_clear || snapshot_clear_completion", i_tile_valid="tile_events", o_tile_ready="tile_events_ready",
        i_tile_payload="tile_event_payload", i_memory_valid=sp["o_event_valid"],
        o_memory_ready=sp["i_event_ready"], i_memory_payload="memory_event_payload",
        i_terminal_valid="terminal_event", o_terminal_ready="terminal_ready",
        i_fault_valid="fault_event", o_fault_ready="fault_event_ready",
        i_fault_code="first_error_code", i_fault_source="first_error_source",
        i_owner_id="owner", i_kernel_id="kernel", i_context_id="context_id",
        i_package_id="commit_inflight ? commit_package : package_id",
        i_epoch="commit_inflight ? commit_epoch : epoch", o_empty="event_empty",
        o_completion_mask="completion_mask", o_duplicate_completion="duplicate_completion",
        o_error="event_error")
    wire("event_error")
    wire("snapshot_clear_completion")

    wire("memory_event_payload", 256)
    w.assign("memory_event_payload", "{191'd0, sp_o_event_generation_b, "
        "sp_o_event_generation_a, sp_o_event_kernel_id, sp_o_event_region_b, "
        "sp_o_event_region_a, sp_o_event_error_code, sp_o_event_code}")
    event_public = {p: p for p in ports("cluster_events", dict(N=n)) if p.startswith(
        ("o_event_", "i_event_"))}
    ids = [t["id"] for t in sorted(d["tiles"], key=lambda t: (t["row"], t["col"]))]
    w.instance("cluster_events", "events", dict(N=n, EW=377), dict(
        NUM_TILES=n, TILE_ID_TABLE=packed(ids, 8)), event_bind, event_public)
    w.port("o_interrupt", "output")
    w.assign("o_interrupt", "!event_empty || fault_event")
    w.assign("transport_idle", f"{mesh['o_idle']} && {sp['o_idle']} && "
        f"{bridge['o_idle']} && {mst['o_mst_quiescent'] if 'o_mst_quiescent' in mst else mst['o_mst_quiescent']} && "
        "!descriptor_pending && !store_bound")
    w.assign("all_quiescent", "&tile_quiescent")
    w.assign(root["i_endpoint_quiescent"], f"{{{ne}{{commit_inflight}}}} | {{{{2{{transport_idle}}}}, tile_quiescent}}")
    # Root fail-stop is distinct from a rejected software request. A bad CRC or
    # permission result can be repaired while held; execution integrity faults isolate.
    w.assign("fault", f"(|tile_fatal) || (running && |tile_error) || cfg_fail_stop || "
        f"{mesh['o_error']} || {sp['o_error']} || {bridge['o_error']} || "
        "(|metadata_error) || (|boundary_bad) || duplicate_completion || "
        f"{proxies[0]['o_error']} || {proxies[1]['o_error']} || "
        "package_o_error || prepared_crc_bad || counter_snapshot_bad || event_error")
    w.assign("fault_code", "(|metadata_error) || (|boundary_bad) ? 8'd14 : "
        "event_error ? 8'd17 : duplicate_completion ? 8'd15 : cfg_fail_stop ? 8'd11 : "
        f"{mesh['o_error']} ? 8'd12 : {sp['o_error']} || {bridge['o_error']} ? 8'd13 : 8'd9")
    tile_source = "8'hff"
    metadata_source = "8'hff"
    for t in reversed(range(n)):
        tile_source = f"tile_fatal[{t}] || (running && tile_error[{t}]) ? 8'd{ids[t]} : " + tile_source
        metadata_source = f"(|metadata_error[{t*2}+:2]) ? 8'd{ids[t]} : " + metadata_source
    w.assign("fault_source", "(|boundary_bad) ? 8'd246 : (|metadata_error) ? ("+
        metadata_source+") : event_error || duplicate_completion ? 8'd245 : cfg_fail_stop ? 8'd242 : "+
        "mesh_o_error ? 8'd240 : sp_o_error || memory_bridge_o_error ? 8'd241 : "+
        "package_o_error || prepared_crc_bad || counter_snapshot_bad ? 8'd244 : ("+tile_source+")")
    status = dict(topology_id=(32, mesh["o_topology_id"]),
        package_manifest_valid=(1, "package_o_manifest_valid"),
        cluster_id=(8, f"8'd{d['cluster_id']}"), arch_version=(16, "16'd1"),
        cluster_state=(4, control["o_state"]), owner_id=(16, "owner"), kernel_id=(16, "kernel"),
        package_id=(32, "package_id"), execution_epoch=(4, "epoch"),
        allocation_generation=(16, "allocation_generation"), tile_active_mask=(n, "tile_busy"),
        tile_idle_mask=(n, "tile_idle"), tile_error_mask=(n, "tile_error"),
        scratchpad_busy=(1, f"!{sp['o_idle']} || !{bridge['o_idle']}"),
        network_busy=(1, f"!{mesh['o_idle']}"), dma_busy=(1, f"!{mst['o_mst_quiescent']}"),
        configuration_busy=(1, "!cfg_idle || !package_idle"),
        quiescent=(1, "transport_idle && all_quiescent && cfg_idle && event_empty && "
        "package_idle && !o_runtime_response_valid"),
        error=(1, control["o_error"]), fatal_error=(1, control["o_fatal"]),
        first_error_code=(8, "first_error_code"), first_error_source=(8, "first_error_source"),
        completion_mask=(n, "completion_mask"), tile_versions=(n*16, "tile_versions"),
        scratchpad_generation=(16, proxies[1]["o_region_generation"]))
    for name, (width, value) in status.items():
        w.port("o_status_"+name, "output", width)
        w.assign("o_status_"+name, value)
    w.port("o_status_stall_reasons", "output", 8)
    w.assign("o_status_stall_reasons", " | ".join(f"tile_stalls[{t*8}+:8]" for t in range(n)))
    w.port("o_status_manifest_hash", "output", 256)
    w.assign("o_status_manifest_hash", "256'hMANIFEST_HASH")
    # Reuse the released counter bank; a snapshot is coherent and owner-scoped.
    for name, direction, width in (("i_counter_read", "input", 1),
        ("i_counter_owner_id", "input", 16), ("i_counter_index", "input", 3),
        ("o_counter_valid", "output", 1), ("o_counter_value", "output", 48),
        ("o_counter_snapshot_valid", "output", 1)):
        w.port(name, direction, width)
    for name,width in dict(counter_snapshot_current=1,counter_snapshot_bad=1,
                           counter_native_snapshot_valid=1,counter_native_valid=1,
                           counter_native_value=48).items(): wire(name,width)
    w.instances.append("""    // A new allocation cannot authorize the previous owner's snapshot.
    tile_shell_state #(.WIDTH(1), .PROTECTION(1)) u_counter_ownership (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_enable(counter_clear || snapshot),
        .i_data(snapshot && !counter_clear),
        .o_data(counter_snapshot_current),
        .o_bad(counter_snapshot_bad),
        .o_corrected()
    );""")
    wire("counter_access")
    w.assign("counter_access", "allocated && counter_snapshot_current && !counter_snapshot_bad && "
             "i_counter_read === 1'b1 && i_counter_owner_id === owner")
    w.assign("o_counter_valid", "counter_access && counter_native_valid")
    w.assign("o_counter_value", "counter_access ? counter_native_value : 48'd0")
    w.assign("o_counter_snapshot_valid", "allocated && counter_snapshot_current && "
             "!counter_snapshot_bad && counter_native_snapshot_valid")
    wire("counter_events", 8)
    w.assign("counter_events", "{fault, cfg_commit_complete, o_mst_completion_valid && "
        "i_mst_completion_ready, (|mesh_o_boundary_tx_valid), (|mesh_i_boundary_rx_valid), "
        "o_runtime_ready && i_runtime_valid, running, allocated}")
    w.instances.append("""    performance_counters #(
        .COUNTER_WIDTH(48),
        .NUM_COUNTERS(8),
        .NUM_EVENTS(8),
        .INCREMENT_WIDTH(1),
        .HAS_THRESHOLD(0)
    ) u_counters (
        .i_clk(i_clk),
        .i_rstb(i_rstb),
        .i_global_enable(allocated),
        .i_freeze(1'b0),
        .i_counter_enable(8'hff),
        .i_clear({8{counter_clear}}),
        .i_event_select(24'hfac688),
        .i_event_valid(counter_events),
        .i_event_increment(8'hff),
        .i_threshold_enable(8'd0),
        .i_threshold_value(384'd0),
        .i_snapshot(snapshot),
        .i_read_enable(counter_access),
        .i_read_snapshot(1'b1),
        .i_read_index(i_counter_index),
        .o_read_data(counter_native_value), .o_read_overflow(), .o_read_valid(counter_native_valid),
        .o_counter_overflow(), .o_threshold_event(), .o_config_error(),
        .o_snapshot_valid(counter_native_snapshot_valid)
    );""")


def format_rtl(text):
    """Keep generated declarations and expressions within the 100-column RTL style."""
    lines = []
    for line in text.splitlines():
        while len(line) > 100:
            choices = [line.rfind(token, 0, 96) for token in (" && ", " || ", ", ", " ? ", " : ", " | ", " = ")]
            cut = max(choices)
            if cut < 20:
                # A long port name plus a long signal can exceed one line even
                # without arithmetic. Break inside the named connection.
                cut = line.find("(")+1 if line.lstrip().startswith(".") else -1
                if cut < 20: break
                lines.append(line[:cut].rstrip())
                line = "            " + line[cut:].lstrip()
                continue
            cut += 3 if line[cut:cut+3] in (" &&", " ||") else (2 if line[cut] == " " else 1)
            lines.append(line[:cut].rstrip())
            line = "        " + line[cut:].lstrip()
        lines.append(line)
    return "\n".join(lines) + "\n"


def generate(descriptor: Path, output: Path, artifacts: Path):
    raw = descriptor.read_bytes()
    d = tomllib.loads(raw.decode("utf-8"))
    g = validate(d)
    for name in SOURCES:
        if not (RTL / f"{name}.sv").is_file():
            raise ValueError(f"Missing released dependency: {name}")
    wrapper, tiles, word_counts = build(d, g)
    hashes = {f"src/rtl/{name}.sv": hashlib.sha256((RTL / f"{name}.sv").read_bytes()).hexdigest()
              for name in SOURCES}
    contract = dict(schema="mosaic-cluster-contract-v1", descriptor=d, geometry=g,
        tile_parameter_table=[dict(id=t["id"], parameters=tile_parameters(t)) for t in tiles],
        tile_present_mask=(1 << g["n"]) - 1,
        tile_class_table=[0 if t["class"] == "BCT" else 3 for t in tiles],
        tile_id_table=[t["id"] for t in tiles], tile_coordinate_table=[
            [t["row"], t["col"]] for t in tiles],
        config_endpoint_table=[dict(id=t["id"], type=t["class"], slot=i, words=word_counts[i])
            for i, t in enumerate(tiles)] + [dict(id=240, type="static_mesh", words=word_counts[-2]),
                                           dict(id=241, type="scratchpad", words=2)],
        scratchpad_client_table=[dict(client=2, tile=next(t["id"] for t in tiles if t["class"] == "MST"))]
            + [dict(client=c, boundary=i) for i,c in enumerate((0,1,3))],
        domain_table=dict(clock="i_clk", reset="i_rstb", always_on="cluster_control/events/counters",
                          power="single always-powered domain", isolation="ready/valid containment"),
        features=dict(predicate_network=False, express_links=False, global_noc=False,
                      power_gating=False, retention=False, dvfs=False, async_clocks=False,
                      partitioning=False, dma="released MST streaming ingress/egress"),
        event_transport=dict(arbitration="fault, terminal, memory, then held round-robin tile grant",
            queue="released parity-protected event_barrier_queue",
            identity="captured in full at admission", sequence="32-bit nonwrapping, reset-only recovery",
            failure="sticky integrity fault source 245; corrupt export is invalid until global reset",
            critical_fairness="tiles progress only when higher-priority sources eventually deassert"),
        metadata=dict(schema="mosaic-cluster-stream-v1", width=512, native_common_width=256,
                      routing_prefix_bits=56, common_offset=64, owner_offset=320,
                      package_offset=336, producer_offset=368, reserved_from=376),
        dependency_sha256=hashes,
        generator_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in HERE.glob("*.py")},
        signoff=dict(python_simulation="NOT_RUN", synthesis="Design Compiler (deferred)",
                     lint="NOT_RUN", cdc="NOT_RUN", physical="NOT_CHARACTERIZED"),
        disabled_input_ties=wrapper.ties)
    identity = hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()
    contract["manifest_sha256"] = identity
    text = wrapper.render(identity).replace("256'hMANIFEST_HASH", "256'h"+identity)
    for name in getattr(wrapper, "registers", ()):
        text = re.sub(r"    wire (\[[^\]]+\] )?"+name+r";",
                      lambda m: "    logic "+(m[1] or "")+name+";", text)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_rtl(text))
    artifacts.mkdir(parents=True, exist_ok=True)
    contract["generated_rtl_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    (artifacts/"manifest.json").write_text(json.dumps(contract, indent=2)+"\n")
    # Relative file lists remain usable after moving the checkout to the DC server.
    (artifacts/"sources.f").write_text("\n".join(f"src/rtl/{n}.sv" for n in SOURCES)+
                                      "\n"+str(output.relative_to(ROOT) if output.is_relative_to(ROOT) else output)+"\n")
    (artifacts/"ports.json").write_text(json.dumps(wrapper.public, indent=2)+"\n")
    return contract


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--descriptor", type=Path, default=HERE/"mvp.toml")
    parser.add_argument("--output", type=Path, default=RTL/"mosaic_blocks/cluster.sv")
    parser.add_argument("--artifacts", type=Path, default=HERE/"generated")
    args = parser.parse_args()
    contract = generate(args.descriptor.resolve(), args.output.resolve(), args.artifacts.resolve())
    print(f"Generated {args.output}: {contract['manifest_sha256']}")


if __name__ == "__main__":
    main()
