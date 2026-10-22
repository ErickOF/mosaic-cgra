"""Sample actual ports before NBA, after settling, and during held cycles."""
import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from load_engine.transaction import INPUTS, OUTPUTS, Observation


class LoadEngineMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        item = self.active['item']
        observation = Observation({name: logic(getattr(cocotb.top, name))
                                   for name in (*INPUTS, *OUTPUTS)},
                                  {index: logic(handle) for index, handle in self.active['storage'].items()},
                                  item, stage)
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
        if self.active['check_internals']:
            bank = cocotb.top.g_engine
            self.active['storage'].update({f'{kind}{n}': getattr(bank.g_slot[n], inst).o_q
                for n in range(self.active['slots'])
                for kind, inst in (('m', 'u_metadata'), ('r', 'u_response'),
                                   ('a', 'u_allocated'), ('p', 'u_present'))})
        task = cocotb.start_soon(self.edges())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            task.cancel()
