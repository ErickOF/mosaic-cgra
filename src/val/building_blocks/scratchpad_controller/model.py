"""Independent per-client obligation queues and arithmetic mapping reference.

Public bank responses update obligations; a separate storage scoreboard validates
those payloads. Arbitration is modeled with rotating Python lists, not RTL state.
"""
from collections import deque
from mosaic_uvm.logic import bits
from scratchpad_controller.transaction import PORTS, REQ_FIELDS, RSP_FIELDS


def number(raw):
    return int(raw, 2) if isinstance(raw, str) and set(raw) <= {'0', '1'} else raw if isinstance(raw, int) else None


def raw(value, width):
    return bits(value, width) if isinstance(value, int) else value.lower()


def unpack(value, count, width):
    text = raw(value, count * width)
    return [number(text[len(text) - (n + 1) * width:len(text) - n * width]) for n in range(count)]


def pack(values, width):
    return ''.join(raw(v, width) for v in reversed(values))


def fields(p, prefix, count, c, names):
    return [{name: unpack(p[prefix + name], count, c.widths[prefix + name] // count)[n]
             for name in names} for n in range(count)]


def mapping(c, address):
    # Enumerating stripe owners expresses the reference without binary slicing.
    stripe, offset = divmod(address, c.INTERLEAVE_BYTES)
    row, bank = divmod(stripe, c.NUM_BANKS)
    if c.MAP_MODE:
        bank ^= row % c.NUM_BANKS
    return bank, row * c.INTERLEAVE_BYTES + offset


def classify(c, req):
    if any(req[n] is None for n in ('write', 'address', 'size_log2', 'tag')) or (
            req['write'] and req['wstrobe'] is None):
        return 1
    if req['address'] >= c.capacity:
        return 2
    if req['size_log2'] > c.bytes.bit_length() - 1:
        return 3
    size = 2 ** req['size_log2']
    if req['address'] % c.bytes + size > c.bytes:
        return 5
    if req['address'] % size:
        return 4
    if req['write'] and req['wstrobe'] >= 2 ** size:
        return 6
    return 0


def response(write=0, tag=0, data=0, code=0, corrected=0, uncorrectable=0):
    return dict(write=write, tag=tag, rdata=data, error=int(code != 0), error_code=code,
                corrected=corrected, uncorrectable=uncorrectable)


def winner(candidates, pointer, count):
    return next((n for n in [(pointer + k) % count for k in range(count)] if n in candidates), None)


class ControllerModel:
    def __init__(self, c):
        self.c = c
        self.accepted = self.retired = self.canceled = 0
        self.reset()

    def reset(self):
        c = self.c
        if hasattr(self, 'queues'):
            self.canceled += sum(map(len, self.queues))
        self.queues = [deque() for _ in range(c.NUM_CLIENTS)]
        self.issue = [0] * c.NUM_CLIENTS
        self.rpointer = [0] * c.NUM_BANKS
        self.pending = [None] * c.NUM_BANKS
        self.cpointer = [0] * c.NUM_CLIENTS
        self.read = [c.DEFAULT_ALLOW] * (c.NUM_CLIENTS * c.NUM_BANKS)
        self.write = self.read.copy()
        self.error = 0
        self.flushing = self.seen = self.done = False
        self.acks = set()
        self.events = dict(o_request_accepted=0, o_response_accepted=0,
                           o_permission_denied=0, o_bank_conflict=0, o_permission_updated=0)

    def evaluate(self, ports):
        c = self.c
        p = {n: number(v) for n, v in ports.items()}
        reqs = fields(ports, 'i_client_req_', c.NUM_CLIENTS, c, REQ_FIELDS)
        rsps = fields(ports, 'i_bank_rsp_', c.NUM_BANKS, c, RSP_FIELDS)
        req_valid = unpack(ports['i_client_req_valid'], c.NUM_CLIENTS, 1)
        bank_valid = unpack(ports['i_bank_rsp_valid'], c.NUM_BANKS, 1)
        bank_ready = unpack(ports['i_bank_req_ready'], c.NUM_BANKS, 1)
        ready = unpack(ports['i_client_rsp_ready'], c.NUM_CLIENTS, 1)
        run = p['i_rstb'] == 1
        start = run and p['i_flush'] == 1 and not (self.seen or self.flushing or self.done)
        cancel = self.flushing or p['i_flush'] != 0 or self.done
        active = run and not cancel
        empty = not any(self.queues)
        quiet = empty and p['i_bank_idle'] == (1 << c.NUM_BANKS) - 1 and not any(
            n is not None for n in self.pending) and not cancel
        perm_ready = bool(c.ENFORCE_PERMISSIONS and run and quiet and not self.error)
        perm_accept = perm_ready and p['i_perm_valid'] == 1
        issuing = active and not self.error and not perm_accept
        errors, mapped, candidates = [], [], [set() for _ in range(c.NUM_BANKS)]
        for n, req in enumerate(reqs):
            code = classify(c, req) if req_valid[n] == 1 else 0
            location = mapping(c, req['address']) if req_valid[n] == 1 and code == 0 else (0, 0)
            if req_valid[n] == 1 and not code and c.ENFORCE_PERMISSIONS:
                permission = self.write if req['write'] else self.read
                if permission[n * c.NUM_BANKS + location[0]] != 1:
                    code = 10
            errors.append(code)
            mapped.append(location)
            if issuing and req_valid[n] == 1 and not code and len(self.queues[n]) < c.MAX_OUTSTANDING_PER_CLIENT:
                candidates[location[0]].add(n)
        selected = [self.pending[b] if self.pending[b] is not None else
                    winner(candidates[b], self.rpointer[b], c.NUM_CLIENTS) for b in range(c.NUM_BANKS)]
        bank_requests = [None] * c.NUM_BANKS
        client_ready = [0] * c.NUM_CLIENTS
        for n in range(c.NUM_CLIENTS):
            if issuing and req_valid[n] == 1 and errors[n] and len(self.queues[n]) < c.MAX_OUTSTANDING_PER_CLIENT:
                client_ready[n] = 1
        for b, n in enumerate(selected):
            if n is not None and n in candidates[b]:
                req = reqs[n].copy()
                req['address'] = mapped[n][1]
                req['tag'] = n * 2 ** c.slot_width + self.issue[n]
                if not req['write']:
                    req['wdata'] = req['wstrobe'] = 0
                else:
                    # Unknown disabled bytes are isolated, and need not resolve.
                    original = raw(ports['i_client_req_wdata'], c.NUM_CLIENTS * c.DATA_WIDTH)
                    text = original[-(n + 1) * c.DATA_WIDTH:len(original) - n * c.DATA_WIDTH]
                    clean = ''.join(text[k:k+8] if req['wstrobe'] >> ((c.DATA_WIDTH - k) // 8 - 1) & 1 else
                                    '00000000' for k in range(0, c.DATA_WIDTH, 8))
                    req['wdata'] = number(clean) if number(clean) is not None else clean
                bank_requests[b] = req
                client_ready[n] = int(bank_ready[b] == 1)
        client_responses = [q[0]['result'] if active and q and q[0]['result'] is not None else None for q in self.queues]
        allocations = [n for n in range(c.NUM_CLIENTS) if req_valid[n] == 1 and client_ready[n]]
        retirements = [n for n in range(c.NUM_CLIENTS) if client_responses[n] is not None and ready[n] == 1]
        targets = [None] * c.NUM_BANKS
        malformed = [0] * c.NUM_BANKS
        entry = [None] * c.NUM_BANKS
        for b, rsp in enumerate(rsps):
            if bank_valid[b] != 1:
                continue
            tag = rsp['tag']
            if tag is None:
                malformed[b] = 1
                continue
            n, slot = divmod(tag, 2 ** c.slot_width)
            if n >= c.NUM_CLIENTS:
                malformed[b] = 2
            elif slot >= c.MAX_OUTSTANDING_PER_CLIENT:
                malformed[b] = 3
            else:
                entry[b] = next((e for e in self.queues[n] if e['slot'] == slot), None)
                e = entry[b]
                if e is None:
                    malformed[b] = 4
                elif e['result'] is not None:
                    malformed[b] = 5
                else:
                    targets[b] = n
                    if e['bank'] != b:
                        malformed[b] = 6
                    elif rsp['write'] != e['req']['write']:
                        malformed[b] = 7
                    elif any(rsp[f] is None for f in ('error', 'error_code', 'corrected', 'uncorrectable')) or (
                        rsp['error_code'] > 9 or rsp['corrected'] and rsp['uncorrectable'] or
                        rsp['error'] != int(rsp['error_code'] != 0) or rsp['uncorrectable'] and not rsp['error']):
                        malformed[b] = 8
        collections = [winner({b for b in range(c.NUM_BANKS) if targets[b] == n},
                       self.cpointer[n], c.NUM_BANKS) if active else None for n in range(c.NUM_CLIENTS)]
        rsp_ready = [int(active and bank_valid[b] == 1 and targets[b] is None) for b in range(c.NUM_BANKS)]
        for b in collections:
            if b is not None:
                rsp_ready[b] = 1
        bank_accept = [b for b in range(c.NUM_BANKS) if bank_requests[b] and bank_ready[b] == 1]
        bank_collect = [b for b in range(c.NUM_BANKS) if bank_valid[b] == 1 and rsp_ready[b]]
        flush = [int(run and (start or self.flushing) and (start or b not in self.acks)) for b in range(c.NUM_BANKS)]
        out = dict(o_client_req_ready=pack(client_ready, 1), o_bank_rsp_ready=pack(rsp_ready, 1),
            o_bank_flush=pack(flush, 1), o_flushing=int(run and (start or self.flushing)),
            o_flush_completed=int(run and self.done), o_idle=int(run and quiet and not self.error),
            o_busy=int(run and (not empty or start or self.flushing)), o_perm_ready=int(perm_ready),
            o_client_outstanding=pack([len(q) if run else 0 for q in self.queues], c.aliases['O']),
            o_error=int(run and self.error != 0), o_error_code=self.error if run else 0)
        for side, kind, payloads, names in [('bank', 'req', bank_requests, REQ_FIELDS),
                                           ('client', 'rsp', client_responses, RSP_FIELDS)]:
            out[f'o_{side}_{kind}_valid'] = pack([int(e is not None) for e in payloads], 1)
            for name in names:
                port = f'o_{side}_{kind}_{name}'
                out[port] = pack([e[name] if e else 0 for e in payloads], c.widths[port] // len(payloads))
        out.update({n: v if run else 0 for n, v in self.events.items()})
        plan = dict(p=p, reqs=reqs, rsps=rsps, run=run, start=start, cancel=cancel, active=active,
            quiet=quiet, errors=errors, mapped=mapped, candidates=candidates, selected=selected,
            bank_requests=bank_requests, client_responses=client_responses, allocations=allocations,
            retirements=retirements, collections=collections, targets=targets, entry=entry,
            malformed=malformed, bank_accept=bank_accept, bank_collect=bank_collect, flush=flush,
            perm_accept=perm_accept, old_error=bool(self.error))
        return {n: raw(v, c.widths[n]) for n, v in out.items()}, plan

    def step(self, ports, edge):
        out, q = self.evaluate(ports)
        c, p = self.c, q['p']
        if p['i_rstb'] == 0 and (edge or c.ASYNC_RESET):
            self.reset()
        elif edge and q['run']:
            self.events = dict(o_request_accepted=sum(1 << n for n in q['allocations']),
                o_response_accepted=sum(1 << n for n in q['retirements']),
                o_permission_denied=sum(1 << n for n in q['allocations'] if q['errors'][n] == 10),
                o_bank_conflict=sum(1 << b for b, v in enumerate(q['candidates']) if len(v) > 1),
                o_permission_updated=int(q['perm_accept']))
            # Collect before allocating: a zero-cycle bank response is never a
            # response to a request first accepted on this same edge.
            for n, b in enumerate(q['collections']):
                if b is not None:
                    e = q['entry'][b]
                    e['result'] = response(e['req']['write'], e['req']['tag'], code=9, uncorrectable=1) if q['malformed'][b] else (
                        q['rsps'][b] | dict(tag=e['req']['tag']))
                    self.cpointer[n] = (b + 1) % c.NUM_BANKS
            for n in q['retirements']:
                self.queues[n].popleft()
                self.retired += 1
            for n in q['allocations']:
                req = q['reqs'][n].copy()
                req['tag'] = req['tag'] or 0
                req['write'] = int(req['write'] == 1)
                code = q['errors'][n]
                self.queues[n].append(dict(slot=self.issue[n], req=req, bank=q['mapped'][n][0],
                    result=response(req['write'], req['tag'], code=code) if code else None))
                self.issue[n] = (self.issue[n] + 1) % c.MAX_OUTSTANDING_PER_CLIENT
                self.accepted += 1
            if not self.error:
                self.error = next((q['malformed'][b] for b in q['bank_collect'] if q['malformed'][b]), 0)
            elif q['quiet'] and p['i_error_clear'] == 1 and not any(q['malformed'][b] for b in q['bank_collect']):
                self.error = 0
            for b, selected in enumerate(q['selected']):
                if q['cancel'] or q['old_error']:
                    self.pending[b] = None
                    self.rpointer[b] = 0
                elif b in q['bank_accept']:
                    self.rpointer[b] = (selected + 1) % c.NUM_CLIENTS
                    self.pending[b] = None
                elif selected is not None:
                    self.pending[b] = selected
            if q['perm_accept']:
                self.read = [int(v == 1) for v in unpack(ports['i_read_permission'], c.NUM_CLIENTS * c.NUM_BANKS, 1)]
                self.write = [int(v == 1) for v in unpack(ports['i_write_permission'], c.NUM_CLIENTS * c.NUM_BANKS, 1)]
            self.done = False
            if q['start']:
                self.acks = set()
            if q['start'] or self.flushing:
                self.acks.update(b for b, bit in enumerate(unpack(ports['i_bank_flush_completed'], c.NUM_BANKS, 1))
                                 if q['flush'][b] and bit == 1)
                self.flushing = len(self.acks) < c.NUM_BANKS
                self.done = not self.flushing
            if p['i_flush'] in (0, 1):
                self.seen = p['i_flush'] == 1
            if self.flushing or q['start'] or p['i_flush'] == 1 or q['cancel'] and p['i_flush'] == 0:
                self.canceled += sum(map(len, self.queues))
                self.queues = [deque() for _ in range(c.NUM_CLIENTS)]
                self.issue = [0] * c.NUM_CLIENTS
                self.cpointer = [0] * c.NUM_CLIENTS
        return q
