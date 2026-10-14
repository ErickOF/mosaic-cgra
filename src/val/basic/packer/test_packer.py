"""Decorated PyUVM entry point for complete conversion and stream validation."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from packer.config import PackerConfig
from packer.env import PackerEnv
from packer.sequences import PackerSequence
from packer.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class PackerTest(uvm_test):
    def build_phase(self):
        config = self.config = PackerConfig.from_environment()
        for name, width in config.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong interface width: {name}'
        if config.check_internals:
            for name, value in config.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong elaborated parameter: {name}'
            assert int(cocotb.top.IN_DATA_WIDTH.value) == config.elements * config.source_width
            assert int(cocotb.top.OUT_DATA_WIDTH.value) == config.elements * config.destination_width
        config.coverage_file.unlink(missing_ok=True)
        ConfigDB().set(self, 'env.*', 'config', config)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, quiet=set(), sample=Event()))
        self.env = PackerEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await PackerSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
