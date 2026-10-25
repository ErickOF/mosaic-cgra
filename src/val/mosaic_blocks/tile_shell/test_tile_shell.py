"""Run the actual tile-shell top with structured PyUVM components."""
import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from tile_shell.config import TileShellConfig
from tile_shell.env import TileShellEnv
from tile_shell.sequences import TileShellSequence
from tile_shell.transaction import INPUTS

@test(timeout_time=20, timeout_unit='ms')
class TileShellTest(uvm_test):
    def build_phase(self):
        c = self.c = TileShellConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        for name, value in c.parameters.items():
            assert int(getattr(cocotb.top, name).value) == value, f'Wrong parameter: {name}'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, sample=Event()))
        self.env = TileShellEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        cocotb.top.i_cfg_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        sequence = TileShellSequence(self.c)
        sequence.coverage = self.env.coverage
        await sequence.start(self.env.sequencer)
        await Timer(1, unit='ns')
        self.drop_objection()
