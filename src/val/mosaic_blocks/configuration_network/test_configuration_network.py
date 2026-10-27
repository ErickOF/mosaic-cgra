"""Exercise the production configuration fabric through separated PyUVM components."""

import cocotb
from cocotb.triggers import Event
from pyuvm import ConfigDB, test, uvm_test
from configuration_network.config import NetworkConfig
from configuration_network.env import NetworkEnv
from configuration_network.sequences import NetworkSequence
from configuration_network.transaction import INPUTS


@test(timeout_time=100, timeout_unit="ms")
class ConfigurationNetworkTest(uvm_test):
    def build_phase(self):
        self.c = NetworkConfig.from_environment()
        self.c.coverage_file.unlink(missing_ok=True)
        for n, w in self.c.widths.items():
            assert len(getattr(cocotb.top, n)) == w, (n, w)
        for n, v in self.c.parameters.items():
            assert int(getattr(cocotb.top, n).value) == v, n
        self.active = dict(
            pre=Event(), post=Event(), diagnostic=False, records=[], endpoint_errors={}
        )
        ConfigDB().set(self, "env.*", "config", self.c)
        ConfigDB().set(self, "env.*", "active", self.active)
        self.env = NetworkEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for n in INPUTS:
            getattr(cocotb.top, n).value = 0
        await NetworkSequence(self.c, self.active, self.env.coverage).start(
            self.env.sequencer
        )
        self.drop_objection()
