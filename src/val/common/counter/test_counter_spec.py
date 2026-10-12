"""PyUVM test entry points for counter."""

import cocotb
from cocotb.clock import Clock
from pyuvm import ConfigDB, test, uvm_test
from counter.config import CounterConfig
from counter.env import CounterEnv
from counter.sequences import CounterSpecSequence


@test(timeout_time=1, timeout_unit="ms")
class CounterSpecTest(uvm_test):
    """Run a real PyUVM sequencer/driver/monitor/scoreboard environment."""

    def build_phase(self):
        self.config = CounterConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.o_count) == self.config.width, "WIDTH override was not applied"
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None})
        self.env = CounterEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        dut = cocotb.top
        dut.i_clk.value = 0
        dut.i_rstb.value = 0
        dut.i_enable.value = 0
        dut.i_clear.value = 0
        dut.i_load.value = 0
        dut.i_direction.value = 0
        dut.i_load_value.value = 0
        clock = cocotb.start_soon(Clock(dut.i_clk, self.config.clock_ns, unit="ns").start(start_high=False))
        await CounterSpecSequence(self.config).start(self.env.sequencer)
        clock.cancel()
        self.drop_objection()
