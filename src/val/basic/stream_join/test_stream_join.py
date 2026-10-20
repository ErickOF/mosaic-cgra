"""Decorated PyUVM entry point for the clockless combinational DUT."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from stream_join.config import StreamJoinConfig
from stream_join.env import StreamJoinEnv
from stream_join.sequences import StreamJoinSequence
from stream_join.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class StreamJoinTest(uvm_test):
    def build_phase(self):
        c = self.config = StreamJoinConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong interface width: {name}'
        if c.check_parameters:
            for name, value in c.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong elaborated parameter: {name}'
            assert int(cocotb.top.OUTPUT_WIDTH.value) == c.inputs*c.width
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, quiet=set(), sample=Event(), tick=Event()))
        self.env = StreamJoinEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await StreamJoinSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
