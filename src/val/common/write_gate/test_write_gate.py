"""PyUVM test entry points for write_gate."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from write_gate.config import WriteGateConfig
from write_gate.env import WriteGateEnv
from write_gate.sequences import WriteGateSequence


@test(timeout_time=1, timeout_unit="ms")
class WriteGateTest(uvm_test):
    def build_phase(self):
        self.config = WriteGateConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        for name in ("i_write_enable", "i_suppress", "o_write_enable", "o_write_suppressed"):
            assert len(getattr(cocotb.top, name)) == self.config.width, f"Wrong width for {name}"
        if self.config.integration:
            assert len(cocotb.top.i_write_data) == len(cocotb.top.o_register_state) == self.config.width
            assert len(cocotb.top.o_memory_state) == 4 * self.config.width
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None, "quiet": False, "capture_window": False, "sample": Event()})
        self.env = WriteGateEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_write_enable.value = 0
        cocotb.top.i_suppress.value = 0
        if self.config.integration:
            cocotb.top.i_clk.value = 0
            cocotb.top.i_rstb.value = 0
            cocotb.top.i_capture_valid.value = 0
            cocotb.top.i_destination.value = 0
            cocotb.top.i_address.value = 0
            cocotb.top.i_write_data.value = 0
            await Timer(1, unit="ps")
            cocotb.top.i_clk.value = 1
            await Timer(1, unit="ps")
            cocotb.top.i_clk.value = 0
            cocotb.top.i_rstb.value = 1
        await WriteGateSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
