"""PyUVM entry point for the actual generated array and production source closure."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]/'gen/global_noc'))
import cocotb
from cocotb.triggers import Event
from pyuvm import ConfigDB, test, uvm_test
from mosaic_blocks.array.config import ArrayConfig
from mosaic_blocks.array.env import ArrayEnv
from mosaic_blocks.array.sequences import ArraySequence

@test(timeout_time=100, timeout_unit='ms')
class ArrayTest(uvm_test):
    def build_phase(self):
        self.c = ArrayConfig.from_environment()
        self.c.coverage_file.unlink(missing_ok=True)
        for name, (_, width) in self.c.ports.items():
            assert len(getattr(cocotb.top, name)) == width, (name, width)
        active = dict(pre=Event(), post=Event(), reset_count=0, fault_mode=False)
        ConfigDB().set(self, 'env.*', 'config', self.c)
        ConfigDB().set(self, 'env.*', 'active', active)
        self.env = ArrayEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name, (direction, _) in self.c.ports.items():
            if direction == 'input' and name != 'i_clk': getattr(cocotb.top, name).value = 0
        await ArraySequence(self.c, self.env.coverage).start(self.env.sequencer)
        self.drop_objection()
