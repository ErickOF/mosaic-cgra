"""Drive only real ports; sample before, after, and while holding each edge."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from performance_counters.transaction import INPUTS, OUTPUTS


class PerformanceCountersDriver(uvm_driver):
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
            state = {'live_counts', 'o_counter_overflow', 'o_threshold_event', 'o_snapshot_valid'}
            shadow = {'snapshot_counts', 'snapshot_overflow'}
            quiet = shadow | state
            if self.config.asynchronous and item.ports['i_rstb'] != '1':
                quiet = shadow
            self.active.update(item=item, quiet=quiet)
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            await Timer(2, unit='ps')
            await self.sample('pre')
            quiet = set() if item.edge else state | shadow
            if item.ports['i_snapshot'] == '0' or item.ports['i_rstb'] == '0':
                quiet |= shadow
            self.active['quiet'] = quiet
            if item.edge:
                cocotb.top.i_clk.value = 1
            await Timer(2, unit='ps')
            await self.sample('post')
            self.active['quiet'] = set(OUTPUTS) | set(self.active['internals'])
            await Timer(10, unit='ps')
            await self.sample('held')
            cocotb.top.i_clk.value = 0
            await Timer(1, unit='ps')
            self.seq_item_port.item_done()
