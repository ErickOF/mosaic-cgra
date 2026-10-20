"""Observe arbitration, actual acceptance edges and continuous pending activity."""

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from round_robin_arbiter.transaction import Activity, Observation, STATE


class ArbiterMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        c, item = self.config, self.active['item']
        observation = Observation({name: logic(getattr(cocotb.top, name)) for name in c.widths},
            {name: logic(handle) for name, handle in self.active['internals'].items()}, item, stage)
        self.ap.write(observation)
        item.observation = observation
        if stage == 'pre': item.pre = observation

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk)
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
        c = self.config
        if c.check_internals:
            top = cocotb.top.u_arbiter if c.fixture else cocotb.top
            self.active['internals'].update({name: getattr(top.g_arbiter, name) for name in STATE})
        handles = {name: getattr(cocotb.top, name) for name in c.widths} | self.active['internals']
        tasks = [cocotb.start_soon(self.edges())]
        tasks.extend(cocotb.start_soon(self.watch(name, handle)) for name, handle in handles.items())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            for task in tasks: task.cancel()
