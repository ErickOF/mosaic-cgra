"""Drive real clock opportunities and exact per-lane storage-write permissions."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from accumulator.transaction import INPUTS, OUTPUTS, PERSISTENT, RAW, RESPONSE


class AccumulatorDriver(uvm_driver):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')

    def permissions(self, ports, edge):
        c = self.config
        allow = {name:set() for name in (*OUTPUTS, *RAW)}
        if (edge or c.asynchronous) and ports['i_rstb'] == '0':
            for name in OUTPUTS:
                allow[name] = set(range(c.widths[name]))
        elif edge and ports['i_clock_enable'] == '1':
            for name in RESPONSE:
                allow[name] = set(range(c.widths[name]))
            selected = self.active['selected']
            initialize = ports['i_command'] in ('00', '01')
            word_bits = {k*c.width+b for k in selected for b in range(c.width)}
            allow['state_data'] = allow['o_data'] = word_bits
            if initialize:
                allow['state_signed'] = allow['o_state_signed'] = allow['o_state_valid'] = set(selected)
        return allow

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
            self.active.update(item=item, permissions=self.permissions(item.ports, False))
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            await Timer(2, unit='ps')
            await self.sample('pre')
            self.active['permissions'] = self.permissions(item.ports, item.edge)
            if item.edge:
                cocotb.top.i_clk.value = 1
            await Timer(2, unit='ps')
            await self.sample('post')
            self.active['permissions'] = {name:set() for name in (*OUTPUTS, *RAW)}
            if item.pulse:
                handle = getattr(cocotb.top, item.pulse)
                original = item.ports[item.pulse]
                await Timer(2, unit='ps')
                handle.value = (int(original, 2) ^ 1) if set(original) <= {'0', '1'} else '0'*len(original)
                await Timer(1, unit='ps')
                handle.value = original
            await Timer(6, unit='ps')
            await self.sample('held')
            cocotb.top.i_clk.value = 0
            await Timer(1, unit='ps')
            self.seq_item_port.item_done()
