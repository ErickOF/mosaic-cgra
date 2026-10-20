"""Sample actual ports and detect finite pulses in quiet combinational cones."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from parity.transaction import Activity, INPUTS, OUTPUTS, Observation


class ParityMonitor(uvm_monitor):
    def build_phase(self):
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
        tasks = [cocotb.start_soon(self.watch(name, getattr(cocotb.top, name))) for name in OUTPUTS]
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.ap.write(Observation({name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
                                         self.active['item'], self.active['stage']))
                self.active['sample'].clear()
        finally:
            for task in tasks:
                task.cancel()
