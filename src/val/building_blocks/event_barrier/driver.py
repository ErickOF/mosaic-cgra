"""Drive stable requests and real edges; fault injection uses parity sidecars."""
import cocotb
from cocotb.handle import Force, Release
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_driver
from event_barrier.transaction import INPUTS


class EventBarrierDriver(uvm_driver):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.forced = None

    async def sample(self, stage):
        self.active['stage'] = stage
        self.active['sample'].set()
        await ReadOnly()
        await Timer(1, unit='ps')
        assert not self.active['sample'].is_set(), f'Missed {stage} observation'

    def fault_handle(self, target):
        bank = cocotb.top.g_unit
        return {
            'policy': lambda: bank.u_policy.g_protection.u_parity_bit.o_q,
            'event': lambda: bank.g_event[0].g_protection.u_parity_bit.o_q,
            'wait': lambda: bank.g_wait[0].u_state.g_protection.u_parity_bit.o_q,
            'barrier': lambda: bank.g_barrier[0].u_state.g_protection.u_parity_bit.o_q,
            'generation': lambda: bank.g_barrier[0].g_protection.u_parity_bit.o_q,
            'queue': lambda: bank.u_results.u_metadata.g_protection.u_parity_bit.o_q,
        }[target]()

    async def run_phase(self):
        await Timer(4, unit='ns')
        while True:
            item = await self.seq_item_port.get_next_item()
            self.active['item'] = item
            self.active['window'] = 'inputs'
            if self.forced is not None and item.ports['i_rstb'] == 0:
                self.forced.value = Release()
                self.forced = None
            for name in INPUTS:
                getattr(cocotb.top, name).value = item.ports[name]
            if item.fault:
                self.forced = self.fault_handle(item.fault)
                self.forced.value = Force(1 - int(self.forced.value))
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
