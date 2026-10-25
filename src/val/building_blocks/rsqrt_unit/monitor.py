"""Observe actual pre-NBA edges, settled ports, and seed access enables."""
import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from rsqrt_unit.ports import INPUTS, OUTPUTS
from rsqrt_unit.transaction import Observation


class RsqrtMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.config = ConfigDB().get(self, '', 'config')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        c = self.config
        bank = cocotb.top.g_unit
        internals = {name: logic(getattr(bank, name)) for name in (
            'epsilon_access', 'normalize_access', 'seed_access', 'multiply_enable', 'iteration_commit',
            'finish', 'raw_corrupt', 'lane_valid', 'fatal_now', 'seed_corrected', 'seed_bad')}
        internals['phases'] = tuple(logic(bank.phase[p]) for p in range(c.lanes))
        internals['addresses'] = tuple(logic(bank.g_stage[p].seed_address) for p in range(c.lanes))
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
