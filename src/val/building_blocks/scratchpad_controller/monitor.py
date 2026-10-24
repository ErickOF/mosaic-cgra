"""Passive observations before NBA, after NBA, and between active edges."""
import cocotb
from cocotb.triggers import ReadOnly, RisingEdge, Timer
from pyuvm import ConfigDB, uvm_analysis_port, uvm_monitor
from scratchpad_controller.transaction import Observation, PORTS


class ControllerMonitor(uvm_monitor):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.active = ConfigDB().get(self, '', 'active')
        self.ap = uvm_analysis_port('ap', self)
        self.storage = {}

    def observe(self, stage):
        item = self.active['item']
        if item is None:
            return
        ports = {n: str(getattr(self.dut, n).value).lower() for n in PORTS}
        storage = {n: str(h.value).lower() for n, h in self.storage.items()}
        obs = Observation(ports, storage, item, stage)
        if stage == 'pre':
            item.pre = obs
        elif stage == 'post':
            item.post = obs
        self.ap.write(obs)

    async def edges(self):
        while True:
            await RisingEdge(cocotb.top.i_clk)
            self.observe('edge')

    async def run_phase(self):
        await Timer(2, unit='ns')
        self.dut = cocotb.top.u_controller if self.c.integration else cocotb.top
        core = self.dut.g_controller
        for c in range(self.c.NUM_CLIENTS):
            client = core.g_client[c]
            for kind in ('issue', 'retire', 'occupancy'):
                self.storage[f'{c}:{kind}'] = getattr(client, 'u_' + kind).o_q
            for s in range(self.c.MAX_OUTSTANDING_PER_CLIENT):
                slot = client.g_slot[s]
                for kind in ('metadata', 'result', 'allocated', 'present'):
                    inst = getattr(slot, 'u_' + kind)
                    for pin in ('o_q', 'i_d', 'i_enable', 'i_rstb'):
                        self.storage[f'{c}:{s}:{kind}:{pin}'] = getattr(inst, pin)
        for b in range(self.c.NUM_BANKS):
            arb = core.g_request_arbiter[b].u_arbiter.g_arbiter
            self.storage[f'pointer:{b}'] = arb.u_pointer.o_q
            self.storage[f'pending:{b}'] = arb.u_pending.o_q
        self.storage['read_permission'] = core.u_read_permission.o_q
        self.storage['write_permission'] = core.u_write_permission.o_q
        if self.c.instrumentation:
            instrument = core.u_instrumentation
            for n in ('counts', 'peaks', 'disabled_counts', 'disabled_peaks'):
                self.storage['counter:' + n] = getattr(instrument, n)
        if self.c.integration:
            from scratchpad_bank.transaction import PORTS as BANK_PORTS
            for b in range(self.c.NUM_BANKS):
                bank = cocotb.top.g_bank[b].u_bank
                for n in BANK_PORTS:
                    self.storage[f'bank:{b}:{n}'] = getattr(bank, n)
                memory = bank.g_bank.u_storage.g_shell.u_backend.g_inferred.memory
                for word in range(self.c.BANK_DEPTH_WORDS):
                    self.storage[f'memory:{b}:{word}'] = memory[word]
        task = cocotb.start_soon(self.edges())
        try:
            while True:
                await self.active['sample'].wait()
                await ReadOnly()
                self.observe(self.active['stage'])
                self.active['sample'].clear()
        finally:
            task.cancel()
