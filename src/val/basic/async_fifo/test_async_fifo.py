"""PyUVM entry point for portable zero-delay async FIFO validation."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test

from async_fifo.config import AsyncFifoConfig
from async_fifo.env import AsyncFifoEnv
from async_fifo.sequences import AsyncFifoSequence
from async_fifo.transaction import CHAINS, INPUTS


@test(timeout_time=1, timeout_unit="ms")
class AsyncFifoTest(uvm_test):
    def build_phase(self):
        self.config = AsyncFifoConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.i_w_data) == len(cocotb.top.o_r_data) == self.config.width
        assert len(cocotb.top.o_w_level) == len(cocotb.top.o_r_level) == self.config.pointer_width
        if self.config.check_internals:
            for name in CHAINS:
                assert len(getattr(cocotb.top, name)) == self.config.stages, f"Missing/wrong synchronizer array: {name}"
            assert len(cocotb.top.memory) == self.config.depth
            for name, expected in self.config.parameters.items():
                assert int(getattr(cocotb.top, name).value) == expected, f"Elaborated {name} does not match configuration"
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", dict(item=None, allowed={"w": False, "r": False}, sample=Event()))
        self.env = AsyncFifoEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await AsyncFifoSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
