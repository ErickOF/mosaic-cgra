"""Predicate-specific control and lane scenarios over shared mesh traffic sequences."""

from collections import deque
from itertools import accumulate
import json
import os
import random
from cocotb.types import LogicArray
from static_mesh.sequences import MeshSequence
from pyuvm import uvm_sequence
from predicate_network.transaction import INPUTS, PredicateItem, native
from predicate_network.topology import (
    physical,
    dimensions,
    topology_id,
    image,
    metadata,
    graph,
    proof_id,
)


class PredicateSequence(MeshSequence):
    def __init__(self, c, active, coverage):
        # Reuse route selection, path, multicast, and randomized traffic methods.
        uvm_sequence.__init__(self, "predicate_specification")
        self.c, self.active, self.coverage = c, active, coverage
        self.rng = random.Random(c.seed)
        self.count = 0
        self.p = c.parameters.copy() | dict(FLOW_PROFILE=0)
        self.a = dimensions(c.parameters)
        self.g = physical(c.parameters)
        self.ports = dict.fromkeys(INPUTS, 0)
        self.artifacts = []
        self.producers = iter(())
        self.context = 1
        self.version = 1
        self.kernel = 3
        self.epoch = 1

    async def cycle(self, label="cycle", fault=None, **ports):
        self.ports.update(ports)
        item = PredicateItem(f"{label}_{self.count}", native(self.ports, self.a), fault)
        self.count += 1
        if os.getenv("PREDICATE_NETWORK_TRACE"):
            print(item.get_name(), flush=True)
        await self.start_item(item)
        await self.finish_item(item)
        return item

    async def reset(self):
        self.active.update(routes=None, fault_mode=False)
        self.ports = dict.fromkeys(INPUTS, 0)
        for _ in range(3):
            await self.cycle("reset")
        for _ in range(3):
            await self.cycle("reset_release", i_reset_n=1)
        self.context = 1
        self.version = 1
        self.kernel = 3
        self.epoch = 1
        self.p["FLOW_PROFILE"] = 0

    async def prepare(
        self, routes, *, expected=0, scheduled=False, period=1, check=True, **overrides
    ):
        packet = image(
            self.c.parameters,
            routes,
            context=self.context,
            version=self.version,
            kernel=self.kernel,
            epoch=self.epoch,
            scheduled=scheduled,
            period=period,
            check=check,
        )
        fields = dict(
            i_cfg_route_image=packet["route"],
            i_cfg_schedule_enable=packet["schedule_enable"],
            i_cfg_schedule_slot_image=packet["slots"],
            i_cfg_schedule_period=packet["period"],
            i_cfg_context_id=self.context,
            i_cfg_context_version=self.version,
            i_cfg_kernel_id=self.kernel,
            i_cfg_epoch=self.epoch,
            i_cfg_route_proof_id=packet["proof"],
        )
        fields.update(overrides)
        if (
            overrides
            and "i_cfg_route_proof_id" not in overrides
            and all(isinstance(v, int) for v in fields.values())
        ):
            fields["i_cfg_route_proof_id"] = proof_id(self.c.parameters, fields)
        for _ in range(50):
            item = await self.cycle("prepare", i_cfg_prepare_valid=1, **fields)
            if item.pre["o_cfg_prepare_ready"]:
                break
        else:
            raise AssertionError("prepare readiness timeout")
        self.ports["i_cfg_prepare_valid"] = 0
        for _ in range(2 * self.a["RES"] + 12):
            if item.post["o_cfg_prepared"] or item.post["o_cfg_prepare_rejected"]:
                break
            item = await self.cycle("validate")
        else:
            raise AssertionError(("prepare completion timeout", item.post))
        assert item.post["o_cfg_prepare_error_code"] == expected, (
            expected,
            item.post["o_cfg_prepare_error_code"],
        )
        assert item.post["o_cfg_prepared"] == int(expected == 0)
        assert item.post["o_cfg_prepare_rejected"] == int(expected != 0)
        if expected == 0:
            self.pending = packet
            self.pending_routes = routes
            self.artifacts.append(
                dict(
                    parameters=self.c.parameters,
                    **{
                        k: (hex(v) if k in ("route", "slots", "schedule_enable", "proof") else v)
                        for k, v in packet.items()
                        if k != "certificate"
                    },
                    routes=[dict(node=n, output=o, source=i) for (n, o), i in routes.items()],
                    depths=[[*u, d] for u, d in packet["certificate"]["depths"].items()]
                    if check
                    else [],
                )
            )
        self.coverage.hit("prepare" if expected == 0 else f"prepare_error_{expected}")
        await self.cycle("prepare_report_release")
        return item

    async def commit(self):
        for _ in range(40):
            item = await self.cycle(
                "commit",
                i_cfg_commit_valid=1,
                i_cfg_commit_context_id=self.context,
                i_cfg_commit_context_version=self.version,
            )
            if item.pre["o_cfg_commit_ready"]:
                break
        else:
            raise AssertionError("commit readiness timeout")
        self.ports["i_cfg_commit_valid"] = 0
        for _ in range(12):
            if item.post["o_cfg_committed"]:
                break
            item = await self.cycle("commit_ack")
        else:
            raise AssertionError("atomic commit acknowledgement timeout")
        for key, value in dict(
            o_active_context_id=self.context,
            o_active_context_version=self.version,
            o_active_kernel_id=self.kernel,
            o_active_epoch=self.epoch,
        ).items():
            assert item.post[key] == value, key
        assert item.post["o_active_context_valid"] and not item.post["o_shadow_valid"]
        self.active.update(routes=self.pending_routes, generation=self.active["generation"] + 1)
        self.p["FLOW_PROFILE"] = int(self.pending["schedule_enable"] != 0)
        self.coverage.hit("commit")
        await self.cycle("commit_report_release")

    async def load(self, routes, **kwargs):
        await self.prepare(routes, **kwargs)
        await self.commit()

    def packet(self, serial, producer=None):
        a = self.a
        producer = next(self.producers, 0) if producer is None else producer
        full = (1 << a["PV"]) - 1
        masks = [
            full,
            full,
            1,
            1 << (a["PV"] - 1),
            full & 0x5555,
            0,
            1,
            self.rng.randrange(full + 1),
        ]
        mask = masks[serial % len(masks)]
        value = (
            0 if serial % 8 == 0 else full if serial % 8 == 1 else self.rng.getrandbits(a["PV"])
        ) & mask
        kind = (
            (0 if a["PV"] == 1 or serial % 8 == 6 else 1)
            if mask
            else (2 if a["PV"] == 1 or serial % 16 == 5 else 3)
        )
        if kind == 0:
            mask = 1
            value = int(serial // 8 % 2) if serial % 8 == 6 else value & 1
        meta = metadata(
            self.c.parameters,
            self.context,
            self.version,
            self.kernel,
            self.epoch,
            producer,
            serial % (1 << a["T"]),
            kind,
            int(serial % 11 == 0),
            self.rng.getrandbits(a["M"] - a["REQ"]),
        )
        return value | (mask << a["PV"]), meta

    def multicast_tree(self):
        """Keep a bounded subset of the shared physical broadcast arborescence."""
        routes = super().multicast_tree()
        a, g = self.a, self.g
        terminals = sorted(k for k in routes if k[1] < a["RX"])
        if len(terminals) <= self.p["MAX_TREE_DESTINATIONS"]:
            return routes
        bounded = {}
        for terminal in terminals[: self.p["MAX_TREE_DESTINATIONS"]]:
            node, output = terminal
            while True:
                source = routes[node, output]
                bounded[node, output] = source
                if source < a["TX"]:
                    break
                edge = g["edges"][g["inputs"][node, source]]
                node, output = edge["source_node"], edge["source_port"]
        return bounded

    async def traffic(self, routes, *, beats=12, stalls=True, cycles=None):
        self.producers = iter(
            (j if group == "tile" else self.a["N"] * self.a["TX"] + j)
            for group, j in self.roots(routes)
            for _ in range(beats)
        )
        return await super().traffic(routes, beats=beats, stalls=stalls, cycles=cycles)

    async def flush(self):
        self.active["fault_mode"] = True
        old = self.epoch
        item = await self.cycle("flush", i_flush=1, i_tile_tx_valid=0, i_boundary_rx_valid=0)
        assert not item.post["o_pred_rx_valid"] and not item.post["o_boundary_pred_valid"]
        for _ in range(4):
            item = await self.cycle("flush_hold")
        self.epoch = (old + 1) % (1 << self.a["EP"])
        assert item.post["o_active_epoch"] == self.epoch
        await self.cycle("flush_release", i_flush=0, i_enable=0, i_drain=0)
        self.active["routes"] = None
        self.coverage.hit("flush")

    async def protocol(self, local):
        a = self.a
        await self.reset()
        await self.prepare(local)
        # Rejection preserves an already prepared legal image.
        await self.prepare(local, expected=7, i_cfg_route_proof_id=self.pending["proof"] ^ 1)
        assert (await self.cycle("shadow_preserved")).post["o_shadow_valid"]
        await self.commit()
        self.active["fault_mode"] = True
        await self.prepare(local, expected=6)
        self.version = 2
        await self.prepare(local)
        await self.cycle("abort", i_cfg_abort=1)
        item = await self.cycle(
            "abort_release",
            i_cfg_abort=0,
            i_cfg_commit_valid=1,
            i_cfg_commit_context_id=self.context,
            i_cfg_commit_context_version=self.version,
        )
        assert not item.post["o_shadow_valid"] and not item.pre["o_cfg_commit_ready"]
        assert item.post["o_active_context_version"] == 1
        await self.cycle("commit_cancel", i_cfg_commit_valid=0)
        self.coverage.hit("abort")
        # Prepare while an old token is held: shadow work cannot modify its value.
        self.version = 1
        root = self.roots(local)[0][1]
        data, meta = self.packet(0, root)
        item = await self.cycle(
            "hold_old",
            i_enable=1,
            i_tile_tx_valid=1 << root,
            i_tile_tx_data=data << (root * a["D"]),
            i_tile_tx_metadata=meta << (root * a["M"]),
            i_tile_rx_ready=0,
        )
        assert item.pre["o_pred_tx_ready"] >> root & 1
        await self.cycle("old_owned", i_tile_tx_valid=0, i_enable=0, i_drain=1)
        self.version = 2
        await self.prepare(local)
        item = await self.cycle(
            "commit_busy",
            i_cfg_commit_valid=1,
            i_cfg_commit_context_id=self.context,
            i_cfg_commit_context_version=self.version,
        )
        assert not item.pre["o_cfg_commit_ready"] and item.post["o_active_context_version"] == 1
        await self.cycle(
            "retire_old", i_cfg_commit_valid=0, i_tile_rx_ready=(1 << (a["N"] * a["RX"])) - 1
        )
        await self.cycle("empty_old")
        # Commit wins over a new old-context presentation on the empty edge.
        item = await self.cycle(
            "commit_ingress_collision",
            i_enable=1,
            i_drain=0,
            i_tile_tx_valid=1 << root,
            i_tile_tx_data=data << (root * a["D"]),
            i_tile_tx_metadata=meta << (root * a["M"]),
            i_cfg_commit_valid=1,
            i_cfg_commit_context_id=self.context,
            i_cfg_commit_context_version=self.version,
        )
        assert item.pre["o_cfg_commit_ready"]
        assert not item.pre["o_pred_tx_ready"] and not item.pre["o_boundary_pred_ready"]
        # The old presentation was not accepted; the coordinator cancels it.
        self.ports.update(i_cfg_commit_valid=0, i_tile_tx_valid=0, i_enable=0)
        for _ in range(12):
            item = await self.cycle("commit_collision_ack")
            if item.post["o_cfg_committed"]:
                break
        else:
            raise AssertionError("Collision commit did not complete")
        assert item.post["o_active_context_version"] == self.version
        assert item.post["o_idle"] and not item.post["o_pred_rx_valid"]
        self.active.update(routes=local, generation=self.active["generation"] + 1)
        self.coverage.hit("commit_ingress_collision")
        self.version += 1
        await self.prepare(local)
        await self.commit()
        await self.flush()
        self.coverage.hit("shadow_isolation")

    async def lane_and_alignment(self, local):
        a = self.a
        await self.reset()
        await self.load(local)
        root = self.roots(local)[0][1]
        dest = root // a["TX"] * a["RX"]
        self.active["fault_mode"] = True
        # A consumer with a different data tag cannot consume the predicate.
        data, meta = self.packet(1, root)
        await self.cycle(
            "alignment_token",
            i_enable=1,
            i_tile_tx_valid=1 << root,
            i_tile_tx_data=data << (root * a["D"]),
            i_tile_tx_metadata=meta << (root * a["M"]),
            i_tile_rx_ready=0,
        )
        item = await self.cycle(
            "alignment_mismatch",
            i_tile_tx_valid=0,
            i_tile_rx_ready=1 << dest,
            i_endpoint_alignment_error=1 << dest,
            i_endpoint_alignment_expected_tag=2 << (dest * a["T"]),
            i_endpoint_alignment_observed_tag=1 << (dest * a["T"]),
        )
        assert not (item.pre["o_pred_rx_valid"] >> dest & 1)
        assert item.post["o_alignment_error_event"] >> dest & 1 and item.post["o_error_code"] == 14
        assert item.post["o_error_tag"] == 1 and item.post["o_error_expected_tag"] == 2
        assert item.post["o_error_source"] == root
        item = await self.cycle("alignment_quarantine", i_endpoint_alignment_error=0)
        assert not (item.post["o_pred_rx_valid"] >> dest & 1)
        await self.flush()
        self.coverage.hit("alignment_containment")
        for label, kind, mask, value, change, code in (
            ("invalid_lane", 1, 0, 1, 0, 10),
            ("empty_ordinary", 1, 0, 0, 0, 10),
            ("stale_epoch", 0, 1, 0, 1 << (a["CI"] + a["V"] + a["K"]), 12),
            ("wrong_producer", 0, 1, 0, 1 << (a["CI"] + a["V"] + a["K"] + a["EP"]), 13),
        ):
            if code in (12, 13) and not self.p["CHECK_CONTEXT"]:
                continue
            await self.reset()
            await self.load(local)
            self.active["fault_mode"] = True
            meta = metadata(self.c.parameters, 1, 1, 3, 1, root, 0, kind) ^ change
            item = await self.cycle(
                label,
                i_enable=1,
                i_tile_tx_valid=1 << root,
                i_tile_tx_data=(value | (mask << a["PV"])) << (root * a["D"]),
                i_tile_tx_metadata=meta << (root * a["M"]),
            )
            assert (
                not (item.pre["o_pred_tx_ready"] >> root & 1) and item.post["o_error_code"] == code
            ), (label, item.post)
            self.coverage.hit(label)
        # Unknown inactive values are canonical zero; the active lane is known.
        if a["PV"] > 1:
            await self.reset()
            await self.load(local)
            meta = metadata(self.c.parameters, 1, 1, 3, 1, root, 0, 0)
            value = "0" * (a["N"] * a["TX"] * a["PV"])
            begin = len(value) - (root + 1) * a["PV"]
            value = value[:begin] + ("X" * (a["PV"] - 1) + "0") + value[begin + a["PV"] :]
            self.ports["i_pred_tx_value"] = LogicArray(value)
            self.ports["i_pred_tx_lane_valid"] = 1 << (root * a["PV"])
            self.ports["i_pred_tx_metadata"] = meta << (root * a["M"])
            item = await self.cycle("inactive_unknown", i_pred_tx_valid=1 << root, i_enable=1)
            assert item.pre["o_pred_tx_ready"] >> root & 1
            item = await self.cycle(
                "inactive_unknown_deliver",
                i_pred_tx_valid=0,
                i_pred_rx_ready=(1 << (a["N"] * a["RX"])) - 1,
            )
            assert item.pre["o_pred_rx_valid"] >> dest & 1
            assert item.pre["o_pred_rx_value"] == 0
            await self.cycle("inactive_unknown_empty", i_enable=0)
            self.coverage.hit("inactive_unknown")

    async def reliability(self, route):
        if not route:
            return
        a = self.a
        await self.reset()
        await self.load(route)
        self.active["fault_mode"] = True
        link = next(self.g["outputs"][n, o] for n, o in route if o >= a["RX"])
        if self.p["SUPPORT_LINK_EXCLUSION"]:
            item = await self.cycle("fault_add", i_link_fault_valid=1, i_link_fault_mask=1 << link)
            assert item.pre["o_link_fault_ready"]
            item = await self.cycle("fault_ack", i_link_fault_valid=0)
            assert item.post["o_active_link_fault"] and item.post["o_error_code"] == 9
            assert item.post["o_error_link"] == link
            self.version = 2
            await self.prepare(route, expected=9)
            await self.cycle("fault_clear", i_link_fault_valid=1, i_link_fault_mask=0)
            await self.cycle("fault_clear_ack", i_link_fault_valid=0, i_error_clear=1)
            self.coverage.hit("directed_fault")
        if self.p["ENABLE_LINK_PARITY"]:
            for field, bit in [
                ("value", 0),
                ("validity", a["PV"]),
                ("metadata", a["D"] + a["CI"] + a["V"] + a["K"] + a["EP"] + a["PR"]),
            ]:
                await self.reset()
                await self.load(route)
                self.active["fault_mode"] = True
                edge = self.g["edges"][link]
                root = edge["source_node"] * a["TX"]
                for j in range(3):
                    data, meta = self.packet(j, root)
                    await self.cycle(
                        "fill_parity",
                        i_enable=1,
                        i_tile_tx_valid=1 << root,
                        i_tile_tx_data=data << (root * a["D"]),
                        i_tile_tx_metadata=meta << (root * a["M"]),
                        i_tile_rx_ready=0,
                    )
                path = f"g_network.g_link[{link}].g_internal.u_link.u_skid.g_skid.buffer_data"
                item = await self.cycle(
                    "parity_" + field, fault=(path, 1 << bit), i_tile_tx_valid=0
                )
                assert (
                    item.post["o_error_code"] == 15
                    and item.post["o_parity_error_event"] >> link & 1
                )
                assert item.post["o_error_tag"] == (1 ^ (1 if field == "metadata" else 0))
                await self.cycle("parity_release", fault=("release", 0))
                await self.flush()
                self.coverage.hit("parity_" + field)
        if self.p["CONTROL_PROTECTION"]:
            await self.reset()
            await self.load(route)
            self.active["fault_mode"] = True
            path = "g_network.u_control.u_active.stored"
            item = await self.cycle("control_bit", fault=(path, 1))
            if self.p["CONTROL_PROTECTION"] == 2:
                assert not item.post["o_error"]
            else:
                assert item.pre["o_error_code"] == 16
            await self.cycle("control_release", fault=("release", 0))
            if self.p["CONTROL_PROTECTION"] == 2:
                item = await self.cycle("control_double", fault=(path, 3))
                assert item.pre["o_error_code"] == 16
                await self.cycle("control_double_release", fault=("release", 0))
            self.coverage.hit("control_protection")

    async def counter(self, index):
        item = await self.cycle("counter_request", i_counter_read=1, i_counter_index=index)
        assert item.post["o_counter_valid"]
        value = item.post["o_counter_value"]
        await self.cycle("counter_release", i_counter_read=0)
        return value

    async def semantics_and_join(self, local):
        """Independent ordered data queue models an endpoint, never a fabric join."""
        a = self.a
        root = self.roots(local)[0][1]
        dest = root // a["TX"] * a["RX"]
        await self.reset()
        await self.load(local)
        packets = [self.packet(j, root) for j in range(24)]
        sent = consumed = 0
        data_queue = deque()
        ready_cycles = [max(0, j * 3 + (4 if j % 2 else -4)) for j in range(24)]
        # Preserve data order while varying whether data or predicate arrives first.
        ready_cycles = list(accumulate(ready_cycles, max))
        data_sent = 0
        false_valid = invalid = 0
        skew = set()
        for tick in range(300):
            while data_sent < len(packets) and ready_cycles[data_sent] <= tick:
                data_queue.append((data_sent, 100 + data_sent))
                data_sent += 1
            data, meta = packets[sent] if sent < len(packets) else (0, 0)
            item = await self.cycle(
                "tagged_join",
                i_enable=1,
                i_tile_tx_valid=(1 << root) if sent < len(packets) else 0,
                i_tile_tx_data=data << (root * a["D"]),
                i_tile_tx_metadata=meta << (root * a["M"]),
                i_tile_rx_ready=(1 << dest) if data_queue else 0,
                i_drain=int(sent == len(packets)),
            )
            if sent < len(packets) and item.pre["o_pred_tx_ready"] >> root & 1:
                sent += 1
            if item.pre["o_pred_rx_valid"] >> dest & 1:
                if not data_queue:
                    skew.add("predicate_first")
                else:
                    serial, operand = data_queue.popleft()
                    delivered_meta = item.pre["o_pred_rx_metadata"] >> (dest * a["M"]) & (
                        (1 << a["M"]) - 1
                    )
                    assert delivered_meta == packets[serial][1]
                    tag = delivered_meta >> (a["CI"] + a["V"] + a["K"] + a["EP"] + a["PR"]) & (
                        (1 << a["T"]) - 1
                    )
                    assert tag == serial and serial == consumed
                    value = item.pre["o_pred_rx_value"] >> (dest * a["PV"]) & ((1 << a["PV"]) - 1)
                    mask = item.pre["o_pred_rx_lane_valid"] >> (dest * a["PV"]) & (
                        (1 << a["PV"]) - 1
                    )
                    # False lanes consume the associated operation without authorizing it.
                    authorized = [
                        operand if value >> lane & mask >> lane & 1 else None
                        for lane in range(a["PV"])
                    ]
                    assert sum(v is not None for v in authorized) == (value & mask).bit_count()
                    false_valid += int(mask != 0 and value == 0)
                    invalid += int(mask == 0)
                    if ready_cycles[serial] < tick:
                        skew.add("data_first")
                    consumed += 1
            if consumed == len(packets) and item.post["o_drained"]:
                break
        assert sent == consumed == len(packets) and not data_queue
        assert false_valid and invalid and len(skew) == 2
        await self.cycle("join_empty", i_tile_tx_valid=0, i_enable=0)
        assert await self.counter(1) == len(packets)
        assert await self.counter(2) == len(packets)
        assert await self.counter(32 + root * 4 + 2) == sum(
            (d >> a["PV"]).bit_count() for d, _ in packets
        )
        self.coverage.hit("tagged_join")
        self.coverage.hit("counter_accounting")

    async def rejection_cases(self, local, route):
        await self.reset()
        await self.prepare(local)
        self.version = 2
        await self.prepare(local, expected=1, i_cfg_route_image=LogicArray("X" * self.a["RI"]))
        assert (await self.cycle("unknown_shadow_preserved")).post["o_shadow_valid"]
        await self.prepare(local, expected=8, period=0)
        await self.prepare(local, expected=8, i_cfg_schedule_slot_image=1)
        # Complete valid hash but an impossible output source selector.
        node, output = next(iter(local))
        broken = dict(local)
        broken[node, output] = (1 << self.a["S"]) - 1
        await self.prepare(broken, expected=2, check=False)
        if route:
            orphan = {k: v for k, v in route.items() if k[1] < self.a["RX"]}
            await self.prepare(orphan, expected=5, check=False)
            dangling = {k: v for k, v in route.items() if k[1] >= self.a["RX"]}
            await self.prepare(dangling, expected=5, check=False)
            if not self.p["SUPPORT_MULTICAST"]:
                fanout = dict(route)
                source_node = next(n for n, o in route if o >= self.a["RX"])
                fanout[source_node, 0] = 0
                await self.prepare(fanout, expected=3, check=False)
        # Four legal cardinal turns form a resource cycle, without U-turns.
        for row in range(self.a["R"] - 1):
            found = False
            for col in range(self.a["C"] - 1):
                nw = row * self.a["C"] + col
                nodes = [nw, nw + 1, nw + self.a["C"] + 1, nw + self.a["C"]]
                edges = []
                for n, dst in zip(nodes, nodes[1:] + nodes[:1]):
                    edge = next(
                        (
                            e
                            for e in self.g["edges"][: self.a["IL"]]
                            if e["source_node"] == n
                            and e["destination_node"] == dst
                            and self.g["mask"] >> e["index"] & 1
                        ),
                        None,
                    )
                    if edge is None:
                        break
                    edges.append(edge)
                if len(edges) != 4:
                    continue
                cycle = {
                    (e["source_node"], e["source_port"]): edges[j - 1]["destination_port"]
                    for j, e in enumerate(edges)
                }
                if not all(
                    self.g["connectivity"] >> (n * self.a["O"] * self.a["I"] + o * self.a["I"] + i)
                    & 1
                    for (n, o), i in cycle.items()
                ):
                    continue
                await self.prepare(cycle, expected=5, check=False)
                self.coverage.hit("cycle_rejected")
                found = True
                break
            if found:
                break
        if self.p["SUPPORT_MULTICAST"]:
            full_tree = super().multicast_tree()
            if sum(o < self.a["RX"] for n, o in full_tree) > self.p["MAX_TREE_DESTINATIONS"]:
                await self.prepare(full_tree, expected=4, check=False)
                self.coverage.hit("tree_rejected")
        self.version = 1
        # Neither a mismatching peer identity nor its version consumes the shadow.
        item = await self.cycle(
            "wrong_commit",
            i_cfg_commit_valid=1,
            i_cfg_commit_context_id=0,
            i_cfg_commit_context_version=1,
        )
        assert not item.pre["o_cfg_commit_ready"] and item.post["o_shadow_valid"]
        await self.cycle("wrong_commit_cancel", i_cfg_commit_valid=0)
        await self.commit()
        self.coverage.hit("configuration_rejection")

    async def turns(self):
        a, g = self.a, self.g
        seen = set()
        edges = [e for e in g["edges"][: a["IL"]] if g["mask"] >> e["index"] & 1]
        for incoming in edges:
            for outgoing in edges:
                node = incoming["destination_node"]
                if node != outgoing["source_node"]:
                    continue
                source = incoming["destination_port"]
                output = outgoing["source_port"]
                key = (source - a["TX"], output - a["RX"])
                if key in seen:
                    continue
                start, end = incoming["source_node"], outgoing["destination_node"]
                if start == end:
                    continue
                routes = {
                    (start, incoming["source_port"]): 0,
                    (node, output): source,
                    (end, 0): outgoing["destination_port"],
                }
                try:
                    graph(self.c.parameters, routes)
                except AssertionError:
                    continue
                seen.add(key)
                await self.reset()
                await self.load(routes)
                await self.traffic(routes, beats=4)
                self.coverage.hit(f"turn_{key[0]}_{key[1]}")

    async def scheduled_period(self, route):
        a = self.a
        if not route or not self.p["SUPPORT_SCHEDULE_CHECK"] or a["PM"] < 3:
            return
        await self.reset()
        await self.load(route, scheduled=True, period=3)
        roots = self.roots(route)
        # A shared safe-point stalls the entire schedule before execution starts.
        for _ in range(4):
            item = await self.cycle("safe_pause", i_schedule_pause=1)
            assert not item.post["o_error"]
        for tick in range(32):
            valid = data = meta = 0
            if tick % 3 == 0 and tick < 24:
                for group, root in roots:
                    assert group == "tile"
                    packet, identity = self.packet(tick // 3, root)
                    valid |= 1 << root
                    data |= packet << (root * a["D"])
                    meta |= identity << (root * a["M"])
            item = await self.cycle(
                "period_three",
                i_schedule_pause=0,
                i_enable=1,
                i_drain=int(tick >= 24),
                i_tile_tx_valid=valid,
                i_tile_tx_data=data,
                i_tile_tx_metadata=meta,
                i_tile_rx_ready=(1 << (a["N"] * a["RX"])) - 1,
            )
            assert not item.post["o_error"], (tick, item.post["o_error_code"])
        assert item.post["o_drained"]
        self.coverage.hit("periodic_schedule")
        for kind in ("off_slot", "backpressure"):
            await self.reset()
            await self.load(route, scheduled=True, period=3)
            self.active["fault_mode"] = True
            for tick in range(4):
                valid = data = meta = 0
                if tick == 0 or (kind == "off_slot" and tick == 1):
                    for _, root in roots:
                        packet, identity = self.packet(tick, root)
                        valid |= 1 << root
                        data |= packet << (root * a["D"])
                        meta |= identity << (root * a["M"])
                item = await self.cycle(
                    kind,
                    i_enable=1,
                    i_tile_tx_valid=valid,
                    i_tile_tx_data=data,
                    i_tile_tx_metadata=meta,
                    i_tile_rx_ready=0,
                )
                if item.post["o_error_code"] == 8:
                    break
            assert item.post["o_error_code"] == 8
            self.coverage.hit("schedule_" + kind)

    async def boundary_fault(self):
        if not self.p["EXPOSE_BOUNDARY_PORTS"] or not self.p["ENABLE_LINK_PARITY"]:
            return
        a, g = self.a, self.g
        b = next(b for b in range(a["B"]) if g["mask"] >> (a["IL"] + 2 * b) & 1)
        edge = g["edges"][a["IL"] + 2 * b]
        routes = {(edge["destination_node"], 0): edge["destination_port"]}
        await self.reset()
        await self.load(routes)
        self.active["fault_mode"] = True
        data, meta = self.packet(7, a["N"] * a["TX"] + b)
        item = await self.cycle(
            "boundary_parity",
            i_enable=1,
            i_boundary_rx_valid=1 << b,
            i_boundary_rx_data=data << (b * a["D"]),
            i_boundary_rx_metadata=meta << (b * a["M"]),
            i_boundary_rx_parity=(1 ^ ((data.bit_count() + meta.bit_count()) % 2)) << b,
        )
        assert not item.pre["o_boundary_pred_ready"] >> b & 1
        assert item.post["o_error_code"] == 15
        assert item.post["o_error_link"] == a["IL"] + 2 * b
        assert item.post["o_error_source"] == a["N"] * a["TX"] + b
        assert item.post["o_error_tag"] == 7
        self.coverage.hit("boundary_parity")

    async def recovery_and_unknowns(self, local):
        a = self.a
        root = self.roots(local)[0][1]
        dest = root // a["TX"] * a["RX"]
        # Reset cancels active, shadow, and pending transport ownership.
        for phase in ("prepare", "commit", "traffic"):
            await self.reset()
            await self.prepare(local)
            if phase == "prepare":
                self.version = 2
                await self.cycle("reset_pending_prepare", i_cfg_prepare_valid=1)
            elif phase == "commit":
                await self.cycle(
                    "reset_pending_commit",
                    i_cfg_commit_valid=1,
                    i_cfg_commit_context_id=1,
                    i_cfg_commit_context_version=1,
                )
            else:
                await self.commit()
                data, meta = self.packet(0, root)
                await self.cycle(
                    "reset_pending_token",
                    i_enable=1,
                    i_tile_tx_valid=1 << root,
                    i_tile_tx_data=data << (root * a["D"]),
                    i_tile_tx_metadata=meta << (root * a["M"]),
                )
            await self.reset()
            item = await self.cycle("reset_empty")
            assert item.post["o_quiescent"] and not item.post["o_active_context_valid"]
            assert not item.post["o_shadow_valid"] and not item.post["o_error"]
        # The coordinated data-side cancellation is represented by discarding
        # endpoint queues in the model at this same recovery boundary.
        await self.load(local)
        data, meta = self.packet(0, root)
        item = await self.cycle(
            "flush_pending_token",
            i_enable=1,
            i_tile_tx_valid=1 << root,
            i_tile_tx_data=data << (root * a["D"]),
            i_tile_tx_metadata=meta << (root * a["M"]),
        )
        assert item.pre["o_pred_tx_ready"] >> root & 1
        await self.flush()
        item = await self.cycle("post_flush_no_old_epoch")
        assert item.post["o_active_context_valid"] and item.post["o_active_context_version"] == 1
        assert not item.post["o_pred_rx_valid"] and item.post["o_quiescent"]
        assert await self.counter(1) == 1
        self.active.update(routes=local, fault_mode=False, generation=self.active["generation"] + 1)
        await self.traffic(local, beats=8)
        self.coverage.hit("reset_recovery")
        self.coverage.hit("flush_pending")
        # Unknown request controls stop admission. Unknown consumer readiness
        # holds its token rather than allowing an ambiguous consumption.
        for kind in ("enable", "valid", "ready", "value", "mask", "metadata"):
            await self.reset()
            await self.load(local)
            self.active["fault_mode"] = True
            data, meta = self.packet(0, root)
            fields = dict(
                i_enable=1,
                i_pred_tx_valid=1 << root,
                i_pred_tx_value=0,
                i_pred_tx_lane_valid=1 << (root * a["PV"]),
                i_pred_tx_metadata=meta << (root * a["M"]),
            )
            if kind == "enable":
                fields["i_enable"] = LogicArray("X")
            if kind == "valid":
                fields["i_pred_tx_valid"] = LogicArray("X" * (a["N"] * a["TX"]))
            if kind == "mask":
                fields["i_pred_tx_lane_valid"] = LogicArray("X" * (a["N"] * a["TX"] * a["PV"]))
            if kind == "metadata":
                fields["i_pred_tx_metadata"] = LogicArray("X" * (a["N"] * a["TX"] * a["M"]))
            if kind == "value":
                fields["i_pred_tx_value"] = LogicArray("X" * (a["N"] * a["TX"] * a["PV"]))
            if kind == "ready":
                await self.cycle("ready_token", **fields)
                fields = dict(
                    i_pred_tx_valid=0, i_pred_rx_ready=LogicArray("X" * (a["N"] * a["RX"]))
                )
            item = await self.cycle("unknown_" + kind, **fields)
            assert item.post["o_error_code"] == 1, (kind, item.post["o_error_code"])
            if kind != "ready":
                assert not item.pre["o_pred_tx_ready"] >> root & 1
            else:
                item = await self.cycle("unknown_ready_held", i_pred_rx_ready=0)
                assert item.pre["o_pred_rx_valid"] >> dest & 1
            self.coverage.hit("unknown_" + kind)

    async def power_observations(self, local):
        a = self.a
        await self.reset()
        await self.load(local)
        item = await self.cycle("idle_clock_hints")
        assert item.post["o_node_clock_enable"] == 0
        item = await self.cycle("test_clock_hints", i_test_enable=1)
        assert item.post["o_node_clock_enable"] == self.g["nodes"]
        item = await self.cycle("scan_clock_hints", i_test_enable=0, i_scan_enable=1)
        assert item.post["o_node_clock_enable"] == self.g["nodes"]
        await self.cycle("clock_hint_release", i_scan_enable=0)
        root = self.roots(local)[0][1]
        data, meta = self.packet(0, root)
        item = await self.cycle(
            "isolation_pending",
            i_enable=1,
            i_tile_tx_valid=1 << root,
            i_tile_tx_data=data << (root * a["D"]),
            i_tile_tx_metadata=meta << (root * a["M"]),
        )
        assert item.pre["o_pred_tx_ready"] >> root & 1
        item = await self.cycle("isolation_wait", i_boundary_isolate=1, i_tile_tx_valid=0)
        assert (
            not item.post["o_boundary_isolated"]
            and item.post["o_node_clock_enable"] >> (root // a["TX"]) & 1
        )
        assert item.pre["o_pred_tx_ready"] == 0
        for _ in range(4):
            item = await self.cycle(
                "isolation_drain", i_drain=1, i_tile_rx_ready=(1 << (a["N"] * a["RX"])) - 1
            )
        assert item.post["o_boundary_isolated"] and item.post["o_drained"]
        for _ in range(3):
            item = await self.cycle("isolated_hold")
            assert item.post["o_boundary_isolated"] and not item.post["o_pred_tx_ready"]
        await self.cycle("isolation_release", i_boundary_isolate=0, i_drain=0, i_enable=0)
        self.coverage.hit("isolation_clock_hints")

    async def body(self):
        a, p = self.a, self.p
        await self.reset()
        item = await self.cycle("topology")
        assert item.post["o_topology_id"] == topology_id(self.c.parameters)
        local = {
            (n, o): o % a["TX"]
            for n in range(a["N"])
            for o in range(min(a["TX"], a["RX"]))
            if self.g["connectivity"] >> (n * a["O"] * a["I"] + o * a["I"] + o % a["TX"]) & 1
        }
        await self.load(local)
        await self.traffic(local, beats=24)
        for direction in range(4):
            for channel in range(a["H"]):
                routes = self.one_hop(direction, channel)
                if routes:
                    await self.reset()
                    await self.load(routes)
                    await self.traffic(routes, beats=10)
                    self.coverage.hit(f"direction_{direction}_channel_{channel}")
        path = self.longest_path()
        if path:
            await self.reset()
            await self.load(path)
            latency = await self.traffic(path, beats=12, stalls=False)
            assert latency == len(path)
            self.coverage.hit("latency")
            await self.traffic(path, beats=self.c.random_cycles)
        if p["SUPPORT_MULTICAST"]:
            tree = self.multicast_tree()
            if len(tree) > 1:
                await self.reset()
                await self.load(tree)
                await self.traffic(tree, beats=32)
                self.coverage.hit("broadcast")
        if p["EXPOSE_BOUNDARY_PORTS"]:
            for direction in range(4):
                routes = {}
                for b in range(a["B"]):
                    e = self.g["edges"][a["IL"] + 2 * b]
                    out = self.g["edges"][a["IL"] + 2 * b + 1]
                    if (e["destination_port"] - a["TX"]) // a["H"] != direction:
                        continue
                    if not (self.g["mask"] >> (a["IL"] + 2 * b) & 3) == 3:
                        continue
                    lane = (e["destination_port"] - a["TX"]) % a["H"]
                    node = e["destination_node"]
                    if lane >= min(a["TX"], a["RX"]):
                        continue
                    routes[node, lane] = e["destination_port"]
                    routes[node, out["source_port"]] = lane
                if routes:
                    await self.reset()
                    await self.load(routes)
                    await self.traffic(routes, beats=12)
                    self.coverage.hit("boundary")
        route = next((self.one_hop(d, 0) for d in range(4) if self.one_hop(d, 0)), None)
        if route and p["SUPPORT_SCHEDULE_CHECK"]:
            await self.reset()
            await self.load(route, scheduled=True)
            await self.traffic(route, beats=32, stalls=False)
            self.coverage.hit("scheduled")
            self.active["fault_mode"] = True
            await self.cycle("schedule_restart", i_enable=0, i_drain=0, i_error_clear=1)
            item = await self.cycle("missing_slot", i_enable=1, i_error_clear=0)
            assert item.post["o_error_code"] == 8 and item.post["o_schedule_violation"]
            self.coverage.hit("schedule_missing")
        await self.turns()
        await self.semantics_and_join(local)
        await self.rejection_cases(local, route)
        await self.scheduled_period(route)
        await self.boundary_fault()
        await self.power_observations(local)
        await self.recovery_and_unknowns(local)
        await self.protocol(local)
        await self.lane_and_alignment(local)
        await self.reliability(route)
        await self.reset()
        self.coverage.goals = {
            k: bool(self.coverage.bins[k])
            for k in (
                "prepare",
                "prepare_error_7",
                "commit",
                "abort",
                "shadow_isolation",
                "commit_ingress_collision",
                "flush",
                "traffic",
                "latency",
                "alignment_containment",
                "invalid_lane",
                "empty_ordinary",
                "tagged_join",
                "counter_accounting",
                "configuration_rejection",
                "reset_recovery",
                "flush_pending",
                "unknown_ready",
                "isolation_clock_hints",
                "class_0",
                "class_2",
                "false_valid",
                "invalid",
            )
        }
        for k, needed in dict(
            broadcast=bool(p["SUPPORT_MULTICAST"] and len(self.multicast_tree()) > 1),
            boundary=bool(p["EXPOSE_BOUNDARY_PORTS"]),
            scheduled=bool(route and p["SUPPORT_SCHEDULE_CHECK"]),
            periodic_schedule=bool(route and p["SUPPORT_SCHEDULE_CHECK"] and a["PM"] >= 3),
            boundary_parity=bool(p["EXPOSE_BOUNDARY_PORTS"] and p["ENABLE_LINK_PARITY"]),
            parity_value=bool(route and p["ENABLE_LINK_PARITY"]),
            parity_validity=bool(route and p["ENABLE_LINK_PARITY"]),
            parity_metadata=bool(route and p["ENABLE_LINK_PARITY"]),
            control_protection=bool(route and p["CONTROL_PROTECTION"]),
        ).items():
            if needed:
                self.coverage.goals[k] = bool(self.coverage.bins[k])
        for lane in range(a["PV"]):
            for value, valid in ((0, 0), (0, 1), (1, 1)):
                label = f"lane_{lane}_value_{value}_valid_{valid}"
                self.coverage.goals[label] = bool(self.coverage.bins[label])
        for label in ("enable", "valid", "ready", "value", "mask", "metadata"):
            self.coverage.goals["unknown_" + label] = bool(self.coverage.bins["unknown_" + label])
        if a["PV"] > 1:
            for label in ("class_1", "class_3", "inactive_unknown"):
                self.coverage.goals[label] = bool(self.coverage.bins[label])
        self.c.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.c.coverage_file.with_name("contract.json").write_text(
            json.dumps(
                dict(
                    schema="mosaic-predicate-network-v1",
                    parameters=self.c.parameters,
                    topology_id=topology_id(self.c.parameters),
                    routes=self.artifacts,
                    physical_timing="NOT_CHARACTERIZED",
                    energy="NOT_CHARACTERIZED",
                    alignment="ordered tagged endpoint join; network never evaluates predicates",
                ),
                indent=2,
            )
            + "\n"
        )
