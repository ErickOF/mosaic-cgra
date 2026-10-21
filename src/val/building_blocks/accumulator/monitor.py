"""Observe pre-NBA edge transfers, raw storage and lane-local isolated operands."""

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from accumulator.transaction import Activity, INPUTS, OUTPUTS, Observation, RAW


class AccumulatorMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        item = self.active['item']
        observation = Observation({name:logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
            {name:logic(handle) for name, handle in self.active['internals'].items()}, item, stage)
        self.ap.write(observation)
        item.observation = observation
        if stage == 'pre':
            item.pre = observation

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk)
            self.observe('edge')

    async def watch(self, name, handle):
        previous = logic(handle)
        while True:
            await handle.value_change
            allowed = self.active['permissions'].get(name)
            allowed = None if allowed is None else set(allowed)
            await ReadOnly()
            current = logic(handle)
            if current != previous:
                changed = {b for b, (old, new) in enumerate(zip(reversed(previous), reversed(current))) if old != new}
                forbidden = set() if allowed is None else changed-allowed
                self.ap.write(Activity(name, tuple(sorted(forbidden))))
                previous = current

    async def run_phase(self):
        await Timer(2, unit='ps')
        await ReadOnly()
        c, internals = self.config, self.active['internals']
        if c.check_internals:
            bank = cocotb.top.g_bank
            internals.update({name:getattr(bank, name) for name in RAW})
            for k in range(c.lanes):
                scope = bank.g_lane[k]
                for name in ('add_left', 'add_right'):
                    internals[f'{name}[{k}]'] = getattr(scope, name)
                if c.subtract:
                    for name in ('sub_left', 'sub_right'):
                        internals[f'{name}[{k}]'] = getattr(scope.g_subtract, name)
        handles = {name:getattr(cocotb.top, name) for name in (*INPUTS, *OUTPUTS)} | internals
        tasks = [cocotb.start_soon(self.edges())]
        tasks.extend(cocotb.start_soon(self.watch(name, handle)) for name, handle in handles.items())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            for task in tasks:
                task.cancel()
