"""Read actual pre-NBA edge and settled ports without consulting driver values."""
import cocotb
from cocotb.triggers import ReadOnly,RisingEdge,Timer
from pyuvm import ConfigDB,uvm_monitor,uvm_analysis_port
from mosaic_uvm.logic import logic
from dma_engine.constants import INPUTS,OUTPUTS
from dma_engine.transaction import Observation


class DmaMonitor(uvm_monitor):
    def build_phase(self):
        self.active=ConfigDB().get(self,'','active');self.ap=uvm_analysis_port('ap',self)
        self.c=ConfigDB().get(self,'','config')

    def observe(self,stage):
        item=self.active['item']
        internals={}
        if self.c.check_internals:
            for name in ('bytes_read','bytes_written'):
                handles=getattr(cocotb.top.g_dma,name)
                internals[name]=tuple(logic(handles[ch]) for ch in range(self.c.NUM_CHANNELS))
        obs=Observation({name:logic(getattr(cocotb.top,name)) for name in (*INPUTS,*OUTPUTS)},item,stage,internals)
        self.ap.write(obs);item.observation=obs
        if stage=='pre':item.pre=obs

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk);self.observe('edge')

    async def storage(self,name,handle):
        while True:
            await handle.value_change
            window=self.active.get('window','initial')
            allowed=window in ('initial','edge') or (self.c.ASYNC_RESET and logic(cocotb.top.i_rstb)=='0')
            assert allowed,f'DMA between-edge storage assertion: {name}'

    async def run_phase(self):
        await Timer(2,unit='ps');await ReadOnly()
        task=cocotb.start_soon(self.edges())
        watchers=[]
        if self.c.check_internals:
            for ch in range(self.c.NUM_CHANNELS):
                scope=cocotb.top.g_dma.g_channel[ch]
                for name in ('source_count','destination_count'):
                    watchers.append(cocotb.start_soon(self.storage(f'{name}[{ch}]',getattr(scope,name))))
                for name in ('phase','bytes_read','bytes_written'):
                    watchers.append(cocotb.start_soon(self.storage(f'{name}[{ch}]',getattr(cocotb.top.g_dma,name)[ch])))
        try:
            while True:
                await self.active['sample'].wait();await ReadOnly()
                self.observe(self.active['stage']);self.active['sample'].clear()
        finally:
            task.cancel()
            for watcher in watchers:watcher.cancel()
