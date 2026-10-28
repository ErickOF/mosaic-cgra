"""Drive the NoC clock independently of synchronous endpoint clock pins."""
import cocotb
from cocotb.triggers import Timer, ReadOnly
from cocotb.handle import Force, Release
from pyuvm import ConfigDB, uvm_driver
from global_noc.transaction import INPUTS

class NocDriver(uvm_driver):
    def build_phase(self):self.active=ConfigDB().get(self,'','active')

    async def run_phase(self):
        forced=None
        await Timer(1,unit='ns')
        while True:
            item=await self.seq_item_port.get_next_item()
            self.active['item']=item
            d=cocotb.top
            d.i_noc_clk.value=0
            if forced is not None:
                forced.value=Release()
                forced=None
            for name in INPUTS:getattr(d,name).value=item.ports[name]
            await Timer(2,unit='ns')
            if self.active.get('inject_parity') and not self.active.get('fault_applied'):
                router=d.g_noc.g_node[0].u_router
                valid=int(router.i_in_valid.value)
                if valid:
                    forced=router.i_in_parity
                    forced.value=Force(int(forced.value)^valid)
                    self.active['fault_applied']=True
            await Timer(2,unit='ns')
            d.i_noc_clk.value=1
            await Timer(4,unit='ns')
            self.active['sample'].set()
            await ReadOnly()
            await Timer(2,unit='ns')
            self.seq_item_port.item_done()
