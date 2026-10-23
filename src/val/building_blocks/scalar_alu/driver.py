"""Drive purely combinational requests and two stable observation windows."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from scalar_alu.transaction import INPUTS


class AluDriver(uvm_driver):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')

    async def sample(self, stage):
        self.active['stage'] = stage
        self.active['sample'].set()
        await ReadOnly()
        await Timer(1, unit='ps')
        assert not self.active['sample'].is_set(), f'Monitor missed {stage}'

    async def run_phase(self):
        await Timer(4, unit='ps')
        while True:
            item = await self.seq_item_port.get_next_item()
            self.active['item'] = item
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            if self.c.settle_ns:
                await Timer(self.c.settle_ns, unit='ns')
            else:
                await Timer(2, unit='ps')
            await self.sample('settled')
            await Timer(3, unit='ps')
            await self.sample('held')
            self.seq_item_port.item_done()
