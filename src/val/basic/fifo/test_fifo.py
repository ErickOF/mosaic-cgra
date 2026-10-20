"""PyUVM entry point with strict port and parameter checks."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from fifo.config import FifoConfig
from fifo.env import FifoEnv
from fifo.sequences import FifoSequence
from fifo.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class FifoTest(uvm_test):
    def build_phase(self):
        config = self.config = FifoConfig.from_environment()
        for name, width in config.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong interface width: {name}'
        if config.check_internals:
            for name, value in config.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong elaborated parameter: {name}'
            assert int(cocotb.top.PTR_WIDTH.value) == config.pointer_width
            assert int(cocotb.top.OCC_WIDTH.value) == config.depth.bit_length()
        config.coverage_file.unlink(missing_ok=True)
        ConfigDB().set(self, 'env.*', 'config', config)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, quiet=set(), sample=Event(), internals={}))
        self.env = FifoEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await FifoSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
