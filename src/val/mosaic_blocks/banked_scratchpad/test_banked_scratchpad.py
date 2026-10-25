"""PyUVM verification of production controller/bank composition."""
import cocotb
from pyuvm import ConfigDB, test, uvm_test
from banked_scratchpad.config import ScratchpadConfig
from banked_scratchpad.env import ScratchpadEnv
from banked_scratchpad.sequences import ScratchpadSequence
from banked_scratchpad.transaction import INPUTS, OUTPUTS


@test(timeout_time=30, timeout_unit='ms')
class BankedScratchpadTest(uvm_test):
    def build_phase(self):
        self.c = ScratchpadConfig.from_environment()
        self.c.coverage_file.unlink(missing_ok=True)
        for name, width in self.c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, name
        for name, value in self.c.parameters.items():
            assert int(getattr(cocotb.top, name).value) == value, name
        self.active = dict(item=None, outputs=OUTPUTS)
        ConfigDB().set(self, 'env.*', 'config', self.c)
        ConfigDB().set(self, 'env.*', 'active', self.active)
        self.env = ScratchpadEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await ScratchpadSequence(self.c, self.active, self.env.coverage).start(self.env.sequencer)
        self.drop_objection()
