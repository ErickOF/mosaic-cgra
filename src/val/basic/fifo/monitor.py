"""Observe DUT outputs and each storage entry, including finite hold pulses."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from fifo.transaction import Activity, INPUTS, OUTPUTS, Observation


class FifoMonitor(uvm_monitor):
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
            bank = cocotb.top.g_fifo
            internals.update(read_pointer=bank.read_pointer, write_pointer=bank.write_pointer)
            internals.update({f'memory:{index}': bank.memory[index] for index in range(self.config.depth)})
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
                if observation.stage == 'pre':
                    observation.item.pre = observation
                self.active['sample'].clear()
        finally:
            for task in tasks:
                task.cancel()
