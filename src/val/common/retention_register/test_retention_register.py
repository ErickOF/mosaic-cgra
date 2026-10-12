"""PyUVM test entry points for retention_register."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from retention_register.config import RetentionConfig
from retention_register.env import RetentionEnv
from retention_register.sequences import RetentionSequence


@test(timeout_time=1, timeout_unit="ms")
class RetentionRegisterTest(uvm_test):
    def build_phase(self):
        self.config = RetentionConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.i_d) == len(cocotb.top.o_q) == self.config.width
        assert all(len(getattr(cocotb.top, name)) == 1 for name in ("i_clk", "i_rstb", "i_enable", "i_save", "i_restore"))
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None, "allowed": False, "sample": Event()})
        self.env = RetentionEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        for name in ("i_clk", "i_rstb", "i_enable", "i_save", "i_restore", "i_d"):
            getattr(cocotb.top, name).value = 0
        await RetentionSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
