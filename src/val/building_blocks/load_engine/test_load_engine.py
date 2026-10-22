"""Run the decorated PyUVM environment against the actual load_engine top."""
import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from load_engine.config import LoadEngineConfig
from load_engine.env import LoadEngineEnv
from load_engine.sequences import LoadEngineSequence
from load_engine.transaction import INPUTS


@test(timeout_time=20, timeout_unit='ms')
class LoadEngineTest(uvm_test):
    def build_phase(self):
        c = self.config = LoadEngineConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong port width: {name}'
        if c.check_internals:
            for name, value in c.parameters.items():
                assert int(getattr(cocotb.top, name).value) == value, f'Wrong parameter: {name}'
        if c.hdl_assertions:
            assert hasattr(cocotb.top.g_engine, 'u_assertions'), 'HDL checker missing'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, window='initial', sample=Event(), storage={},
                           check_internals=c.check_internals, slots=c.MAX_OUTSTANDING))
        self.env = LoadEngineEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS:
            getattr(cocotb.top, name).value = 0
        await LoadEngineSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ns')
        self.drop_objection()
