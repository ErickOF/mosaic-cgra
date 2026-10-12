"""PyUVM test entry points for priority_encoder."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from priority_encoder.config import PriorityEncoderConfig
from priority_encoder.env import PriorityEncoderEnv
from priority_encoder.sequences import PriorityEncoderSequence


@test(timeout_time=1, timeout_unit="ms")
class PriorityEncoderTest(uvm_test):
    def build_phase(self):
        self.config = PriorityEncoderConfig.from_environment()
        self.config.coverage_file.unlink(missing_ok=True)
        assert len(cocotb.top.i_request) == len(cocotb.top.o_onehot) == self.config.width
        assert len(cocotb.top.o_index) == self.config.index_width
        assert len(cocotb.top.o_valid) == len(cocotb.top.o_multiple) == 1
        ConfigDB().set(self, "env.*", "config", self.config)
        ConfigDB().set(self, "env.*", "active", {"item": None, "quiet": False, "sample": Event()})
        self.env = PriorityEncoderEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_request.value = 0
        await PriorityEncoderSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
