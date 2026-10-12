"""PyUVM test entry points for reset_synchronizer."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from reset_synchronizer.config import ResetSynchronizerConfig
from reset_synchronizer.env import ResetSynchronizerEnv
from reset_synchronizer.sequences import ResetSynchronizerSequence


@test(timeout_time=1, timeout_unit="ms")
class ResetSynchronizerTest(uvm_test):
    def build_phase(self):
        self.config = ResetSynchronizerConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.i_clk) == len(cocotb.top.i_async_rstb) == len(cocotb.top.o_rstb) == 1
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None, "allowed": False, "rising_clock": False, "sample": Event()})
        self.env = ResetSynchronizerEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        cocotb.top.i_async_rstb.value = 0
        await ResetSynchronizerSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
