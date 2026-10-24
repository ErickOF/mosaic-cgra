"""Programmable bank peers with persistent byte storage and stable responses.

This stimulus BFM commits synthetic writes at bank acceptance and schedules one
response per acceptance. The passive scoreboard owns a separate storage oracle.
"""
from collections import deque
import random
from scratchpad_controller.model import fields, number, pack, response, unpack
from scratchpad_controller.transaction import REQ_FIELDS, RSP_FIELDS


class BankPeers:
    def __init__(self, c):
        self.c = c
        self.rng = random.Random(c.seed ^ 0xBA4C)
        self.memory = [bytearray(c.BANK_DEPTH_WORDS * c.bytes) for _ in range(c.NUM_BANKS)]
        self.clock = 0
        self.reset()

    def reset(self):
        self.queues = [deque() for _ in range(self.c.NUM_BANKS)]
        self.presented = [None] * self.c.NUM_BANKS
        self.flushing = [None] * self.c.NUM_BANKS
        self.flush_seen = [False] * self.c.NUM_BANKS

    def inputs(self, options):
        c = self.c
        all_banks = (1 << c.NUM_BANKS) - 1
        launch = options.get('launch', all_banks)
        valid = []
        payloads = []
        ack = []
        idle = []
        for b in range(c.NUM_BANKS):
            if self.presented[b] is None and self.queues[b] and launch >> b & 1 and self.queues[b][0][0] <= self.clock:
                self.presented[b] = self.queues[b][0][1]
            valid.append(int(self.presented[b] is not None))
            payloads.append(self.presented[b] or response())
            ack.append(int(self.flushing[b] is not None and self.flushing[b] <= self.clock))
            idle.append(int(not self.queues[b]))
        ports = dict(i_bank_req_ready=options.get('ready', all_banks),
                     i_bank_rsp_valid=pack(valid, 1), i_bank_idle=pack(idle, 1),
                     i_bank_flush_completed=pack(ack, 1))
        for name in RSP_FIELDS:
            key = 'i_bank_rsp_' + name
            ports[key] = pack([v[name] for v in payloads], c.widths[key] // c.NUM_BANKS)
        if 'inject' in options:
            b, changes = options['inject']
            payloads[b] = response() | changes
            valid[b] = 1
            ports['i_bank_rsp_valid'] = pack(valid, 1)
            for name in RSP_FIELDS:
                key = 'i_bank_rsp_' + name
                ports[key] = pack([v[name] for v in payloads], c.widths[key] // c.NUM_BANKS)
        return ports

    def step(self, ports, edge, options):
        c = self.c
        if number(ports['i_rstb']) == 0 and (edge or c.ASYNC_RESET):
            self.reset()
        if not edge:
            return
        self.clock += 1
        if number(ports['i_rstb']) != 1:
            return
        req = fields(ports, 'o_bank_req_', c.NUM_BANKS, c, REQ_FIELDS)
        reqv = unpack(ports['o_bank_req_valid'], c.NUM_BANKS, 1)
        ready = unpack(ports['i_bank_req_ready'], c.NUM_BANKS, 1)
        rspv = unpack(ports['i_bank_rsp_valid'], c.NUM_BANKS, 1)
        rspr = unpack(ports['o_bank_rsp_ready'], c.NUM_BANKS, 1)
        flush = unpack(ports['o_bank_flush'], c.NUM_BANKS, 1)
        ack = unpack(ports['i_bank_flush_completed'], c.NUM_BANKS, 1)
        for b in range(c.NUM_BANKS):
            if flush[b] == 1:
                self.queues[b].clear()
                self.presented[b] = None
                if not self.flush_seen[b]:
                    self.flushing[b] = self.clock + (b % 4) + 1
                    self.flush_seen[b] = True
                if ack[b] == 1:
                    self.flushing[b] = None
                continue
            self.flush_seen[b] = False
            if rspv[b] == 1 and rspr[b] == 1 and self.presented[b] is not None:
                self.queues[b].popleft()
                self.presented[b] = None
            if reqv[b] != 1 or ready[b] != 1:
                continue
            e = req[b]
            address, size = e['address'], 1 << e['size_log2']
            assert 0 <= address < len(self.memory[b])
            if e['write']:
                data = e['wdata']
                assert data is not None, 'SCRATCHPAD_CONTROLLER_PROTOCOL: unknown selected write data'
                for k in range(size):
                    if e['wstrobe'] >> k & 1:
                        self.memory[b][address + k] = data >> (8 * k) & 255
                value = 0
            else:
                value = int.from_bytes(self.memory[b][address:address + size], 'little')
            status = options.get('status', {}).get(b, {})
            result = response(e['write'], e['tag'], value) | status
            self.queues[b].append((self.clock + options.get('latency', self.rng.randrange(1, 9)), result))
