"""Exercise production runtime RTL using external Python system/array peers."""
import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from runtime_controller.config import RuntimeConfig
from runtime_controller.env import RuntimeEnv
from runtime_controller.sequences import RuntimeSequence
from runtime_controller.transaction import INPUTS


@test(timeout_time=100, timeout_unit='ms')
class RuntimeControllerTest(uvm_test):
    def build_phase(self):
        self.c = RuntimeConfig.from_environment()
        self.c.coverage_file.unlink(missing_ok=True)
        for name, width in self.c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, ('Port width', name, width)
        for name, value in self.c.parameters.items():
            assert int(getattr(cocotb.top, name).value) == value, ('Parameter', name)
        ConfigDB().set(self, 'env.*', 'config', self.c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, sample=Event()))
        self.env = RuntimeEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        sequence = RuntimeSequence(self.c)
        sequence.coverage = self.env.coverage
        sequence.scoreboard = self.env.scoreboard
        sequence.active = ConfigDB().get(self, 'env.agent', 'active')
        await sequence.start(self.env.sequencer)
        await Timer(1, unit='ns')
        self.drop_objection()
