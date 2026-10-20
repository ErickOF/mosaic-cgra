"""Decorated PyUVM test for the unit and actual payload/receiver fixture."""
import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from round_robin_arbiter.config import ArbiterConfig
from round_robin_arbiter.env import ArbiterEnv
from round_robin_arbiter.sequences import ArbiterSequence


@test(timeout_time=10, timeout_unit='ms')
class RoundRobinArbiterTest(uvm_test):
    def build_phase(self):
        c = self.config = ArbiterConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name, width in c.widths.items():
            assert len(getattr(cocotb.top, name)) == width, f'Wrong interface width: {name}'
        if c.check_internals:
            top = cocotb.top.u_arbiter if c.fixture else cocotb.top
            for name, value in (c.parameters | dict(INDEX_WIDTH=c.index_width)).items():
                assert int(getattr(top, name).value) == value, f'Wrong elaborated parameter: {name}'
        ConfigDB().set(self, 'env.*', 'config', c)
        ConfigDB().set(self, 'env.*', 'active', dict(item=None, quiet=set(), sample=Event(), internals={}, edge_window=False, pulse_owner=0))
        self.env = ArbiterEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in self.config.inputs: getattr(cocotb.top, name).value = 0
        await ArbiterSequence(self.config).start(self.env.sequencer)
        await Timer(1, unit='ps')
        await ReadOnly()
        self.drop_objection()
