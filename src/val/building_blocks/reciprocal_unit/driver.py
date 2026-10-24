"""Drive public interfaces and explicit storage faults without predicting outputs."""
import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from reciprocal_unit.ports import INPUTS


class ReciprocalDriver(uvm_driver):
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
                from cocotb.handle import Force, Release
                kind, *values = item.fault
                top = cocotb.top.g_unit
                if kind == 'release':
                    self.forced.value = Release()
                    self.forced = None
                elif kind == 'seed':
                    address, value = values
                    self.forced = top.g_stage[self.config.seed_lane].g_seed.u_seed.g_word[
                        address].codeword
                    self.forced.value = Force(value)
                elif kind == 'internal':
                    self.forced = top.arithmetic_bad
                    self.forced.value = Force(1)
                elif kind == 'identity':
                    self.forced = cocotb.top.o_seed_checksum
                    self.forced.value = Force(int(self.forced.value) ^ 1)
                else:
                    if kind == 'errors':
                        handle = top.u_errors.u_data.o_q
                    elif kind == 'queue':
                        handle = top.u_results.u_metadata.u_data.o_q
                    elif self.config.EVALUATION_ARCH:
                        handle = top.g_unrolled.g_lane[0].u_stage.u_metadata.u_data.o_q
                    else:
                        handle = top.g_iterative.u_state.u_data.o_q
                    handle.value = int(handle.value) ^ (values[0] if values else 1)
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
