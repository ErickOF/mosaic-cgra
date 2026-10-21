"""Run exactly one decorated PyUVM test against the requested elaborated geometry."""
import cocotb
from cocotb.triggers import Event, ReadOnly, Timer
from pyuvm import ConfigDB, test, uvm_test
from agu.config import AguConfig
from agu.env import AguEnv
from agu.sequences import AguSequence
from agu.transaction import INPUTS


@test(timeout_time=1, timeout_unit='ms')
class AguTest(uvm_test):
    def build_phase(self):
        c = self.config = AguConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name,width in c.widths.items():
            assert len(getattr(cocotb.top,name))==width, f'Wrong port width: {name}'
        if c.check_internals:
            for name,value in c.parameters.items():
                assert int(getattr(cocotb.top,name).value)==value, f'Wrong parameter: {name}'
            assert int(cocotb.top.ELEMENT_SIZE_WIDTH.value)==c.size_width
            assert int(cocotb.top.ACCEPTED_COUNT_WIDTH.value)==2*c.count
        if c.hdl_assertions:
            assert hasattr(cocotb.top.g_sequence,'u_assertions'), 'HDL checker missing'
        ConfigDB().set(self,'env.*','config',c)
        ConfigDB().set(self,'env.*','active',dict(item=None,window='initial',sample=Event(),internals={}))
        self.env = AguEnv('env',self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for name in INPUTS: getattr(cocotb.top,name).value = 0
        await AguSequence(self.config).start(self.env.sequencer)
        await Timer(1,unit='ps')
        await ReadOnly()
        self.drop_objection()
