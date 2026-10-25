"""Observe actual pre-NBA edges, settled ports, and coefficient access enables."""
import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from polynomial_unit.ports import INPUTS, OUTPUTS
from polynomial_unit.transaction import Observation


class PolynomialMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.config = ConfigDB().get(self, '', 'config')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        c = self.config
        bank = cocotb.top.g_unit
        internals = {name: logic(getattr(bank, name)) for name in (
            'read_enable', 'read_corrected', 'read_bad', 'stage_commit', 'stage_saturated',
            'finish', 'raw_corrupt', 'pipe_valid')}
        for name in ('read_bank', 'read_index'):
            internals[name] = tuple(logic(getattr(bank, name)[p]) for p in range(c.read_ports))
        obs = Observation({name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
                          self.active['item'], stage, internals)
        self.ap.write(obs)
        obs.item.observation = obs
        if stage == 'pre':
            obs.item.pre = obs

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
