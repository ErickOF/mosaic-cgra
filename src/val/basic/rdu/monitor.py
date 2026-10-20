"""Observe real ports and optional flat storage; reject finite held-state pulses."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from rdu.transaction import Activity, INPUTS, OUTPUTS, Observation


class RduMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    async def watch(self, name, handle):
        previous = logic(handle)
        while True:
            await handle.value_change
            mask = self.active['quiet'].get(name, 0)
            await ReadOnly()
            current = logic(handle)
            if current != previous:
                changed = sum(1 << bit for bit, (old, new) in enumerate(zip(reversed(previous), reversed(current))) if old != new)
                self.ap.write(Activity(name, bool(changed & mask)))
                previous = current

    async def run_phase(self):
        await Timer(2, unit='ps')
        await ReadOnly()
        internals = self.active['internals']
        if self.config.check_internals:
            internals.update({name: getattr(cocotb.top.g_rdu, name) for name in ('delay_data', 'delay_valid')})
        handles = {name: getattr(cocotb.top, name) for name in (*INPUTS, *OUTPUTS)} | internals
        tasks = [cocotb.start_soon(self.watch(name, handle)) for name, handle in handles.items()]
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                observation = Observation({name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
                    {name: logic(handle) for name, handle in internals.items()}, self.active['item'], self.active['stage'])
                self.ap.write(observation)
                observation.item.observation = observation
                if observation.stage == 'pre':
                    observation.item.pre = observation
                self.active['sample'].clear()
        finally:
            for task in tasks:
                task.cancel()
