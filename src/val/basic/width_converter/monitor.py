"""Sample ports before NBA updates and monitor finite between-sample activity."""

import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from width_converter.transaction import Activity, INPUTS, OUTPUTS, Observation, STORAGE


class WidthConverterMonitor(uvm_monitor):
    def build_phase(self):
        self.config = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        item = self.active['item']
        observation = Observation({name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)},
            {name: logic(handle) for name, handle in self.active['internals'].items()}, item, stage)
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
            quiet = name in self.active['quiet']
            allowed = set(self.active['writable_bits'])
            await ReadOnly()
            current = logic(handle)
            if current != previous:
                changed = {bit for bit, (old, new) in enumerate(zip(reversed(previous), reversed(current))) if old != new}
                forbidden = changed if quiet else changed-allowed if name == 'buffered_data' else set()
                self.ap.write(Activity(name, previous, current, tuple(sorted(forbidden))))
                previous = current

    async def run_phase(self):
        await Timer(2, unit='ps')
        await ReadOnly()
        internals = self.active['internals']
        c = self.config
        if c.check_internals:
            scope = cocotb.top.g_converter
            internals.update({name: getattr(scope, name) for name in (*STORAGE, 'valid')})
            if c.mode != 'equal':
                control = scope.g_pack if c.mode == 'pack' else scope.g_forward.g_unpack
                internals['index'] = control.index
                if c.mode == 'unpack':
                    internals['terminal'] = control.terminal
        handles = {name: getattr(cocotb.top, name) for name in (*INPUTS, *OUTPUTS)} | internals
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
