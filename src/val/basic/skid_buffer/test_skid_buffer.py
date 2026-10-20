"""Decorated PyUVM entry point with strict port and elaboration checks."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from skid_buffer.config import SkidBufferConfig
from skid_buffer.env import SkidBufferEnv
from skid_buffer.sequences import SkidBufferSequence
from skid_buffer.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class SkidBufferTest(uvm_test):
    def build_phase(self):
        c = self.config = SkidBufferConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong interface width: {name}'
        if c.check_internals:
            for name, value in c.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong elaborated parameter: {name}'
            assert len(cocotb.top.g_skid.buffer_data) == c.width
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, quiet=set(), sample=Event(), internals={}, occupied=False))
        self.env = SkidBufferEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await SkidBufferSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
