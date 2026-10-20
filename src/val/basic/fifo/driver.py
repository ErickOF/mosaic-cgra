"""Set up inputs while low, sample before/after the edge, then hold quiet."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from fifo.transaction import INPUTS, OUTPUTS


class FifoDriver(uvm_driver):
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
            internals = set(self.active['internals'])
            quiet = (set(OUTPUTS) - {'o_ready'}) | internals
            if self.config.asynchronous and item.ports['i_rstb'] != '1':
                quiet = {name for name in internals if name.startswith('memory:')}
            self.active.update(item=item, quiet=quiet)
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            await Timer(2, unit='ps')
            await self.sample('pre')
            # Reset never writes storage; a real push may update just one entry.
            quiet = {name for name in internals if name.startswith('memory:')}
            if not item.edge:
                quiet = set(OUTPUTS) | internals
            elif item.ports['i_rstb'] == '1':
                push = item.ports['i_valid'] == '1' and item.pre.ports['o_ready'] == '1'
                pop = item.pre.ports['o_valid'] == '1' and item.ports['i_ready'] == '1'
                if push and self.config.check_internals:
                    quiet.discard(f"memory:{int(item.pre.internals['write_pointer'], 2)}")
                if not push:
                    quiet.add('write_pointer')
                if not pop:
                    quiet.add('read_pointer')
                if push == pop:
                    quiet.update(set(OUTPUTS) - {'o_data'})
                if not pop and item.pre.ports['o_valid'] == '1':
                    quiet.add('o_data')
            self.active['quiet'] = quiet
            if item.edge:
                cocotb.top.i_clk.value = 1
            await Timer(2, unit='ps')
            await self.sample('post')
            self.active['quiet'] = set(OUTPUTS) | internals
            await Timer(10, unit='ps')
            await self.sample('held')
            cocotb.top.i_clk.value = 0
            await Timer(1, unit='ps')
            self.seq_item_port.item_done()
