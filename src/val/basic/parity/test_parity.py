"""Decorated PyUVM entry point for the independent combinational codec."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from parity.config import ParityConfig
from parity.env import ParityEnv
from parity.sequences import ParitySequence
from parity.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class ParityTest(uvm_test):
    def build_phase(self):
        config = self.config = ParityConfig.from_environment()
        for name, width in config.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong interface width: {name}'
        if config.check_internals:
            for name, value in config.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong elaborated parameter: {name}'
            assert int(cocotb.top.PARITY_WIDTH.value) == config.parity_width
            assert int(cocotb.top.CODE_WIDTH.value) == config.code_width
        config.coverage_file.unlink(missing_ok=True)
        ConfigDB().set(self, 'env.*', 'config', config)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, quiet=set(), sample=Event()))
        self.env = ParityEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await ParitySequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
