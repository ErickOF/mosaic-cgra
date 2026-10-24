"""Observe real ports at settled samples and at the actual rising edge."""

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from tile_power_controller.transaction import INPUTS, OUTPUTS, Observation


class PowerMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)
        self.storage = {}

    def observe(self, stage):
        item = self.active['item']
        observation = Observation(
            {n: logic(getattr(cocotb.top, n)) for n in (*INPUTS, *OUTPUTS)},
            {n: logic(h) for n, h in self.storage.items()},
            item,
            stage,
        )
        self.ap.write(observation)
        if stage == 'pre':
            item.pre = observation
        if stage == 'post':
            item.post = observation

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_aon_clk)
            self.observe('edge')

    async def run_phase(self):
        await Timer(2, unit='ns')
        b = cocotb.top.g_controller
        from tile_power_controller.config import TIMERS

        self.storage = {n: getattr(b, n + '_count') for n in TIMERS}
        edges = cocotb.start_soon(self.edges())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            edges.cancel()
