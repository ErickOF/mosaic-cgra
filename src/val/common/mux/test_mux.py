"""PyUVM test entry points for mux."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from mux.config import MuxConfig
from mux.env import MuxEnv
from mux.sequences import MuxSequence


@test(timeout_time=1, timeout_unit="ms")
class MuxTest(uvm_test):
    def build_phase(self):
        self.config = MuxConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.i_data) == self.config.num_inputs * self.config.data_width
        assert len(cocotb.top.o_data) == self.config.data_width
        assert len(cocotb.top.i_select) == self.config.select_width
        assert len(cocotb.top.o_select_valid) == 1
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {
            "item": None, "sample": Event(), "stage": "settled", "kind": "stable", "quiet": False,
        })
        self.env = MuxEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_data.value = 0
        cocotb.top.i_select.value = 0
        await MuxSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
