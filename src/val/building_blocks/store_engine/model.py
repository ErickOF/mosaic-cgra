"""Independent affine descriptor math and an ordered completion ledger.

The shared load reference supplies mathematical rectangle/address functions only;
store handshakes, framing, ownership, retirement and errors are predicted here.
No private DUT state seeds functional expectations.
"""

from collections import deque
from load_engine.model import address as load_address, legality, number
from store_engine.transaction import DESCRIPTOR, EVENTS, OUTPUTS


def mapped_descriptor(p):
    return p | {'i_emit_end_of_stream': p['i_expect_end_of_stream']}


def address(c, d, index):
    return load_address(c, mapped_descriptor(d), index)


def stream_fault(p, expected):
    fields = ('i_stream_keep', 'i_stream_first', 'i_stream_last', 'i_stream_row_first',
              'i_stream_row_last', 'i_stream_end_of_stream', 'i_stream_error',
              'i_stream_channel_id', 'i_stream_context_id')
    if any(p[name] is None for name in fields):
        return 16
    if p['i_stream_error']:
        return 17
    if p['i_stream_context_id'] != expected['context_id']:
        return 18
    if p['i_stream_channel_id'] != expected['channel_id']:
        return 19
    if p['i_stream_keep'] != expected['keep']:
        return 20
    if any(p['i_stream_' + name] != expected[name] for name in
           ('first', 'last', 'row_first', 'row_last', 'end_of_stream')):
        return 21
    return 0


