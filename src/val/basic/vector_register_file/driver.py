"""Drive setup, rising-edge, post-NBA and held observations without a reset."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from vector_register_file.model import legal_writes
from vector_register_file.transaction import INPUTS


class VectorRegisterFileDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')

    async def sample(self, stage):
        self.active['stage'] = stage
        self.active['sample'].set()
        await ReadOnly()
        await Timer(1, unit='ps')
        assert not self.active['sample'].is_set(), f'Monitor missed {stage} sample'

    async def run_phase(self):
        await Timer(4, unit='ps')
        while True:
            item = await self.seq_item_port.get_next_item()
            self.active.update(item=item, writable=set(), hold_output=item.quiet)
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            await Timer(2, unit='ps')
            await self.sample('pre')
            if item.edge:
                self.active['writable'] = {write.address*self.config.mask_width+s
                    for write in legal_writes(self.config, item.ports) for s in write.slices}
                self.active['hold_output'] = False
                cocotb.top.i_clk.value = 1
            await Timer(2, unit='ps')
            await self.sample('post')
            self.active.update(writable=set(), hold_output=True)
            await Timer(10, unit='ps')
            await self.sample('held')
            cocotb.top.i_clk.value = 0
            await Timer(1, unit='ps')
            self.seq_item_port.item_done()
