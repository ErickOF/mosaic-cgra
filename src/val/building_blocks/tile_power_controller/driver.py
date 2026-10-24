"""Drive clock opportunities and an externally bounded physical handshake peer."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from mosaic_uvm.logic import bits, logic
from tile_power_controller.transaction import INPUTS


class PowerDriver(uvm_driver):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
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
            # Ordinary physical responses acknowledge only a currently active request.
            ports = dict.fromkeys(INPUTS, 0)
            ports.update(
                i_aon_rstb=1,
                i_tile_quiescent=1,
                i_drain_done=1,
                i_power_good_async=int(logic(cocotb.top.o_power_switch_enable) == '1'),
                i_retention_save_ack=int(logic(cocotb.top.o_retention_save) == '1'),
                i_retention_restore_ack=int(logic(cocotb.top.o_retention_restore) == '1'),
            )
            ports.update(item.controls)
            for n in INPUTS:
                getattr(cocotb.top, n).value = bits(ports[n], self.c.widths[n])
            await Timer(2, unit='ns')
            await self.sample('pre')
            if item.edge:
                cocotb.top.i_aon_clk.value = 1
            await Timer(2, unit='ns')
            await self.sample('post')
            await Timer(3, unit='ns')
            await self.sample('held')
            cocotb.top.i_aon_clk.value = 0
            await Timer(3, unit='ns')
            self.seq_item_port.item_done()
