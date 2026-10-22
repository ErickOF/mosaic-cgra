"""Run the decorated PyUVM test and verify actual elaboration before stimulus."""
import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from mac.config import MacConfig
from mac.env import MacEnv
from mac.sequences import MacSequence
from mac.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class MacTest(uvm_test):
    def build_phase(self):
        c = self.config = MacConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        if c.check_internals:
            for name, value in c.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong parameter: {name}'
            assert int(cocotb.top.PRODUCT_WIDTH.value) == 2 * c.operand
            core = cocotb.top.g_mac.u_core.g_datapath
            assert len(core.g_accumulation.exact_sum) == c.width + 1
            assert hasattr(core, 'g_saturation') == bool(c.saturation)
            assert hasattr(core, 'g_product_controls') == (c.latency >= 2)
        if c.hdl_assertions:
            assert hasattr(cocotb.top.g_mac, 'u_assertions'), 'HDL checker missing'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active',
                       dict(item=None, window='initial', sample=Event(), internals={}))
        self.env = MacEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await MacSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
