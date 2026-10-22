"""Drive real clock edges and optional verification-only state corruption."""
import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from loop_controller.transaction import INPUTS


class LoopControllerDriver(uvm_driver):
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
                bank = cocotb.top.g_controller
                node = {'config': bank.u_configuration, 'candidate': bank.u_candidate}.get(
                    item.fault, bank.u_state)
                handle = node.u_data.o_q
                bit = (self.active['config'].II_WIDTH + self.active['config'].MAX_LOOP_DEPTH + 14 +
                       self.active['config'].LINEAR_COUNT_WIDTH - 1
                       if item.fault == 'invariant' else 0)
                handle.value = int(handle.value) ^ (1 << bit)
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
