"""Execute the structured PyUVM environment on the actual controller RTL."""

import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from tile_power_controller.config import PowerConfig
from tile_power_controller.env import PowerEnv
from tile_power_controller.sequences import PowerSequence
from tile_power_controller.transaction import INPUTS


@test(timeout_time=100, timeout_unit='ms')
class TilePowerControllerTest(uvm_test):
    def build_phase(self):
        self.config = PowerConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        for name, width in self.config.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        ConfigDB().set(self, 'env.*', 'config', self.config)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, sample=Event()))
        self.env = PowerEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_aon_clk.value = 0
        for n in INPUTS:
            getattr(cocotb.top, n).value = 0
        await PowerSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ns')
        self.drop_objection()
