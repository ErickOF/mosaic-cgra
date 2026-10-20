"""Observe actual ports and portable state, including finite quiet-window pulses."""

import cocotb
from cocotb.triggers import ReadOnly, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from mosaic_uvm.logic import logic
from data_aligner.transaction import Activity, INPUTS, OUTPUTS, Observation


class AlignerMonitor(uvm_monitor):
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
        await Timer(5, unit='ps')
        await ReadOnly()
        internals = {}
        if self.config.check_internals:
            internals['isolated_data'] = cocotb.top.g_aligner.isolated_data
            if self.config.registered:
                bank = cocotb.top.g_aligner.g_registered
                internals.update(stored_result=bank.stored_result, stored_valid=bank.stored_valid)
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