class StoreEngineModel:
    def __init__(self, c):
        self.c = c
        self.accepted = self.retired = self.discarded = self.legal_beats = 0
        self.fault = False
        self.reset()

    def reset(self):
        self.discarded += len(getattr(self, 'pending', ()))
        self.pending = deque()
        self.descriptor = None
        self.cursor = 0
        self.next_tag = 0
        self.active = False
        self.error = self.memory_error = 0
        self.events = dict.fromkeys(EVENTS, 0)

    def evaluate(self, ports):
        p = {name: number(raw) for name, raw in ports.items()}
        c = self.c
        run = p['i_rstb'] == 1
        out = dict.fromkeys(OUTPUTS, 0)
        out.update(o_busy=int(self.active or bool(self.pending)),
                   o_idle=int(not self.active and not self.pending and not self.error),
                   o_error=int(bool(self.error)), o_error_code=self.error,
                   o_memory_error_seen=self.memory_error, o_outstanding=len(self.pending),
                   o_mem_rsp_ready=int(run),
                   o_config_ready=int(run and not self.active and not self.pending and
                                      not self.error and not self.fault and p['i_error_clear'] == 0))
        out.update({name: value if run else 0 for name, value in self.events.items()})
        issuing = (run and self.active and not self.error and not self.fault and
                   self.cursor < self.descriptor['i_inner_count'] * self.descriptor['i_outer_count'])
        expected = address(c, self.descriptor, self.cursor) if issuing else None
        presented = issuing and p['i_stream_valid'] == 1
        stream_error = stream_fault(p, expected) if presented else 0
        capacity = len(self.pending) < c.MAX_OUTSTANDING
        out['o_stream_ready'] = int(issuing and (stream_error != 0 or
                                                capacity and p['i_mem_req_ready'] == 1))
        if presented and not stream_error and capacity:
            out['o_mem_req_valid'] = 1
            for name in ('address', 'size_log2', 'address_space', 'channel_id', 'context_id'):
                out['o_mem_req_' + name] = expected[name]
            out['o_mem_req_tag'] = self.next_tag
            out['o_mem_req_strobe'] = expected['keep']
            # Preserve X/Z in disabled bytes; only enabled bytes enter prediction.
            low_bits = expected['keep'].bit_count() * 8
            raw = ports['i_stream_data']
            if isinstance(raw, int):
                data = raw & ((1 << low_bits) - 1)
            else:
                data = number(raw[-low_bits:])
            out['o_mem_req_data'] = data
        config = bool(out['o_config_ready'] and p['i_config_valid'] == 1)
        request = bool(out['o_mem_req_valid'] and p['i_mem_req_ready'] == 1)
        stream = bool(out['o_stream_ready'] and p['i_stream_valid'] == 1)
        response = run and p['i_mem_rsp_valid'] == 1
        retire = bool(run and self.pending and self.pending[0]['response'] is not None)
        desc_error = legality(c, mapped_descriptor(p)) if config else 0
        rsp_error = 0
        target = None
        if response:
            tag = p['i_mem_rsp_tag']
            if tag is None or p['i_mem_rsp_error'] is None:
                rsp_error = 15
            elif tag >= c.MAX_OUTSTANDING:
                rsp_error = 12
            else:
                target = next((e for e in self.pending if e['tag'] == tag), None)
                rsp_error = 13 if target is None else 14 if target['response'] is not None else 0
        bad_stream = bool(stream and stream_error)
        runtime = self.active and not self.error and self.fault
        fatal = rsp_error or desc_error or (stream_error if bad_stream else 0) or (11 if runtime else 0)
        start = config and not desc_error
        remaining = len(self.pending) + request - retire
        retiring_error = retire and bool(self.pending[0]['response'])
        finish = bool(retire and self.pending[0]['last'] and not self.error and not fatal)
        fail = bool(desc_error or ((self.error or fatal) and (self.active or start) and not remaining))
        return out, dict(p=p, run=run, issuing=issuing, expected=expected, config=config,
                         request=request, stream=stream, response=response, retire=retire,
                         desc_error=desc_error, rsp_error=rsp_error, stream_error=stream_error,
                         bad_stream=bad_stream, target=target, fatal=fatal, start=start,
                         prior_occupancy=len(self.pending), prior_active=self.active,
                         prior_cursor=self.cursor, prior_error=self.error, prior_descriptor=self.descriptor,
                         prior_head=self.pending[0]['tag'] if self.pending else None,
                         prior_reordered=any(e['response'] is not None for e in list(self.pending)[1:]),
                         finish=finish, fail=fail, retiring_error=retiring_error)

    def step(self, ports, edge):
        _, plan = self.evaluate(ports)
        p = plan['p']
        if not edge:
            return set(), plan
        if p['i_rstb'] == 0:
            self.reset()
            return {'reset'}, plan
        if not plan['run']:
            return set(), plan
        events = set()
        self.events = dict.fromkeys(EVENTS, 0)
        for key, port in (('start', 'o_command_started'), ('stream', 'o_stream_accepted'),
                          ('request', 'o_request_accepted'), ('response', 'o_response_accepted'),
                          ('retire', 'o_response_retired'), ('finish', 'o_command_completed'),
                          ('fail', 'o_command_failed')):
            self.events[port] = int(plan[key])
            if plan[key]:
                events.add(key)
        self.events['o_completed_with_error'] = int(plan['finish'] and
                                                   (self.memory_error or plan['retiring_error']))
        if plan['config']:
            self.memory_error = 0
        if plan['start']:
            self.descriptor = {name: p[name] for name in DESCRIPTOR}
            self.cursor = 0
        if plan['response'] and not plan['rsp_error']:
            plan['target']['response'] = p['i_mem_rsp_error']
            if p['i_mem_rsp_error']:
                events.add('memory_error')
        if plan['retire']:
            if plan['retiring_error']:
                self.memory_error = 1
            self.pending.popleft()
            self.retired += 1
        if plan['request']:
            assert plan['stream'] and not plan['stream_error'], 'Unpaired write'
            assert all(e['tag'] != self.next_tag for e in self.pending), 'Early tag reuse'
            entry = address(self.c, self.descriptor, self.cursor)
            entry.update(tag=self.next_tag, response=None, ordinal=self.cursor)
            self.pending.append(entry)
            self.cursor += 1
            self.next_tag = (self.next_tag + 1) % self.c.MAX_OUTSTANDING
            self.accepted += 1
            self.legal_beats += 1
        if plan['bad_stream']:
            events.add('malformed')
        if plan['fatal']:
            events.add('fatal')
            if not self.error:
                self.error = plan['fatal']
        elif not self.active and not self.pending and p['i_error_clear'] == 1:
            self.error = 0
            events.add('clear')
        if plan['start']:
            self.active = True
        if plan['finish'] or plan['fail']:
            self.active = False
        assert self.accepted == self.retired + self.discarded + len(self.pending)
        return events, plan
