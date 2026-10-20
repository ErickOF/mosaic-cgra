"""Observe real edge-time transfers and continuous input/output/storage activity."""

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from skid_buffer.transaction import Activity, INPUTS, OUTPUTS, Observation


class SkidBufferMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        item = self.active['item']
        observation = Observation({name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
            {name: logic(handle) for name, handle in self.active['internals'].items()}, item, stage)
        self.ap.write(observation)
        item.observation = observation
        if stage == 'pre':
            item.pre = observation

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk)
            # A release consumes the old buffered token before bypass resumes.
            self.observe('edge')

    async def watch(self, name, handle):
        previous = logic(handle)
        while True:
            await handle.value_change
            forbidden = name in self.active['quiet']
            await ReadOnly()
            current = logic(handle)
            if current != previous:
                self.ap.write(Activity(name, forbidden))
                previous = current

    async def run_phase(self):
        await Timer(2, unit='ps')
        await ReadOnly()
        internals = self.active['internals']
        if self.config.check_internals:
            internals.update({name: getattr(cocotb.top.g_skid, name) for name in ('buffer_valid', 'buffer_data')})
        handles = {name: getattr(cocotb.top, name) for name in (*INPUTS, *OUTPUTS)} | internals
        tasks = [cocotb.start_soon(self.edges())]
        tasks.extend(cocotb.start_soon(self.watch(name, handle)) for name, handle in handles.items())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            for task in tasks:
                task.cancel()
