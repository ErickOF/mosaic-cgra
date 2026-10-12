"""PyUVM test entry points for lane_mask."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from lane_mask.config import LaneMaskConfig
from lane_mask.constants import OUTPUTS, SOURCES
from lane_mask.env import LaneMaskEnv
from lane_mask.sequences import LaneMaskSequence


@test(timeout_time=1, timeout_unit="ms")
class LaneMaskTest(uvm_test):
    def build_phase(self):
        self.config = LaneMaskConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        for name in (*SOURCES, *OUTPUTS):
            assert len(getattr(cocotb.top, name)) == self.config.lanes, f"Incorrect width on {name}"
        assert len(cocotb.top.i_operation_valid) == 1
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None, "sample": Event()})
        self.env = LaneMaskEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_operation_valid.value = 0
        for name in SOURCES:
            getattr(cocotb.top, name).value = 0
        await LaneMaskSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
