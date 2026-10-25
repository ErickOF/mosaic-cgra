"""Decorated PyUVM entry point against the native polynomial_unit RTL top."""
import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from polynomial_unit.config import PolynomialConfig
from polynomial_unit.env import PolynomialEnv
from polynomial_unit.ports import INPUTS
from polynomial_unit.sequences import PolynomialSequence


@test(timeout_time=20, timeout_unit='ms')
class PolynomialUnitTest(uvm_test):
    def build_phase(self):
        c = self.config = PolynomialConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        for name, value in c.parameters.items():
            assert int(getattr(cocotb.top, name).value) == value, f'Wrong parameter: {name}'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, sample=Event()))
        self.env = PolynomialEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await PolynomialSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ns')
        self.drop_objection()
