"""Set unrelated words concurrently and fence independent/held output cones."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from mosaic_uvm.logic import logic
from parity.transaction import CHECK_OUTPUTS, OUTPUTS


class ParityDriver(uvm_driver):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')

    async def sample(self, stage):
        self.active['stage'] = stage
        self.active['sample'].set()
        await ReadOnly()
        await Timer(1, unit='ps')
        assert not self.active['sample'].is_set(), f'Monitor missed {stage} sample'

    async def run_phase(self):
        await Timer(3, unit='ps')
        while True:
            item = await self.seq_item_port.get_next_item()
            quiet = set()
            if logic(cocotb.top.i_generate_data) == item.source:
                quiet.add('o_generated_parity')
            if logic(cocotb.top.i_check_data) == item.data and logic(cocotb.top.i_check_parity) == item.parity:
                quiet.update(CHECK_OUTPUTS)
            self.active.update(item=item, quiet=quiet)
            cocotb.top.i_generate_data.value = item.source
            cocotb.top.i_check_data.value = item.data
            cocotb.top.i_check_parity.value = item.parity
            await Timer(1, unit='ps')
            await self.sample('settled')
            self.active['quiet'] = set(OUTPUTS)
            await Timer(10, unit='ps')
            await self.sample('held')
            self.seq_item_port.item_done()
