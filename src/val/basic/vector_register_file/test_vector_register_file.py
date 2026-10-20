"""Decorated PyUVM test with exact interface and optional geometry checks."""

import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from vector_register_file.config import VectorRegisterFileConfig
from vector_register_file.env import VectorRegisterFileEnv
from vector_register_file.sequences import VectorRegisterFileSequence
from vector_register_file.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class VectorRegisterFileTest(uvm_test):
    def build_phase(self):
        config = self.config = VectorRegisterFileConfig.from_environment()
        config.coverage_file.unlink(missing_ok=True)
        for name, width in config.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong interface width: {name}'
        if config.check_internals:
            for name, value in (config.parameters | config.derived).items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong elaborated parameter: {name}'
            for lane in range(config.lanes):
                for s in range(config.slices_per_lane):
                    storage = cocotb.top.g_vector_file.g_lane[lane].g_slice[s].u_bank.g_register_file.registers
                    assert len(storage) == config.depth and len(storage[0]) == config.slice_width, 'Wrong bank geometry'
        ConfigDB().set(self, 'env.*', 'config', config)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, writable=set(), hold_output=False, sample=Event()))
        self.env = VectorRegisterFileEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await VectorRegisterFileSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
