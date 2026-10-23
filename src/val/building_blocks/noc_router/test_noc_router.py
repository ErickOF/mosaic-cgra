"""Run the decorated PyUVM router environment against the native RTL top."""

import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from noc_router.config import RouterConfig
from noc_router.env import RouterEnv
from noc_router.sequences import RouterSequence
from noc_router.transaction import INPUTS


@test(timeout_time=5, timeout_unit='ms')
class RouterTest(uvm_test):
    def build_phase(self):
        c = self.config = RouterConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(
            self, 'env.*', 'active', dict(item=None, window='initial', sample=Event(), config=c)
        )
        self.env = RouterEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await RouterSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        self.drop_objection()
