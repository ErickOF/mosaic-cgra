"""Actual-router mesh integration with behavioral flit endpoints, not TNI RTL."""

import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from noc_router.mesh import MeshConfig, MeshEnv, MeshSequence
from noc_router.transaction import INPUTS


@test(timeout_time=5, timeout_unit='ms')
class MeshTest(uvm_test):
    def build_phase(self):
        c = self.config = MeshConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Mesh port width: {name}'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, sample=Event(), config=c))
        self.env = MeshEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await MeshSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        self.drop_objection()
