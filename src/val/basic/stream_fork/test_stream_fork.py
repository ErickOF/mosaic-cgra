"""Decorated PyUVM entry point with strict port and elaboration checks."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from stream_fork.config import StreamForkConfig
from stream_fork.env import StreamForkEnv
from stream_fork.sequences import StreamForkSequence
from stream_fork.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class StreamForkTest(uvm_test):
    def build_phase(self):
        c = self.config = StreamForkConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong interface width: {name}'
        if c.check_internals:
            for name, value in c.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong elaborated parameter: {name}'
            assert len(cocotb.top.g_fork.fork_data) == c.width
            assert len(cocotb.top.g_fork.pending) == c.outputs
            assert int(cocotb.top.OUTPUT_WIDTH.value) == c.width*c.outputs
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, quiet=set(), sample=Event(), internals={}))
        self.env = StreamForkEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await StreamForkSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
