"""Passive public snapshots, actual backend operations and enabled storage banks."""
import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from mosaic_uvm.logic import logic
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from scratchpad_bank.transaction import INPUTS, OUTPUTS, Observation


class ScratchpadBankMonitor(uvm_monitor):
    def build_phase(self):
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)

    def observe(self, stage):
        item = self.active['item']
        storage = {n: logic(h) for n, h in self.active['storage'].items()}
        if self.active['check_internals']:
            words = {0}
            if set(storage['backend:i_addr']) <= set('01'):
                words.add(int(storage['backend:i_addr'], 2))
            if item.pre and 'backend:i_addr' in item.pre.storage:
                address = item.pre.storage['backend:i_addr']
                if set(address) <= set('01'):
                    words.add(int(address, 2))
            if item.fault:
                words.add(item.fault[0])
            for word in words:
                if word < self.active['config'].DEPTH_WORDS:
                    storage[f'memory:{word}'] = logic(self.memory[word])
        obs = Observation({n: logic(getattr(cocotb.top, n)) for n in (*INPUTS, *OUTPUTS)}, storage, item, stage)
        self.ap.write(obs)
        item.observation = obs
        if stage == 'pre':
            item.pre = obs

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk)
            self.observe('edge')

    async def run_phase(self):
        await Timer(2, unit='ns')
        if self.active['check_internals']:
            core = cocotb.top.g_bank
            self.memory = core.u_storage.g_shell.u_backend.g_inferred.memory
            for n in range(self.active['config'].MAX_OUTSTANDING):
                for name in ('metadata', 'result', 'allocated', 'present', 'awaiting'):
                    bank = getattr(core.g_slot[n], 'u_' + name)
                    for pin in ('o_q', 'i_d', 'i_enable', 'i_rstb'):
                        self.active['storage'][f'{n}:{name}:{pin}'] = getattr(bank, pin)
            backend = core.u_storage.g_shell.u_backend
            for pin in ('i_enable', 'i_write', 'i_addr', 'i_wdata', 'i_wmask'):
                self.active['storage']['backend:' + pin] = getattr(backend, pin)
            for name in ('issue_pointer', 'retire_pointer', 'work_state', 'return_ok', 'return_bad',
                         'backend_rsp_valid', 'backend_rsp_tag', 'illegal_events', 'read_bytes', 'write_bytes'):
                self.active['storage'][name] = getattr(core, name)
        if self.active['config'].instrumentation:
            instrument = cocotb.top.g_bank.u_instrumentation
            for name in ('counts', 'disabled_counts', 'peak', 'disabled_peak'):
                self.active['storage']['counter:' + name] = getattr(instrument, name)
        task = cocotb.start_soon(self.edges())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            task.cancel()
