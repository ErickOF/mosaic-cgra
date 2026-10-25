"""Byte-accurate raw storage, independent protected words and ordered obligations.

The reference uses the existing independently qualified ECC model. It predicts
storage commits from public accepts and a timestamped read calendar, not DUT RAM.
"""
from collections import deque
from ecc.model import encode as ecc_encode, decode as ecc_decode
from mosaic_uvm.logic import bits
from scratchpad_bank.transaction import EVENTS, OUTPUTS


def number(raw):
    return raw if isinstance(raw, int) else None if set(raw.lower()) & set('xz') else int(raw, 2)


def splice(raw, data, mask):
    data = bits(data, len(raw))
    return ''.join(data[n] if mask >> (len(raw) - 1 - n) & 1 else bit for n, bit in enumerate(raw))


def encode(c, data):
    data = bits(data, c.DATA_WIDTH)
    if c.PROTECTION_MODE == 0:
        return data
    if c.PROTECTION_MODE == 2:
        return bits(ecc_encode(c.ecc, int(data, 2)), c.stored_width)
    parity = []
    for g in reversed(range(c.DATA_WIDTH // c.PARITY_GRANULARITY)):
        group = data[c.DATA_WIDTH - (g + 1) * c.PARITY_GRANULARITY:c.DATA_WIDTH - g * c.PARITY_GRANULARITY]
        parity.append('x' if set(group) & set('xz') else str(group.count('1') % 2))
    return ''.join(parity) + data


def legality(c, ports):
    p = {n: number(v) for n, v in ports.items()}
    if any(p[n] is None for n in ('i_req_write', 'i_req_address', 'i_req_size_log2', 'i_req_tag')) or p['i_req_write'] == 1 and p['i_req_wstrobe'] is None:
        return 1
    if p['i_req_address'] >= c.DEPTH_WORDS * c.bytes:
        return 2
    if p['i_req_size_log2'] > c.byte_log:
        return 3
    size = 1 << p['i_req_size_log2']
    if p['i_req_address'] % c.bytes + size > c.bytes:
        return 5
    if p['i_req_address'] % size:
        return 4
    if p['i_req_write'] and p['i_req_wstrobe'] >> size:
        return 6
    return 0


def response(write, tag, data=0, error=0, corrected=False, uncorrectable=False):
    return dict(o_rsp_write=int(write), o_rsp_tag=tag, o_rsp_rdata=data, o_rsp_error=int(bool(error)),
                o_rsp_error_code=error, o_rsp_corrected=int(corrected), o_rsp_uncorrectable=int(uncorrectable))


class ScratchpadBankModel:
    def __init__(self, c):
        self.c = c
        self.memory = ['x' * c.stored_width for _ in range(c.DEPTH_WORDS)]
        self.initialized_bits = [0] * c.DEPTH_WORDS
        self.total_in = self.total_out = self.discarded = self.clock = 0
        self.reset()

    def reset(self, *, flush=False):
        self.discarded += len(getattr(self, 'pending', ()))
        self.pending = deque()
        self.reads = deque()
        self.next_slot = 0
        self.work = None
        if not flush:
            self.error = self.flush_seen = 0
        self.events = dict.fromkeys(EVENTS, 0)

    def request(self, ports):
        c = self.c
        p = {n: number(v) for n, v in ports.items()}
        error = legality(c, ports)
        write = p['i_req_write'] == 1
        entry = dict(slot=self.next_slot, tag=p['i_req_tag'] or 0, write=write,
                     result=None, error=error, rmw=False, word=0, offset=0, size=0,
                     shifted_data='0' * c.DATA_WIDTH, mask=0)
        if not error:
            word, offset = divmod(p['i_req_address'], c.bytes)
            size = 1 << p['i_req_size_log2']
            mask = p['i_req_wstrobe'] << offset if write else 0
            raw = bits(ports['i_req_wdata'], c.DATA_WIDTH)
            shifted = '0' * c.DATA_WIDTH
            for b in range(c.bytes):
                if write and p['i_req_wstrobe'] >> b & 1:
                    byte = raw[c.DATA_WIDTH - 8 * (b + 1):c.DATA_WIDTH - 8 * b]
                    if set(byte) & set('xz'):
                        raise AssertionError(f'SCRATCHPAD_BANK_PROTOCOL: selected write byte {b}')
                    shifted = splice(shifted, int(byte, 2) << (8 * (b + offset)), 255 << (8 * (b + offset)))
            group_bytes = c.PARITY_GRANULARITY // 8
            partial = any(0 < (mask >> start & ((1 << group_bytes) - 1)) < (1 << group_bytes) - 1
                          for start in range(0, c.bytes, group_bytes))
            rmw = bool(write and mask and (c.PROTECTION_MODE == 2 and not (
                offset == 0 and size == c.bytes and p['i_req_wstrobe'] == (1 << c.bytes) - 1) or
                c.PROTECTION_MODE == 1 and partial))
            entry.update(word=word, offset=offset, size=size, mask=mask, rmw=rmw, shifted_data=shifted)
        return entry

    def write_operation(self, entry, data):
        c = self.c
        code = encode(c, data)
        mask = entry['mask']
        if c.PROTECTION_MODE == 0:
            physical_mask = mask
            bitmask = sum(255 << (8 * b) for b in range(c.bytes) if mask >> b & 1)
        elif c.PROTECTION_MODE == 2:
            physical_mask = bitmask = (1 << c.stored_width) - 1
        else:
            group = c.PARITY_GRANULARITY // 8
            physical_mask = 0
            for g in range(c.DATA_WIDTH // c.PARITY_GRANULARITY):
                if mask >> (g * group) & ((1 << group) - 1):
                    physical_mask |= ((1 << c.PARITY_GRANULARITY) - 1) << (g * c.PARITY_GRANULARITY)
                    physical_mask |= 1 << (c.DATA_WIDTH + g)
            bitmask = physical_mask
        return dict(write=True, word=entry['word'], data=code, mask=physical_mask, bitmask=bitmask)

    def decode(self, entry, raw, initialized=0):
        c = self.c
        corrected, good, repaired = False, True, raw
        data = raw[-c.DATA_WIDTH:]
        if c.PROTECTION_MODE == 0:
            for bit in range(8 * entry['offset'], 8 * (entry['offset'] + entry['size'])):
                if initialized >> bit & 1 and raw[-1 - bit] in 'xz':
                    raise AssertionError('SCRATCHPAD_BANK_PROTOCOL: unknown initialized read data')
        if c.PROTECTION_MODE == 2:
            if set(raw) & set('xz'):
                good = False
            else:
                result = ecc_decode(c.ecc, int(raw, 2))
                good = result['o_uncorrectable'] == '0'
                corrected = result['o_corrected'] == '1' and good
                data, repaired = result['o_decoded_data'], result['o_corrected_codeword']
        elif c.PROTECTION_MODE == 1:
            group = c.PARITY_GRANULARITY // 8
            for g in range(c.DATA_WIDTH // c.PARITY_GRANULARITY):
                touched = entry['mask'] >> (g * group) & ((1 << group) - 1)
                check = 0 < touched < (1 << group) - 1 if entry['write'] else (
                    g * group < entry['offset'] + entry['size'] and (g + 1) * group > entry['offset'])
                if check:
                    values = data[c.DATA_WIDTH - (g + 1) * c.PARITY_GRANULARITY:c.DATA_WIDTH - g * c.PARITY_GRANULARITY] + raw[-1 - c.DATA_WIDTH - g]
                    good &= not (set(values) & set('xz')) and values.count('1') % 2 == 0
        error = 0 if good else 7 if c.PROTECTION_MODE == 1 else 8
        value = 0
        if good and not entry['write']:
            selected = data[c.DATA_WIDTH - 8 * (entry['offset'] + entry['size']):c.DATA_WIDTH - 8 * entry['offset']]
            value = '0' * (c.DATA_WIDTH - len(selected)) + selected
        rsp = response(entry['write'], entry['tag'], value, error, corrected, not good)
        operation = None
        if good and entry['rmw']:
            bitmask = sum(255 << (8 * b) for b in range(c.bytes) if entry['mask'] >> b & 1)
            merged = splice(data, entry['shifted_data'], bitmask)
            operation = self.write_operation(entry, merged)
        elif good and corrected and c.SCRUB_ON_CORRECT:
            operation = dict(write=True, word=entry['word'], data=repaired,
                             mask=(1 << c.stored_width) - 1, bitmask=(1 << c.stored_width) - 1)
        return rsp, operation, corrected, not good

    def evaluate(self, ports, protocol=None):
        c = self.c
        p = {n: number(v) for n, v in ports.items()}
        run = p['i_rstb'] == 1
        normal = run and p['i_flush'] == 0
        flushing = run and p['i_flush'] == 1
        entry = self.request(ports) if p['i_req_valid'] == 1 else None
        busy = bool(self.pending or self.reads or self.work or flushing)
        out = dict.fromkeys(OUTPUTS, 0)
        out.update(o_busy=int(busy), o_idle=int(not busy and not self.error),
                   o_outstanding=len(self.pending), o_error=int(bool(self.error)), o_error_code=self.error,
                   o_req_ready=int(normal and not self.error and len(self.pending) < c.MAX_OUTSTANDING and
                                   self.work is None and not (protocol and 'backend_req_ready' in protocol)),
                   o_rsp_valid=int(normal and bool(self.pending) and self.pending[0]['result'] is not None))
        if out['o_rsp_valid']:
            out.update(self.pending[0]['result'])
        out.update({n: value if run else 0 for n, value in self.events.items()})
        accept = bool(out['o_req_ready'] and p['i_req_valid'] == 1)
        consume = bool(out['o_rsp_valid'] and p['i_rsp_ready'] == 1)
        capture = bool(normal and self.reads and self.reads[0]['due'] <= self.clock)
        commit = bool(normal and self.work and self.work['stage'] == 'commit')
        physical = None
        if commit:
            physical = self.work['operation']
        elif accept and not entry['error'] and (not entry['write'] or entry['mask']):
            physical = (dict(write=False, word=entry['word'], data='0' * c.stored_width, mask=0)
                        if not entry['write'] or entry['rmw'] else self.write_operation(entry, entry['shifted_data']))
        return out, dict(p=p, run=run, normal=normal, flushing=flushing, accept=accept, consume=consume,
                         capture=capture, commit=commit, entry=entry, physical=physical,
                         occupancy=len(self.pending), work=None if self.work is None else self.work['stage'],
                         protocol=protocol, corrected=False, uncorrectable=False, scrub=False,
                         result=None)

    def step(self, ports, edge, protocol=None):
        _, q = self.evaluate(ports, protocol)
        if not edge:
            return q
        p = q['p']
        if p['i_rstb'] == 0:
            self.reset()
        elif q['run']:
            self.events = dict.fromkeys(EVENTS, 0)
            if q['normal'] and protocol:
                self.error = 9
            elif q['normal'] and not self.pending and not self.work and not self.reads and p['i_error_clear'] == 1:
                self.error = 0
            if q['flushing']:
                was_seen = self.flush_seen
                self.reset(flush=True)
                self.events['o_flush_completed'] = int(not was_seen)
            else:
                if q['consume']:
                    self.pending.popleft()
                    self.total_out += 1
                if q['commit']:
                    work = self.work
                    work['entry']['result'] = work['result']
                    q['scrub'] = not work['entry']['write']
                    self.work = None
                if q['capture']:
                    read = self.reads.popleft()
                    target = read['entry']
                    rsp, operation, corrected, bad = self.decode(target, read['raw'], read['initialized'])
                    q.update(corrected=corrected, uncorrectable=bad, result=rsp)
                    if operation:
                        self.work = dict(stage='commit', entry=target, result=rsp, operation=operation)
                    else:
                        target['result'] = rsp
                        if self.work and self.work['entry'] is target:
                            self.work = None
                if q['accept']:
                    target = q['entry']
                    self.pending.append(target)
                    self.total_in += 1
                    self.next_slot = (self.next_slot + 1) % self.c.MAX_OUTSTANDING
                    if target['error'] or target['write'] and not target['rmw']:
                        target['result'] = response(target['write'], target['tag'], error=target['error'])
                    else:
                        self.reads.append(dict(entry=target, raw=self.memory[target['word']],
                                               initialized=self.initialized_bits[target['word']],
                                               due=self.clock + self.c.BACKEND_READ_LATENCY + 1))
                        if target['rmw'] or self.c.PROTECTION_MODE == 2:
                            self.work = dict(stage='wait', entry=target)
                if q['physical'] and q['physical']['write']:
                    operation = q['physical']
                    self.memory[operation['word']] = splice(self.memory[operation['word']], operation['data'], operation['bitmask'])
                    self.initialized_bits[operation['word']] |= operation['bitmask']
                self.events.update(o_request_accepted=int(q['accept']),
                    o_read_accepted=int(q['accept'] and not q['entry']['error'] and not q['entry']['write']),
                    o_write_accepted=int(q['accept'] and not q['entry']['error'] and q['entry']['write']),
                    o_response_accepted=int(q['consume']), o_corrected_event=int(q['corrected']),
                    o_uncorrectable_event=int(q['uncorrectable']), o_scrub_completed=int(q['scrub']))
            if p['i_flush'] in (0, 1):
                self.flush_seen = int(q['flushing'])
        self.clock += 1
        assert self.total_in == self.total_out + self.discarded + len(self.pending)
        return q
