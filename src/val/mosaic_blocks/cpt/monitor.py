"""Observe actual pre-NBA transfers in both domains and settled public outputs."""
import cocotb
from cocotb.triggers import Timer, RisingEdge, ReadOnly
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from cpt.transaction import INPUTS, OUTPUTS, Observation

class CptMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.c = ConfigDB().get(self, '', 'config')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, domain):
        item = self.active['item']
        obs = Observation({n: logic(getattr(cocotb.top, n)) for n in (*INPUTS, *OUTPUTS)}, domain, item)
        if domain == 'core':
            body = cocotb.top.g_cpt.u_body
            obs.body = {n: logic(getattr(body, n)) for n in (
                'issue', 'execute', 'retire', 'phase', 'command_legal', 'command_class',
                'native_ready', 'native_done', 'command_condition', 'initialized',
                'command_meta', 'command_data', 'ingress_fire', 'ingress_legal',
                'o_body_start', 'context_change', 'o_body_flush', 'i_body_completed',
                'o_body_context_id', 'o_body_context_version', 'o_body_context_image',
                'loop_token_ready', 'loop_frame_active', 'loop_await_delivery',
                'eb_counts', 'eb_generations', 'eb_arrivals', 'fatal',
                'eb_fatal', 'loop_fatal', 'egress_fatal', 'loop_config_rejected',
                'event_init_sent', 'loop_init_sent', 'loop_initialized', 'event_initialized')}
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
