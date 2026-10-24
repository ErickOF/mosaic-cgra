"""Decorated PyUVM test against the synthesizable loop_controller top."""
import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from loop_controller.config import LoopControllerConfig
from loop_controller.env import LoopControllerEnv
from loop_controller.sequences import LoopControllerSequence
from loop_controller.transaction import INPUTS


@test(timeout_time=20, timeout_unit='ms')
class LoopControllerTest(uvm_test):
    def build_phase(self):
        c = self.config = LoopControllerConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        if c.check_internals:
            for name, value in c.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong parameter: {name}'
        if c.hdl_assertions:
            assert hasattr(cocotb.top.g_controller, 'u_assertions'), 'HDL checker missing'
        else:
            assert not hasattr(cocotb.top.g_controller, 'u_assertions'), (
                'HDL checker must be absent for Python-only validation'
            )
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, window='initial', sample=Event(), config=c))
        self.env = LoopControllerEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await LoopControllerSequence(self.config).start(self.env.sequencer)
        if self.config.hdl_assertions:
            assert int(cocotb.top.g_controller.u_assertions.checks.value) > 1000
        await Timer(1, unit='ns')
        self.drop_objection()
