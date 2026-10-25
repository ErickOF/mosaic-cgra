"""Sample actual ports before NBA, after settling, and during held cycles."""
import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from lut_unit.transaction import INPUTS, OUTPUTS, Observation


class LutUnitMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        item = self.active['item']
        storage = {}
        if self.active['config'].check_internals:
            unit = cocotb.top.g_unit
            storage = {b: logic(unit.g_bank[b].u_table.i_read)
                       for b in range(self.active['config'].NUM_BANKS)}
        observation = Observation({name: logic(getattr(cocotb.top, name))
                                   for name in (*INPUTS, *OUTPUTS)},
                                  item, stage, storage)
        self.ap.write(observation)
        item.observation = observation
        if stage == 'pre':
            item.pre = observation

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk)
            self.observe('edge')

    async def run_phase(self):
        await Timer(2, unit='ns')
        task = cocotb.start_soon(self.edges())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            task.cancel()
