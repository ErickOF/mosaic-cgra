"""Decorated PyUVM DMA entry point with exact interface geometry checks."""
import os
import cocotb
from cocotb.triggers import Event,ReadOnly,Timer
from pyuvm import ConfigDB,test,uvm_test
from dma_engine.config import DmaConfig
from dma_engine.constants import INPUTS
from dma_engine.env import DmaEnv
from dma_engine.sequences import DmaSequence


@test(timeout_time=1,timeout_unit='ms')
class DmaEngineTest(uvm_test):
    def build_phase(self):
        c=self.config=DmaConfig.from_environment();c.coverage_file.unlink(missing_ok=True)
        for name,width in c.widths.items():assert len(getattr(cocotb.top,name))==width,f'Wrong DMA port width: {name}'
        for name,value in c.parameters.items():assert int(getattr(cocotb.top,name).value)==value,f'Wrong DMA parameter: {name}'
        ConfigDB().set(self,'env.*','config',c)
        ConfigDB().set(self,'env.*','active',dict(item=None,stage='',sample=Event()))
        if os.getenv('DMA_ENGINE_HDL_ASSERTIONS','0')=='1':
            assert hasattr(cocotb.top.g_dma.g_channel[0],'u_assertions'),'DMA HDL checker missing'
        else:
            assert not hasattr(cocotb.top.g_dma.g_channel[0], 'u_assertions'), (
                'DMA HDL checker must be absent for a Python-only run'
            )
        self.env=DmaEnv('env',self)

    async def run_phase(self):
        self.raise_objection();cocotb.top.i_clk.value=0
        for name in INPUTS:getattr(cocotb.top,name).value=0
        await DmaSequence(self.config).start(self.env.sequencer)
        await Timer(1,unit='ps');await ReadOnly();self.drop_objection()
