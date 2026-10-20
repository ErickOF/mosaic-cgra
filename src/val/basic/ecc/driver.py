"""Drive both independent combinational cones and observe settled/held results."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from mosaic_uvm.logic import logic
from ecc.transaction import DECODE_OUTPUTS, OUTPUTS


class EccDriver(uvm_driver):
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
            if logic(cocotb.top.i_encode_data) == item.encode:
                quiet.add('o_encoded_codeword')
            if logic(cocotb.top.i_decode_codeword) == item.received:
                quiet.update(DECODE_OUTPUTS)
                quiet.add('correction_mask')
            self.active.update(item=item, quiet=quiet)
            cocotb.top.i_encode_data.value = item.encode
            cocotb.top.i_decode_codeword.value = item.received
            await Timer(1, unit='ps')
            await self.sample('settled')
            self.active['quiet'] = set(OUTPUTS) | {'correction_mask'}
            await Timer(10, unit='ps')
            await self.sample('held')
            self.seq_item_port.item_done()
