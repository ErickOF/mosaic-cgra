"""Drive operands between virtual clock edges without adding a DUT clock port."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from stream_join.transaction import INPUTS, OUTPUTS


class StreamJoinDriver(uvm_driver):
    def build_phase(self):
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
            self.active.update(item=item, quiet=set(OUTPUTS) if item.quiet else set())
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            await Timer(2, unit='ps')
            await self.sample('pre')
            self.active['quiet'] = set(OUTPUTS)
            if item.pulse:
                name, value = item.pulse
                getattr(cocotb.top, name).value = value
                await Timer(1, unit='ps')
                getattr(cocotb.top, name).value = item.ports[name]
                await Timer(1, unit='ps')
            if item.edge:
                # The passive monitor reads real ports at this logical clock
                # edge. The combinational RTL itself has no clock or storage.
                self.active['tick'].set()
                await ReadOnly()
                await Timer(1, unit='ps')
                assert not self.active['tick'].is_set(), 'Monitor missed a sampling edge'
            await self.sample('post')
            await Timer(10, unit='ps')
            await self.sample('held')
            self.seq_item_port.item_done()
