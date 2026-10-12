"""PyUVM test entry points for isolation_cell."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from isolation_cell.config import IsolationCellConfig
from isolation_cell.env import IsolationCellEnv
from isolation_cell.sequences import IsolationCellSequence


@test(timeout_time=1, timeout_unit="ms")
class IsolationCellTest(uvm_test):
    def build_phase(self):
        self.config = IsolationCellConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.i_data) == len(cocotb.top.o_data) == self.config.width
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None, "quiet": False, "sample": Event()})
        self.env = IsolationCellEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_isolate.value = self.config.inactive_control
        cocotb.top.i_data.value = 0
        await IsolationCellSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
