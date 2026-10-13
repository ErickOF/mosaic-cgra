"""PyUVM integration of the controller with real two-port committed storage.

The unit suite owns the exhaustive controller graph. This fixture checks the
memory/controller boundary with the existing independent memory model and the
sequencer visit-history model. Neither model obtains validity from the DUT.
"""

import json
from types import SimpleNamespace
import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import test, uvm_test
from mosaic_uvm.logic import bits, logic
from context_memory.model import ContextModel
from context_sequencer.config import SequencerConfig
from context_sequencer.constants import INPUTS, INTERNALS, OUTPUTS, REGISTERED, Mode, State
from context_sequencer.model import SequencerModel


MEMORY_INPUTS = ("i_memory_write_enable", "i_memory_write_mask", "i_memory_write_address", "i_memory_write_data",
                 "i_memory_commit_enable", "i_memory_commit_address", "i_memory_invalidate_enable", "i_memory_invalidate_address")
VALIDITY_INPUTS = {"i_active_context_valid", "i_candidate_context_valid"}


@test(timeout_time=1, timeout_unit="ms")
class ContextSequencerMemoryTest(uvm_test):
    def build_phase(self):
        self.config = config = SequencerConfig.from_environment()
        self.widths = config.widths | dict.fromkeys(MEMORY_INPUTS, 1)
        self.widths.update(i_memory_write_mask=2, i_memory_write_data=8,
                          i_memory_write_address=config.address_width, i_memory_commit_address=config.address_width,
                          i_memory_invalidate_address=config.address_width)
        self.seq = SequencerModel(config)
        self.memory = ContextModel(SimpleNamespace(width=8, depth=config.depth, slice_width=4, read_ports=2,
                                                  address_width=config.address_width, raw=False, async_reset=config.async_reset))
        self.goals = set()
        self.checks = 0
        self.quiet = set()
        self.tasks = []
        config.coverage_file.unlink(missing_ok=True)

    def memory_ports(self, ports):
        active_read, candidate = self.seq.reads(ports)
        result = {name.replace("i_memory_", "i_"): ports[name] for name in MEMORY_INPUTS}
        result.update(i_clk=ports["i_clk"], i_rstb=ports["i_rstb"], i_read_raw="00",
                      i_read_enable=bits(int(active_read) | (int(candidate is not None) << 1), 2),
                      i_read_address=bits((candidate or 0) << self.config.address_width | self.seq.active, 2 * self.config.address_width))
        return result

    def validities(self, ports):
        reads = self.memory.reads(self.memory_ports(ports))
        return ports | dict(zip(("i_active_context_valid", "i_candidate_context_valid"), (entry[1] for entry in reads)))

    async def watch(self, name, handle):
        previous = logic(handle)
        while True:
            await handle.value_change
            protected = name in self.quiet
            await ReadOnly()
            value = logic(handle)
            if previous != value:
                assert not protected, f"Integration quiet-waveform assertion failed: {name}"
                previous = value

    async def check(self, ports, phase, *, advance=False):
        if advance:
            # Both sequential blocks sample the same pre-edge memory validity.
            # A commit performed on this edge becomes visible only afterward.
            sampled = self.validities(ports)
            memory_sample = self.memory_ports(ports)
            self.seq.step(sampled)
            self.memory.step(memory_sample)
        expected_ports = self.validities(ports)
        expected = self.seq.outputs(expected_ports)
        for name, value in expected.items():
            assert logic(getattr(cocotb.top, name)) == bits(int(value), self.widths[name]), f"Integration sequencer assertion failed: {phase}/{name}"
        for name in INPUTS:
            assert logic(getattr(cocotb.top, name)) == expected_ports[name], f"Integration input/validity assertion failed: {phase}/{name}"
        for name in MEMORY_INPUTS:
            assert logic(getattr(cocotb.top, name)) == ports[name], f"Integration stimulus was coerced: {name}"
        reads = self.memory.reads(self.memory_ports(ports))
        for name, (data, _) in zip(("o_memory_active_data", "o_memory_candidate_data"), reads):
            assert logic(getattr(cocotb.top, name)) == data, f"Integration context-data assertion failed: {phase}/{name}"
        if self.config.check_internals:
            for index, word in enumerate(self.memory.data):
                assert logic(cocotb.top.memory.context_data[index]) == word, f"Integration storage assertion failed: {index}"
            assert logic(cocotb.top.memory.context_valid) == "".join(reversed(self.memory.valid)), "Integration committed-valid assertion failed"
            for name, value, width in (("state", int(self.seq.state), 4), ("pending_context", self.seq.pending, self.config.address_width),
                                       ("pending_scheduled", int(self.seq.pending_scheduled), 1)):
                assert logic(getattr(cocotb.top.dut.g_controller, name)) == bits(value, width), f"Integration private-state assertion failed: {name}"
        self.checks += 1
        await Timer(1, unit="ps")

    async def cycle(self, label, *, violation=None, **updates):
        values = dict.fromkeys((*INPUTS, *MEMORY_INPUTS), 0)
        values.update(i_rstb=1, i_loop_count=1)
        values.update(updates)
        data_names = {f"memory_data:{index}" for index in range(self.config.depth)}
        registered = REGISTERED | {"internal:" + name for name in INTERNALS} | {"memory_valid"}
        for clock in (0, 1):
            old_clock = logic(cocotb.top.i_clk)
            ports = {name: bits(value, self.widths[name]) for name, value in (values | {"i_clk": clock}).items()}
            reset = self.config.async_reset and ports["i_rstb"] == "0"
            self.quiet = data_names | (set() if reset else registered)
            for name in (*INPUTS, *MEMORY_INPUTS):
                if name != "i_clk" and name not in VALIDITY_INPUTS:
                    getattr(cocotb.top, name).value = ports[name]
            await Timer(1, unit="ps")
            await ReadOnly()
            pre = ports | {"i_clk": old_clock}
            await self.check(pre, label + "/pre", advance=True)
            if clock:
                found = self.seq.fault(self.validities(pre))
                assert (found[1] if found else None) == violation, f"Integration protocol assertion failed: {found}"
            self.quiet = set() if clock or reset else registered | data_names
            cocotb.top.i_clk.value = clock
            await Timer(1, unit="ps")
            await ReadOnly()
            await self.check(ports, label + "/post", advance=True)
            self.quiet = registered | data_names | set(OUTPUTS) | {"o_memory_active_data", "o_memory_candidate_data"}
            await Timer(10, unit="ps")
            await ReadOnly()
            await self.check(ports, label + "/held")

    async def run_phase(self):
        self.raise_objection()
        for name in (*INPUTS, *MEMORY_INPUTS):
            if name not in VALIDITY_INPUTS:
                getattr(cocotb.top, name).value = 0
        await Timer(1, unit="ps")
        cocotb.top.i_clk.value = 1
        await Timer(1, unit="ps")
        cocotb.top.i_clk.value = 0
        await Timer(1, unit="ps")
        self.memory.valid[:] = ["0"] * self.config.depth
        watched = {name: getattr(cocotb.top, name) for name in (*OUTPUTS, "o_memory_active_data", "o_memory_candidate_data")}
        if self.config.check_internals:
            watched.update({"internal:" + name: getattr(cocotb.top.dut.g_controller, name) for name in INTERNALS})
            watched.update({f"memory_data:{index}": cocotb.top.memory.context_data[index] for index in range(self.config.depth)})
            watched["memory_valid"] = cocotb.top.memory.context_valid
        self.tasks = [cocotb.start_soon(self.watch(name, handle)) for name, handle in watched.items()]
        try:
            await self.cycle("cold_start", i_start_enable=1)
            assert self.seq.state == State.START_WAIT
            self.goals.add("cold_start_wait")
            await self.cycle("partial_load", i_memory_write_enable=1, i_memory_write_mask=1, i_memory_write_data=0x05)
            await self.cycle("atomic_final_load", i_memory_write_enable=1, i_memory_write_mask=2, i_memory_write_data=0xA0, i_memory_commit_enable=1)
            assert self.seq.state == State.START_WAIT and self.memory.data[0] == "10100101"
            self.goals.update(("atomic_masked_load", "commit_requires_next_edge"))
            await self.cycle("committed_activation")
            assert self.seq.state == State.ACTIVE
            if self.config.switch:
                target = self.config.depth - 1
                await self.cycle("switch_request", i_switch_request=1, i_switch_context=target)
                await self.cycle("switch_draining")
                assert self.seq.state == State.SWITCH_PENDING
                await self.cycle("switch_safe", i_safe_point=1)
                if target:
                    assert self.seq.state == State.SWITCH_WAIT
                    await self.cycle("switch_load", i_memory_write_enable=1, i_memory_write_mask=3, i_memory_write_address=target,
                                     i_memory_write_data=0x60 + target, i_memory_commit_enable=1, i_memory_commit_address=target)
                    assert self.seq.state == State.SWITCH_WAIT
                    await self.cycle("switch_commit_activation")
                    self.goals.add("switch_commit_wait")
                assert self.seq.state == State.ACTIVE and self.seq.active == target
                self.goals.add("safe_switch")
                await self.cycle("end_switched_sequence", i_step_accepted=1, i_transition_mode=Mode.END)
                await self.cycle("restart_original", i_start_enable=1)
            if self.config.loop and self.config.maximum_count > 1:
                await self.cycle("counted_loop", i_step_accepted=1, i_transition_mode=Mode.LOOP, i_loop_count=2)
                if self.config.suspend:
                    await self.cycle("suspend_loop", i_suspend_request=1)
                    await self.cycle("suspend_loop_drain")
                    await self.cycle("suspend_loop_safe", i_safe_point=1)
                    await self.cycle("resume_loop", i_resume_request=1)
                    assert self.seq.remaining == 1 and self.seq.owner == 0
                    self.goals.add("loop_suspend_resume")
                if self.config.depth > 1:
                    await self.cycle("loop_fallthrough_wait", i_step_accepted=1, i_transition_mode=Mode.LOOP)
                    # A two-entry fixture can already have committed the fall-through.
                    if self.seq.state == State.CONTEXT_WAIT and self.config.suspend:
                        await self.cycle("suspend_candidate", i_suspend_request=1, i_safe_point=1)
                        await self.cycle("load_while_suspended", i_memory_write_enable=1, i_memory_write_mask=3, i_memory_write_address=1,
                                         i_memory_write_data=0x3C, i_memory_commit_enable=1, i_memory_commit_address=1)
                        await self.cycle("resume_candidate", i_resume_request=1)
                        assert self.seq.state == State.CONTEXT_WAIT
                        await self.cycle("activate_preserved_candidate")
                        assert self.seq.active == 1
                        self.goals.add("suspend_pending_candidate")
                else:
                    await self.cycle("spatial_loop_end", i_step_accepted=1, i_transition_mode=Mode.END)
                    await self.cycle("spatial_restart", i_start_enable=1)
            active = self.seq.active
            await self.cycle("invalidate_execution", i_memory_invalidate_enable=1, i_memory_invalidate_address=active)
            assert self.seq.state == State.ACTIVE and logic(cocotb.top.o_context_enable) == "0"
            self.goals.add("immediate_execution_clamp")
            await self.cycle("active_invalid_error", violation="active_invalid")
            assert self.seq.state == State.ERROR
            self.goals.add("active_invalid_error")
            await self.cycle("error_clear", i_error_clear=1)
            retained = tuple(self.memory.data)
            await self.cycle("reset_priority", i_rstb=0, i_start_enable=1, i_memory_write_enable=1,
                             i_memory_write_mask=3, i_memory_write_data=0xFF, i_memory_commit_enable=1)
            assert self.seq.state == State.IDLE and tuple(self.memory.data) == retained and set(self.memory.valid) == {"0"}
            self.goals.add("reset_retains_data")
            await self.cycle("reset_release")
            self.goals.add("raw_execution_disabled")
        finally:
            for task in self.tasks:
                task.cancel()
        self.drop_objection()

    def check_phase(self):
        config = self.config
        required = {"cold_start_wait", "atomic_masked_load", "commit_requires_next_edge", "immediate_execution_clamp",
                    "active_invalid_error", "reset_retains_data", "raw_execution_disabled"}
        if config.switch:
            required.add("safe_switch")
            if config.depth > 1: required.add("switch_commit_wait")
        if config.loop and config.maximum_count > 1 and config.suspend: required.add("loop_suspend_resume")
        if config.depth > 2 and config.suspend and config.loop: required.add("suspend_pending_candidate")
        goals = {name: name in self.goals for name in sorted(required)}
        report = dict(status="PASS" if all(goals.values()) else "FAIL", parameters=config.parameters, interface_version=1,
                      seed=config.seed, checked_observations=self.checks, structural_assertions="PASS" if config.check_internals else "NOT_RUN",
                      goals=goals, observed=sorted(self.goals), scope="real_context_memory_two_port_integration",
                      waivers=dict(depth_one_uncommitted_self_destination=config.depth == 1, physical_safe_point="NOT_RUN"))
        config.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        config.coverage_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        assert all(goals.values()), f"Missing memory-integration goals: {required - self.goals}"
