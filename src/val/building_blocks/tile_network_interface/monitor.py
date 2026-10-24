"""Observe real ports at settled samples and at the actual rising edge."""

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from tile_network_interface.transaction import INPUTS, OUTPUTS, Observation


class InterfaceMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        item = self.active['item']
        observation = Observation(
            {n: logic(getattr(cocotb.top, n)) for n in (*INPUTS, *OUTPUTS)}, {}, item, stage
        )
        self.ap.write(observation)
        if stage == 'pre':
            item.pre = observation
        if stage == 'post':
            item.post = observation

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk)
            self.observe('edge')

    async def run_phase(self):
        await Timer(2, unit='ns')
        edges = cocotb.start_soon(self.edges())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            edges.cancel()
