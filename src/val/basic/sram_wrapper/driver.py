"""Drive setup, real acceptance edges and continuous low-activity hold windows."""
import cocotb
from cocotb.triggers import ReadOnly,Timer
from pyuvm import ConfigDB,uvm_driver
from sram_wrapper.transaction import INPUTS,OUTPUTS


class SramDriver(uvm_driver):
    def build_phase(self):
        self.config=ConfigDB().get(self,'','config')
        self.active=ConfigDB().get(self,'','active')

    async def sample(self,stage):
        self.active['stage']=stage;self.active['sample'].set()
        await ReadOnly();await Timer(1,unit='ps')
        assert not self.active['sample'].is_set(),f'Monitor missed {stage} sample'

    async def run_phase(self):
        await Timer(4,unit='ps')
        while True:
            item=await self.seq_item_port.get_next_item()
            raw=set(self.active['internals'])
            quiet={name for name in raw if not name.startswith('backend_')}
            if self.config.asynchronous and item.ports['i_rstb']=='0':
                quiet={name for name in raw if name.startswith(('mem_','rsp_'))}
            self.active.update(item=item,quiet=quiet)
            for name in INPUTS:getattr(cocotb.top,name).value=item.ports[name]
            await Timer(2,unit='ps');await self.sample('pre')
            if item.edge:
                quiet={name for name in raw if name.startswith(('mem_','rsp_'))}
                if self.active['memory_write'] is not None:quiet.discard(f'mem_{self.active["memory_write"]}')
                if self.active['response_write'] is not None:quiet.discard(f'rsp_{self.active["response_write"]}')
            else:quiet=raw|set(OUTPUTS)
            self.active['quiet']=quiet
            if item.edge:cocotb.top.i_clk.value=1
            await Timer(2,unit='ps');await self.sample('post')
            self.active['quiet']=raw|set(OUTPUTS)
            if item.pulse:
                await Timer(2,unit='ps')
                cocotb.top.i_req_addr.value=int(item.ports['i_req_addr'],2)^1
                await Timer(1,unit='ps');cocotb.top.i_req_addr.value=item.ports['i_req_addr']
            await Timer(10,unit='ps');await self.sample('held')
            cocotb.top.i_clk.value=0
            await Timer(1,unit='ps');self.seq_item_port.item_done()
