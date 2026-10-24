"""Run one structured PyUVM test against the controller or released-bank system."""
import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from scratchpad_controller.config import ControllerConfig
from scratchpad_controller.env import ControllerEnv
from scratchpad_controller.sequences import ControllerSequence
from scratchpad_controller.transaction import INPUTS


@test(timeout_time=50, timeout_unit='ms')
class ScratchpadControllerTest(uvm_test):
    def build_phase(self):
        c = self.config = ControllerConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        dut = cocotb.top.u_controller if c.integration else cocotb.top
        for n, width in c.widths.items():
            assert len(getattr(dut, n)) == width, f'Wrong public width {n}'
        for n, value in c.parameters.items():
            assert int(getattr(dut, n).value) == value, f'Wrong elaborated parameter {n}'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, sample=Event(), stage='initial'))
        self.env = ControllerEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for n in INPUTS:
            if not (self.config.integration and n.startswith('i_bank_')):
                getattr(cocotb.top, n).value = 0
        await ControllerSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ns')
        self.drop_objection()
