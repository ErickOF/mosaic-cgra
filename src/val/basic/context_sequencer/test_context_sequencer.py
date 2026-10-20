"""PyUVM entry point for sequencer protocol, state, loop, and runtime checks."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from context_sequencer.config import SequencerConfig
from context_sequencer.constants import INPUTS
from context_sequencer.env import SequencerEnv
from context_sequencer.sequences import SequencerSequence


@test(timeout_time=1, timeout_unit="ms")
class ContextSequencerTest(uvm_test):
    def build_phase(self):
        config = self.config = SequencerConfig.from_environment()
        for name, width in config.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f"Wrong port width: {name}"
        if config.check_internals:
            for name, expected in config.parameters.items():
                assert int(getattr(cocotb.top, name).value) == expected, f"Wrong elaborated parameter: {name}"
            assert int(cocotb.top.INTERFACE_VERSION.value) == 1, "Wrong local interface version"
        config.coverage_file.unlink(missing_ok=True)
        ConfigDB().set(self, "env.*", "config", config)
        ConfigDB().set(self, "env.*", "active", dict(item=None, quiet=set(), sample=Event()))
        self.env = SequencerEnv("env", self)

    async def run_phase(self):
        self.raise_objection()
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        # Supply a real cold-reset edge before the monitor begins, rather than
        # assuming synchronous state is initialized by a reset level alone.
        await Timer(1, unit="ps")
        cocotb.top.i_clk.value = 1
        await Timer(1, unit="ps")
        cocotb.top.i_clk.value = 0
        await Timer(1, unit="ps")
        await SequencerSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit="ps")
        await ReadOnly()
        self.drop_objection()
