"""Observe ports, real edge-time reads, and optional unreset storage activity."""

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from register_file.transaction import Activity, INPUTS, Observation


class RegisterFileMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)
        self.storage = ()

    def observe(self, stage):
        item = self.active['item']
        observation = Observation({name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, 'o_read_data')},
            tuple(logic(handle) for handle in self.storage), item, stage)
        self.ap.write(observation)
        if stage == 'pre':
            item.pre = observation

    async def sample_edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk)
            # Read immediately in the edge phase, before nonblocking storage
            # updates. Waiting for ReadOnly here would observe the new word.
            self.observe('edge')

    async def watch(self, name, handle, entry=None):
        previous = logic(handle)
        while True:
            await handle.value_change
            forbidden = (entry not in self.active['writable']) if entry is not None else self.active['hold_output']
            await ReadOnly()
            current = logic(handle)
            if current != previous:
                self.ap.write(Activity(name, forbidden))
                previous = current

    async def run_phase(self):
        await Timer(2, unit='ps')
        await ReadOnly()
        if self.config.check_internals:
            self.storage = tuple(cocotb.top.g_register_file.registers[index] for index in range(self.config.depth))
        tasks = [cocotb.start_soon(self.sample_edges()),
            cocotb.start_soon(self.watch('o_read_data', cocotb.top.o_read_data))]
        tasks.extend(cocotb.start_soon(self.watch(f'registers[{index}]', handle, index))
            for index, handle in enumerate(self.storage))
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            for task in tasks:
                task.cancel()
