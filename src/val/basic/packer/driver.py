"""Coordinate pre-edge, post-edge and held samples without sampling predictions."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from mosaic_uvm.logic import logic
from packer.model import isolated_input
from packer.transaction import FIELDS, INPUTS, OUTPUTS


class PackerDriver(uvm_driver):
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
        private = {'stored_valid', 'stored_result'} if self.config.registered else set()
        while True:
            item = await self.seq_item_port.get_next_item()
            old = {name: logic(getattr(cocotb.top, name)) for name in INPUTS}
            quiet = set() if self.config.asynchronous and item.ports['i_rstb'] != '1' else set(private)
            if self.config.registered and old['i_rstb'] == item.ports['i_rstb'] == '1' and old['i_flush'] == item.ports['i_flush'] == '0':
                quiet.update((*FIELDS, 'o_any_overflow', 'o_any_saturated', 'o_busy', 'o_valid'))
            if isolated_input(self.config, old) == isolated_input(self.config, item.ports):
                quiet.add('isolated_data')
            self.active.update(item=item, quiet=quiet)
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            await Timer(2, unit='ps')
            await self.sample('pre')
            quiet = set(OUTPUTS) | private | {'isolated_data'}
            if item.edge:
                quiet = {'isolated_data'}
                if self.config.registered and item.ports['i_rstb'] == '1':
                    accept = item.ports['i_valid'] == '1' and item.pre.ports['o_ready'] == '1'
                    if not accept:
                        quiet.add('stored_result')
                    if item.pre.ports['o_valid'] == '1' and item.ports['i_ready'] == '0' and item.ports['i_flush'] == '0':
                        quiet.update((*FIELDS, 'o_any_overflow', 'o_any_saturated', 'o_valid', 'o_busy', 'stored_valid'))
                if not self.config.registered:
                    quiet.update(OUTPUTS)
            self.active['quiet'] = quiet
            if item.edge:
                cocotb.top.i_clk.value = 1
            await Timer(2, unit='ps')
            await self.sample('post')
            self.active['quiet'] = set(OUTPUTS) | private | {'isolated_data'}
            await Timer(10, unit='ps')
            await self.sample('held')
            cocotb.top.i_clk.value = 0
            await Timer(1, unit='ps')
            self.seq_item_port.item_done()
