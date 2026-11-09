"""Generate a rectangular native-tile fabric using the released local switches.

Each tile retains its native configuration, runtime, predicate and event ports.
All MST scratchpad clients share real permission-checked SRAM banks. Native
payloads are transported in full; an incompatible narrowing stalls and reports
an error instead of truncating a token. Routing is configured per local switch.
"""

import hashlib
import importlib.util
import json
from pathlib import Path

from flavor.model import ROOT, generator as legacy
from flavor.native import defaults, integer, ports
from flavor.tile_catalog import effective

PROFILE = "Configurable"


def load_sources(directory, filename):
    path = ROOT / f"src/gen/{directory}/{filename}.py"
    spec = importlib.util.spec_from_file_location(f"flavor_{filename}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SOURCES


_sources = tuple(dict.fromkeys((*legacy.SOURCES, *load_sources("sft", "sft_sources"),
    *load_sources("cpt", "cpt_sources"), "mosaic_blocks/sft", "mosaic_blocks/cpt",
    "building_blocks/vector_lane_pkg", "mosaic_blocks/vct_pkg", "basic/vector_register_file",
    "building_blocks/vector_lane", "mosaic_blocks/vct_vrf", "mosaic_blocks/vct_accumulator",
    "mosaic_blocks/vct_body", "mosaic_blocks/vct")))
SOURCES = tuple(name for name in _sources if name.endswith("_pkg")) + tuple(
    name for name in _sources if not name.endswith("_pkg"))


def parameters(tile):
    kind = tile["class"]
    p = defaults(kind) | effective(tile) | {"TILE_ID": tile["id"]}
    if kind == "BCT":
        p.update(DATA_INPUT_PORTS=2, DATA_OUTPUT_PORTS=2)
    if kind == "SFT":
        p["CONFIG_WORD_COUNT"] = (512 + (1 << p["LUT_ADDRESS_WIDTH"]) * p["OUTPUT_WIDTH"] +
            ((p["POLY_MAX_DEGREE"] + 1) * p["POLY_COEFFICIENT_WIDTH"] if p["ENABLE_POLYNOMIAL"]
             else 0) + 63) // 64
    if kind == "CPT":
        p["PREDICATE_WIDTH"] = p["PREDICATE_LANES"]
        p["CONFIG_WORD_COUNT"] = (512 + p["MAX_LOOP_DEPTH"] *
            (3 * p["INDEX_WIDTH"] + p["TRIP_COUNT_WIDTH"] + 5) + 63) // 64
    return p


def validate_parameters(tile):
    p = parameters(tile)
    kind = tile["class"]

    def require(condition, message):
        if not condition:
            raise ValueError(f"Tile {tile['id']}: {message}")

    if kind == "BCT":
        require(2 * p["MULTIPLY_OPERAND_WIDTH"] <= p["DATA_WIDTH"],
                "twice the multiplier operand width must fit the tile data width")
    if kind == "MST":
        require(p["SUPPORT_CIRCULAR"] == 0,
                "circular addressing requires an unreleased MST adapter")
        require(p["SUPPORT_WIDTH_CONVERSION"] or p["SHELL_DATA_WIDTH"] == p["MEMORY_DATA_WIDTH"],
                "different shell and memory widths require width conversion")
    if kind == "VCT":
        require(p["ACC_WIDTH"] >= 2 * p["ELEMENT_WIDTH"],
                "ACC_WIDTH must be at least twice ELEMENT_WIDTH")
        require(p["WRITE_SLICE_WIDTH"] <= p["ELEMENT_WIDTH"] and
                p["ELEMENT_WIDTH"] % p["WRITE_SLICE_WIDTH"] == 0 and
                p["ACC_WIDTH"] % p["WRITE_SLICE_WIDTH"] == 0,
                "write slices must divide both element and accumulator widths")
        require(max(p["MUL_LATENCY"], p["MAC_LATENCY"]) <= p["LANE_LATENCY"],
                "lane latency must cover multiplier and MAC latency")
        require(not p["ENABLE_DOT_PRODUCT"] or p["ACC_WIDTH"] >=
                2 * p["ELEMENT_WIDTH"] + (p["NUM_LANES"] - 1).bit_length(),
                "dot-product accumulator is too narrow")
    if kind == "SFT":
        require(p["INPUT_FRAC_BITS"] < p["INPUT_WIDTH"] and
                p["OUTPUT_FRAC_BITS"] < p["OUTPUT_WIDTH"] and
                p["INTERNAL_FRAC_BITS"] < p["INTERNAL_WIDTH"],
                "fraction bits must fit their associated number format")
        require(p["INPUT_FRAC_BITS"] < p["POLY_COEFFICIENT_WIDTH"] <= p["INTERNAL_WIDTH"],
                "polynomial coefficients must fit the internal format")
        for prefix, headroom in (("RECIP", 2), ("RSQRT", 3)):
            require(p[f"{prefix}_INTERNAL_FRAC_BITS"] + headroom <=
                    p[f"{prefix}_INTERNAL_WIDTH"] and p[f"{prefix}_SEED_ADDRESS_WIDTH"] + 2
                    <= p[f"{prefix}_INTERNAL_FRAC_BITS"],
                    f"{prefix} internal format needs integer and seed headroom")
        require(p["REDUCTION_LANES"] * p["REDUCTION_ELEMENT_WIDTH"] <= p["SHELL_DATA_WIDTH"],
                "reduction lanes exceed the shell payload width")
        require(2 * p["REDUCTION_ELEMENT_WIDTH"] + p["MAX_REDUCTION_ELEMENTS"].bit_length()
                <= p["REDUCTION_ACC_WIDTH"] <= p["SHELL_DATA_WIDTH"],
                "reduction accumulator cannot represent exact SUMSQ growth")
        require(p["RESULT_QUEUE_DEPTH"] >= p["MAX_INFLIGHT"],
                "result queue must cover all in-flight operations")
    if kind == "CPT":
        require(tile["id"] <= 255, "CPT native event records require an eight-bit producer ID")
        require(p["LOOP_EXPORT_LEVELS"] <= p["MAX_LOOP_DEPTH"],
                "loop export levels exceed loop depth")
        require(min(p["ACTION_QUEUE_DEPTH"], p["ACTION_RESPONSE_DEPTH"]) >=
                p["MAX_OUTSTANDING_ACTIONS"], "action queues must cover outstanding actions")
    return p


def validate(d):
    required = {"schema", "profile", "cluster_id", "rows", "cols", "context_depth",
                "scratchpad_banks", "scratchpad_bank_words", "clock_gating",
                "lifecycle_timeout", "tiles"}
    if not isinstance(d, dict) or set(d) != required:
        raise ValueError("A configurable grid requires the standard cluster descriptor fields")
    if d["schema"] != "mosaic-cluster-v1" or d["profile"] != PROFILE:
        raise ValueError("Expected the Configurable cluster profile")
    if any(type(d[key]) is not int or d[key] < 1 for key in ("rows", "cols")):
        raise ValueError("Grid rows and columns must be positive integers")
    if d["context_depth"] != 4 or type(d["context_depth"]) is not int:
        raise ValueError("Native flavor contexts use depth four")
    if type(d["clock_gating"]) is not bool:
        raise ValueError("clock_gating must be a boolean")
    if type(d["cluster_id"]) is not int or not 0 <= d["cluster_id"] < 65536:
        raise ValueError("cluster_id must be an integer from 0 to 65535")
    if type(d["lifecycle_timeout"]) is not int or not 16 <= d["lifecycle_timeout"] <= 16777215:
        raise ValueError("lifecycle_timeout must be an integer from 16 to 16777215")
    for key in ("scratchpad_banks", "scratchpad_bank_words"):
        value = d[key]
        if type(value) is not int or value < 1 or value & (value - 1):
            raise ValueError("Scratchpad banks and words must be positive powers of two")
    capacity = d["scratchpad_banks"] * d["scratchpad_bank_words"] * 8
    if d["scratchpad_banks"] > 16 or not 16 <= capacity <= 1048576:
        raise ValueError("Scratchpad geometry must use at most 16 banks and 16 B–1 MiB")
    tiles = d["tiles"]
    if not isinstance(tiles, list) or len(tiles) != d["rows"] * d["cols"]:
        raise ValueError("Every grid position requires an explicit tile")
    ids, positions = set(), set()
    native = []
    for tile in tiles:
        if (not isinstance(tile, dict) or not {"id", "class", "row", "col"} <= tile.keys()
                or tile.keys() - {"id", "class", "row", "col", "parameters"}):
            raise ValueError("Tiles require id, class, row, col and optional parameters")
        if any(type(tile[key]) is not int for key in ("id", "row", "col")):
            raise ValueError("Tile identities and coordinates must be integers")
        if tile["class"] not in ("BCT", "MST", "VCT", "SFT", "CPT"):
            raise ValueError(f"Unsupported tile class: {tile['class']}")
        position = tile["row"], tile["col"]
        if (not 0 <= tile["id"] < 65536 or tile["id"] in ids or position in positions or
                not 0 <= tile["row"] < d["rows"] or not 0 <= tile["col"] < d["cols"]):
            raise ValueError("Duplicate or out-of-range tile identity or position")
        ids.add(tile["id"])
        positions.add(position)
        p = validate_parameters(tile)
        interface = ports(f"mosaic_blocks/{tile['class'].lower()}", p)
        native.append(dict(tile=tile, parameters=p, ports=interface,
            width=interface["i_data_in_payload"][1] // interface["i_data_in_valid"][1],
            metadata=interface["i_data_in_metadata"][1] // interface["i_data_in_valid"][1]))
    return dict(n=len(tiles), capacity=capacity, native=native,
                data_width=max(item["width"] for item in native),
                metadata_width=max(item["metadata"] for item in native))


class Fabric(legacy.Wrapper):
    port_catalog = staticmethod(ports)


def build(d, geometry):
    w = Fabric()
    for name in ("i_clk", "i_rstb", "i_enable", "i_test_mode", "i_scan_enable"):
        w.port(name, "input")
    w.port("o_cluster_id", "output", 16)
    w.assign("o_cluster_id", f"16'd{d['cluster_id']}")
    w.wire("gclk")
    if d["clock_gating"]:
        w.instance("common/clock_gate", "clock_gate", {}, {}, dict(i_clk="i_clk",
            i_enable="i_enable || !i_rstb", i_test_enable="i_test_mode || i_scan_enable",
            o_gclk="gclk"))
    else:
        w.assign("gclk", "i_clk")
    width, metadata = geometry["data_width"], geometry["metadata_width"]
    natives, routers, descriptions = [], {}, []
    for item in sorted(geometry["native"], key=lambda item:
                       (item["tile"]["row"], item["tile"]["col"])):
        tile, p, interface = item["tile"], item["parameters"], item["ports"]
        prefix = f"tile_{tile['id']}"
        bindings = dict(i_clk="gclk", i_rstb="i_rstb", i_cfg_clk="gclk", i_cfg_rstb="i_rstb",
            i_test_enable="i_test_mode", i_scan_enable="i_scan_enable")
        expose = {name: name[:2] + prefix + "_" + name[2:] for name in interface
                  if name not in bindings and not name.startswith(("i_data_", "o_data_",
                                                                  "i_scratchpad_", "o_scratchpad_"))}
        for name in interface:
            if name.startswith(("i_data_", "o_data_", "i_scratchpad_", "o_scratchpad_")):
                bindings[name] = w.wire(prefix + "_" + name, interface[name][1])
        native = w.instance("mosaic_blocks/" + tile["class"].lower(), prefix, p, p,
                            bindings, expose)
        natives.append((tile, native))
        sp = dict(NUM_INPUTS=6, NUM_OUTPUTS=6, DATA_WIDTH=width,
                  METADATA_WIDTH=metadata, CONTEXT_ID_WIDTH=8)
        bindings = dict(i_clk="gclk", i_rstb="i_rstb")
        for name, (_, bits) in ports("building_blocks/local_switch", sp).items():
            if name.startswith(("i_input_", "o_input_", "i_output_", "o_output_")):
                bindings[name] = w.wire(f"router_{tile['id']}_{name}", bits)
        expose = {name: name[:2] + f"route_{tile['id']}_" + name[2:]
                  for name in ports("building_blocks/local_switch", sp) if name not in bindings}
        router = w.instance("building_blocks/local_switch", f"router_{tile['id']}", sp,
                            sp, bindings, expose)
        routers[tile["row"], tile["col"]] = router
        # Slots 0/1 connect the native tile. Slots 2/3/4/5 are N/E/S/W.
        for channel in range(2):
            tx = channel < interface["o_data_out_valid"][1]
            rx = channel < interface["i_data_in_valid"][1]
            for suffix, source, count in (("data", "payload", item["width"]),
                                          ("metadata", "metadata", item["metadata"])):
                bus = width if suffix == "data" else metadata
                value = f"{bus}'({native['o_data_out_' + source]}[{channel*count}+:{count}])"
                w.assign(f"{router['i_input_' + suffix]}[{channel*bus}+:{bus}]", value if tx else "'0")
            source = native['o_data_out_valid']
            if interface["o_data_out_valid"][1] > 1:
                source += f"[{channel}]"
            w.assign(f"{router['i_input_valid']}[{channel}]", source if tx else "1'b0")
            if tx:
                target = native['i_data_out_ready']
                if interface["i_data_out_ready"][1] > 1:
                    target += f"[{channel}]"
                w.assign(target, f"{router['o_input_ready']}[{channel}]")
            fit = []
            if rx:
                for suffix, destination, count in (("data", "payload", item["width"]),
                                                   ("metadata", "metadata", item["metadata"])):
                    bus = width if suffix == "data" else metadata
                    w.assign(f"{native['i_data_in_' + destination]}[{channel*count}+:{count}]",
                             f"{router['o_output_' + suffix]}[{channel*bus}+:{count}]")
                    if count < bus:
                        fit.append(f"!(|{router['o_output_' + suffix]}"
                                   f"[{channel*bus+count}+:{bus-count}])")
                compatible = " && ".join(fit) or "1'b1"
                w.assign(f"{native['i_data_in_valid']}[{channel}]",
                         f"{router['o_output_valid']}[{channel}] && ({compatible})")
                w.assign(f"{router['i_output_ready']}[{channel}]",
                         f"{native['o_data_in_ready']}[{channel}] && ({compatible})")
                name = w.port(f"o_tile_{tile['id']}_width_error_{channel}", "output")
                w.assign(name, f"{router['o_output_valid']}[{channel}] && !({compatible})")
            else:
                w.assign(f"{router['i_output_ready']}[{channel}]", "1'b0")
        descriptions.append(dict(id=tile["id"], module=tile["class"].lower(),
            parameters=p, native_data_width=item["width"], native_metadata_width=item["metadata"],
            port_prefix=prefix, route_prefix=f"route_{tile['id']}",
            inputs=interface["i_data_in_valid"][1], outputs=interface["o_data_out_valid"][1]))
    boundaries = []
    directions = ((-1, 0, 2, 4, "north"), (0, 1, 3, 5, "east"),
                  (1, 0, 4, 2, "south"), (0, -1, 5, 3, "west"))
    for (row, col), router in routers.items():
        for dr, dc, slot, opposite, direction in directions:
            neighbor = routers.get((row + dr, col + dc))
            if neighbor:
                for field, bits in (("valid", 1), ("data", width), ("metadata", metadata)):
                    w.assign(f"{router['i_input_' + field]}[{slot*bits}+:{bits}]",
                             f"{neighbor['o_output_' + field]}[{opposite*bits}+:{bits}]")
                w.assign(f"{router['i_output_ready']}[{slot}]",
                         f"{neighbor['o_input_ready']}[{opposite}]")
            else:
                prefix = f"boundary_{row}_{col}_{direction}"
                boundaries.append(dict(row=row, col=col, direction=direction, slot=slot,
                                       prefix=prefix))
                for field, bits in (("valid", 1), ("data", width), ("metadata", metadata)):
                    source = w.port(f"i_{prefix}_rx_{field}", "input", bits)
                    dest = w.port(f"o_{prefix}_tx_{field}", "output", bits)
                    w.assign(f"{router['i_input_' + field]}[{slot*bits}+:{bits}]", source)
                    w.assign(dest, f"{router['o_output_' + field]}[{slot*bits}+:{bits}]")
                ready = w.port(f"o_{prefix}_rx_ready", "output")
                w.assign(ready, f"{router['o_input_ready']}[{slot}]")
                ready = w.port(f"i_{prefix}_tx_ready", "input")
                w.assign(f"{router['i_output_ready']}[{slot}]", ready)
    memory(w, d, natives)
    return w, descriptions, boundaries


def memory(w, d, natives):
    msts = [(tile, native) for tile, native in natives if tile["class"] == "MST"]
    tag_width = max((ports("mosaic_blocks/mst", parameters(tile))["o_scratchpad_read_tag"][1]
                     for tile, _ in msts), default=81)
    p = dict(DATA_WIDTH=64, NUM_BANKS=d["scratchpad_banks"],
        BANK_DEPTH_WORDS=d["scratchpad_bank_words"], NUM_CLIENTS=len(msts) + 1,
        CLIENT_TAG_WIDTH=tag_width, CONTROL_PROTECTION=1)
    bindings = dict(i_clk="gclk", i_reset_n="i_rstb", i_enable="i_enable")
    interface = ports("mosaic_blocks/banked_scratchpad", p)
    for name, (_, bits) in interface.items():
        if name.startswith(("i_client_", "o_client_")):
            bindings[name] = w.wire(f"scratchpad_{name}", bits)
    expose = {name: name[:2] + "memory_" + name[2:] for name in interface if name not in bindings}
    sp = w.instance("mosaic_blocks/banked_scratchpad", "scratchpad", p, p, bindings, expose)
    # Client zero is a public host port for initialization and result readback.
    for name, (direction, total) in interface.items():
        if not name.startswith(("i_client_", "o_client_")):
            continue
        bits = total // p["NUM_CLIENTS"]
        public = w.port(name[:2] + "memory_host_" + name[2:].removeprefix("client_"), direction, bits)
        signal = sp[name] if total == 1 else f"{sp[name]}[0+:{bits}]"
        w.assign(signal if direction == "input" else public,
                 public if direction == "input" else signal)
    for client, (tile, native) in enumerate(msts, 1):
        bp = dict(ADDRESS_WIDTH=(d["scratchpad_banks"] * d["scratchpad_bank_words"] * 8 - 1).bit_length(),
                  TAG_WIDTH=tag_width, IDENTITY_WIDTH=138)
        bind = dict(i_clk="gclk", i_rstb="i_rstb")
        for kind in ("read", "write"):
            for short, suffix in dict(valid="valid", address="address", size_log2="size_log2",
                tag="tag", identity="identity", region="region_id", generation="generation").items():
                bind[f"i_{kind}_{short}"] = native[f"o_scratchpad_{kind}_{suffix}"]
            bind[f"o_{kind}_ready"] = native[f"i_scratchpad_{kind}_ready"]
            bind[f"o_{kind}_rsp_valid"] = native[f"i_scratchpad_{kind}_response_valid"]
            bind[f"i_{kind}_rsp_ready"] = native[f"o_scratchpad_{kind}_response_ready"]
        bind.update(i_write_data=native["o_scratchpad_write_data"],
            i_write_strobe=native["o_scratchpad_write_strobe"],
            o_read_data=native["i_scratchpad_read_response_data"],
            o_write_bytes_committed=native["i_scratchpad_write_response_bytes_committed"])
        mapping = dict(o_request_valid="i_client_req_valid", i_request_ready="o_client_req_ready",
            o_request_opcode="i_client_req_opcode", o_request_address="i_client_req_addr",
            o_request_size="i_client_req_size", o_request_data="i_client_req_wdata",
            o_request_strobe="i_client_req_wstrb", o_request_owner="i_client_req_owner_id",
            o_request_kernel="i_client_req_kernel_id", o_request_region="i_client_req_region_id",
            o_request_generation="i_client_req_generation", o_request_tag="i_client_req_tag",
            i_response_valid="o_client_rsp_valid", o_response_ready="i_client_rsp_ready",
            i_response_error="o_client_rsp_error", i_response_data="o_client_rsp_rdata",
            i_response_tag="o_client_rsp_tag", i_response_opcode="o_client_rsp_opcode",
            i_response_region="o_client_rsp_region_id", i_response_generation="o_client_rsp_generation")
        for name, target in mapping.items():
            bits = interface[target][1] // p["NUM_CLIENTS"]
            bind[name] = f"{sp[target]}[{client*bits}+:{bits}]"
        bridge = w.instance("mosaic_blocks/cluster_memory_bridge", f"memory_{tile['id']}", bp, bp, bind)
        for kind in ("read", "write"):
            for suffix in ("error", "tag", "identity"):
                w.assign(native[f"i_scratchpad_{kind}_response_{suffix}"], bridge[f"o_rsp_{suffix}"])
        w.assign(native["i_scratchpad_conflict"], "|" + sp["o_bank_conflict"])


def generate(descriptor, output, artifacts):
    import tomllib
    d = tomllib.loads(Path(descriptor).read_text())
    g = validate(d)
    wrapper, tiles, boundaries = build(d, g)
    record = dict(schema="mosaic-native-fabric-v1", descriptor=d,
        geometry={key: value for key, value in g.items() if key != "native"},
        tile_parameter_table=tiles, boundaries=boundaries,
        routing=dict(slots={"tile0": 0, "tile1": 1, "north": 2, "east": 3, "south": 4, "west": 5},
                     policy="native local_switch configuration; opaque full-width payloads"),
        width_policy="unsigned zero extension; incompatible narrowing stalls and asserts width_error",
        control="per-tile native shell configuration, runtime, predicates and events",
        scratchpad_clients=[dict(client=0, type="host")] + [dict(client=i, tile=tile["id"])
            for i, tile in enumerate((t for t in d["tiles"] if t["class"] == "MST"), 1)],
        dependency_sha256={f"src/rtl/{name}.sv": hashlib.sha256(
            (ROOT / f"src/rtl/{name}.sv").read_bytes()).hexdigest() for name in SOURCES})
    identity = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    record["manifest_sha256"] = identity
    text = wrapper.render(identity).replace("src/gen/cluster/generate.py", "src/gen/flavor/fabric.py")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(legacy.format_rtl(text))
    record["generated_rtl_sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
    artifacts = Path(artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)
    (artifacts / "manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    (artifacts / "ports.json").write_text(json.dumps(wrapper.public, indent=2) + "\n")
    return record
