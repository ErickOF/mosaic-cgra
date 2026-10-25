"""Decorated PyUVM test against the synthesizable lut_unit top."""
import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from lut_unit.config import LutUnitConfig
from lut_unit.env import LutUnitEnv
from lut_unit.sequences import LutUnitSequence
from lut_unit.transaction import INPUTS


@test(timeout_time=20, timeout_unit='ms')
class LutUnitTest(uvm_test):
    def build_phase(self):
        c = self.config = LutUnitConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        if c.check_internals:
            for name, value in c.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong parameter: {name}'
        if c.hdl_assertions:
            assert hasattr(cocotb.top.g_unit, 'u_assertions'), 'HDL checker missing'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, window='initial', sample=Event(), config=c))
        self.env = LutUnitEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await LutUnitSequence(self.config).start(self.env.sequencer)
        if self.config.hdl_assertions:
            assert int(cocotb.top.g_unit.u_assertions.checks.value) > 1000
        await Timer(1, unit='ns')
        self.drop_objection()
