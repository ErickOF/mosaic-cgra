"""Drive external commands and independent backend peers on one clock domain."""
import os
import cocotb
from cocotb.triggers import ReadOnly,Timer
from pyuvm import ConfigDB,uvm_driver
from mosaic_uvm.logic import bits
from dma_engine.constants import INPUTS
from dma_engine.backends import Backends


class DmaDriver(uvm_driver):
    def build_phase(self):
        self.c=ConfigDB().get(self,'','config');self.active=ConfigDB().get(self,'','active')
        self.backends=Backends(self.c)

    async def sample(self,stage):
        self.active['stage']=stage;self.active['sample'].set()
        await ReadOnly();await Timer(1,unit='ps')
        assert not self.active['sample'].is_set()

    async def run_phase(self):
        await Timer(4,unit='ps')
        while True:
            item=await self.seq_item_port.get_next_item()
            if os.getenv('DMA_ENGINE_TRACE'):self.logger.info('Drive %s',item.get_name())
            p=dict.fromkeys(INPUTS,0)
            p.update(i_rstb=1,i_completion_ready=1,i_event_ready=1)
            p.update(self.backends.prepare(item.options));p.update(item.ports)
            unknown=item.options.get('unknown_payload')
            if unknown:
                side,index,state=unknown
                peer=self.backends.load[0] if side=='load' else self.backends.owner[0]
                position=peer['index'] if side=='load' and peer else self.backends.tile_index[0]
                if peer and position==index:
                    name='i_load_stream_data' if side=='load' else 'i_stream_data'
                    word=bits(p[name],self.c.widths[name]);p[name]=word[:-8]+state*8
            item.ports={name:bits(value,self.c.widths[name]) for name,value in p.items()}
            self.active['item']=item
            self.active['window']='inputs'
            for name,value in item.ports.items():getattr(cocotb.top,name).value=value
            if item.options.get('corrupt_command'):
                channel,slot,bit=item.options['corrupt_command']
                memory=cocotb.top.g_dma.g_channel[channel].u_commands.u_fifo.g_fifo.memory
                memory[slot].value=int(memory[slot].value)^(1<<bit)
            await Timer(2,unit='ps');await self.sample('pre')
            self.active['window']='edge' if item.edge else 'hold'
            if item.edge:cocotb.top.i_clk.value=1
            await Timer(2,unit='ps');await self.sample('post')
            self.active['window']='hold'
            await Timer(3,unit='ps');await self.sample('held')
            if item.edge:self.backends.advance(item.pre.ports,item.observation.ports,item.options)
            elif item.ports['i_rstb']=='0' and self.c.ASYNC_RESET:self.backends.reset()
            cocotb.top.i_clk.value=0;await Timer(1,unit='ps')
            self.seq_item_port.item_done()
