"""Sample actual four-state ports and optional isolated operand cones."""

import cocotb
from cocotb.triggers import ReadOnly
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from scalar_alu.transaction import INPUTS, OUTPUTS, Observation


class AluMonitor(uvm_monitor):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    async def run_phase(self):
        while True:
            await self.active['sample'].wait()
            await ReadOnly()
            internal = {}
            if self.c.check_internals:
                core = cocotb.top.g_datapath
                internal = {
                    name: logic(getattr(core, name))
                    for name in ('isolated_a', 'isolated_b', 'math_a', 'math_b')
                }
            self.ap.write(
                Observation(
                    {name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
                    internal,
                    self.active['item'],
                    self.active['stage'],
                )
            )
            self.active['sample'].clear()
