"""Observe real ports and reject finite pulses or cross-cone interference."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from ecc.transaction import Activity, INPUTS, OUTPUTS, Observation


class EccMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    async def watch(self, name, handle):
        previous = logic(handle)
        while True:
            await handle.value_change
            quiet = name in self.active['quiet']
            await ReadOnly()
            current = logic(handle)
            if current != previous:
                self.ap.write(Activity(name, quiet))
                previous = current

    async def run_phase(self):
        await Timer(2, unit='ps')
        await ReadOnly()
        internals = {'correction_mask': cocotb.top.g_codec.correction_mask} if self.config.check_internals else {}
        tasks = [cocotb.start_soon(self.watch(name, handle)) for name, handle in
                 ({name: getattr(cocotb.top, name) for name in OUTPUTS} | internals).items()]
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.ap.write(Observation({name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
                    {name: logic(handle) for name, handle in internals.items()}, self.active['item'], self.active['stage']))
                self.active['sample'].clear()
        finally:
            for task in tasks:
                task.cancel()
