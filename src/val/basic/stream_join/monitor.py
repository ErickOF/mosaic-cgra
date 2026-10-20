"""Read actual DUT interfaces and watch live controls and stable output intervals."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from stream_join.transaction import Activity, INPUTS, OUTPUTS, Observation


class StreamJoinMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        item = self.active['item']
        observation = Observation({name: logic(getattr(cocotb.top, name)) for name in (*INPUTS, *OUTPUTS)}, item, stage)
        self.ap.write(observation)
        item.observation = observation
        if stage == 'pre':
            item.pre = observation

    async def edges(self):
        while True:
            await self.active['tick'].wait()
            await ReadOnly()
            self.observe('edge')
            self.active['tick'].clear()

    async def watch(self, name):
        handle = getattr(cocotb.top, name)
        previous = logic(handle)
        while True:
            await handle.value_change
            forbidden = name in self.active['quiet']
            await ReadOnly()
            current = logic(handle)
            if current != previous:
                self.ap.write(Activity(name, forbidden))
                previous = current

    async def run_phase(self):
        await Timer(2, unit='ps')
        await ReadOnly()
        tasks = [cocotb.start_soon(self.edges())]
        tasks.extend(cocotb.start_soon(self.watch(name)) for name in (*INPUTS, *OUTPUTS))
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            for task in tasks:
                task.cancel()
