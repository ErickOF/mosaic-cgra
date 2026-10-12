"""PyUVM test entry points for level_shifter."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from level_shifter.config import LevelShifterConfig
from level_shifter.env import LevelShifterEnv
from level_shifter.sequences import LevelShifterSequence


@test(timeout_time=1, timeout_unit="ms")
class LevelShifterTest(uvm_test):
    def build_phase(self):
        self.config = LevelShifterConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.i_data) == len(cocotb.top.o_data) == self.config.width
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {
            "item": None, "sample": Event(), "stage": "settled", "stable": False,
        })
        self.env = LevelShifterEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_data.value = 0
        await LevelShifterSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
