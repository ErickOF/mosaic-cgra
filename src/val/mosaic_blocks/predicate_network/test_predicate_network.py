"""Run the production predicate fabric with specification-based PyUVM scenarios."""

import cocotb
from cocotb.triggers import Event
from pyuvm import ConfigDB, test, uvm_test
from predicate_network.config import PredicateConfig
from predicate_network.env import PredicateEnv
from predicate_network.sequences import PredicateSequence
from predicate_network.transaction import INPUTS


@test(timeout_time=100, timeout_unit="ms")
class PredicateNetworkTest(uvm_test):
    def build_phase(self):
        self.c = PredicateConfig.from_environment()
        self.c.coverage_file.unlink(missing_ok=True)
        for n, w in self.c.widths.items():
            assert len(getattr(cocotb.top, n)) == w, (n, w)
        for n, v in self.c.parameters.items():
            assert int(getattr(cocotb.top, n).value) == v, n
        self.active = dict(routes=None, generation=0, pre=Event(), post=Event(), fault_mode=False)
        ConfigDB().set(self, "env.*", "config", self.c)
        ConfigDB().set(self, "env.*", "active", self.active)
        self.env = PredicateEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for n in INPUTS:
            getattr(cocotb.top, n).value = 0
        await PredicateSequence(self.c, self.active, self.env.coverage).start(self.env.sequencer)
        self.drop_objection()
