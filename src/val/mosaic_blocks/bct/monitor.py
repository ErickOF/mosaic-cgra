"""Observe actual pre-NBA transfers in both domains and settled public outputs."""
import cocotb
from cocotb.triggers import Timer, RisingEdge, ReadOnly
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from bct.transaction import INPUTS, OUTPUTS, Observation

class BctMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.c = ConfigDB().get(self, '', 'config')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, domain):
        item = self.active['item']
        obs = Observation({n: logic(getattr(cocotb.top, n)) for n in (*INPUTS, *OUTPUTS)}, domain, item)
        if domain == 'core':
            body = cocotb.top.g_bct.u_body
            obs.body = {n: logic(getattr(body, n)) for n in (
                'issue', 'commit', 'advance', 'result', 'head', 'latency', 'a', 'b', 'c',
                'commit_data', 'commit_rf_enable', 'commit_predicate_enable',
                'commit_accumulator_enable', 'commit_bypass_enable',
                'o_body_context_id', 'o_body_context_version', 'o_body_context_image',
                'i_body_data_out_valid', 'i_body_data_out_payload', 'i_body_data_out_metadata',
                'i_body_predicate_out_valid', 'i_body_predicate_out_payload',
                'i_body_error', 'i_body_error_code', 'i_body_fatal_error',
                'context_change', 'o_body_flush', 'pipeline_valid', 'queue_count')}
        self.ap.write(obs)
        if domain == 'post':
            item.post = obs.ports
        else:
            item.edges[domain] = obs.ports

    async def edges(self, clock, domain):
        while True:
            await RisingEdge(clock)
            self.observe(domain)

    async def run_phase(self):
        await Timer(1, unit='ns')
        tasks = [cocotb.start_soon(self.edges(cocotb.top.i_clk, 'core'))]
        if self.c.CONFIG_ASYNC:
            tasks.append(cocotb.start_soon(self.edges(cocotb.top.i_cfg_clk, 'cfg')))
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe('post')
                self.active['sample'].clear()
        finally:
            for task in tasks:
                task.cancel()
