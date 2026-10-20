"""Decorated PyUVM test with exact interface and optional geometry checks."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from register_file.config import RegisterFileConfig
from register_file.env import RegisterFileEnv
from register_file.sequences import RegisterFileSequence
from register_file.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class RegisterFileTest(uvm_test):
    def build_phase(self):
        config = self.config = RegisterFileConfig.from_environment()
        config.coverage_file.unlink(missing_ok=True)
        for name, width in config.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong interface width: {name}'
        if config.check_internals:
            derived = dict(ADDR_WIDTH=config.address_width, READ_ADDR_WIDTH=config.read_ports*config.address_width,
                WRITE_ADDR_WIDTH=config.write_ports*config.address_width, READ_DATA_WIDTH=config.read_ports*config.width,
                WRITE_DATA_WIDTH=config.write_ports*config.width)
            for name, value in (config.parameters | derived).items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong elaborated parameter: {name}'
            assert len(cocotb.top.g_register_file.registers) == config.depth, 'Wrong storage depth'
        ConfigDB().set(self, 'env.*', 'config', config)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, writable=set(), hold_output=False, sample=Event()))
        self.env = RegisterFileEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await RegisterFileSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
