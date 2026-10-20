"""PyUVM entry point with strict interface and elaboration checks."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from performance_counters.config import PerformanceCountersConfig
from performance_counters.env import PerformanceCountersEnv
from performance_counters.sequences import PerformanceCountersSequence
from performance_counters.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class PerformanceCountersTest(uvm_test):
    def build_phase(self):
        config = self.config = PerformanceCountersConfig.from_environment()
        for name, width in config.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong interface width: {name}'
        if config.check_internals:
            derived = dict(COUNTER_ADDR_WIDTH=config.counter_address_width, EVENT_ADDR_WIDTH=config.event_address_width,
                EVENT_SELECT_WIDTH=config.counters*config.event_address_width,
                EVENT_INCREMENT_WIDTH=config.events*config.increment_width, THRESHOLD_BUS_WIDTH=config.counters*config.width)
            for name, value in (config.parameters | derived).items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong elaborated parameter: {name}'
        config.coverage_file.unlink(missing_ok=True)
        ConfigDB().set(self, 'env.*', 'config', config)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, quiet=set(), sample=Event(), internals={}))
        self.env = PerformanceCountersEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await PerformanceCountersSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
