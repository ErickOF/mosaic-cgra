"""PyUVM entry point for the production static mesh."""

import cocotb
from cocotb.triggers import Event
from pyuvm import ConfigDB, test, uvm_test
from static_mesh.config import MeshConfig
from static_mesh.env import MeshEnv
from static_mesh.sequences import MeshSequence
from static_mesh.transaction import INPUTS


@test(timeout_time=100, timeout_unit="ms")
class StaticMeshTest(uvm_test):
    def build_phase(self):
        self.c = MeshConfig.from_environment()
        self.c.coverage_file.unlink(missing_ok=True)
        for n, w in self.c.widths.items():
            assert len(getattr(cocotb.top, n)) == w, (n, w)
        for n, v in self.c.parameters.items():
            assert int(getattr(cocotb.top, n).value) == v, n
        active = dict(routes=None, generation=0, pre=Event(), post=Event(), fault_mode=False)
        ConfigDB().set(self, "env.*", "config", self.c)
        ConfigDB().set(self, "env.*", "active", active)
        self.active = active
        self.env = MeshEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for n in INPUTS:
            getattr(cocotb.top, n).value = 0
        seq = MeshSequence(self.c, self.active, self.env.coverage)
        await seq.start(self.env.sequencer)
        self.drop_objection()
