"""Independent affine descriptors and an ordered, tag-owned transaction ledger.

No DUT storage, AGU internals, generated model or RTL recurrence is used to predict
addresses. The nth address follows the descriptor's mathematical row/column formula.
"""
from collections import deque
from load_engine.transaction import DESCRIPTOR, EVENTS, OUTPUTS


def number(raw):
    if isinstance(raw, int):
        return raw
    return None if any(b in raw.lower() for b in 'xz') else int(raw, 2)


def signed(value, width):
    return value - (1 << width) if value >> (width - 1) else value


def legality(c, d):
    if any(d[n] is None for n in DESCRIPTOR):
        return 9
    mode, inner, outer, size = (d[n] for n in (
        'i_mode', 'i_inner_count', 'i_outer_count', 'i_element_size_log2'))
    if mode == 3:
        return 1
    if not inner:
        return 2
    if not outer:
        return 3
    if mode != 2 and outer != 1:
        return 4
    if size > c.max_log2:
        return 5
    element = 1 << size
    base = d['i_base_address']
    step = element if mode == 0 else signed(d['i_inner_stride'], c.ADDR_WIDTH)
    row = signed(d['i_outer_stride'], c.ADDR_WIDTH) if mode == 2 else 0
    if base % element:
        return 6
    if mode != 0 and step % element:
        return 7
    if mode == 2 and row % element:
        return 8
    corners = [base + i * step + o * row for i in (0, inner - 1) for o in (0, outer - 1)]
    if min(corners) < 0 or max(corners) + element > 1 << c.ADDR_WIDTH:
        return 10
    return 0


def address(c, d, index):
    row, col = divmod(index, d['i_inner_count'])
    size = d['i_element_size_log2']
    inner = 1 << size if d['i_mode'] == 0 else signed(d['i_inner_stride'], c.ADDR_WIDTH)
    outer = signed(d['i_outer_stride'], c.ADDR_WIDTH) if d['i_mode'] == 2 else 0
    final = index + 1 == d['i_inner_count'] * d['i_outer_count']
    return dict(address=d['i_base_address'] + row * outer + col * inner, size_log2=size,
                address_space=d['i_address_space'], channel_id=d['i_channel_id'],
                context_id=d['i_context_id'], keep=(1 << (1 << size)) - 1,
                first=int(index == 0), last=int(final), row_first=int(col == 0),
                row_last=int(col + 1 == d['i_inner_count']),
                end_of_stream=int(final and d['i_emit_end_of_stream']))


