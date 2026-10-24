"""Decorated PyUVM entry point against the native reciprocal_unit RTL top."""
import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from reciprocal_unit.images import verify_default_image
from reciprocal_unit.config import ReciprocalConfig
from reciprocal_unit.env import ReciprocalEnv
from reciprocal_unit.ports import INPUTS
from reciprocal_unit.sequences import ReciprocalSequence


@test(timeout_time=20, timeout_unit='ms')
class ReciprocalUnitTest(uvm_test):
    def build_phase(self):
        verify_default_image()
        c = self.config = ReciprocalConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        for name, value in c.parameters.items():
            assert int(getattr(cocotb.top, name).value) == value, f'Wrong parameter: {name}'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, sample=Event()))
        self.env = ReciprocalEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await ReciprocalSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ns')
        self.drop_objection()
