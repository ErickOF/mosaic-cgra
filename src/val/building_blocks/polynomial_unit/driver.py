"""Drive public interfaces and explicit storage faults without predicting outputs."""
import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from polynomial_unit.ports import INPUTS


class PolynomialDriver(uvm_driver):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.config = ConfigDB().get(self, '', 'config')

    async def sample(self, stage):
        self.active['stage'] = stage
        self.active['sample'].set()
        await ReadOnly()
        await Timer(1, unit='ps')
        assert not self.active['sample'].is_set()

    async def run_phase(self):
        await Timer(4, unit='ns')
        while True:
            item = await self.seq_item_port.get_next_item()
            self.active['item'] = item
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            if item.fault:
                kind, *values = item.fault
                top = cocotb.top.g_unit
                if kind == 'coefficient':
                    bank, copy, index, mask = values
                    handle = top.g_bank[bank].g_copy[copy].u_coefficients.memory[index]
                elif kind == 'ownership':
                    handle = top.g_bank[values[0]].u_metadata.u_data.o_q
                    c = self.config
                    bit = c.MAX_DEGREE.bit_length() + 2 * c.INPUT_WIDTH + c.RESULT_SHIFT_WIDTH + 3
                    mask = 1 << bit
                else:
                    if self.config.EVALUATION_ARCH:
                        handle = top.g_unrolled.g_stage[0].u_stage.u_metadata.u_data.o_q
                    else:
                        handle = top.g_iterative.u_evaluation.u_data.o_q
                    mask = 1
                handle.value = int(handle.value) ^ mask
            await Timer(2, unit='ns')
            await self.sample('pre')
            if item.edge:
                cocotb.top.i_clk.value = 1
            await Timer(2, unit='ns')
            await self.sample('post')
            await Timer(3, unit='ns')
            await self.sample('held')
            cocotb.top.i_clk.value = 0
            await Timer(3, unit='ns')
            self.seq_item_port.item_done()
