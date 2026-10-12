"""PyUVM test entry points for dff."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from dff.config import DffConfig
from dff.env import DffEnv
from dff.sequences import DffSequence


@test(timeout_time=1, timeout_unit="ms")
class DffTest(uvm_test):
    """Check state, legal output events, control assertions, and coverage gates."""

    def build_phase(self):
        self.config = DffConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.o_q) == self.config.width
        assert len(cocotb.top.i_d) == self.config.width
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None, "sample": Event()})
        self.env = DffEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        cocotb.top.i_rstb.value = 1
        cocotb.top.i_enable.value = 0
        cocotb.top.i_d.value = 0
        await DffSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
