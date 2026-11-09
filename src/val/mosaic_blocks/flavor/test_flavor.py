"""PyUVM checks for every native shell and the actual generated grid wiring."""

import json
import os
from pathlib import Path
import random

import cocotb
from pyuvm import test, uvm_component, uvm_test
from flavor.driver import FabricDriver


class FabricScoreboard(uvm_component):
    def build_phase(self):
        self.transfers = 0

    def transferred(self, actual, expected):
        assert actual == expected, ("Grid token mismatch", actual, expected)
        self.transfers += 1


class FabricCoverage(uvm_component):
    def build_phase(self):
        self.goals = {}

    def hit(self, name):
        self.goals[name] = True


@test(timeout_time=100, timeout_unit="ms")
class FabricTest(uvm_test):
    def build_phase(self):
        self.bundle = Path(os.environ["FLAVOR_ARTIFACTS"])
        self.manifest = json.loads((self.bundle / "manifest.json").read_text())
        self.interface = json.loads((self.bundle / "ports.json").read_text())
        self.driver = FabricDriver("driver", self)
        self.scoreboard = FabricScoreboard("scoreboard", self)
        self.coverage = FabricCoverage("coverage", self)
        self.seed = int(os.environ["FLAVOR_SEED"])
        self.random_cycles = int(os.environ["FLAVOR_RANDOM_CYCLES"])
        self.rng = random.Random(self.seed)

    async def run_phase(self):
        self.raise_objection()
        for name, (direction, width) in self.interface.items():
            signal = getattr(cocotb.top, name)
            assert len(signal) == width, (name, width, len(signal))
            if direction == "input":
                signal.value = 0
        initialize = {"i_enable": 1}
        for tile in self.manifest["descriptor"]["tiles"]:
            prefix = f"tile_{tile['id']}"
            self.driver.physical_peers += [
                (f"o_{prefix}_body_power_enable", f"i_{prefix}_body_power_good"),
                (f"o_{prefix}_body_isolate", f"i_{prefix}_body_isolation_ack")]
        for name, (direction, width) in self.interface.items():
            if direction == "input" and (name.endswith(("response_ready", "event_out_ready",
                    "predicate_out_ready", "body_power_good", "body_save_done", "body_restore_done"))
                    or name == "i_memory_bank_power_ack"):
                initialize[name] = (1 << width) - 1
        for _ in range(5):
            await self.driver.cycle(initialize | {"i_rstb": 0})
        for _ in range(32):
            await self.driver.cycle({"i_rstb": 1})
        classes = dict(BCT=0, VCT=1, SFT=2, MST=3, CPT=4)
        for tile in self.manifest["descriptor"]["tiles"]:
            prefix = f"tile_{tile['id']}"
            actual = await self.driver.cycle(sample=[f"o_{prefix}_status_tile_id",
                f"o_{prefix}_status_tile_class", f"o_{prefix}_status_fatal_error"])
            assert actual[f"o_{prefix}_status_tile_id"] == tile["id"]
            assert actual[f"o_{prefix}_status_tile_class"] == classes[tile["class"]]
            assert actual[f"o_{prefix}_status_fatal_error"] == 0
            await self.driver.request(prefix, "runtime", {
                f"i_{prefix}_runtime_request_command": 0,
                f"i_{prefix}_runtime_request_owner_id": 5,
                f"i_{prefix}_runtime_request_kernel_id": 3,
                f"i_{prefix}_runtime_request_tag": 7,
            }, dict(command=0, tag=7, error=0))
            await self.driver.request(prefix, "cfg", {
                f"i_{prefix}_cfg_request_command": 5,
                f"i_{prefix}_cfg_request_tile_id": tile["id"],
                f"i_{prefix}_cfg_request_owner_id": 5,
                f"i_{prefix}_cfg_request_context_id": 0,
                f"i_{prefix}_cfg_request_tag": 9,
            }, dict(command=5, tag=9, error=0, context_version=0))
            self.coverage.hit(f"native_shell_{tile['id']}_{tile['class']}")
        await self.transport()
        await self.memory()
        await self.narrowing()
        report = dict(status="PASS", parameters=self.manifest["descriptor"], seed=self.seed,
            random_cycles=self.random_cycles, manifest_sha256=self.manifest["manifest_sha256"],
            cycles=self.driver.cycles, transfers=self.scoreboard.transfers,
            goals=self.coverage.goals, framework="PyUVM")
        Path(os.environ["FLAVOR_COVERAGE_FILE"]).write_text(json.dumps(report, indent=2) + "\n")
        self.drop_objection()

    async def transport(self):
        d = self.manifest["descriptor"]
        by_position = {(tile["row"], tile["col"]): tile for tile in d["tiles"]}
        width = self.manifest["geometry"]["data_width"]
        metadata = self.manifest["geometry"]["metadata_width"]
        paths = [("row", row, 0, row, d["cols"] - 1, "west", "east", 5, 3)
                 for row in range(d["rows"])]
        paths += [("column", 0, col, d["rows"] - 1, col, "north", "south", 2, 4)
                  for col in range(d["cols"])]
        for axis, r0, c0, r1, c1, ingress, egress, incoming, outgoing in paths:
            coordinates = [(r0, col) for col in range(d["cols"])] if axis == "row" else [
                (row, c0) for row in range(d["rows"])]
            # Local switches retain configuration only after public acceptance.
            for position in coordinates:
                tile = by_position[position]
                prefix = f"route_{tile['id']}"
                valid = f"i_{prefix}_config_valid"
                ready = f"o_{prefix}_config_ready"
                for _ in range(100):
                    observed = await self.driver.cycle({valid: 1,
                        f"i_{prefix}_config_output_enable": 1 << outgoing,
                        f"i_{prefix}_config_output_select": incoming << (3 * outgoing)}, [ready])
                    if observed[ready]:
                        break
                else:
                    raise AssertionError(f"Route configuration timed out: {position}")
                await self.driver.cycle({valid: 0})
            source = f"boundary_{r0}_{c0}_{ingress}"
            sink = f"boundary_{r1}_{c1}_{egress}"
            count = max(8, self.random_cycles // len(paths))
            offered, received = 0, 0
            pending = []
            held = None
            for cycle in range(count * 10 + len(coordinates) * 5):
                if offered < count and held is None:
                    held = (self.rng.getrandbits(width), self.rng.getrandbits(metadata))
                values = {f"i_{source}_rx_valid": int(held is not None),
                          f"i_{sink}_tx_ready": int(self.rng.randrange(4) != 0)}
                if held is not None:
                    values.update({f"i_{source}_rx_data": held[0],
                                   f"i_{source}_rx_metadata": held[1]})
                names = [f"o_{source}_rx_ready", f"o_{sink}_tx_valid",
                         f"o_{sink}_tx_data", f"o_{sink}_tx_metadata"]
                observed = await self.driver.cycle(values, names)
                if held is not None and observed[names[0]]:
                    pending.append(held)
                    offered += 1
                    held = None
                if observed[names[1]] and values[f"i_{sink}_tx_ready"]:
                    assert pending, "Unexpected output token"
                    self.scoreboard.transferred((observed[names[2]], observed[names[3]]),
                                                pending.pop(0))
                    received += 1
                if received == count:
                    break
            assert offered == received == count and not pending, (axis, offered, received, count)
            await self.driver.cycle({f"i_{source}_rx_valid": 0, f"i_{sink}_tx_ready": 0})
            self.coverage.hit(f"{axis}_{r0 if axis == 'row' else c0}_wide_transport_backpressure")

    async def memory(self):
        d = self.manifest["descriptor"]
        clients = len(self.manifest["scratchpad_clients"])
        values = dict(i_memory_region_cmd_valid=1, i_memory_region_cmd_opcode=1,
            i_memory_region_owner_id=5, i_memory_region_kernel_id=3,
            i_memory_region_base=0,
            i_memory_region_limit=d["scratchpad_banks"] * d["scratchpad_bank_words"] * 8,
            i_memory_region_state=5, i_memory_region_contents_valid=1,
            i_memory_region_read_mask=(1 << clients) - 1,
            i_memory_region_write_mask=(1 << clients) - 1,
            i_memory_region_rsp_ready=1, i_memory_event_ready=1)
        for _ in range(100):
            observed = await self.driver.cycle(values, ["o_memory_region_cmd_ready"])
            if observed["o_memory_region_cmd_ready"]:
                break
        else:
            raise AssertionError("Shared SRAM region provisioning timed out")
        for _ in range(100):
            observed = await self.driver.cycle({"i_memory_region_cmd_valid": 0},
                ["o_memory_region_rsp_valid", "o_memory_region_rsp_error"])
            if observed["o_memory_region_rsp_valid"]:
                assert observed["o_memory_region_rsp_error"] == 0
                break
        else:
            raise AssertionError("Shared SRAM region response timed out")
        for opcode in (1, 0):
            word = 0xFEDCBA9876543210
            values = dict(i_memory_host_req_valid=1, i_memory_host_req_opcode=opcode,
                i_memory_host_req_addr=0, i_memory_host_req_size=8,
                i_memory_host_req_wdata=word, i_memory_host_req_wstrb=255,
                i_memory_host_req_owner_id=5, i_memory_host_req_kernel_id=3,
                i_memory_host_req_generation=1, i_memory_host_req_tag=opcode + 8,
                i_memory_host_rsp_ready=1)
            for _ in range(100):
                observed = await self.driver.cycle(values, ["o_memory_host_req_ready"])
                if observed["o_memory_host_req_ready"]:
                    break
            else:
                raise AssertionError("Shared SRAM host request timed out")
            for _ in range(100):
                observed = await self.driver.cycle({"i_memory_host_req_valid": 0},
                    ["o_memory_host_rsp_valid", "o_memory_host_rsp_error",
                     "o_memory_host_rsp_rdata", "o_memory_host_rsp_tag"])
                if observed["o_memory_host_rsp_valid"]:
                    assert observed["o_memory_host_rsp_error"] == 0, observed
                    assert observed["o_memory_host_rsp_tag"] == opcode + 8
                    if opcode == 0:
                        assert observed["o_memory_host_rsp_rdata"] == word
                    break
            else:
                raise AssertionError("Shared SRAM host response timed out")
        self.coverage.hit("shared_sram_host_write_read")

    async def narrowing(self):
        width = self.manifest["geometry"]["data_width"]
        metadata = self.manifest["geometry"]["metadata_width"]
        by_id = {tile["id"]: tile for tile in self.manifest["tile_parameter_table"]}
        for boundary in self.manifest["boundaries"]:
            tile = next(tile for tile in self.manifest["descriptor"]["tiles"]
                        if tile["row"] == boundary["row"] and tile["col"] == boundary["col"])
            native = by_id[tile["id"]]
            if native["native_data_width"] == width and native["native_metadata_width"] == metadata:
                continue
            prefix = f"route_{tile['id']}"
            await self.driver.cycle({f"i_{prefix}_config_valid": 1,
                f"i_{prefix}_config_output_enable": 1,
                f"i_{prefix}_config_output_select": boundary["slot"]})
            await self.driver.cycle({f"i_{prefix}_config_valid": 0})
            source = boundary["prefix"]
            values = {f"i_{source}_rx_valid": 1,
                      f"i_{source}_rx_data": (1 << (width - 1)) if native["native_data_width"] < width else 0,
                      f"i_{source}_rx_metadata": (1 << (metadata - 1)) if native["native_metadata_width"] < metadata else 0}
            for _ in range(100):
                observed = await self.driver.cycle(values, [f"o_{source}_rx_ready"])
                if observed[f"o_{source}_rx_ready"]:
                    break
            else:
                raise AssertionError("Narrowing test input timed out")
            for _ in range(3):
                observed = await self.driver.cycle({f"i_{source}_rx_valid": 0},
                                                   [f"o_tile_{tile['id']}_width_error_0"])
                assert observed[f"o_tile_{tile['id']}_width_error_0"] == 1
            await self.driver.cycle({f"i_{prefix}_flush": 1})
            await self.driver.cycle({f"i_{prefix}_flush": 0})
            self.coverage.hit("incompatible_narrowing_is_held_and_reported")
            return
        self.coverage.hit("uniform_native_widths_need_no_narrowing")
