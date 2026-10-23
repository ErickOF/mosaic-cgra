"""Drive real clock opportunities and verification-only AGU runtime failures."""
import cocotb
from cocotb.handle import Force, Release
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from store_engine.transaction import INPUTS


class StoreEngineDriver(uvm_driver):
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
                self.forced = cocotb.top.g_engine.agu_error
                self.forced.value = Force(1)
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
