"""Run the decorated PyUVM test against the unclocked ALU top."""

import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from scalar_alu.config import AluConfig
from scalar_alu.env import AluEnv
from scalar_alu.sequences import AluSequence
from scalar_alu.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class ScalarAluTest(uvm_test):
    def build_phase(self):
        c = self.config = AluConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        if c.check_internals:
            for name, value in c.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong parameter: {name}'
            core = cocotb.top.g_datapath
            assert int(cocotb.top.SHIFT_WIDTH.value) == max(1, (c.width - 1).bit_length())
            assert hasattr(core, 'g_saturation') == bool(c.saturation)
            assert hasattr(core, 'g_minmax') == bool(c.minmax)
        if c.hdl_assertions:
            assert hasattr(cocotb.top.g_datapath, 'u_assertions'), 'Native HDL checker missing'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, sample=Event()))
        self.env = AluEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await AluSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        self.drop_objection()
