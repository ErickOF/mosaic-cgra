"""Drive real clock opportunities and verification-only table/ownership faults."""
import cocotb
from cocotb.handle import Force, Release
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from exp_unit.transaction import INPUTS


class ExpUnitDriver(uvm_driver):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.forced = None

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
            if item.release and self.forced is not None:
                self.forced.value = Release()
                self.forced = None
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            if item.fault:
                kind, index, mask = item.fault
                bank = cocotb.top.g_unit
                if kind == 'rom':
                    self.forced = bank.u_table.g_word[index].stored_codeword
                elif kind == 'identity':
                    self.forced = bank.image_identity
                elif kind == 'stage':
                    self.forced = bank.g_stage[index].u_slice.control_output
                elif kind == 'owner':
                    self.forced = bank.g_stage[index].u_slice.o_valid
                self.forced.value = Force(int(self.forced.value) ^ mask)
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
