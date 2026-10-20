"""Drive setup, edge, settled and held intervals with explicit hold obligations."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from stream_fork.transaction import INPUTS, OUTPUTS
from stream_fork.model import lane


class StreamForkDriver(uvm_driver):
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
            quiet = {'o_valid', 'o_data'} | internals
            if self.config.asynchronous and item.ports['i_rstb'] != '1':
                quiet = {'fork_data'}
            self.active.update(item=item, quiet=quiet, held_lanes={})
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            await Timer(2, unit='ps')
            await self.sample('pre')
            if item.ports['i_rstb'] == '1':
                self.active['held_lanes'] = {k: lane(item.pre.ports['o_data'], k, self.config.width)
                    for k in range(self.config.outputs) if item.pre.ports['o_valid'][-k-1] == '1'
                    and item.ports['i_ready'][-k-1] == '0'}
            quiet = set(OUTPUTS) | internals
            if item.edge:
                quiet = set()
                accepted = item.ports['i_rstb'] == '1' and item.ports['i_valid'] == '1' and item.pre.ports['o_ready'] == '1'
                if not accepted:
                    quiet.add('fork_data')
                if item.ports['i_rstb'] == '1' and item.pre.ports['o_valid'].count('1') == 0 and not accepted:
                    quiet |= set(OUTPUTS) | internals
            self.active['quiet'] = quiet
            if item.edge:
                cocotb.top.i_clk.value = 1
            await Timer(2, unit='ps')
            await self.sample('post')
            self.active['quiet'] = set(OUTPUTS) | internals
            if item.pulse:
                await Timer(2, unit='ps')
                cocotb.top.i_data.value = int(item.ports['i_data'], 2) ^ 1
                await Timer(1, unit='ps')
                cocotb.top.i_data.value = item.ports['i_data']
            await Timer(10, unit='ps')
            await self.sample('held')
            cocotb.top.i_clk.value = 0
            await Timer(1, unit='ps')
            self.seq_item_port.item_done()
