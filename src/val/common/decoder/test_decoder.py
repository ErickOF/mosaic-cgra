"""PyUVM test entry points for decoder."""

import cocotb
from cocotb.triggers import Event
from pyuvm import ConfigDB, test, uvm_test
from decoder.config import DecoderConfig
from decoder.env import DecoderEnv
from decoder.sequences import DecoderSequence


@test(timeout_time=1, timeout_unit="ms")
class DecoderTest(uvm_test):
    def build_phase(self):
        self.config = DecoderConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.o_decoded) == self.config.num_outputs, "NUM_OUTPUTS override was not applied"
        assert len(cocotb.top.i_select) == self.config.select_width, "SELECT_WIDTH must be derived from NUM_OUTPUTS"
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None, "sample": Event(), "quiet": False})
        self.env = DecoderEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_enable.value = 0
        cocotb.top.i_select.value = 0
        await DecoderSequence(self.config).start(self.env.sequencer)
        self.drop_objection()
