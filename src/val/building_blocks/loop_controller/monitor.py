"""Sample actual ports before NBA, after settling, and during held cycles."""
import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from loop_controller.transaction import INPUTS, OUTPUTS, Observation


class LoopControllerMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.config = ConfigDB().get(self, '', 'config')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        item = self.active['item']
        internals = {}
        if self.config.check_internals:
            bank = cocotb.top.g_controller
            internals = {
                name: logic(getattr(bank, name))
                for name in ('control_decoded', 'advance_valid', 'advance_level',
                             'advance_onehot', 'level_write')
            }
        observation = Observation({name: logic(getattr(cocotb.top, name))
                                   for name in (*INPUTS, *OUTPUTS)},
                                  item, stage, internals)
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
