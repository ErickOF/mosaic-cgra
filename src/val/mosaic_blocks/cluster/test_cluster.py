"""PyUVM entry point for the actual generated cluster and production dependencies."""
import cocotb
import os
from cocotb.triggers import Event
from pyuvm import ConfigDB, test, uvm_test
from cluster.config import ClusterConfig
from cluster.env import ClusterEnv
from cluster.sequences import ClusterSequence

@test(timeout_time=100, timeout_unit='ms')
class ClusterTest(uvm_test):
    def build_phase(self):
        self.c = ClusterConfig.from_environment()
        self.c.coverage_file.unlink(missing_ok=True)
        for name, width in self.c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, (name, width)
        active = dict(pre=Event(), post=Event(), reset_count=0, fault_mode=False)
        ConfigDB().set(self, 'env.*', 'config', self.c)
        ConfigDB().set(self, 'env.*', 'active', active)
        self.active = active
        self.env = ClusterEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name, (direction, _) in self.c.ports.items():
            if direction == 'input' and name != 'i_clk':
                getattr(cocotb.top, name).value = 0
        await ClusterSequence(self.c, self.active, self.env.coverage).start(self.env.sequencer)
        self.drop_objection()

# Default make pyuvm registers the full integration test only. The campaign
# explicitly selects the additional smoke/failure entry points by environment.
if os.getenv('CLUSTER_MODE') == 'smoke':
    @test(timeout_time=100, timeout_unit='ms')
    class ClusterSmokeTest(ClusterTest):
        async def run_phase(self):
            from cluster.sequences import ClusterSmokeSequence
            self.raise_objection()
            cocotb.top.i_clk.value=0
            for name,(direction,_) in self.c.ports.items():
                if direction=='input' and name!='i_clk': getattr(cocotb.top,name).value=0
            await ClusterSmokeSequence(self.c,self.active,self.env.coverage).start(self.env.sequencer)
            self.drop_objection()

if os.getenv('CLUSTER_MODE') == 'partial':
    @test(timeout_time=100, timeout_unit='ms')
    class ClusterCommitFaultTest(ClusterTest):
        async def run_phase(self):
            from cluster.sequences import ClusterCommitFaultSequence
            self.raise_objection()
            cocotb.top.i_clk.value=0
            for name,(direction,_) in self.c.ports.items():
                if direction=='input' and name!='i_clk': getattr(cocotb.top,name).value=0
            await ClusterCommitFaultSequence(self.c,self.active,self.env.coverage).start(self.env.sequencer)
            self.drop_objection()
