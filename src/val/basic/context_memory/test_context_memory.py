"""PyUVM entry point for opaque context lifecycle and combinational read timing."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from context_memory.config import ContextMemoryConfig
from context_memory.env import ContextMemoryEnv
from context_memory.sequences import ContextMemorySequence
from context_memory.transaction import INPUTS


@test(timeout_time=1, timeout_unit="ms")
class ContextMemoryTest(uvm_test):
    def build_phase(self):
        config = self.config = ContextMemoryConfig.from_environment()
        widths = dict(i_read_enable=config.read_ports, i_read_raw=config.read_ports, i_read_address=config.read_ports * config.address_width,
                      o_read_data=config.read_ports * config.width, o_read_valid=config.read_ports, i_write_mask=config.slices,
                      i_write_address=config.address_width, i_commit_address=config.address_width, i_invalidate_address=config.address_width,
                      i_write_data=config.width)
        for name, expected in widths.items():
            assert len(getattr(cocotb.top, name)) == expected, f"Wrong port width: {name}"
        if config.check_internals:
            assert len(cocotb.top.context_data) == config.depth and len(cocotb.top.context_valid) == config.depth
            for name, expected in config.parameters.items():
                assert int(getattr(cocotb.top, name).value) == expected, f"Wrong elaborated parameter: {name}"
        config.coverage_file.unlink(missing_ok=True)
        ConfigDB().set(self, "env.*", "config", config)
        ConfigDB().set(self, "env.*", "active", dict(item=None, quiet={}, sample=Event()))
        self.env = ContextMemoryEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await ContextMemorySequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
