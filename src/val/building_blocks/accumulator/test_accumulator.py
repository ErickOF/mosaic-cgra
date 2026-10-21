"""Decorated PyUVM entry point with exact geometry and HDL-checker checks."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from accumulator.config import AccumulatorConfig
from accumulator.env import AccumulatorEnv
from accumulator.sequences import AccumulatorSequence
from accumulator.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class AccumulatorTest(uvm_test):
    def build_phase(self):
        c = self.config = AccumulatorConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong interface width: {name}'
        if c.check_internals:
            for name, value in c.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong elaborated parameter: {name}'
            assert int(cocotb.top.DATA_WIDTH.value) == c.width*c.lanes
            assert len(cocotb.top.g_bank.state_data) == c.width*c.lanes
        if c.hdl_assertions:
            assert hasattr(cocotb.top.g_bank, 'u_assertions'), 'HDL assertion checker was not elaborated'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, selected=set(), permissions={}, sample=Event(), internals={}))
        self.env = AccumulatorEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await AccumulatorSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
