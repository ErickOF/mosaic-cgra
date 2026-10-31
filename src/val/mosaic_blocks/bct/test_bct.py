"""Specification-based scalar tile test with the actual shell and body RTL."""
import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from bct.config import BctConfig
from bct.env import BctEnv
from bct.sequences import BctSequence
from bct.transaction import INPUTS

@test(timeout_time=40, timeout_unit='ms')
class BctTest(uvm_test):
    def build_phase(self):
        c = self.c = BctConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        for name, value in c.parameters.items():
            assert int(getattr(cocotb.top, name).value) == value, f'Wrong parameter: {name}'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, sample=Event(), contexts={}))
        self.env = BctEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        cocotb.top.i_cfg_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        sequence = BctSequence(self.c)
        sequence.coverage = self.env.coverage
        sequence.active = ConfigDB().get(self, 'env.agent', 'active')
        await sequence.start(self.env.sequencer)
        await Timer(1, unit='ns')
        self.drop_objection()
