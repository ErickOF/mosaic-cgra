"""Real pre-NBA edges, settled ports, completion DFFs and optional counters."""

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from mosaic_uvm.logic import logic
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from store_engine.transaction import INPUTS, OUTPUTS, Observation


class StoreEngineMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        item = self.active['item']
        obs = Observation({name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
                          {key: logic(handle) for key, handle in self.active['storage'].items()},
                          item, stage)
        self.ap.write(obs)
        item.observation = obs
        if stage == 'pre':
            item.pre = obs

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk)
            self.observe('edge')

    async def run_phase(self):
        await Timer(2, unit='ns')
        if self.active['check_internals']:
            core = cocotb.top.g_engine
            for n in range(self.active['slots']):
                for kind, instance in (('a', 'u_allocated'), ('p', 'u_present'),
                                       ('l', 'u_last'), ('e', 'u_response_error')):
                    bank = getattr(core.g_slot[n], instance)
                    key = f'{kind}{n}'
                    self.active['storage'][key] = bank.o_q
                    for pin in ('i_enable', 'i_d', 'i_rstb'):
                        self.active['storage'][key + ':' + pin] = getattr(bank, pin)
            for label, instance in (('descriptor', core.u_descriptor_write),
                                    ('response', core.u_response_write)):
                for pin in ('i_write_enable', 'i_suppress', 'o_write_enable', 'o_write_suppressed'):
                    self.active['storage'][f'gate:{label}:{pin}'] = getattr(instance, pin)
        if self.active['hdl_assertions']:
            checker = cocotb.top.g_engine.u_assertions
            for key in ('counts', 'disabled_counts', 'peak', 'disabled_peak'):
                self.active['storage']['counter:' + key] = getattr(checker, key)
        task = cocotb.start_soon(self.edges())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            task.cancel()
