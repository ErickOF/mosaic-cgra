"""Sample real public transfers before NBA updates and settled outputs after."""
import cocotb
from cocotb.triggers import RisingEdge, ReadOnly
from pyuvm import ConfigDB, uvm_monitor, uvm_analysis_port
from global_noc.transaction import INPUTS, OUTPUTS, Observation
from global_noc_contract import FLIT_FIELDS

def number(handle):
    try:return int(handle.value)
    except ValueError:return None

class NocMonitor(uvm_monitor):
    def build_phase(self):
        self.active=ConfigDB().get(self,'','active')
        self.ap=uvm_analysis_port('ap',self)
        self.c=ConfigDB().get(self,'','config')
        self.routers=[cocotb.top.g_noc.g_node[n].u_router for n in range(self.c.a['NN'])]

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_noc_clk)
            p={n:number(getattr(cocotb.top,n)) for n in (*INPUTS,*OUTPUTS)}
            item=self.active['item']
            item.pre=p
            transfers=[]
            credit_events=[]
            a=self.c.a
            if p['i_noc_rstb']==1 and not p['o_flushing']:
                for n,r in enumerate(self.routers):
                    valid=number(r.o_out_valid) or 0
                    if self.c.parameters['FLOW_CONTROL']==0:valid &= number(r.i_out_ready) or 0
                    if valid:
                        fields={k:number(getattr(r,'o_out_'+k)) for k in FLIT_FIELDS}
                        for port in range(5):
                            if valid>>port&1:
                                f={k:v>>(port*(int(w) if w.isdigit() else a[w]))&
                                    ((1<<(int(w) if w.isdigit() else a[w]))-1)
                                    for k,v in fields.items() for w in (FLIT_FIELDS[k],)}
                                transfers.append((n,port,f))
                    returns=number(r.i_out_credit_valid) or 0
                    if returns:
                        vcs=number(r.i_out_credit_vc)
                        epochs=number(r.i_out_credit_epoch)
                        for port in range(5):
                            if returns>>port&1:
                                credit_events.append((n,port,vcs>>(port*a['VW'])&
                                    ((1<<a['VW'])-1),epochs>>(port*a['E'])&((1<<a['E'])-1)))
            self.ap.write(Observation(p,item,transfers,credit_events))

    async def run_phase(self):
        task=cocotb.start_soon(self.edges())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.active['item'].post={n:number(getattr(cocotb.top,n)) for n in OUTPUTS}
                self.active['sample'].clear()
        finally:task.cancel()
