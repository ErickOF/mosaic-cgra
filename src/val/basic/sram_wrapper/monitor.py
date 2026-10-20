"""Observe public traffic, physical backend issue/maturity and committed storage."""
import cocotb
from cocotb.triggers import ReadOnly,RisingEdge,Timer
from pyuvm import ConfigDB,uvm_analysis_port,uvm_monitor
from mosaic_uvm.logic import logic
from sram_wrapper.transaction import INPUTS,OUTPUTS,BACKEND,STATE,Observation,Activity


class SramMonitor(uvm_monitor):
    def build_phase(self):
        self.config=ConfigDB().get(self,'','config');self.active=ConfigDB().get(self,'','active')
        self.ap=uvm_analysis_port('ap',self)

    def observe(self,stage):
        item=self.active['item']
        obs=Observation({name:logic(getattr(cocotb.top,name)) for name in (*INPUTS,*OUTPUTS)},
            {name:logic(handle) for name,handle in self.active['internals'].items()},item,stage)
        self.ap.write(obs);item.observation=obs
        if stage=='pre':item.pre=obs

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk);self.observe('edge')

    async def watch(self,name,handle):
        previous=logic(handle)
        while True:
            await handle.value_change
            forbidden=name in self.active['quiet']
            await ReadOnly();current=logic(handle)
            if current!=previous:
                self.ap.write(Activity(name,forbidden));previous=current

    async def run_phase(self):
        await Timer(2,unit='ps');await ReadOnly()
        c=self.config
        if c.check_internals:
            shell=cocotb.top.g_shell
            memory=getattr(shell.u_backend,'g_inferred' if c.backend=='inferred' else 'g_reference').memory
            self.active['internals'].update({name:getattr(shell,name) for name in (*BACKEND,*STATE)})
            self.active['internals'].update({f'mem_{i}':memory[i] for i in range(c.depth)})
            self.active['internals'].update({f'rsp_{i}':shell.responses[i] for i in range(c.credits)})
            self.active['internals'].update({f'tag_{i}':shell.g_tag[i].u_tag.o_q for i in range(c.latency+1)})
        handles={name:getattr(cocotb.top,name) for name in (*INPUTS,*OUTPUTS)}|self.active['internals']
        tasks=[cocotb.start_soon(self.edges())]
        tasks.extend(cocotb.start_soon(self.watch(name,handle)) for name,handle in handles.items())
        try:
            while True:
                await self.active['sample'].wait();await ReadOnly()
                self.observe(self.active['stage']);self.active['sample'].clear()
        finally:
            for task in tasks:task.cancel()
