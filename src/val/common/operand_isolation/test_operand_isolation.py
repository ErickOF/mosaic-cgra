"""PyUVM test entry points for operand_isolation."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from operand_isolation.config import OperandIsolationConfig
from operand_isolation.env import OperandIsolationEnv
from operand_isolation.sequences import OperandIsolationSequence


@test(timeout_time=1, timeout_unit="ms")
class OperandIsolationTest(uvm_test):
    def build_phase(self):
        self.config = OperandIsolationConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.i_data) == len(cocotb.top.o_data) == self.config.width
        assert len(cocotb.top.i_isolate) == 1
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None, "quiet": False, "sample": Event()})
        self.env = OperandIsolationEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_data.value = 0
        cocotb.top.i_isolate.value = 0
        await OperandIsolationSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
