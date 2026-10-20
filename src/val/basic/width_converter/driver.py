"""Drive actual clock edges with bit-specific storage write permissions."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from width_converter.model import known
from width_converter.transaction import INPUTS, OUTPUTS, STORAGE


class WidthConverterDriver(uvm_driver):
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
        c = self.config
        while True:
            item = await self.seq_item_port.get_next_item()
            internals = set(self.active['internals'])
            self.active.update(item=item, quiet={'o_data', 'o_keep', 'o_user', 'o_last', 'o_valid'} | internals,
                writable_bits=set())
            # Cancellation can clamp outputs and asynchronously clear controls.
            if item.ports['i_rstb'] != '1' or item.ports['i_flush'] != '0' or self.active['cancelled']:
                self.active['quiet'] = set(STORAGE)
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            await Timer(2, unit='ps')
            await self.sample('pre')
            quiet = set(OUTPUTS) | internals
            if item.edge:
                quiet = set(STORAGE)
                p = item.pre.ports
                if p['i_valid'] == p['o_ready'] == '1':
                    quiet -= {'buffered_keep', 'buffered_last'}
                    position = self.active['position']
                    if c.mode != 'pack' or position == 0:
                        quiet.discard('buffered_user')
                    if known(p['i_keep']):
                        offset = (position if c.lsb_first else c.ratio-1-position)*c.in_units if c.mode == 'pack' else 0
                        self.active['writable_bits'] = {((offset+k)*c.unit_width+b)
                            for k in range(c.in_units) if p['i_keep'][-k-1] == '1' for b in range(c.unit_width)}
                    quiet.discard('buffered_data')
                self.active['quiet'] = quiet
                cocotb.top.i_clk.value = 1
            await Timer(2, unit='ps')
            await self.sample('post')
            self.active.update(quiet=set(OUTPUTS) | internals, writable_bits=set())
            if item.pulse:
                handle = getattr(cocotb.top, item.pulse)
                original = item.ports[item.pulse]
                await Timer(2, unit='ps')
                handle.value = int(original, 2) ^ 1
                await Timer(1, unit='ps')
                handle.value = original
            await Timer(10, unit='ps')
            await self.sample('held')
            self.active['cancelled'] = item.ports['i_rstb'] != '1' or item.ports['i_flush'] != '0'
            cocotb.top.i_clk.value = 0
            await Timer(1, unit='ps')
            self.seq_item_port.item_done()
