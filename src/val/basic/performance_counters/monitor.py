"""Observe the interface and optional storage/arithmetic cones continuously."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from performance_counters.transaction import Activity, INPUTS, OUTPUTS, Observation


class PerformanceCountersMonitor(uvm_monitor):
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
        internals = self.active['internals']
        if self.config.check_internals:
            bank = cocotb.top.g_bank
            internals.update({name: getattr(bank, name) for name in ('live_counts', 'snapshot_counts', 'snapshot_overflow')})
            for c in range(self.config.counters):
                counter = bank.g_counter[c]
                internals.update({f'{name}:{c}': getattr(counter, name) for name in ('isolated_count', 'isolated_increment', 'wide_sum')})
        handles = {name: getattr(cocotb.top, name) for name in OUTPUTS} | internals
        tasks = [cocotb.start_soon(self.watch(name, handle)) for name, handle in handles.items()]
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                observation = Observation({name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
                    {name: logic(handle) for name, handle in internals.items()}, self.active['item'], self.active['stage'])
                self.ap.write(observation)
                observation.item.observation = observation
                self.active['sample'].clear()
        finally:
            for task in tasks:
                task.cancel()
