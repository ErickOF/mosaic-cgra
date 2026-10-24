"""Run the specification-based PyUVM test on the real RTL top."""

import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from tile_network_interface.config import InterfaceConfig
from tile_network_interface.env import InterfaceEnv
from tile_network_interface.sequences import InterfaceSequence
from tile_network_interface.transaction import INPUTS


@test(timeout_time=50, timeout_unit='ms')
class TileNetworkInterfaceTest(uvm_test):
    def build_phase(self):
        self.config = InterfaceConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        for name, width in self.config.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        ConfigDB().set(self, 'env.*', 'config', self.config)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, sample=Event()))
        self.env = InterfaceEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await InterfaceSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ns')
        self.drop_objection()
