"""Production manager, released tile controllers, gates, reset and clamp cells."""
import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from cluster_power_manager.config import PowerConfig
from cluster_power_manager.env import PowerEnv
from cluster_power_manager.sequences import PowerSequence
from cluster_power_manager.transaction import INPUTS


@test(timeout_time=100, timeout_unit='ms')
class ClusterPowerManagerTest(uvm_test):
    def build_phase(self):
        self.c = PowerConfig.from_environment()
        self.c.coverage_file.unlink(missing_ok=True)
        for name, width in self.c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, ('Port width', name, width)
        for name, value in self.c.parameters.items():
            assert int(getattr(cocotb.top, name).value) == value, ('Parameter', name)
        ConfigDB().set(self, 'env.*', 'config', self.c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, sample=Event()))
        self.env = PowerEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_aon_clk.value = 0
        cocotb.top.i_functional_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        sequence = PowerSequence(self.c)
        sequence.coverage = self.env.coverage
        sequence.scoreboard = self.env.scoreboard
        sequence.active = ConfigDB().get(self, 'env.agent', 'active')
        await sequence.start(self.env.sequencer)
        await Timer(1, unit='ns')
        self.drop_objection()
