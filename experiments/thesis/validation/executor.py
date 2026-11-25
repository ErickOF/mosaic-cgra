"""Execute real SRAM/MST/BCT/VCT kernels on exported experimental flat grids."""

import json
import importlib.util
import os
from pathlib import Path
import sys

import cocotb
from cocotb.utils import get_sim_time
from pyuvm import uvm_component

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
from cases import ROOT, digest
from schedule import schedule
sys.path[:0] = [str(ROOT / "src/val/mosaic_blocks"), str(ROOT / "src/val/lib")]
from validation.driver import ExperimentDriver
from bct.model import pack as bct_pack, sources as bct_sources
from vct.model import pack as vct_pack, sources as vct_sources, payload
from mst.model import pack as mst_pack, stream_beats
from tile_shell.model import crc32c


class ThesisExecutor(uvm_component):
    def build_phase(self):
        self.bundle = Path(os.environ["THESIS_BUNDLE"])
        self.output = Path(os.environ["THESIS_OUTPUT"])
        self.manifest = json.loads((self.bundle / "manifest.json").read_text())
        self.ports = json.loads((self.bundle / "ports.json").read_text())
        self.jobs = json.loads(Path(os.environ["THESIS_JOBS"]).read_text())
        self.driver = ExperimentDriver("driver", self)
        self.tiles = {t["id"]: t for t in self.manifest["tile_parameter_table"]}
        self.positions = {t["id"]: (t["row"], t["col"])
                          for t in self.manifest["descriptor"]["tiles"]}
        self.tag = 0
        self.command = 0
        self.current = None

    async def run_phase(self):
        self.raise_objection()
        reports = []
        for index, job in enumerate(self.jobs):
            self.current = dict(status="FAIL", job=job, phase="reset", windows={}, metrics={},
                                configuration_responses=[], descriptors=[])
            self.case_output = self.output / f"case_{index:02d}"
            self.case_output.mkdir(parents=True, exist_ok=True)
            try:
                await self.execute(job)
                self.current["status"] = "PASS"
            finally:
                self.current["phase"] = self.driver.phase
                (self.case_output / "functional.json").write_text(
                    json.dumps(self.current, indent=2) + "\n")
                (self.case_output / "trace.json").write_text(
                    json.dumps(self.driver.trace, indent=2) + "\n")
                reports.append(str(self.case_output / "functional.json"))
        Path(os.environ["THESIS_COVERAGE_FILE"]).write_text(json.dumps(dict(
            status="PASS", framework="PyUVM", reports=reports,
            goals=dict(real_sram=True, native_kernels=True, exact_output=True,
                       sentinels=True, stable_backpressure=True)), indent=2) + "\n")
        self.drop_objection()

    async def reset(self):
        d = self.driver
        d.trace, d.pending_outputs, d.peer_history = [], {}, {}
        d.phase = "reset"
        d.cycles = 0
        self.time_origin_ns = float(get_sim_time(unit="ns"))
        self.packet_index = 0
        d.tiles = list(self.tiles.values())
        d.sample_ports = [n for n, (direction, _) in self.ports.items()
            if direction == "output" and (n == "o_memory_bank_conflict" or
                n.startswith("o_thesis_") or n.endswith((
                "status_error", "status_fatal_error", "status_error_code", "status_power_state",
                "body_power_enable", "body_isolate")))]
        for name, (direction, _) in self.ports.items():
            if direction == "input":
                getattr(cocotb.top, name).value = 0
        values = dict(i_enable=1)
        for name, (direction, width) in self.ports.items():
            if direction == "input" and name.endswith(("response_ready", "rsp_ready",
                    "completion_ready", "rejection_ready", "event_out_ready", "event_ready",
                    "predicate_out_ready",
                    "memory_bank_power_ack")):
                values[name] = (1 << width) - 1
        for _ in range(5):
            await d.cycle(values | dict(i_rstb=0))
        for _ in range(40):
            await d.cycle(dict(i_rstb=1))

    async def idle(self, count=1, **values):
        for _ in range(count):
            await self.driver.cycle(values)

    async def wait(self, condition, label, limit=2000):
        for _ in range(limit):
            if condition():
                return
            await self.driver.cycle()
        raise AssertionError(f"{label} timed out in {self.driver.phase}; "
                             f"pending={self.driver.pending_outputs}; cycle={self.driver.cycles}")

    async def request(self, ident, channel, command, *, context=0, **fields):
        self.tag = (self.tag + 1) % 256
        prefix = f"tile_{ident}"
        values = dict(command=command, context_id=context, owner_id=5, tag=self.tag)
        values.update(dict(tile_id=ident) if channel == "cfg" else dict(kernel_id=3))
        values.update(fields)
        values = {f"i_{prefix}_{channel}_request_{k}": v for k, v in values.items()}
        ready = f"o_{prefix}_{channel}_request_ready"
        valid = f"i_{prefix}_{channel}_request_valid"
        response = f"o_{prefix}_{channel}_response_"
        for _ in range(500):
            observed = await self.driver.cycle(values | {valid: 1}, [ready])
            if observed[ready]:
                break
        else:
            raise AssertionError((ident, channel, command, "request timeout"))
        names = [response + n for n in ("valid", "error", "error_code", "tag")]
        if channel == "cfg":
            names.append(response + "context_version")
        for _ in range(500):
            observed = await self.driver.cycle({valid: 0}, names)
            if observed[names[0]]:
                record = dict(tile=ident, channel=channel, command=command,
                              cycle=self.driver.cycles,
                              response={n: observed[n] for n in names})
                self.current["configuration_responses"].append(record)
                assert observed[response + "tag"] == self.tag
                assert not observed[response + "error"], record
                return observed.get(response + "context_version")
        raise AssertionError((ident, channel, command, "response timeout"))

    async def program(self, ident, context, image):
        p = self.tiles[ident]["parameters"]
        for word in range(p["CONFIG_WORD_COUNT"]):
            await self.request(ident, "cfg", 0, context=context, word_index=word,
                write_data=image >> (64 * word) & ((1 << 64) - 1), write_strobe=255)
        crc = crc32c(image.to_bytes(8 * p["CONFIG_WORD_COUNT"], "little"))
        return await self.request(ident, "cfg", 2, context=context, expected_crc=crc)

    async def host(self, address, *, value=None):
        fields = dict(i_memory_host_req_opcode=int(value is not None),
            i_memory_host_req_addr=address, i_memory_host_req_size=8,
            i_memory_host_req_wdata=value or 0, i_memory_host_req_wstrb=255,
            i_memory_host_req_owner_id=5, i_memory_host_req_kernel_id=3,
            i_memory_host_req_generation=1, i_memory_host_req_tag=13)
        for _ in range(300):
            observed = await self.driver.cycle(fields | dict(i_memory_host_req_valid=1),
                                               ["o_memory_host_req_ready"])
            if observed["o_memory_host_req_ready"]:
                break
        else:
            raise AssertionError("Host SRAM request timed out")
        names = ["o_memory_host_rsp_" + n for n in ("valid", "error", "rdata", "tag")]
        for _ in range(300):
            observed = await self.driver.cycle(dict(i_memory_host_req_valid=0), names)
            if observed[names[0]]:
                assert not observed[names[1]] and observed[names[3]] == 13, observed
                return observed[names[2]]
        raise AssertionError("Host SRAM response timed out")

    async def provision_memory(self, contents):
        d = self.manifest["descriptor"]
        clients = len(self.manifest["scratchpad_clients"])
        values = dict(i_memory_region_cmd_valid=1, i_memory_region_cmd_opcode=1,
            i_memory_region_owner_id=5, i_memory_region_kernel_id=3,
            i_memory_region_base=0, i_memory_region_limit=len(contents), i_memory_region_state=5,
            i_memory_region_contents_valid=1, i_memory_region_read_mask=(1 << clients) - 1,
            i_memory_region_write_mask=(1 << clients) - 1)
        for _ in range(100):
            observed = await self.driver.cycle(values, ["o_memory_region_cmd_ready"])
            if observed["o_memory_region_cmd_ready"]:
                break
        else:
            raise AssertionError("Region request timed out")
        for _ in range(100):
            observed = await self.driver.cycle(dict(i_memory_region_cmd_valid=0),
                ["o_memory_region_rsp_valid", "o_memory_region_rsp_error"])
            if observed["o_memory_region_rsp_valid"]:
                assert not observed["o_memory_region_rsp_error"]
                break
        else:
            raise AssertionError("Region response timed out")
        for address in range(0, len(contents), 8):
            await self.host(address, value=int.from_bytes(contents[address:address + 8], "little"))

    async def management(self, ident):
        p = self.tiles[ident]["parameters"]
        record = mst_pack(p, "region", dict(valid=1, generation=1, space=0, base=0,
            limit=self.capacity, owner=5, kernel=3, allocation=1, read_enable=1,
            write_enable=1, dma_enable=1, channel_mask=255, buffer_mask=3))
        prefix = f"tile_{ident}"
        for _ in range(100):
            observed = await self.driver.cycle({f"i_{prefix}_region_valid": 1,
                f"i_{prefix}_region_index": 0, f"i_{prefix}_region_record": record},
                [f"o_{prefix}_region_ready"])
            if observed[f"o_{prefix}_region_ready"]:
                break
        else:
            raise AssertionError("MST region request timed out")
        observed = await self.driver.cycle({f"i_{prefix}_region_valid": 0},
            [f"o_{prefix}_region_response_valid", f"o_{prefix}_region_response_error"])
        assert observed[f"o_{prefix}_region_response_valid"]
        assert not observed[f"o_{prefix}_region_response_error"]

    def path(self, source, destination, mode="short"):
        start, finish = self.positions[source], self.positions[destination]
        rows, cols = self.manifest["descriptor"]["rows"], self.manifest["descriptor"]["cols"]
        # Enumerate simple paths deterministically; detours add two hops when available.
        distance = abs(start[0] - finish[0]) + abs(start[1] - finish[1])
        target = distance + (2 if mode == "detour" else 0)
        def visit(path):
            r, c = path[-1]
            if (r, c) == finish:
                return path if len(path) - 1 == target else None
            if len(path) - 1 >= target:
                return None
            for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                nxt = r + dr, c + dc
                remaining = abs(nxt[0] - finish[0]) + abs(nxt[1] - finish[1])
                if (0 <= nxt[0] < rows and 0 <= nxt[1] < cols and nxt not in path
                        and len(path) + remaining <= target):
                    found = visit(path + [nxt])
                    if found:
                        return found
            return None
        found = visit([start])
        if found is None:
            raise AssertionError(("No legal route", source, destination, mode))
        by_position = {pos: ident for ident, pos in self.positions.items()}
        return [by_position[pos] for pos in found]

    async def route(self, source, destination, port=0):
        path = self.path(source, destination, self.job.get("route", "short"))
        directions = {(-1, 0): 2, (0, 1): 3, (1, 0): 4, (0, -1): 5}
        selections = {}
        for index, ident in enumerate(path):
            pos = self.positions[ident]
            incoming = 0 if index == 0 else directions[tuple(
                a - b for a, b in zip(self.positions[path[index - 1]], pos))]
            outgoing = port if index == len(path) - 1 else directions[tuple(
                a - b for a, b in zip(self.positions[path[index + 1]], pos))]
            selections[ident] = outgoing, incoming
        for ident in self.tiles:
            outgoing, incoming = selections.get(ident, (0, 0))
            values = {f"i_route_{ident}_config_valid": 1,
                f"i_route_{ident}_config_output_enable": (1 << outgoing) if ident in selections else 0,
                f"i_route_{ident}_config_output_select": incoming << (3 * outgoing)}
            for _ in range(100):
                observed = await self.driver.cycle(values, [f"o_route_{ident}_config_ready"])
                if observed[f"o_route_{ident}_config_ready"]:
                    break
            else:
                raise AssertionError(("Route config timeout", ident, path))
            await self.driver.cycle({f"i_route_{ident}_config_valid": 0})
        self.driver.trace.append(dict(kind="route", phase=self.driver.phase,
            cycle=self.driver.cycles, source=source, destination=destination, port=port,
            tiles=path, hops=len(path) - 1, selections=selections))

    async def adapt(self, ident, port, metadata):
        await self.driver.cycle({f"i_thesis_{ident}_adapt_{port}": 1,
                                 f"i_thesis_{ident}_metadata_{port}": metadata})

    def descriptor(self, ident, *, store=False, copy=False, address=0, destination=0,
                   element_log2=2, lanes_log2=0, output_log2=None, count=1, stride=0,
                   destination_stride=0):
        self.command += 1
        p = self.tiles[ident]["parameters"]
        return dict(identity=dict(command=self.command, generation=1, owner=5, kernel=3,
            package_id=11, context_id=0, version=self.versions[ident, 0], allocation=1,
            epoch=int(getattr(cocotb.top, f"o_tile_{ident}_execution_epoch").value)),
            mode=dict(transfer=2 if copy else int(store), address_mode=int(bool(stride)),
                      load_channel=0, store_channel=0),
            source=dict(space=2 if store else 0, channel=0, base=address,
                        region_id=0, region_generation=1, inner_stride=stride),
            destination=dict(space=0 if store or copy else 2, channel=0, base=destination,
                        region_id=0, region_generation=1, inner_stride=destination_stride),
            format=dict(source_log2=element_log2,
                        destination_log2=element_log2 if output_log2 is None else output_log2,
                        lane_log2=lanes_log2, signed_mode=1, eos=1), events={},
            control=dict(inner_count=count, outer_count=1, cancelable=1))

    async def submit(self, ident, descriptor):
        self.current["descriptors"].append(dict(tile=ident, cycle=self.driver.cycles,
                                                 descriptor=descriptor))
        p = self.tiles[ident]["parameters"]
        fields = {f"i_tile_{ident}_descriptor_{name}": mst_pack(p,
            "endpoint" if name in ("source", "destination") else name, value)
            for name, value in descriptor.items()}
        for _ in range(300):
            observed = await self.driver.cycle(fields | {f"i_tile_{ident}_descriptor_valid": 1},
                                               [f"o_tile_{ident}_descriptor_ready"])
            if observed[f"o_tile_{ident}_descriptor_ready"]:
                break
        else:
            raise AssertionError("MST descriptor request timed out")
        await self.driver.cycle({f"i_tile_{ident}_descriptor_valid": 0})

    async def completion(self, ident, descriptor):
        names = [f"o_tile_{ident}_completion_{n}" for n in (
            "valid", "identity", "status", "error_code", "bytes_written", "bytes_read", "elements")]
        identity = mst_pack(self.tiles[ident]["parameters"], "identity", descriptor["identity"])
        # Ready is deliberately low until the corresponding completion is inspected.
        for _ in range(2000):
            observed = await self.driver.cycle(sample=names + [f"o_tile_{ident}_rejection_valid"])
            assert not observed[f"o_tile_{ident}_rejection_valid"], descriptor
            if observed[names[0]]:
                assert observed[names[1]] == identity, (observed, descriptor)
                assert not observed[names[2]] and not observed[names[3]], (observed, descriptor)
                expected = descriptor["control"]["inner_count"] * (
                    1 << (descriptor["format"]["destination_log2"] +
                          descriptor["format"]["lane_log2"]))
                assert observed[names[4]] == expected, (observed, descriptor)
                self.driver.trace.append(dict(kind="completion", phase=self.driver.phase,
                    cycle=self.driver.cycles, tile=ident,
                    values={n: observed[n] for n in names}))
                await self.idle(1, **{f"i_tile_{ident}_completion_ready": 1})
                await self.idle(1, **{f"i_tile_{ident}_completion_ready": 0})
                return
        raise AssertionError(("MST completion timeout", ident, descriptor))

    def transfers(self, ident, group, port=0):
        return sum(e["kind"] == "transfer" and e["tile"] == ident and
                   e["direction"] == group and e["port"] == port for e in self.driver.trace)

    async def transfer_to(self, source, dest, descriptor, *, port=0, metadata=0):
        before = self.transfers(dest, "input", port)
        await self.adapt(dest, port, metadata)
        await self.route(source, dest, port)
        await self.idle(1, **{f"i_thesis_tile_{source}_stall": 0})
        if descriptor is not None:
            await self.submit(source, descriptor)
            await self.completion(source, descriptor)
        await self.wait(lambda: self.transfers(dest, "input", port) == before + 1,
                        "Receiver packet")
        await self.idle(3)

    async def power(self, ident, state, *, error=False):
        prefix = f"tile_{ident}"
        for _ in range(300):
            observed = await self.driver.cycle({f"i_{prefix}_power_request_valid": 1,
                f"i_{prefix}_power_request_state": state}, [f"o_{prefix}_power_request_ready"])
            if observed[f"o_{prefix}_power_request_ready"]:
                break
        else:
            raise AssertionError(("Power request timeout", ident, state))
        for _ in range(500):
            names = [f"o_{prefix}_power_response_{n}" for n in ("valid", "error", "error_code")]
            observed = await self.driver.cycle({f"i_{prefix}_power_request_valid": 0}, names)
            if observed[names[0]]:
                assert bool(observed[names[1]]) == error, (ident, state, observed)
                await self.idle(5)
                return
        raise AssertionError(("Power response timeout", ident, state))

    async def off(self):
        self.driver.phase = "power_off"
        for ident in self.compute:
            await self.power(ident, 4)
        for ident in self.compute:
            assert int(getattr(cocotb.top, f"o_tile_{ident}_body_power_enable").value) == 0
            assert int(getattr(cocotb.top, f"o_tile_{ident}_body_isolate").value) == 1
            assert int(getattr(cocotb.top, f"o_tile_{ident}_status_power_state").value) == 4
        self.off_start = self.driver.cycles

    async def configure(self, case, *, reload=False):
        self.driver.phase = "configuration"
        start = self.driver.cycles
        if not reload:
            self.versions = {}
        monitor = int(self.job.get("monitor", True))
        for ident in (self.bct, *self.msts, *([self.vct] if self.vct is not None else [])):
            if reload and ident in self.msts:
                continue
            if not reload:
                await self.request(ident, "runtime", 0)
            else:
                # Completed contexts are still selected/protected. Keep slot 1
                # selected while rewriting slot 0, then switch to the freshly
                # validated slot 0 before rewriting the remaining slots.
                await self.request(ident, "cfg", 3, context=1)
            p = self.tiles[ident]["parameters"]
            if ident in self.msts:
                await self.management(ident)
                image = mst_pack(p, "context", dict(schema=1, package_id=11, allocation=1,
                    loads=1, stores=1, regions=1, terminal=0))
                self.versions[ident, 0] = await self.program(ident, 0, image)
            elif ident == self.bct:
                sources = bct_sources(p)
                ctx = dict(schema=1, source_a=0, source_b=sources["immediate"], source_c=1,
                    immediates=case["coefficient"] & ((1 << p["DATA_WIDTH"]) - 1),
                    fu=0 if self.vct is not None else 2,
                    opcode=16 if self.vct is not None else 0, signed_a=1, signed_b=1,
                    output_mask=1, iterations=1, terminal=1, monitor=monitor)
                for cid in (0, 1):
                    self.versions[ident, cid] = await self.program(ident, cid, bct_pack(p, ctx))
                    if reload and cid == 0:
                        await self.request(ident, "cfg", 3, context=0)
            else:
                sources = vct_sources(p)
                for cid, mask in ((0, (1 << p["NUM_LANES"]) - 1), (1, 1),
                                  (2, (1 << p["NUM_LANES"]) - 1)):
                    ctx = dict(schema=1, fu=0, opcode=21, signed_mode=1,
                        format_a=0, format_b=0, format_c=2, result_format=2,
                        source_a=0, source_b=sources["immediate"], source_c=1,
                        immediate=payload([case["coefficient"]] * p["NUM_LANES"],
                                          p["ELEMENT_WIDTH"]),
                        lane_mask=mask, runtime_tail=mask, tail_mask=1,
                        output_mask=1, iterations=1, terminal=1, monitor=monitor)
                    self.versions[ident, cid] = await self.program(ident, cid, vct_pack(p, ctx))
                    if reload and cid == 0:
                        await self.request(ident, "cfg", 3, context=0)
            await self.request(ident, "cfg", 3)
            if ident in self.msts:
                await self.request(ident, "runtime", 1)
                await self.idle(1, **{f"i_tile_{ident}_completion_ready": 0})
        window = self.window(start, self.driver.cycles)
        if not reload:
            self.current["windows"]["configuration"] = window
        self.current["windows"].setdefault("configuration_segments", []).append(window)

    async def execute(self, job):
        self.job = job
        self.driver.backpressure = job["backpressure"]
        case = job["case"]
        await self.reset()
        self.compute = [i for i, t in self.tiles.items() if t["module"] in ("bct", "vct")]
        self.msts = [i for i, t in self.tiles.items() if t["module"] == "mst"]
        self.bct = next(i for i, t in self.tiles.items() if t["module"] == "bct")
        self.vct = next((i for i, t in self.tiles.items() if t["module"] == "vct"), None)
        lanes = self.tiles[self.vct]["parameters"]["NUM_LANES"] if self.vct is not None else 1
        self.current["schedule"] = schedule(case, job["policy"], dict(
            bct=self.bct, vct=self.vct, msts=self.msts, lanes=lanes))
        self.capacity = self.manifest["geometry"]["capacity"]
        initial = bytearray([case["memory"]["sentinel"]] * self.capacity)
        m = case["memory"]
        if case["workload"] == "copy":
            for index, value in enumerate(case["x"]):
                start = m["x_base"] + index * m["source_stride"]
                initial[start:start + 4] = (value & 0xFFFFFFFF).to_bytes(4, "little")
        else:
            for index, value in enumerate(case["x"]):
                initial[m["x_base"] + index] = value & 255
            for index, value in enumerate(case["y"]):
                start = m["y_base"] + 4 * index
                initial[start:start + 4] = (value & 0xFFFFFFFF).to_bytes(4, "little")
            # Padding is input-only; guards surrounding output must stay untouched.
            for index in range(case["count"], ((case["count"] + lanes - 1) // lanes) * lanes):
                initial[m["x_base"] + index] = 0
                start = m["y_base"] + 4 * index
                initial[start:start + 4] = bytes(4)
        await self.provision_memory(initial)
        # Consume the scheduler's decisions; policy names alone never substitute
        # for an executed sequence in the evidence.
        for action in self.current["schedule"]["actions"]:
            command = action["action"]
            if command.startswith("execute_") or command == "verify_committed_output":
                break
            self.driver.trace.append(dict(kind="schedule", action=command,
                cycle=self.driver.cycles, phase=self.driver.phase, domain=action["domain"]))
            if command == "configure":
                await self.configure(case)
            elif command == "close_admission":
                assert not self.driver.pending_outputs
            elif command == "drain":
                await self.idle(4)
                assert not self.driver.pending_outputs
            elif command == "power_off":
                await self.off()
            elif command == "idle":
                self.driver.phase = "scheduled_idle"
                await self.idle(action["cycles"])
            elif command == "wake":
                self.driver.phase = "wake"
                self.wake_start = self.driver.cycles
                for ident in self.compute:
                    await self.power(ident, 0)
            elif command != "restart_external_operand_contexts":
                raise AssertionError(f"Unknown schedule action: {command}")
        repetitions = job.get("repetitions", 1)
        segments = []
        for repetition in range(repetitions):
            if repetition and job.get("residency") == "reload":
                await self.configure(case, reload=True)
            self.driver.phase = "kernel"
            self.driver.trace.append(dict(kind="schedule", action="execute_" + case["workload"],
                cycle=self.driver.cycles, phase=self.driver.phase, repetition=repetition))
            start = self.wake_start if (not repetition and job["policy"] == "phase_aware"
                and case["workload"] == "axpy") else self.driver.cycles
            if case["workload"] == "copy":
                desc = self.descriptor(self.msts[0], copy=True, address=m["x_base"],
                    destination=m["output_base"], count=case["count"], stride=m["source_stride"],
                    destination_stride=m["destination_stride"])
                await self.submit(self.msts[0], desc)
                await self.completion(self.msts[0], desc)
            else:
                for offset in range(0, case["count"], lanes):
                    active = min(lanes, case["count"] - offset)
                    await self.axpy_group(case, offset, active)
                if job["policy"] == "phase_aware":
                    assert self.current.get("pending_off_rejected")
                    self.driver.phase = "drain"
                    drain_start = self.driver.cycles
                    assert not self.driver.pending_outputs
                    await self.off()
                    self.current["metrics"]["drain_cycles"] = self.driver.cycles - drain_start
            end = self.driver.cycles
            segments.append(self.window(start, end))
            await self.readback(case, initial)
        self.current["windows"].update(kernel_segments=segments,
            kernel=segments[0] if len(segments) == 1 else None)
        transfers = [e for e in self.driver.trace if e["kind"] == "transfer"]
        if case["workload"] == "axpy":
            for ident in (self.bct, *([self.vct] if self.vct is not None else [])):
                assert any(e["tile"] == ident and e["direction"] == "output" for e in transfers)
        cycles = sum(w["end_cycle"] - w["start_cycle"] for w in segments)
        configuration_cycles = sum(w["end_cycle"] - w["start_cycle"] for w in
                                    self.current["windows"]["configuration_segments"])
        self.current["metrics"].update(kernel_cycles=cycles, kernel_time_s=cycles * 1e-8,
            verified_outputs=len(case["expected"]) * repetitions,
            committed_bytes=4 * len(case["expected"]) * repetitions, transfers=len(transfers),
            repetitions=repetitions, reuses=repetitions - len(
                self.current["windows"]["configuration_segments"]),
            configuration_cycles=configuration_cycles,
            amortized_configuration_cycles=configuration_cycles / repetitions,
            active_lanes=case["count"] * repetitions if case["workload"] == "axpy" else None,
            masked_lanes=(-case["count"]) % lanes * repetitions if case["workload"] == "axpy" else None)
        if "monitor" in job:
            counters = {}
            for ident in (self.bct, *([self.vct] if self.vct is not None else [])):
                measured = await self.debug(ident, 0x81)
                observed = self.transfers(ident, "output")
                assert measured == (observed if job["monitor"] else 0), (ident, measured, observed)
                counters[str(ident)] = dict(counter_retirements=measured,
                                           observed_body_retirements=observed)
            self.current["metrics"]["body_counters"] = counters
        memory = [e for e in self.driver.trace if e["kind"] == "memory" and e["phase"] == "kernel"]
        banks = {str(i): sum(e["bank"] == i for e in memory) for i in range(8)}
        self.current["metrics"]["bank_accesses"] = banks
        self.current["metrics"]["memory_wait_cycles"] = sum(
            e["kind"] == "memory_wait" and e["phase"] == "kernel" for e in self.driver.trace)
        self.current["metrics"]["bank_conflict_cycles"] = sum(
            e["kind"] == "bank_conflict" and e["phase"] == "kernel" for e in self.driver.trace)
        self.current["metrics"]["route_hops"] = sum(e["hops"] for e in self.driver.trace
                                                    if e["kind"] == "route")
        if job["policy"] == "phase_aware":
            if case["workload"] == "copy":
                assert all(int(getattr(cocotb.top, f"o_tile_{i}_body_power_enable").value) == 0
                           for i in self.compute)
                self.current["metrics"]["off_cycles"] = end - self.off_start
            else:
                first = next(e["cycle"] for e in transfers if e["tile"] in self.compute
                             and e["direction"] == "input" and e["cycle"] >= self.wake_start)
                self.current["metrics"]["wake_cycles"] = first - self.wake_start

    def window(self, start, end):
        return dict(start_cycle=start, end_cycle=end, clock_period_ns=10,
                    start_time_ns=self.time_origin_ns + 10 * start,
                    end_time_ns=self.time_origin_ns + 10 * end)

    async def debug(self, ident, address):
        prefix = f"tile_{ident}"
        for _ in range(100):
            observed = await self.driver.cycle({f"i_{prefix}_debug_request_valid": 1,
                f"i_{prefix}_debug_request_owner_id": 5,
                f"i_{prefix}_debug_request_address": address,
                f"i_{prefix}_debug_response_ready": 0}, [f"o_{prefix}_debug_request_ready"])
            if observed[f"o_{prefix}_debug_request_ready"]:
                break
        else:
            raise AssertionError("Counter read request timed out")
        names = [f"o_{prefix}_debug_response_{n}" for n in ("valid", "error", "read_data")]
        for _ in range(100):
            observed = await self.driver.cycle({f"i_{prefix}_debug_request_valid": 0}, names)
            if observed[names[0]]:
                assert not observed[names[1]]
                await self.idle(1, **{f"i_{prefix}_debug_response_ready": 1})
                return observed[names[2]]
        raise AssertionError("Counter read response timed out")

    async def readback(self, case, initial):
        m = case["memory"]
        self.driver.phase = "readback"
        self.driver.trace.append(dict(kind="schedule", action="verify_committed_output",
            cycle=self.driver.cycles, phase=self.driver.phase))
        actual = bytearray()
        for address in range(0, self.capacity, 8):
            actual.extend((await self.host(address)).to_bytes(8, "little"))
        expected_memory = bytearray(initial)
        observed = []
        for index, value in enumerate(case["expected"]):
            address = m["output_base"] + index * (m["destination_stride"]
                                                   if case["workload"] == "copy" else 4)
            expected_memory[address:address + 4] = value.to_bytes(4, "little")
            observed.append(int.from_bytes(actual[address:address + 4], "little"))
        self.current.update(expected=case["expected"], observed=observed,
            memory_sha256=dict(expected=digest(list(expected_memory)), actual=digest(list(actual))))
        assert actual == expected_memory, ("SRAM result/guard mismatch",
            next((i, a, b) for i, (a, b) in enumerate(zip(actual, expected_memory)) if a != b))
        assert not self.driver.pending_outputs, self.driver.pending_outputs
        self.current.setdefault("verified_repetitions", []).append(observed)

    async def axpy_group(self, case, offset, active):
        bct, vct = self.bct, self.vct
        group = self.packet_index
        bcid = group % 2
        cid = (1 if active == 1 else (0, 2)[group % 2]) if vct is not None else 0
        for ident in (bct, *([vct] if vct is not None else [])):
            await self.idle(1, **{f"i_thesis_tile_{ident}_stall": 1})
            await self.request(ident, "cfg", 3, context=cid if ident == vct else bcid)
            await self.request(ident, "runtime", 1, context=cid if ident == vct else bcid)
        m = case["memory"]
        lane_log2 = (active - 1).bit_length()
        store = self.descriptor(self.msts[0], store=True,
            destination=m["output_base"] + 4 * offset,
            element_log2=2 if vct is not None else 4,
            output_log2=2, lanes_log2=lane_log2)
        await self.submit(self.msts[0], store)
        bp = self.tiles[bct]["parameters"]
        bmeta = (self.versions[bct, bcid] << 2) | bcid
        xp = self.descriptor(self.msts[0], address=m["x_base"] + offset,
            element_log2=0, output_log2=0 if vct is not None else 4, lanes_log2=lane_log2)
        await self.transfer_to(self.msts[0], bct, xp, metadata=bmeta)
        if (self.job["policy"] == "phase_aware" and offset == 0):
            # An active tile with accepted work must refuse OFF, preserving the packet.
            await self.power(bct, 4, error=True)
            self.current["pending_off_rejected"] = True
        if vct is not None:
            p = self.tiles[vct]["parameters"]
            full = (1 << p["NUM_LANES"]) - 1
            mask = (1 << active) - 1
            base = 2 + p["CONTEXT_VERSION_WIDTH"]
            meta = (self.versions[vct, cid] << 2) | cid | (full << (base + 3))
            meta |= 1 << (base + 3 + p["NUM_LANES"])
            meta |= mask << (base + 4 + p["NUM_LANES"])
            await self.transfer_to(bct, vct, None, metadata=meta)
            ymeta = meta | (2 << base)
            yload = self.descriptor(self.msts[1], address=m["y_base"] + 4 * offset,
                                   element_log2=2, lanes_log2=lane_log2)
            await self.transfer_to(self.msts[1], vct, yload, port=1, metadata=ymeta)
            producer = vct
        else:
            yload = self.descriptor(self.msts[1], address=m["y_base"] + 4 * offset,
                                   element_log2=2, output_log2=4)
            await self.transfer_to(self.msts[1], bct, yload, port=1, metadata=bmeta)
            producer = bct
        metadata = stream_beats(self.tiles[self.msts[0]]["parameters"], store, [0], source=True)[0][1]
        await self.adapt(self.msts[0], 0, metadata)
        await self.route(producer, self.msts[0])
        if self.job["backpressure"]:
            await self.wait(lambda: bool(self.driver.last.get(
                f"o_thesis_tile_{producer}_data_out_valid")), "Pending compute result")
            await self.idle(11)
        await self.idle(1, **{f"i_thesis_tile_{producer}_stall": 0})
        await self.completion(self.msts[0], store)
        await self.idle(8)
        self.packet_index += 1
