"""Set payload before each edge, then check pre-edge, post-edge and quiet hold."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from mosaic_uvm.logic import logic
from data_aligner.model import isolated_window
from data_aligner.transaction import FIELDS, INPUTS, OUTPUTS


class AlignerDriver(uvm_driver):
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
        await Timer(6, unit='ps')
        private = {'stored_valid', 'stored_result'} if self.config.registered else set()
        while True:
            item = await self.seq_item_port.get_next_item()
            old = {name: logic(getattr(cocotb.top, name)) for name in INPUTS}
            reset = self.config.asynchronous and item.ports['i_rstb'] == '0'
            quiet = set() if reset else set(private)
            if self.config.registered and old['i_rstb'] == item.ports['i_rstb'] == '1' and old['i_flush'] == item.ports['i_flush'] == '0':
                quiet.update((*FIELDS, 'o_busy', 'o_valid'))
            if isolated_window(self.config, old) == isolated_window(self.config, item.ports):
                quiet.add('isolated_data')
            self.active.update(item=item, quiet=quiet)
            for name in INPUTS:
                if name != 'i_clk':
                    getattr(cocotb.top, name).value = item.ports[name]
            await Timer(1, unit='ps')
            await self.sample('pre')
            rising = old['i_clk'] == '0' and item.ports['i_clk'] == '1'
            self.active['quiet'] = set() if rising or reset else set(OUTPUTS) | private | {'isolated_data'}
            cocotb.top.i_clk.value = item.ports['i_clk']
            await Timer(1, unit='ps')
            await self.sample('post')
            self.active['quiet'] = set(OUTPUTS) | private | {'isolated_data'}
            await Timer(item.hold_ps, unit='ps')
            await self.sample('held')
            self.seq_item_port.item_done()
