"""Run the decorated PyUVM test and check the actual multiplier elaboration."""
import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from multiplier.config import MultiplierConfig
from multiplier.env import MultiplierEnv
from multiplier.sequences import MultiplierSequence
from multiplier.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class MultiplierTest(uvm_test):
    def build_phase(self):
        c = self.config = MultiplierConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        if c.check_internals:
            for name, value in c.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong parameter: {name}'
            assert int(cocotb.top.PRODUCT_WIDTH.value) == c.product_width
            assert hasattr(cocotb.top.g_datapath, 'g_pipeline') == bool(c.latency)
        if c.hdl_assertions:
            assert hasattr(cocotb.top.g_datapath, 'u_assertions'), 'HDL checker missing'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active',
                       dict(item=None, window='initial', sample=Event(), internals={}))
        self.env = MultiplierEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await MultiplierSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
