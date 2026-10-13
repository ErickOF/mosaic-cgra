"""PyUVM entry point for combinational and one-stage local forwarding."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test

from bypass_network.config import BypassNetworkConfig
from bypass_network.env import BypassNetworkEnv
from bypass_network.sequences import BypassNetworkSequence
from bypass_network.transaction import INPUTS


@test(timeout_time=1, timeout_unit="ms")
class BypassNetworkTest(uvm_test):
    def build_phase(self):
        config = self.config = BypassNetworkConfig.from_environment()
        widths = dict(i_source_data=config.sources * config.width, i_source_valid=config.sources,
                      i_destination_enable=config.destinations, i_capture_enable=config.destinations,
                      i_select=config.destinations * config.select_width, o_destination_data=config.destinations * config.width,
                      o_destination_valid=config.destinations, o_selection_error=config.destinations)
        for name, width in widths.items():
            assert len(getattr(cocotb.top, name)) == width, f"Wrong packed port width: {name}"
        if config.check_internals:
            assert len(cocotb.top.registered_data) == config.width * config.destinations
            assert len(cocotb.top.registered_valid) == config.destinations
            for name, expected in config.parameters.items():
                assert int(getattr(cocotb.top, name).value) == expected, f"Elaborated parameter differs: {name}"
        config.coverage_file.unlink(missing_ok=True)
        ConfigDB().set(self, "env.*", "config", config)
        ConfigDB().set(self, "env.*", "active", dict(item=None, quiet={}, sample=Event()))
        self.env = BypassNetworkEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await BypassNetworkSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
