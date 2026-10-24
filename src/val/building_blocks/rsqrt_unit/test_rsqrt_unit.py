"""Decorated PyUVM entry point against the native rsqrt_unit RTL top."""
import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from rsqrt_unit.images import verify_default_image
from rsqrt_unit.config import RsqrtConfig
from rsqrt_unit.env import RsqrtEnv
from rsqrt_unit.ports import INPUTS
from rsqrt_unit.sequences import RsqrtSequence


@test(timeout_time=20, timeout_unit='ms')
class RsqrtUnitTest(uvm_test):
    def build_phase(self):
        verify_default_image()
        c = self.config = RsqrtConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        for name, value in c.parameters.items():
            assert int(getattr(cocotb.top, name).value) == value, f'Wrong parameter: {name}'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, sample=Event()))
        self.env = RsqrtEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await RsqrtSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ns')
        self.drop_objection()
