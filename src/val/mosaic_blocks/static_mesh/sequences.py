"""Specification-directed configuration, transport, recovery, and fault sequences."""

from collections import deque
import json
import random
import os
from pyuvm import uvm_sequence
from cocotb.types import LogicArray
from static_mesh.transaction import INPUTS, MeshItem
from static_mesh.topology import (
    dimensions,
    physical,
    image,
    crc32c,
    metadata,
    topology_id,
    manifest,
)


class MeshSequence(uvm_sequence):
    def __init__(self, c, active, coverage):
        super().__init__("mesh_specification")
        self.c, self.active, self.coverage = c, active, coverage
        self.p, self.a = c.parameters, c.aliases
        self.g = physical(self.p)
        self.rng = random.Random(c.seed)
        self.ports = dict.fromkeys(INPUTS, 0)
        self.count = 0
        self.artifacts = []

    async def cycle(self, label="cycle", fault=None, **ports):
        self.ports.update(ports)
        item = MeshItem(f"{label}_{self.count}", self.ports, fault)
        self.count += 1
        if os.getenv("STATIC_MESH_TRACE"):
            print(item.get_name(), flush=True)
        await self.start_item(item)
        await self.finish_item(item)
        return item

    async def reset(self):
        self.active["routes"] = None
        self.active["fault_mode"] = False
        self.ports = dict.fromkeys(INPUTS, 0)
        for _ in range(3):
            await self.cycle("reset")
        for _ in range(3):
            await self.cycle("release_reset", i_reset_n=1, i_cfg_rsp_ready=1)
        self.version = 1
        self.context = 0
        self.kernel = min(3, (1 << self.a["K"]) - 1)
        self.raw = self.proof = self.epoch = 0

    async def command(self, op, expected=0, hold=False, **values):
        a = self.a
        args = dict(
            i_cfg_opcode=op,
            i_cfg_context_id=self.context,
            i_cfg_context_version=self.version,
            i_cfg_kernel_id=self.kernel,
            i_cfg_proof_id=self.proof,
            i_cfg_checksum=crc32c(self.raw.to_bytes(a["IM"] // 8, "little")),
            i_cfg_word_index=0,
            i_cfg_write_data=0,
            i_cfg_write_strobe=(1 << (a["W"] // 8)) - 1,
            i_cfg_valid=1,
            i_cfg_rsp_ready=int(not hold),
        )
        args.update(values)
        for _ in range(40):
            item = await self.cycle("command", **args)
            if item.pre["o_cfg_ready"]:
                break
        else:
            raise AssertionError("Configuration ready timeout")
        self.ports["i_cfg_valid"] = 0
        for _ in range(40):
            if item.post["o_cfg_rsp_valid"]:
                break
            item = await self.cycle("response_wait")
        else:
            raise AssertionError(("Configuration response timeout", op, item.post))
        result = item.post
        assert result["o_cfg_rsp_error_code"] == expected, (
            op,
            expected,
            result["o_cfg_rsp_error_code"],
        )
        assert result["o_cfg_rsp_context_id"] == (
            args["i_cfg_context_id"] if isinstance(args["i_cfg_context_id"], int) else 0
        )
        assert result["o_cfg_rsp_error"] == int(expected != 0)
        if hold:
            keys = (
                "o_cfg_rsp_valid",
                "o_cfg_rsp_read_data",
                "o_cfg_rsp_checksum",
                "o_cfg_rsp_error_code",
            )
            for _ in range(3):
                item = await self.cycle("response_stall")
                assert tuple(item.post[k] for k in keys) == tuple(result[k] for k in keys)
            self.coverage.hit("response_backpressure")
        await self.cycle("response_accept", i_cfg_rsp_ready=1)
        return result

    async def load(self, routes, *, negative=False, period=1, pause=0, activate=True):
        a = self.a
        self.raw, self.proof, certificate = image(
            self.p, routes, version=self.version, kernel=self.kernel, period=period, pause=pause
        )
        if negative:
            await self.command(2, 6, i_cfg_context_version=0)
            self.coverage.hit("incomplete")
        for word in range(a["WORDS"]):
            value = self.raw >> (word * a["W"]) & ((1 << a["W"]) - 1)
            if word == 0 and negative and a["W"] >= 16:
                await self.command(
                    0, i_cfg_word_index=word, i_cfg_write_data=value, i_cfg_write_strobe=1
                )
                await self.command(
                    0,
                    i_cfg_word_index=word,
                    i_cfg_write_data=value,
                    i_cfg_write_strobe=((1 << (a["W"] // 8)) - 1) ^ 1,
                )
                self.coverage.hit("byte_write")
            else:
                await self.command(0, i_cfg_word_index=word, i_cfg_write_data=value)
        if negative:
            await self.command(
                2, 7, i_cfg_checksum=1 ^ crc32c(self.raw.to_bytes(a["IM"] // 8, "little"))
            )
            await self.command(2, 12, i_cfg_proof_id=self.proof ^ 1)
            self.coverage.hit("checksum_proof_rejection")
        await self.command(2)
        for word in sorted({0, a["WORDS"] // 2, a["WORDS"] - 1}):
            result = await self.command(1, hold=negative and word == 0, i_cfg_word_index=word)
            assert result["o_cfg_rsp_read_data"] == self.raw >> (word * a["W"]) & (
                (1 << a["W"]) - 1
            )
        await self.command(5)
        if not activate:
            return
        expected_epoch = (self.epoch + 1) % (1 << a["EP"])
        await self.command(3)
        self.active["generation"] += 1
        self.active["routes"] = routes
        item = await self.cycle("activated")
        assert (
            item.post["o_active_context_valid"] and item.post["o_active_context_id"] == self.context
        )
        assert item.post["o_active_context_version"] == self.version
        assert item.post["o_active_kernel_id"] == self.kernel
        self.epoch = item.post["o_active_epoch"]
        assert self.epoch == expected_epoch
        if negative:
            await self.command(0, 4)
            await self.command(4, 4)
            self.coverage.hit("active_write_rejection")
        record = dict(
            words=[self.raw >> (w * a["W"]) & ((1 << a["W"]) - 1) for w in range(a["WORDS"])],
            proof_id=self.proof,
            checksum=crc32c(self.raw.to_bytes(a["IM"] // 8, "little")),
            routes=[dict(node=n, output=o, source=s) for (n, o), s in routes.items()],
            ranks=[[*r, v] for r, v in certificate["ranks"].items()],
            arrivals=[[*r, v] for r, v in certificate["arrivals"].items()],
            period=period,
            pause=pause,
        )
        self.artifacts.append(record)
        self.coverage.hit("activation")

    def roots(self, routes):
        resources = sorted({(n, s) for (n, _), s in routes.items()})
        roots = []
        for node, source in resources:
            if source < self.a["TX"]:
                roots.append(("tile", node * self.a["TX"] + source))
            else:
                edge = self.g["edges"][self.g["inputs"][node, source]]
                if "boundary_input" in edge:
                    roots.append(("boundary", edge["boundary_input"]))
        return roots

    def packet(self, serial):
        data = self.rng.getrandbits(self.a["D"])
        meta = metadata(
            self.p,
            self.context,
            self.version,
            self.kernel,
            self.epoch,
            first=int(serial % 5 == 0),
            last=int(serial % 5 == 4),
            row_first=int(serial % 7 == 0),
            row_last=int(serial % 7 == 6),
            eos=int(serial % 11 == 0),
            error=int(serial % 13 == 0),
            datatype=serial & 1,
        )
        used = self.a["CI"] + self.a["V"] + self.a["K"] + self.a["EP"] + self.a["D"] // 8 + 8
        meta |= self.rng.getrandbits(self.a["M"] - used) << used
        return data, meta

    async def traffic(self, routes, *, beats=12, stalls=True, cycles=None):
        a = self.a
        sources = {key: deque(self.packet(j) for j in range(beats)) for key in self.roots(routes)}
        held = set()
        total = sum(map(len, sources.values()))
        accepted = delivered = 0
        first_accept = None
        first_delivery = None
        scheduled = self.p["FLOW_PROFILE"] == 1
        if scheduled:
            stalls = False
        limit = cycles if cycles is not None else max(160, beats * 25 + 4 * (a["R"] + a["C"]))
        for cycle in range(limit):
            valid = dict(tile=0, boundary=0)
            data = dict(tile=0, boundary=0)
            meta = dict(tile=0, boundary=0)
            for key, q in sources.items():
                group, j = key
                if q and (key in held or not stalls or self.rng.randrange(4)):
                    held.add(key)
                    valid[group] |= 1 << j
                    data[group] |= q[0][0] << (j * a["D"])
                    meta[group] |= q[0][1] << (j * a["M"])
            rxt = (1 << (a["N"] * a["RX"])) - 1
            rxb = (1 << a["B"]) - 1
            if stalls:
                rxt = sum(int(self.rng.randrange(4) != 0) << j for j in range(a["N"] * a["RX"]))
                rxb = sum(int(self.rng.randrange(3) != 0) << j for j in range(a["B"]))
            draining = accepted == total
            item = await self.cycle(
                "traffic",
                i_enable=1,
                i_drain=int(draining),
                i_tile_tx_valid=valid["tile"],
                i_tile_tx_data=data["tile"],
                i_tile_tx_metadata=meta["tile"],
                i_boundary_rx_valid=valid["boundary"],
                i_boundary_rx_data=data["boundary"],
                i_boundary_rx_metadata=meta["boundary"],
                i_boundary_rx_parity=sum(
                    (
                        (data["boundary"] >> (j * a["D"]) & ((1 << a["D"]) - 1)).bit_count()
                        + (meta["boundary"] >> (j * a["M"]) & ((1 << a["M"]) - 1)).bit_count()
                    )
                    % 2
                    << j
                    for j in range(a["B"])
                ),
                i_tile_rx_ready=rxt,
                i_boundary_tx_ready=rxb,
            )
            for key, q in sources.items():
                group, j = key
                if (
                    valid[group] >> j & 1
                    and item.pre[
                        "o_" + ("tile_tx" if group == "tile" else "boundary_rx") + "_ready"
                    ]
                    >> j
                    & 1
                ):
                    q.popleft()
                    held.discard(key)
                    accepted += 1
                    if first_accept is None:
                        first_accept = cycle
            delivered_now = (item.pre["o_tile_rx_valid"] & rxt).bit_count() + (
                item.pre["o_boundary_tx_valid"] & rxb
            ).bit_count()
            delivered += delivered_now
            if delivered_now and first_delivery is None:
                first_delivery = cycle
            if cycles is None and accepted == total and item.post["o_drained"]:
                break
        else:
            if cycles is None:
                raise AssertionError(("Drain timeout", accepted, total, item.post))
        if cycles is None:
            assert accepted == total and delivered >= total
            assert item.post["o_idle"] and item.post["o_quiescent"]
            self.coverage.hit("traffic")
            if stalls:
                self.coverage.hit("backpressure")
            self.ports.update(
                i_enable=0, i_drain=int(scheduled), i_tile_tx_valid=0, i_boundary_rx_valid=0
            )
        return first_delivery - first_accept if first_delivery is not None else None

    def one_hop(self, direction, channel):
        a, g = self.a, self.g
        routes = {}
        for e in g["edges"][: a["IL"]]:
            if e["source_port"] != a["RX"] + direction * a["H"] + channel or not (
                g["mask"] >> e["index"] & 1
            ):
                continue
            n, o, dst, arrival = (
                e["source_node"],
                e["source_port"],
                e["destination_node"],
                e["destination_port"],
            )
            if (
                g["connectivity"] >> (n * a["O"] * a["I"] + o * a["I"]) & 1
                and g["connectivity"] >> (dst * a["O"] * a["I"] + arrival) & 1
            ):
                routes[n, o] = 0
                routes[dst, 0] = arrival
        return routes

    def longest_path(self):
        a = self.a
        # Search the actual graph, obeying the selected profile's turn matrix.
        # Restrict to east then south for O(N) path construction.
        routes = {}
        node = 0
        source = 0
        for direction, steps in ((2, a["C"] - 1), (1, a["R"] - 1)):
            for _ in range(steps):
                edges = [
                    e
                    for e in self.g["edges"][: a["IL"]]
                    if e["source_node"] == node
                    and e["source_port"] == a["RX"] + direction * a["H"]
                    and self.g["mask"] >> e["index"] & 1
                ]
                if not edges:
                    break
                e = edges[0]
                if not (
                    self.g["connectivity"]
                    >> (node * a["O"] * a["I"] + e["source_port"] * a["I"] + source)
                    & 1
                ):
                    break
                routes[node, e["source_port"]] = source
                node, source = e["destination_node"], e["destination_port"]
        if (
            self.g["nodes"] >> node & 1
            and self.g["connectivity"] >> (node * a["O"] * a["I"] + source) & 1
        ):
            routes[node, 0] = source
        return routes

    def multicast_tree(self):
        """Build a physical arborescence, with local delivery at every visited tile."""
        a = self.a
        routes = {}
        visited = {0}
        frontier = deque([(0, 0)])
        while frontier:
            node, source = frontier.popleft()
            if not self.g["connectivity"] >> (node * a["O"] * a["I"] + source) & 1:
                continue
            routes[node, 0] = source
            branches = 1
            for edge in self.g["edges"][: a["IL"]]:
                if edge["source_node"] != node or edge["destination_node"] in visited:
                    continue
                if not self.g["mask"] >> edge["index"] & 1:
                    continue
                out = edge["source_port"]
                if (
                    not self.g["connectivity"] >> (node * a["O"] * a["I"] + out * a["I"] + source)
                    & 1
                ):
                    continue
                if branches >= self.p["MAX_MULTICAST_FANOUT"]:
                    break
                routes[node, out] = source
                visited.add(edge["destination_node"])
                frontier.append((edge["destination_node"], edge["destination_port"]))
                branches += 1
        return routes

    async def context_switching(self, local):
        a, p = self.a, self.p
        if a["CD"] < 2:
            return
        await self.reset()
        await self.load(local)
        self.active["fault_mode"] = True
        # Keep one accepted beat owned by the old image while staging another.
        root = self.roots(local)[0][1]
        data, meta = self.packet(0)
        await self.cycle(
            "old_context_beat",
            i_enable=1,
            i_tile_tx_valid=1 << root,
            i_tile_tx_data=data << (root * a["D"]),
            i_tile_tx_metadata=meta << (root * a["M"]),
            i_tile_rx_ready=0,
        )
        await self.cycle("old_context_hold", i_enable=0, i_drain=1, i_tile_tx_valid=0)
        self.context = a["CD"] - 1
        await self.load(local, activate=False)
        item = await self.command(3, 13)
        assert item["o_active_context_id"] == 0 and item["o_active_epoch"] == 1
        self.coverage.hit("activation_busy")
        for _ in range(4):
            item = await self.cycle(
                "old_context_drain", i_tile_rx_ready=(1 << (a["N"] * a["RX"])) - 1
            )
        assert item.post["o_drained"]
        # Exercise every context entry, monotonic versions, and nonbaseline kernels.
        for context in range(1, a["CD"]):
            self.context = context
            self.version = 2
            self.kernel = (self.kernel + 1) % (1 << a["K"])
            await self.load(local)
            self.coverage.hit("context_identity")
            await self.command(1, 3, i_cfg_context_version=1)
        # Invalidation clears an inactive image and cannot alter the installed image.
        active_context = self.context
        self.context = 0
        self.version = 1
        await self.command(4)
        item = await self.command(3, 6)
        assert item["o_active_context_id"] == active_context
        self.coverage.hit("invalidate")

    async def diagnostics(self, local):
        a, p = self.a, self.p
        # Read lifetime counters after a fully checked burst, then verify that a
        # flush preserves the counts while it discards transport ownership.
        await self.reset()
        await self.load(local)
        await self.traffic(local, beats=7, stalls=False)
        self.active["fault_mode"] = True
        count = await self.cycle("counter", i_counter_read=1, i_counter_index=1)
        assert count.post["o_counter_valid"]
        assert count.post["o_counter_value"] == 7 * len(self.roots(local))
        await self.cycle("counter_stop", i_counter_read=0)
        await self.cycle("isolate", i_boundary_isolate=1)
        item = await self.cycle("isolated")
        assert item.post["o_boundary_isolated"] and not item.post["o_boundary_tx_valid"]
        await self.cycle("isolation_release", i_boundary_isolate=0)
        self.coverage.hit("counters_isolation")
        # Invalid graph ranks are rejected even when both hash checks are valid.
        route = next((self.one_hop(d, 0) for d in range(4) if self.one_hop(d, 0)), None)
        if route:
            await self.reset()
            raw, proof, _ = image(
                p,
                route,
                version=1,
                kernel=self.kernel,
                ranks={(n, i): 0 for n in range(a["N"]) for i in range(a["I"])},
            )
            self.raw, self.proof = raw, proof
            for word in range(a["WORDS"]):
                await self.command(
                    0,
                    i_cfg_word_index=word,
                    i_cfg_write_data=raw >> (word * a["W"]) & ((1 << a["W"]) - 1),
                )
            await self.command(2, 12)
            self.coverage.hit("dependency_certificate")
        if p["FLOW_PROFILE"]:
            await self.reset()
            await self.load(local)
            self.active["fault_mode"] = True
            item = await self.cycle("missing_slot", i_enable=1)
            assert item.post["o_error_code"] == 16 and item.post["o_schedule_violation"]
            self.coverage.hit("schedule_missing")
            await self.reset()
            await self.load(local, pause=1)
            for _ in range(4):
                item = await self.cycle("legal_pause", i_enable=0)
                assert not item.post["o_error"]
            self.coverage.hit("schedule_pause")
        if p["ENABLE_LINK_PARITY"]:
            if route:
                await self.reset()
                await self.load(route)
                self.active["fault_mode"] = True
                link = next(self.g["outputs"][n, o] for n, o in route if o >= a["RX"])
                edge = self.g["edges"][link]
                root = edge["source_node"] * a["TX"]
                for j in range(3):
                    data, meta = self.packet(j)
                    await self.cycle(
                        "fill_skid_for_parity",
                        i_enable=1,
                        i_tile_tx_valid=1 << root,
                        i_tile_tx_data=data << (root * a["D"]),
                        i_tile_tx_metadata=meta << (root * a["M"]),
                        i_tile_rx_ready=0,
                    )
                path = f"g_mesh.g_link[{link}].g_internal.u_link.u_skid.g_skid.buffer_data"
                item = await self.cycle("link_parity_fault", fault=(path, 1), i_tile_tx_valid=0)
                assert item.post["o_error_code"] == 17
                assert item.post["o_parity_error_event"] >> link & 1
                await self.cycle("parity_fault_release", fault=("release", 0))
                await self.cycle("parity_flush", i_flush=1)
                await self.cycle("parity_flush_release", i_flush=0, i_enable=0)
                self.coverage.hit("internal_parity_containment")
            if p["EXPOSE_BOUNDARY_PORTS"]:
                candidates = [
                    (b, e)
                    for b, e in enumerate(self.g["edges"][a["IL"] :: 2])
                    if self.g["mask"] >> (a["IL"] + 2 * b) & 1
                ]
                if candidates:
                    b, e = candidates[0]
                    route_b = {(e["destination_node"], 0): e["destination_port"]}
                    await self.reset()
                    await self.load(route_b)
                    self.active["fault_mode"] = True
                    data, meta = self.packet(0)
                    parity = (data.bit_count() + meta.bit_count()) % 2
                    item = await self.cycle(
                        "boundary_parity_fault",
                        i_enable=1,
                        i_boundary_rx_valid=1 << b,
                        i_boundary_rx_data=data << (b * a["D"]),
                        i_boundary_rx_metadata=meta << (b * a["M"]),
                        i_boundary_rx_parity=(parity ^ 1) << b,
                    )
                    assert not (item.pre["o_boundary_rx_ready"] >> b & 1)
                    assert (
                        item.post["o_error_code"] == 17
                        and item.post["o_parity_error_event"] >> (a["IL"] + 2 * b) & 1
                    )
                    self.coverage.hit("boundary_parity_containment")
        if p["CONTROL_PROTECTION"]:
            await self.reset()
            await self.load(local)
            self.active["fault_mode"] = True
            path = "g_mesh.u_control.u_active_image.stored"
            item = await self.cycle("protected_bit", fault=(path, 1))
            if p["CONTROL_PROTECTION"] == 2:
                assert not item.post["o_error"], "SECDED failed single-bit correction"
                self.coverage.hit("secded_correction")
            else:
                assert item.pre["o_error_code"] == 18 and not item.pre["o_tile_tx_ready"]
            await self.cycle("protection_release", fault=("release", 0))
            await self.reset()
            await self.load(local)
            self.active["fault_mode"] = True
            item = await self.cycle("protected_double_bit", fault=(path, 3))
            if p["CONTROL_PROTECTION"] == 2:
                assert item.pre["o_error_code"] == 18 and not item.pre["o_tile_tx_ready"]
                self.coverage.hit("secded_containment")
            await self.cycle("protection_double_release", fault=("release", 0))
            self.coverage.hit("control_integrity")

    async def body(self):
        a, p = self.a, self.p
        await self.reset()
        item = await self.cycle("topology")
        assert item.post["o_topology_id"] == topology_id(p)
        self.coverage.hit("topology")
        await self.command(5, 1, i_cfg_context_id=LogicArray("X" * a["CI"]))
        await self.command(5, 1, i_cfg_opcode=LogicArray("XXX"))
        self.coverage.hit("unknown_config")
        # Local ports exercise every local lane, independent of cardinal topology.
        local = {
            (n, o): o % a["TX"]
            for n in range(a["N"])
            for o in range(min(a["TX"], a["RX"]))
            if self.g["connectivity"] >> (n * a["O"] * a["I"] + o * a["I"] + o % a["TX"]) & 1
        }
        if not local:
            raise AssertionError("Regression profile must contain a usable node")
        await self.load(local, negative=True)
        await self.traffic(local, beats=12, stalls=True)
        # Flush owns accepted pending copies, preserves contexts, and changes epoch.
        self.active["fault_mode"] = True
        root = self.roots(local)[0][1]
        data, meta = self.packet(0)
        await self.cycle(
            "fill_for_flush",
            i_enable=1,
            i_tile_tx_valid=1 << root,
            i_tile_tx_data=data << (root * a["D"]),
            i_tile_tx_metadata=meta << (root * a["M"]),
            i_tile_rx_ready=0,
        )
        await self.cycle("hold_for_flush", i_tile_tx_valid=0)
        item = await self.cycle("flush", i_flush=1)
        assert not item.post["o_tile_rx_valid"]
        for _ in range(4):
            item = await self.cycle("flush_hold")
        assert item.post["o_active_epoch"] == (self.epoch + 1) % (1 << a["EP"])
        await self.cycle(
            "flush_release", i_flush=0, i_enable=0, i_tile_rx_ready=(1 << (a["N"] * a["RX"])) - 1
        )
        self.active["routes"] = None
        self.coverage.hit("flush")
        # All cardinal directions/channels are tested independently, including
        # physically asymmetric masks; absent links are never given substitute routes.
        for direction in range(4):
            for channel in range(a["H"]):
                routes = self.one_hop(direction, channel)
                if not routes:
                    continue
                await self.reset()
                await self.load(routes)
                await self.traffic(routes, beats=8, stalls=not p["FLOW_PROFILE"])
                self.coverage.hit(f"direction_{direction}_channel_{channel}")
        routes = self.longest_path()
        if routes:
            await self.reset()
            await self.load(routes)
            latency = await self.traffic(routes, beats=16, stalls=False)
            assert latency == len(routes), ("Unstalled node latency", latency, len(routes))
            self.coverage.hit("registered_path_latency")
            if not p["FLOW_PROFILE"]:
                await self.traffic(
                    routes,
                    beats=max(20, self.c.random_cycles // max(1, len(self.roots(routes)))),
                    stalls=True,
                )
        # Each exposed boundary port carries ingress and egress in its own image.
        for direction in (0, 1, 3, 2):
            routes = {}
            for b, e in enumerate(
                self.g["edges"][a["IL"] :: 2] if p["EXPOSE_BOUNDARY_PORTS"] else []
            ):
                if (
                    not self.g["mask"] >> (a["IL"] + 2 * b) & 1
                    or not self.g["mask"] >> (a["IL"] + 2 * b + 1) & 1
                ):
                    continue
                if (e["destination_port"] - a["TX"]) // a["H"] != direction:
                    continue
                node, source = e["destination_node"], e["destination_port"]
                out = self.g["edges"][a["IL"] + 2 * b + 1]["source_port"]
                # Channels are mapped to separate local ports when available.
                lane = (source - a["TX"]) % a["H"]
                if lane >= min(a["TX"], a["RX"]):
                    continue
                if (node, lane) in routes:
                    continue
                routes[node, lane] = source
                routes[node, out] = lane
            if routes:
                await self.reset()
                await self.load(routes)
                await self.traffic(routes, beats=6, stalls=not p["FLOW_PROFILE"])
                self.coverage.hit("boundary")
        if p["SUPPORT_MULTICAST"] and p["MAX_MULTICAST_FANOUT"] > 1:
            routes = self.longest_path()
            if routes:
                first = min(routes)
                node = first[0]
                if (node, 0) not in routes and self.g["connectivity"] >> (
                    node * a["O"] * a["I"]
                ) & 1:
                    routes[node, 0] = 0
                    await self.reset()
                    await self.load(routes)
                    await self.traffic(routes, beats=24, stalls=not p["FLOW_PROFILE"])
                    self.coverage.hit("multicast")
        if p["SUPPORT_MULTICAST"] and p["MAX_MULTICAST_FANOUT"] > 1:
            tree = self.multicast_tree()
            if len(tree) > 1:
                await self.reset()
                await self.load(tree)
                await self.traffic(tree, beats=24, stalls=not p["FLOW_PROFILE"])
                self.coverage.hit("multicast_tree")
        # Metadata errors do not accept malformed traffic. A quiescent clear
        # permits a coordinated restart; old-epoch beats get a distinct code.
        await self.reset()
        await self.load(local)
        self.active["fault_mode"] = True
        root = self.roots(local)[0][1]
        data, meta = self.packet(0)
        item = await self.cycle(
            "bad_epoch",
            i_enable=1,
            i_tile_tx_valid=1 << root,
            i_tile_tx_data=data << (root * a["D"]),
            i_tile_tx_metadata=(meta ^ (1 << (a["CI"] + a["V"] + a["K"]))) << (root * a["M"]),
        )
        if p["CHECK_CONTEXT"]:
            assert not (item.pre["o_tile_tx_ready"] >> root & 1) and item.post["o_error_code"] == 19
            self.coverage.hit("metadata_epoch")
        await self.cycle("stop_bad_metadata", i_tile_tx_valid=0, i_enable=0)
        await self.cycle("clear", i_error_clear=1, i_tile_rx_ready=(1 << (a["N"] * a["RX"])) - 1)
        await self.cycle("clear_release", i_error_clear=0)
        self.active["routes"] = None
        # Active directed fault is sticky and cannot silently choose a detour.
        candidates = [self.one_hop(d, 0) for d in range(4)]
        route = next((r for r in candidates if r), None)
        if route and p["SUPPORT_LINK_EXCLUSION"]:
            await self.reset()
            await self.load(route)
            self.active["fault_mode"] = True
            link = next(self.g["outputs"][n, o] for n, o in route if o >= a["RX"])
            item = await self.cycle(
                "fault_update", i_link_fault_valid=1, i_link_fault_mask=1 << link
            )
            assert item.pre["o_link_fault_ready"]
            item = await self.cycle("fault_record", i_link_fault_valid=0)
            assert item.post["o_active_link_fault"] and item.post["o_error_code"] == 14
            assert item.post["o_error_link"] == link
            assert item.post["o_error_node"] == self.g["edges"][link]["destination_node"]
            assert not item.post["o_tile_tx_ready"]
            await self.cycle("fault_clear", i_link_fault_valid=1, i_link_fault_mask=0)
            await self.cycle("fault_clear_ack", i_link_fault_valid=0, i_error_clear=1)
            self.coverage.hit("directed_fault")
        await self.context_switching(local)
        await self.diagnostics(local)
        await self.reset()
        self.coverage.goals = {
            name: bool(self.coverage.bins[name])
            for name in (
                "topology",
                "activation",
                "incomplete",
                "checksum_proof_rejection",
                "active_write_rejection",
                "response_backpressure",
                "traffic",
                "flush",
                "registered_path_latency",
            )
        }
        if p["EXPOSE_BOUNDARY_PORTS"] and self.g["mask"] >> a["IL"]:
            self.coverage.goals["boundary"] = bool(self.coverage.bins["boundary"])
        for goal in (
            "counters_isolation",
            "dependency_certificate",
            "schedule_missing",
            "internal_parity_containment",
            "boundary_parity_containment",
            "control_integrity",
        ):
            applicable = (
                goal == "counters_isolation"
                or (goal == "dependency_certificate" and route)
                or (goal == "schedule_missing" and p["FLOW_PROFILE"])
                or (goal == "internal_parity_containment" and p["ENABLE_LINK_PARITY"] and route)
                or (
                    goal == "boundary_parity_containment"
                    and p["ENABLE_LINK_PARITY"]
                    and p["EXPOSE_BOUNDARY_PORTS"]
                    and self.g["mask"] >> a["IL"]
                )
                or (goal == "control_integrity" and p["CONTROL_PROTECTION"])
            )
            if applicable:
                self.coverage.goals[goal] = bool(self.coverage.bins[goal])
        self.c.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        artifact = manifest(p)
        artifact["route_images"] = self.artifacts
        self.c.coverage_file.with_name("contract.json").write_text(
            json.dumps(artifact, indent=2) + "\n"
        )