class LoadEngineModel:
    def __init__(self, config):
        self.c = config
        self.accepted = self.delivered = self.discarded = 0
        self.fault = False
        self.reset()

    def reset(self):
        self.discarded += len(getattr(self, 'pending', ()))
        self.pending = deque()
        self.descriptor = None
        self.cursor = 0
        self.next_tag = 0
        self.active = False
        self.error = 0
        self.memory_error = 0
        self.events = dict.fromkeys(EVENTS, 0)

    def evaluate(self, ports):
        p = {n: number(v) for n, v in ports.items()}
        run = p['i_rstb'] == 1
        c = self.c
        out = dict.fromkeys(OUTPUTS, 0)
        out.update(o_busy=int(self.active or bool(self.pending)),
                   o_idle=int(not self.active and not self.pending and not self.error),
                   o_error=int(bool(self.error)), o_error_code=self.error,
                   o_memory_error_seen=self.memory_error, o_outstanding=len(self.pending),
                   o_mem_rsp_ready=int(run),
                   o_config_ready=int(run and not self.active and not self.pending and
                                      not self.error and not self.fault and p['i_error_clear'] == 0))
        out.update({n: v if run else 0 for n, v in self.events.items()})
        if (run and self.active and not self.error and not self.fault and
                self.cursor < self.descriptor['i_inner_count'] * self.descriptor['i_outer_count'] and
                len(self.pending) < c.MAX_OUTSTANDING):
            out['o_mem_req_valid'] = 1
            req = address(c, self.descriptor, self.cursor)
            for n in ('address', 'size_log2', 'address_space', 'channel_id', 'context_id'):
                out['o_mem_req_' + n] = req[n]
            out['o_mem_req_tag'] = self.next_tag
        if run and self.pending and self.pending[0]['response'] is not None:
            out['o_stream_valid'] = 1
            head = self.pending[0]
            data, error = head['response']
            mask = (1 << (8 * head['keep'].bit_count())) - 1
            out['o_stream_data'] = 0 if error else data & mask
            out['o_stream_error'] = error
            for n in ('keep', 'first', 'last', 'row_first', 'row_last', 'end_of_stream',
                      'channel_id', 'context_id'):
                out['o_stream_' + n] = head[n]
        config = bool(out['o_config_ready'] and p['i_config_valid'] == 1)
        request = bool(out['o_mem_req_valid'] and p['i_mem_req_ready'] == 1)
        response = bool(run and p['i_mem_rsp_valid'] == 1)
        stream = bool(out['o_stream_valid'] and p['i_stream_ready'] == 1)
        desc_error = legality(c, p) if config else 0
        rsp_error = 0
        target = None
        if response:
            if p['i_mem_rsp_tag'] is None or p['i_mem_rsp_error'] is None:
                rsp_error = 15
            elif p['i_mem_rsp_tag'] >= c.MAX_OUTSTANDING:
                rsp_error = 12
            else:
                target = next((e for e in self.pending if e['tag'] == p['i_mem_rsp_tag']), None)
                rsp_error = 13 if target is None else 14 if target['response'] is not None else 0
        runtime = self.active and not self.error and self.fault
        fatal = rsp_error or desc_error or (11 if runtime else 0)
        start = config and not desc_error
        remaining = len(self.pending) + request - stream
        finish = stream and self.pending[0]['last'] and not self.error and not fatal
        fail = bool(desc_error or ((self.error or fatal) and (self.active or start) and not remaining))
        return out, dict(p=p, run=run, config=config, request=request, response=response,
                         stream=stream, desc_error=desc_error, rsp_error=rsp_error, target=target,
                         fatal=fatal, start=start, finish=finish, fail=fail)

    def step(self, ports, edge):
        out, plan = self.evaluate(ports)
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
        for key, port in (('start', 'o_command_started'), ('request', 'o_request_accepted'),
                          ('response', 'o_response_accepted'), ('stream', 'o_stream_accepted'),
                          ('finish', 'o_command_completed'), ('fail', 'o_command_failed')):
            self.events[port] = int(plan[key])
            if plan[key]:
                events.add(key)
        self.events['o_completed_with_error'] = int(plan['finish'] and self.memory_error)
        if plan['config']:
            self.memory_error = 0
        if plan['start']:
            self.descriptor = {n: p[n] for n in DESCRIPTOR}
            self.cursor = 0
        if plan['response'] and not plan['rsp_error']:
            assert p['i_mem_rsp_error'] == 1 or p['i_mem_rsp_data'] is not None, 'Unknown successful data'
            plan['target']['response'] = p['i_mem_rsp_data'], p['i_mem_rsp_error']
            if p['i_mem_rsp_error']:
                self.memory_error = 1
                events.add('memory_error')
        if plan['stream']:
            self.pending.popleft()
            self.delivered += 1
        if plan['request']:
            entry = address(self.c, self.descriptor, self.cursor)
            entry.update(tag=self.next_tag, response=None, ordinal=self.cursor)
            assert all(e['tag'] != self.next_tag for e in self.pending), 'Early tag reuse'
            self.pending.append(entry)
            self.next_tag = (self.next_tag + 1) % self.c.MAX_OUTSTANDING
            self.cursor += 1
            self.accepted += 1
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
        assert self.accepted == self.delivered + self.discarded + len(self.pending)
        return events, plan
