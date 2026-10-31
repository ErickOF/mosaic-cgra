"""PyUVM entry point for actual System-RTL and its generated array source closure."""
import sys
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[2]),str(Path(__file__).resolve().parents[1]),
    str(Path(__file__).resolve().parents[3]/'gen/global_noc')]
import cocotb
from cocotb.triggers import Event
from pyuvm import ConfigDB, test, uvm_test
from mosaic_blocks.system.config import SystemConfig
from mosaic_blocks.system.env import SystemEnv
from mosaic_blocks.system.sequences import SystemSequence

@test(timeout_time=100,timeout_unit='ms')
class SystemTest(uvm_test):
    def build_phase(self):
        self.c=SystemConfig.from_environment()
        self.c.coverage_file.unlink(missing_ok=True)
        for name,(_,width) in self.c.ports.items():
            assert len(getattr(cocotb.top,name))==width,(name,width)
        active=dict(pre=Event(),post=Event(),reset_count=0,fault_mode=False)
        ConfigDB().set(self,'env.*','config',self.c)
        ConfigDB().set(self,'env.*','active',active)
        self.env=SystemEnv('env',self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value=0
        await SystemSequence(self.c,self.env.coverage).start(self.env.sequencer)
        self.drop_objection()
