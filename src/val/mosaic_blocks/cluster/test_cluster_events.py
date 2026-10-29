"""PyUVM verification of the production event collector's public ports."""
import cocotb
from cocotb.triggers import Event
from pyuvm import ConfigDB, test, uvm_test
from cluster.events_config import EventConfig
from cluster.events_env import EventEnv
from cluster.events_sequence import EventSequence


@test(timeout_time=20, timeout_unit='ms')
class ClusterEventsTest(uvm_test):
    def build_phase(self):
        self.c = EventConfig.from_environment()
        self.c.coverage_file.unlink(missing_ok=True)
        for name, width in self.c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, name
        for name, value in self.c.parameters.items():
            assert int(getattr(cocotb.top, name).value) == value, name
        self.active = dict(pre=Event(), post=Event())
        ConfigDB().set(self, 'env.*', 'config', self.c)
        ConfigDB().set(self, 'env.*', 'active', self.active)
        self.env = EventEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name, (direction, _) in self.c.ports.items():
            if direction == 'input' and name != 'i_clk':
                getattr(cocotb.top, name).value = 0
        await EventSequence(self.c, self.env.coverage).start(self.env.sequencer)
        self.drop_objection()
