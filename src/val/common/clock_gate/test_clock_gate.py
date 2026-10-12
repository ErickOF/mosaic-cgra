"""PyUVM test entry points for clock_gate."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from clock_gate.config import ClockGateConfig
from clock_gate.env import ClockGateEnv
from clock_gate.sequences import ClockGateSequence


@test(timeout_time=1, timeout_unit="ms")
class ClockGateTest(uvm_test):
    """Check complete waveforms through actual PyUVM components and coverage."""

    def build_phase(self):
        self.config = ClockGateConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None})
        self.env = ClockGateEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        cocotb.top.i_enable.value = int(self.config.startup_enabled)
        cocotb.top.i_test_enable.value = 0
        await ClockGateSequence(self.config).start(self.env.sequencer)
        # Flush the monitor's final falling-edge snapshot before check_phase.
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
