"""Exercise production routers/TNIs through public endpoints with PyUVM."""
import cocotb
from cocotb.triggers import Event, Timer
from pyuvm import ConfigDB, test, uvm_test
from global_noc.config import NocConfig
from global_noc.env import NocEnv
from global_noc.sequences import NocSequence
from global_noc.transaction import INPUTS

@test(timeout_time=100,timeout_unit='ms')
class GlobalNocTest(uvm_test):
    def build_phase(self):
        c=self.c=NocConfig.from_environment()
        c.coverage_file.unlink(missing_ok=True)
        for name,width in c.widths.items():
            assert len(getattr(cocotb.top,name))==width,('Wrong port width',name,width)
        for name,value in c.parameters.items():
            assert int(getattr(cocotb.top,name).value)==value,('Wrong parameter',name)
        ConfigDB().set(self,'env.*','config',c)
        ConfigDB().set(self,'env.*','active',dict(item=None,sample=Event()))
        self.env=NocEnv('env',self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_noc_clk.value=0
        for name in INPUTS:getattr(cocotb.top,name).value=0
        sequence=NocSequence(self.c)
        sequence.coverage=self.env.coverage
        sequence.active=ConfigDB().get(self,'env.agent','active')
        await sequence.start(self.env.sequencer)
        await Timer(1,unit='ns')
        self.drop_objection()
