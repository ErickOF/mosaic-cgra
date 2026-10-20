"""Decorated PyUVM entry point with strict port and elaboration checks."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from sram_wrapper.config import SramConfig
from sram_wrapper.env import SramEnv
from sram_wrapper.sequences import SramSequence
from sram_wrapper.transaction import INPUTS


@test(timeout_time=10, timeout_unit='ms')
class SramTest(uvm_test):
    def build_phase(self):
        c = self.config = SramConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong interface width: {name}'
        if c.check_internals:
            for name,value in (c.parameters|dict(ADDR_WIDTH=c.address_width,MASK_WIDTH=c.mask_width,OUTSTANDING_WIDTH=c.count_width)).items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong elaborated parameter: {name}'
            assert len(cocotb.top.g_shell.u_backend.o_rdata) == c.width
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, quiet=set(), sample=Event(), internals={}, memory_write=None, response_write=None))
        self.env = SramEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await SramSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
