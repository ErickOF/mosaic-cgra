"""PyUVM entry point with strict interface and elaboration checks."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from rdu.config import RduConfig
from rdu.env import RduEnv
from rdu.sequences import RduSequence
from rdu.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class RduTest(uvm_test):
    def build_phase(self):
        config = self.config = RduConfig.from_environment()
        for name, width in config.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong interface width: {name}'
        if config.check_internals:
            derived = dict(CAPACITY_WIDTH=config.delay_width, DELAY_WIDTH=config.delay_width,
                CHANNEL_DATA_WIDTH=config.channels*config.width, DELAY_BUS_WIDTH=config.channels*config.delay_width,
                CAPACITY_BUS_WIDTH=config.channels*config.delay_width)
            for name, value in (config.parameters | derived).items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong elaborated parameter: {name}'
            for c, (base, capacity) in enumerate(zip(config.bases, config.capacities)):
                channel = cocotb.top.g_rdu.g_channel[c]
                assert int(channel.BASE.value) == base and int(channel.CAPACITY.value) == capacity, 'Wrong partition allocation'
        config.coverage_file.unlink(missing_ok=True)
        ConfigDB().set(self, 'env.*', 'config', config)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, quiet={}, sample=Event(), internals={}))
        self.env = RduEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await RduSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
