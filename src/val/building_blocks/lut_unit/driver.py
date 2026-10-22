"""Drive real clock edges and optional verification-only state corruption."""
import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from lut_unit.transaction import INPUTS


class LutUnitDriver(uvm_driver):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')

    async def sample(self, stage):
        self.active['stage'] = stage
        self.active['sample'].set()
        await ReadOnly()
        await Timer(1, unit='ps')
        assert not self.active['sample'].is_set(), f'Missed {stage}'

    async def run_phase(self):
        await Timer(4, unit='ns')
        while True:
            item = await self.seq_item_port.get_next_item()
            self.active['item'] = item
            self.active['window'] = 'inputs'
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            if item.fault:
                kind, bank, address, mask = item.fault
                unit = cocotb.top.g_unit
                if kind == 'table':
                    handle = unit.g_bank[bank].u_table.memory[address]
                elif kind == 'metadata':
                    handle = unit.g_bank[bank].u_metadata.u_data.o_q
                else:
                    handle = unit.u_results.u_metadata.u_data.o_q
                handle.value = int(handle.value) ^ mask
            await Timer(2, unit='ns')
            await self.sample('pre')
            self.active['window'] = 'edge' if item.edge else 'hold'
            if item.edge:
                cocotb.top.i_clk.value = 1
            await Timer(2, unit='ns')
            await self.sample('post')
            self.active['window'] = 'hold'
            await Timer(3, unit='ns')
            await self.sample('held')
            cocotb.top.i_clk.value = 0
            await Timer(3, unit='ns')
            self.seq_item_port.item_done()
