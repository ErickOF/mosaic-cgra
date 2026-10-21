"""Run the actual decorated PyUVM test with checked elaboration and evidence."""
import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from dot_product.config import DotProductConfig
from dot_product.env import DotProductEnv
from dot_product.sequences import DotProductSequence
from dot_product.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class DotProductTest(uvm_test):
    def build_phase(self):
        c = self.config = DotProductConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        if c.check_internals:
            for name, value in c.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong parameter: {name}'
            for name, value in (('PRODUCT_WIDTH', 2 * c.element),
                                ('REDUCTION_WIDTH', c.reduction_width),
                                ('ACTIVE_COUNT_WIDTH', c.count_width)):
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong derived width: {name}'
            assert hasattr(cocotb.top.g_datapath, 'g_accumulation') == bool(c.accumulate)
            assert hasattr(cocotb.top.g_datapath, 'g_saturation') == bool(c.saturation)
        if c.hdl_assertions:
            assert hasattr(cocotb.top.g_datapath, 'u_assertions'), 'HDL checker missing'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active',
                       dict(item=None, window='initial', sample=Event(), internals={}))
        self.env = DotProductEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await DotProductSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
