"""Drive ordinary schedule edges and declare per-bit storage hold obligations."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from rdu.model import fields, known
from rdu.transaction import INPUTS, OUTPUTS


class RduDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')

    async def sample(self, stage):
        self.active['stage'] = stage
        self.active['sample'].set()
        await ReadOnly()
        await Timer(1, unit='ps')
        assert not self.active['sample'].is_set(), f'Monitor missed {stage} sample'

    def edge_quiet(self, item):
        config, ports = self.config, item.ports
        slots = max(1, config.total)
        data_mask = (1 << (slots*config.width)) - 1
        valid_mask = (1 << slots) - 1
        if not item.edge:
            return dict(delay_data=data_mask, delay_valid=valid_mask)
        if ports['i_rstb'] == '0':
            return dict(delay_data=data_mask, delay_valid=0 if config.total else valid_mask)
        previous = item.pre.internals.get('delay_valid', '0'*slots)
        for c, word in enumerate(fields(ports['i_delay'], config.delay_width)):
            capacity, base = config.capacities[c], config.bases[c]
            if ports['i_flush'][-c-1] == '1':
                valid_mask &= ~(((1 << capacity)-1) << base)
            elif ports['i_channel_enable'][-c-1] == '1' and ports['i_advance'] == '1' and known(word) and int(word, 2) <= capacity:
                for stage in range(int(word, 2)):
                    entry = base + stage
                    valid_mask &= ~(1 << entry)
                    source_valid = ports['i_input_valid'][-c-1] if stage == 0 else previous[-entry]
                    if source_valid == '1':
                        data_mask &= ~(((1 << config.width)-1) << (entry*config.width))
        return dict(delay_data=data_mask, delay_valid=valid_mask)

    async def run_phase(self):
        await Timer(4, unit='ps')
        slots = max(1, self.config.total)
        state_quiet = dict(delay_data=(1 << (slots*self.config.width))-1, delay_valid=(1 << slots)-1)
        while True:
            item = await self.seq_item_port.get_next_item()
            quiet = state_quiet.copy()
            if self.config.asynchronous and item.ports['i_rstb'] != '1' and self.config.total:
                quiet['delay_valid'] = 0
            self.active.update(item=item, quiet=quiet)
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            await Timer(2, unit='ps')
            await self.sample('pre')
            self.active['quiet'] = self.edge_quiet(item)
            if item.edge:
                cocotb.top.i_clk.value = 1
            await Timer(2, unit='ps')
            await self.sample('post')
            self.active['quiet'] = state_quiet | {name: (1 << self.config.widths[name])-1 for name in OUTPUTS}
            await Timer(10, unit='ps')
            await self.sample('held')
            cocotb.top.i_clk.value = 0
            await Timer(1, unit='ps')
            self.seq_item_port.item_done()
