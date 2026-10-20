"""PyUVM entry point for complete byte-window and elastic-interface validation."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from data_aligner.config import AlignerConfig
from data_aligner.env import AlignerEnv
from data_aligner.sequences import AlignerSequence
from data_aligner.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class DataAlignerTest(uvm_test):
    def build_phase(self):
        config = self.config = AlignerConfig.from_environment()
        for name, width in config.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong interface width: {name}'
        if config.check_internals:
            for name, value in config.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong elaborated parameter: {name}'
        config.coverage_file.unlink(missing_ok=True)
        ConfigDB().set(self, 'env.*', 'config', config)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, quiet=set(), sample=Event()))
        self.env = AlignerEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await AlignerSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
