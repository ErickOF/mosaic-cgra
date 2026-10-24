"""Run the decorated PyUVM environment against the actual local_switch top."""
import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from local_switch.config import LocalSwitchConfig
from local_switch.env import LocalSwitchEnv
from local_switch.sequences import LocalSwitchSequence
from local_switch.transaction import INPUTS


@test(timeout_time=20, timeout_unit='ms')
class LocalSwitchTest(uvm_test):
    def build_phase(self):
        c = self.config = LocalSwitchConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        if c.check_internals:
            for name, value in c.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong parameter: {name}'
        if c.hdl_assertions:
            assert hasattr(cocotb.top.g_switch, 'u_assertions'), 'HDL checker missing'
        elif c.check_internals:
            assert not hasattr(cocotb.top.g_switch, 'u_assertions'), 'Expected Python-only checks'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, window='initial', sample=Event(), storage={},
                           check_internals=c.check_internals, inputs=c.NUM_INPUTS))
        self.env = LocalSwitchEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await LocalSwitchSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ns')
        self.drop_objection()
