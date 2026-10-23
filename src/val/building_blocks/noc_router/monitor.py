"""Passive real-port and FIFO-pop sampling, coordinated at stable clock windows."""

import cocotb
from cocotb.triggers import ReadOnly
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from noc_router.transaction import INPUTS, OUTPUTS, Observation


class RouterMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    async def run_phase(self):
        while True:
            await self.active['sample'].wait()
            await ReadOnly()
            item = self.active['item']
            core = cocotb.top.g_router
            internal = {
                name: logic(getattr(core, name))
                for name in (
                    'queue_pop',
                    'queue_push',
                    'switch_fire',
                    'live_fatal',
                    'normal_accept',
                    'high_accept',
                    'normal_waiting',
                )
            }
            obs = Observation(
                {name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
                internal,
                item,
                self.active['stage'],
            )
            self.ap.write(obs)
            item.observation = obs
            if obs.stage == 'pre':
                item.pre = obs
            self.active['sample'].clear()
