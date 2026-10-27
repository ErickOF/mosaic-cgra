"""Cold loads, ordered multicast and coordinated architectural activation."""

import json
import os
import random
from cocotb.types import LogicArray
from pyuvm import uvm_sequence
from configuration_network.transaction import INPUTS, NetworkItem
from configuration_network.model import EndpointServer
from configuration_network.layout import (
    endpoint,
    topology,
    crc32c,
    published_parameters,
    CMD,
    RSP,
)


class NetworkSequence(uvm_sequence):
    def __init__(self, c, active, coverage):
        super().__init__("configuration_specification")
        self.c, self.active, self.coverage = c, active, coverage
        self.a = c.aliases
        self.p = c.parameters
        self.server = EndpointServer(c.parameters, c.seed)
        self.rng = random.Random(c.seed)
        self.count = 0
        self.next_tag = 1
        self.epoch = 0
        self.ports = {}

    async def cycle(self, label="cycle", fault=None, **ports):
        self.ports.update(ports)
        driven = {n: 0 for n in INPUTS if n.startswith("i_endpoint_")}
        driven.update(self.server.drive())
        driven.update(self.ports)
        item = NetworkItem(f"{label}_{self.count}", driven, fault)
        self.count += 1
        if self.count % 1000 == 0:
            print(f"Configuration progress: {self.count} cycles, {label}", flush=True)
        if os.getenv("CONFIGURATION_NETWORK_TRACE"):
            print(item.get_name(), flush=True)
        await self.start_item(item)
        await self.finish_item(item)
        self.server.step(item.pre)
        return item

    async def reset(self):
        self.ports = {n: 0 for n in INPUTS if not n.startswith("i_endpoint_")}
        self.active["diagnostic"] = False
        self.active["records"].clear()
        self.active["endpoint_errors"] = {}
        self.server = EndpointServer(self.c.parameters, self.c.seed)
        for _ in range(3):
            await self.cycle("reset")
        for _ in range(3):
            await self.cycle(
                "reset_release",
                i_reset_n=1,
                i_cfg_response_ready=(1 << self.a["NM"]) - 1,
                i_cfg_request_protocol=sum(1 << (m * 8) for m in range(self.a["NM"])),
            )
        self.epoch = 0
        self.next_tag = 1

    async def send(self, command, destination, master=0, **fields):
        a = self.a
        tag = self.next_tag % (1 << a["TG"])
        self.next_tag += 1
        values = dict(
            command=command,
            destination_mask=destination,
            owner_id=0,
            kernel_id=3,
            package_id=7,
            context_id=0,
            expected_version=0,
            word_index=0,
            write_data=0,
            write_strobe=(1 << a["BY"]) - 1,
            expected_crc=0,
            tag=tag,
            epoch=self.epoch,
            flags=0,
            protocol=1,
        )
        values.update(fields)
        ports = {
            "i_cfg_request_" + n: v
            << (master * (self.c.widths["i_cfg_request_" + n] // a["NM"]))
            for n, v in values.items()
        }
        for _ in range(self.p["TRANSACTION_TIMEOUT_CYCLES"] + 1000):
            item = await self.cycle("request", i_cfg_request_valid=1 << master, **ports)
            if item.pre["o_cfg_request_ready"] >> master & 1:
                break
        else:
            raise AssertionError("Master request admission timed out")
        self.ports["i_cfg_request_valid"] = 0
        return tag

    async def wait(self, tag):
        for _ in range(
            self.p["TRANSACTION_TIMEOUT_CYCLES"] + self.a["NE"] * 100 + 1000
        ):
            records = [r for r in self.active["records"] if r["tag"] == tag]
            if records and records[-1]["last"]:
                self.active["records"] = [
                    r for r in self.active["records"] if r["tag"] != tag
                ]
                return records
            await self.cycle("response_wait")
        raise AssertionError(("Root response timed out", tag))

    async def request(self, command, destination, **fields):
        return await self.wait(await self.send(command, destination, **fields))

    async def load_context(self, selected, context=0, package=7, prepare=True):
        a = self.a
        count = min(
            endpoint(self.p, e)["words"] for e in range(a["NE"]) if selected >> e & 1
        )
        values = [self.rng.getrandbits(a["D"]) for _ in range(count)]
        for word, value in enumerate(values):
            records = await self.request(
                1,
                selected,
                context_id=context,
                package_id=package,
                word_index=word,
                write_data=value,
                expected_version=int(word > 0),
            )
            assert all(r["status"] == 0 for r in records)
        image = crc32c(b"".join(v.to_bytes(a["BY"], "little") for v in values))
        records = await self.request(
            3,
            selected,
            context_id=context,
            package_id=package,
            expected_version=1,
            expected_crc=image,
        )
        assert all(r["status"] == 0 for r in records)
        if prepare:
            records = await self.request(
                6,
                selected,
                context_id=context,
                package_id=package,
                expected_version=1,
                expected_crc=image,
            )
            assert all(r["status"] == 0 and r["prepared"] for r in records)
        return values, image

    async def commit(
        self, selected, context=0, package=7, epoch=1, release=True, failure=False
    ):
        a = self.a
        ports = dict(
            i_commit_destination_mask=selected,
            i_commit_package_id=package,
            i_commit_kernel_id=3,
            i_commit_owner_id=0,
            i_commit_epoch=epoch,
            i_commit_context_ids=sum(
                context << (e * a["CI"]) for e in range(a["NE"]) if selected >> e & 1
            ),
            i_commit_context_versions=sum(
                1 << (e * a["V"]) for e in range(a["NE"]) if selected >> e & 1
            ),
        )
        for _ in range(100):
            item = await self.cycle("commit_request", i_commit_valid=1, **ports)
            if item.pre["o_commit_ready"]:
                break
        else:
            raise AssertionError(("Commit not ready", item.post["o_armed_mask"]))
        assert item.post["o_execution_hold"] and not item.pre["o_endpoint_commit_valid"]
        self.ports["i_commit_valid"] = 0
        delivery = []
        for _ in range(self.p["COMMIT_TIMEOUT_CYCLES"] + 10):
            item = await self.cycle("commit_acknowledgements")
            assert item.pre["o_execution_hold"]
            if item.pre["o_endpoint_commit_valid"]:
                delivery.append(item.pre["o_endpoint_commit_valid"])
            if item.post["o_commit_error"]:
                assert failure
                assert (
                    item.post["o_execution_hold"] and item.post["o_commit_failure_mask"]
                )
                self.coverage.hit("partial_commit")
                return item
            if item.post["o_commit_complete"]:
                break
        else:
            raise AssertionError("Commit result timeout")
        assert not failure and delivery == [selected], delivery
        assert item.post["o_commit_ack_mask"] == selected
        assert (
            item.post["o_active_package_id"] == package
            and item.post["o_active_commit_epoch"] == epoch
        )
        for _ in range(3):
            item = await self.cycle(
                "release_not_safe", i_execution_release=1, i_release_safe=0
            )
            assert item.post["o_execution_hold"]
        if release:
            item = await self.cycle("release_safe", i_release_safe=1)
            assert not item.post["o_execution_hold"]
            await self.cycle("release_drop", i_execution_release=0, i_release_safe=0)
        self.coverage.hit("coordinated_commit")
        return item

    async def pressure_and_order(self):
        a = self.a
        await self.reset()
        self.server.stalls = True
        self.server.delays = {e: 3 * (a["NE"] - e) for e in range(a["NE"])}
        present = self.p["ENDPOINT_PRESENT_MASK"]
        selected = present if self.p["SUPPORT_MULTICAST"] else present & -present
        # Multiple overlapping commands fill completion slots while the master
        # independently stalls the ordered output queue.
        self.ports["i_cfg_response_ready"] = 0
        tags = []
        for j in range(a["NS"]):
            tags.append(
                await self.send(
                    5,
                    1 << next(e for e in range(a["NE"]) if selected >> e & 1),
                    master=j % a["NM"],
                )
            )
        for _ in range(30):
            await self.cycle("master_backpressure")
        self.ports["i_cfg_response_ready"] = (1 << a["NM"]) - 1
        for tag in tags:
            await self.wait(tag)
        if self.p["SUPPORT_MULTICAST"]:
            tag = await self.send(4, selected)
            records = await self.wait(tag)
            assert [r["endpoint_id"] for r in records] == sorted(
                endpoint(self.p, e)["id"] for e in range(a["NE"]) if selected >> e & 1
            )
        self.coverage.hit("queue_pressure")
        self.coverage.hit("ordered_completion")
        # Disjoint query traffic exercises deterministic retirement across masters.
        start = self.count
        while self.count - start < self.c.random_cycles:
            tags = []
            for j in range(a["NS"]):
                e = self.rng.choice([e for e in range(a["NE"]) if present >> e & 1])
                cmd = self.rng.choice(
                    [1, 3, 4, 5, 6, 7] + ([2] if self.p["SUPPORT_READBACK"] else [])
                )
                ci = self.rng.randrange(min(2, endpoint(self.p, e)["contexts"]))
                c = self.server.endpoints[e].context(ci)
                tags.append(
                    await self.send(
                        cmd,
                        1 << e,
                        master=j % a["NM"],
                        context_id=ci,
                        expected_version=c["version"],
                        expected_crc=self.server.endpoints[e].crc(ci),
                        word_index=self.rng.randrange(endpoint(self.p, e)["words"]),
                        write_data=self.rng.getrandbits(a["D"]),
                        write_strobe=self.rng.getrandbits(a["BY"]),
                    )
                )
            for tag in tags:
                await self.wait(tag)
        self.coverage.hit("random_commands")

    async def negative_requests(self):
        a = self.a
        present = self.p["ENDPOINT_PRESENT_MASK"]
        e = next(e for e in range(a["NE"]) if present >> e & 1)
        for command, mask, fields, code in (
            (1, 0, {}, 3),
            (2, present if present.bit_count() > 1 else 0, {}, 3),
            (8, 1 << e, {}, 2),
            (1, 1 << e, dict(owner_id=99), 5),
            (1, 1 << e, dict(word_index=endpoint(self.p, e)["words"]), 7),
            (1, 1 << e, dict(context_id=endpoint(self.p, e)["contexts"]), 8),
            (1, 1 << e, dict(epoch=(self.epoch + 1) % (1 << a["EP"])), 10),
            (1, 1 << e, dict(flags=2), 1),
            (10, 0, dict(epoch=(self.epoch + 1) % (1 << a["EP"])), 10),
            (10, 0, dict(protocol=2), 1),
        ):
            records = await self.request(command, mask, **fields)
            assert all(r["status"] != 0 and r["error_code"] == code for r in records), (
                command,
                records,
            )
            self.coverage.hit("request_rejection")
        for e in range(a["NE"]):
            records = await self.request(5, 1 << e)
            assert records[0]["status"] == (0 if present >> e & 1 else 4)
        self.coverage.hit("endpoint_descriptors")

    async def flush(self):
        self.active["diagnostic"] = True
        before = (await self.cycle("before_flush")).post["o_configuration_epoch"]
        await self.cycle("flush", i_flush=1, i_cfg_request_valid=0, i_commit_valid=0)
        for _ in range(4):
            item = await self.cycle("flush_hold")
        assert item.post["o_configuration_epoch"] == (before + 1) % (1 << self.a["EP"])
        for _ in range(self.p["TRANSACTION_TIMEOUT_CYCLES"] + 100):
            item = await self.cycle("flush_release", i_flush=0)
            if not item.post["o_flushing"] and item.post["o_idle"]:
                break
        else:
            raise AssertionError("Cancellation did not converge")
        assert not item.post["o_endpoint_request_valid"] and item.post["o_idle"]
        self.epoch = item.post["o_configuration_epoch"]
        self.coverage.hit("flush")

    async def cancellation_records(self):
        # Cover both a completed prefix buffered at the root and pending copies.
        await self.reset()
        self.active["diagnostic"] = True
        e = (
            self.p["ENDPOINT_PRESENT_MASK"] & -self.p["ENDPOINT_PRESENT_MASK"]
        ).bit_length() - 1
        await self.cycle("cancel_backpressure", i_cfg_response_ready=0)
        tags = [await self.send(5, 1 << e)]
        for _ in range(50 + 4 * self.a["CF"]):
            await self.cycle("buffer_completion")
        if self.p["MAX_OUTSTANDING_TRANSACTIONS"] > 1:
            tags.append(await self.send(5, 1 << e))
        await self.cycle("cancel_owned_results", i_flush=1)
        await self.cycle("cancel_drop", i_flush=0)
        records = []
        for _ in range(self.p["TRANSACTION_TIMEOUT_CYCLES"] + 500):
            item = await self.cycle("cancellation_retirement", i_cfg_response_ready=1)
            if item.pre["o_cfg_response_valid"] & 1:
                record = {
                    n.removeprefix("o_cfg_response_"): item.pre[n]
                    & ((1 << (w // self.a["NM"])) - 1)
                    for n, w in self.c.widths.items()
                    if n.startswith("o_cfg_response_")
                }
                records.append(record)
            if len(records) == len(tags) and item.post["o_idle"]:
                break
        assert [r["tag"] for r in records] == tags, records
        assert all(
            r["epoch"] == 1
            and r["status"] == 3
            and r["error_code"] == 21
            and r["first"]
            and r["last"]
            and not r["transaction_success"]
            and r["failure_mask"] == 1 << e
            for r in records
        ), records
        self.epoch = 1
        # Canonical FLUSH returns its own successful new-epoch terminal record.
        tag = await self.send(10, 0)
        for _ in range(self.p["TRANSACTION_TIMEOUT_CYCLES"] + 100):
            item = await self.cycle("canonical_flush")
            if item.pre["o_cfg_response_valid"] & 1:
                assert item.pre["o_cfg_response_tag"] & ((1 << self.a["TG"]) - 1) == tag
                assert item.pre["o_cfg_response_status"] & 15 == 0
                assert item.pre["o_cfg_response_epoch"] & ((1 << self.a["EP"]) - 1) == 2
                break
        else:
            raise AssertionError("Canonical FLUSH response missing")
        self.coverage.hit("cancellation_records")
        await self.reset()

    async def canonical_flush_overlap(self):
        await self.reset()
        self.active["diagnostic"] = True
        present = self.p["ENDPOINT_PRESENT_MASK"]
        destinations = [e for e in range(self.a["NE"]) if present >> e & 1]
        destinations = destinations[
            : 4
            if self.p["SUPPORT_MULTICAST"]
            and self.p["MAX_OUTSTANDING_TRANSACTIONS"] > 1
            else 1
        ]
        mask = sum(1 << e for e in destinations)
        await self.cycle("overlap_backpressure", i_cfg_response_ready=0)
        tag = await self.send(1, mask, write_data=0x1234 & ((1 << self.a["D"]) - 1))
        for _ in range(self.p["TRANSACTION_TIMEOUT_CYCLES"] + 100):
            item = await self.cycle("overlap_first_buffered_record")
            if item.post["o_cfg_response_valid"] & 1:
                break
        else:
            raise AssertionError("No multicast completion available")
        # The next record can enter the FIFO on the same edge that accepts FLUSH.
        flush_tag = await self.send(10, 0)
        records = []
        for _ in range(self.p["TRANSACTION_TIMEOUT_CYCLES"] + 100):
            item = await self.cycle("overlap_collect", i_cfg_response_ready=1)
            if item.pre["o_cfg_response_valid"] & 1:
                r = {
                    n.removeprefix("o_cfg_response_"): item.pre[n]
                    & ((1 << (w // self.a["NM"])) - 1)
                    for n, w in self.c.widths.items()
                    if n.startswith("o_cfg_response_")
                }
                records.append(r)
                if r["tag"] == flush_tag:
                    break
        expected = sorted(endpoint(self.p, e)["id"] for e in destinations)
        copies = [r for r in records if r["tag"] == tag]
        assert [r["endpoint_id"] for r in copies] == expected, records
        assert all(
            r["status"] == 3 and r["error_code"] == 21 and r["epoch"] == 1
            for r in copies
        ), records
        assert (
            sum(r["first"] for r in copies) == 1 and sum(r["last"] for r in copies) == 1
        )
        assert records[-1]["tag"] == flush_tag and records[-1]["status"] == 0
        self.coverage.hit("canonical_flush_buffered_results")
        await self.reset()

    async def epoch_wrap(self):
        await self.reset()
        self.active["diagnostic"] = True
        e = (
            self.p["ENDPOINT_PRESENT_MASK"] & -self.p["ENDPOINT_PRESENT_MASK"]
        ).bit_length() - 1
        await self.cycle("wrap_backpressure", i_cfg_response_ready=0)
        tag = await self.send(5, 1 << e)
        for _ in range(50 + 4 * self.a["CF"]):
            await self.cycle("wrap_buffer_old_success")
        for epoch in range(1, (1 << self.a["EP"]) + 1):
            await self.cycle("wrap_flush", i_flush=1)
            for _ in range(5):
                item = await self.cycle("wrap_drain_native", i_flush=0)
            assert not item.post["o_flushing"]
            assert item.post["o_configuration_epoch"] == epoch % (1 << self.a["EP"])
        for _ in range(50):
            item = await self.cycle("wrap_retire", i_cfg_response_ready=1)
            if item.pre["o_cfg_response_valid"] & 1:
                assert item.pre["o_cfg_response_tag"] & ((1 << self.a["TG"]) - 1) == tag
                assert item.pre["o_cfg_response_status"] & 15 == 3
                assert item.pre["o_cfg_response_error_code"] & 255 == 21
                assert item.pre["o_cfg_response_epoch"] & ((1 << self.a["EP"]) - 1) == 0
                break
        else:
            raise AssertionError("Buffered result lost at configuration epoch wrap")
        self.coverage.hit("epoch_wrap")
        await self.reset()

    async def recovery(self, selected):
        a = self.a
        # Drop one native response. Exactly one timeout record must terminate
        # the selected transaction; old native completion cannot create success.
        await self.reset()
        e = next(e for e in range(a["NE"]) if selected >> e & 1)
        self.active["diagnostic"] = True
        self.server.drop = {e}
        tag = await self.send(5, 1 << e)
        for _ in range(self.p["TRANSACTION_TIMEOUT_CYCLES"] + 200):
            item = await self.cycle("native_timeout")
            if item.post["o_error"]:
                break
        assert item.post["o_error_code"] == 15 and item.post["o_execution_hold"]
        assert item.post["o_endpoint_cancel"] >> e & 1
        await self.flush()
        self.coverage.hit("transaction_timeout")
        # CRC and framing faults are injected before link storage protection
        # computes parity, proving end-to-end packet checking itself.
        for mode in (
            ["crc_" + str(j) for j in range(a["CF"])]
            if self.p["ENABLE_PACKET_CRC"]
            else []
        ) + ["frame", "type"]:
            await self.reset()
            self.active["diagnostic"] = True
            await self.send(1, 1 << e, write_data=0x12)
            item = await self.cycle("capture_serializer")
            target = "g_network.u_command_serializer.stored"
            if mode == "frame":
                target = "g_network.u_command_serializer.q"
            if mode == "type":
                target = "g_network.forward_flit"
            mask = (
                (1 << (int(mode.split("_")[1]) * a["F"]))
                if mode.startswith("crc_")
                else (1 << (a["FL"] - 1))
                if mode == "type"
                else 1
            )
            item = await self.cycle("packet_" + mode, fault=(target, mask))
            if mode.startswith("crc_") or mode == "type":
                for _ in range(2 * a["CF"] + 8):
                    item = await self.cycle("packet_fault_held")
            await self.cycle("packet_fault_release", fault=("release", 0))
            for _ in range(self.p["TRANSACTION_TIMEOUT_CYCLES"] + 100):
                item = await self.cycle("packet_fault_result")
                if item.post["o_error"]:
                    break
            assert item.post["o_error_code"] in (11, 12), (
                mode,
                item.post["o_error_code"],
            )
            assert not self.server.native_history, (
                "Corrupt packet mutated an endpoint",
                mode,
            )
            self.coverage.hit("packet_" + ("crc" if mode.startswith("crc_") else mode))
            self.coverage.hit("fault_flit_" + mode)
            if mode == "type":
                self.coverage.hit("packet_type")
            await self.flush()
        await self.reset()
        await self.load_context(1 << e)
        await self.commit(1 << e)
        self.active["diagnostic"] = True
        item = await self.cycle(
            "active_power_loss",
            i_endpoint_power_safe=self.p["ENDPOINT_PRESENT_MASK"] & ~(1 << e),
        )
        assert item.post["o_execution_hold"] and item.post["o_error_code"] == 19
        item = await self.cycle(
            "power_restore_keeps_hold",
            i_endpoint_power_safe=self.p["ENDPOINT_PRESENT_MASK"],
            i_execution_release=1,
            i_release_safe=1,
        )
        assert item.post["o_execution_hold"]
        self.coverage.hit("active_power_loss")
        await self.reset()
        await self.load_context(selected)
        self.active["diagnostic"] = True
        endpoints = [e for e in range(a["NE"]) if selected >> e & 1]
        self.server.commit_drop = {endpoints[-1]}
        item = await self.commit(selected, failure=True)
        for _ in range(3):
            item = await self.cycle(
                "partial_commit_hold", i_execution_release=1, i_release_safe=1
            )
            assert item.post["o_execution_hold"] and item.post["o_fail_stop"]
        await self.cycle("partial_flush_attempt", i_flush=1)
        item = await self.cycle("partial_flush_release", i_flush=0)
        assert item.post["o_execution_hold"] and item.post["o_commit_error"]

    async def drain_and_reset(self):
        a = self.a
        await self.reset()
        tag = await self.send(
            5, self.p["ENDPOINT_PRESENT_MASK"] & -self.p["ENDPOINT_PRESENT_MASK"]
        )
        item = await self.cycle("drain_busy", i_drain=1)
        assert not item.pre["o_cfg_request_ready"]
        await self.wait(tag)
        for _ in range(5):
            item = await self.cycle("drain_empty")
        assert item.post["o_drained"]
        await self.cycle("drain_release", i_drain=0)
        records = await self.request(9, 0)
        assert records[-1]["status"] == 0
        for _ in range(3):
            item = await self.cycle("drain_command_done")
        assert item.post["o_drained"]
        await self.cycle("resume", i_resume=1)
        await self.cycle("resume_drop", i_resume=0)
        # Native queues and packet assembly are discarded by reset at each phase.
        for delay in (0, 1, 3, 8):
            await self.send(
                1, self.p["ENDPOINT_PRESENT_MASK"] & -self.p["ENDPOINT_PRESENT_MASK"]
            )
            for _ in range(delay):
                await self.cycle("reset_phase")
            await self.reset()
            item = await self.cycle("reset_empty")
            assert item.post["o_idle"] and item.post["o_execution_hold"]
            assert (
                not item.post["o_armed_mask"] and not item.post["o_cfg_response_valid"]
            )
        self.coverage.hit("drain")
        self.coverage.hit("reset_recovery")

    async def unknown_and_protection(self):
        a = self.a
        for signal, width in (
            ("i_cfg_request_destination_mask", a["NM"] * a["NE"]),
            ("i_cfg_request_write_strobe", a["NM"] * a["BY"]),
            ("i_flush", 1),
        ):
            await self.reset()
            self.active["diagnostic"] = True
            ports = dict(
                i_cfg_request_valid=1,
                i_cfg_request_command=1,
                i_cfg_request_destination_mask=1,
                i_cfg_request_write_strobe=(1 << a["BY"]) - 1,
            )
            ports[signal] = LogicArray("X" * width)
            item = await self.cycle("unknown_control", **ports)
            assert (
                not item.pre["o_cfg_request_ready"]
                and not item.pre["o_endpoint_request_valid"]
            )
            assert item.post["o_execution_hold"]
        self.coverage.hit("unknown_controls")
        await self.reset()
        self.active["diagnostic"] = True
        if self.p["CONTROL_PROTECTION"]:
            path = "g_network.u_control.stored"
            item = await self.cycle("single_control_bit", fault=(path, 1))
            if self.p["CONTROL_PROTECTION"] == 2:
                assert not item.post["o_error"]
                await self.cycle("single_release", fault=("release", 0))
                item = await self.cycle("double_control_bit", fault=(path, 3))
            assert item.post["o_error_code"] == 20 and item.post["o_execution_hold"]
            await self.cycle("control_fault_release", fault=("release", 0))
            item = await self.cycle("control_fault_latched")
            assert item.post["o_fail_stop"] and item.post["o_execution_hold"]
        self.coverage.hit("control_protection")
        await self.reset()
        for _ in range(2):
            item = await self.cycle("test_mode", i_test_enable=1)
            assert not item.post["o_cfg_request_ready"]
            assert (
                item.post["o_endpoint_clock_enable"] == self.p["ENDPOINT_PRESENT_MASK"]
            )
        await self.cycle("test_mode_release", i_test_enable=0)

    async def multiple_masters(self):
        a = self.a
        await self.reset()
        remaining = (1 << a["NM"]) - 1
        tags = [self.next_tag + m for m in range(a["NM"])]
        self.next_tag += a["NM"]
        self.ports.update(
            i_cfg_request_command=0,
            i_cfg_request_destination_mask=0,
            i_cfg_request_tag=sum(tag << (m * a["TG"]) for m, tag in enumerate(tags)),
            i_cfg_request_protocol=sum(1 << (m * 8) for m in range(a["NM"])),
        )
        accepted = []
        for _ in range(20 + a["NM"]):
            item = await self.cycle(
                "simultaneous_masters", i_cfg_request_valid=remaining
            )
            fired = remaining & item.pre["o_cfg_request_ready"]
            assert fired.bit_count() <= 1
            if fired:
                accepted.append(fired.bit_length() - 1)
            remaining &= ~fired
            if not remaining:
                break
        assert not remaining and sorted(accepted) == list(range(a["NM"]))
        self.ports["i_cfg_request_valid"] = 0
        for master in accepted:
            await self.wait(tags[master])
        self.coverage.hit("master_arbitration")

    async def body(self):
        if os.getenv("CONFIGURATION_NETWORK_FOCUSED_FLUSH") == "1":
            await self.canonical_flush_overlap()
            self.coverage.goals = {"canonical_flush_buffered_results": True}
            self.publish_contract()
            return
        a = self.a
        await self.reset()
        present = self.p["ENDPOINT_PRESENT_MASK"]
        selected = present if self.p["SUPPORT_MULTICAST"] else present & -present
        result = await self.request(0, 0)
        assert result[-1]["status"] == 0
        values, image = await self.load_context(selected)
        self.coverage.hit("cold_load")
        resident = (
            min(
                endpoint(self.p, e)["contexts"]
                for e in range(a["NE"])
                if selected >> e & 1
            )
            > 1
        )
        if resident:
            await self.load_context(selected, context=1, package=8, prepare=False)
        # Re-prepare after loading the other resident context: a native write
        # may disarm the endpoint, even when it addresses another context.
        await self.request(6, selected, expected_version=1, expected_crc=image)
        await self.commit(selected)
        if self.p["SUPPORT_READBACK"]:
            for e in range(a["NE"]):
                if selected >> e & 1:
                    for word, value in (
                        list(enumerate(values))
                        if e == (selected & -selected).bit_length() - 1
                        else [(e % len(values), values[e % len(values)])]
                    ):
                        records = await self.request(2, 1 << e, word_index=word)
                        assert records[0]["read_data"] == value
            self.coverage.hit("readback")
        records = await self.request(1, selected, write_data=0x55, expected_version=1)
        assert all(r["status"] != 0 for r in records)
        self.coverage.hit("active_immutable")
        if resident:
            image1 = self.server.endpoints[
                next(e for e in range(a["NE"]) if selected >> e & 1)
            ].crc(1)
            before = len(self.server.native_history)
            await self.request(
                6,
                selected,
                context_id=1,
                package_id=8,
                expected_version=1,
                expected_crc=image1,
            )
            await self.commit(selected, context=1, package=8, epoch=2 % (1 << a["EP"]))
            assert not any(
                r["command"] == 1 for _, _, r in self.server.native_history[before:]
            )
            self.coverage.hit("fast_switch")
        await self.negative_requests()
        await self.pressure_and_order()
        await self.multiple_masters()
        await self.drain_and_reset()
        await self.unknown_and_protection()
        await self.cancellation_records()
        await self.epoch_wrap()
        await self.canonical_flush_overlap()
        await self.recovery(selected)
        await self.reset()
        self.coverage.goals = {
            k: bool(self.coverage.bins[k])
            for k in (
                "cold_load",
                "coordinated_commit",
                "active_immutable",
                "request_rejection",
                "endpoint_descriptors",
                "queue_pressure",
                "ordered_completion",
                "random_commands",
                "transaction_timeout",
                "packet_frame",
                "packet_type",
                "partial_commit",
                "active_power_loss",
                "flush",
                "cancellation_records",
                "epoch_wrap",
                "canonical_flush_buffered_results",
                "drain",
                "unknown_controls",
                "reset_recovery",
                "control_protection",
                "master_arbitration",
            )
        }
        if self.p["ENABLE_PACKET_CRC"]:
            self.coverage.goals["packet_crc"] = bool(self.coverage.bins["packet_crc"])
        if self.p["SUPPORT_READBACK"]:
            self.coverage.goals["readback"] = bool(self.coverage.bins["readback"])
        if resident:
            self.coverage.goals["fast_switch"] = bool(self.coverage.bins["fast_switch"])
        self.publish_contract()

    def publish_contract(self):
        a = self.a
        self.c.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        self.c.coverage_file.with_name("contract.json").write_text(
            json.dumps(
                dict(
                    schema="mosaic-configuration-network-v1",
                    parameters=published_parameters(self.p),
                    topology=topology(self.p),
                    endpoints=[endpoint(self.p, e) for e in range(a["NE"])],
                    packet=dict(
                        command_fields=CMD,
                        response_fields=RSP,
                        command_body_bits=a["CB"],
                        response_body_bits=a["RB"],
                        command_packet_bits=a["CP"],
                        response_packet_bits=a["RP"],
                        command_flit_bits=a["FL"],
                        response_flit_bits=a["RL"],
                        flit_order="least-significant-first",
                        packet_type_bits=1,
                        crc_polynomial="0x82f63b78",
                        crc_initial_final="0xffffffff",
                    ),
                    commit=dict(
                        domain="root-clock",
                        delivery="simultaneous-single-edge",
                        release="all-acknowledgements-and-explicit-safe-release",
                        partial_failure="fail-stop-no-rollback",
                    ),
                    cancellation="native-drain-before-ack; ordered-new-epoch-results",
                    formal="NOT_RUN",
                    cdc="NOT_IMPLEMENTED",
                    physical_timing="NOT_CHARACTERIZED",
                    energy="NOT_CHARACTERIZED",
                ),
                indent=2,
            )
            + "\n"
        )
