"""Independent mathematical framing, byte mapping, and ordered beat ledger."""
from stream_formatter.transaction import CLAIMS, CONFIG, EVENTS, OUTPUTS, RESULT


def number(raw):
    if isinstance(raw, int):
        return raw
    return None if set(raw.lower()) & set('xz') else int(raw, 2)


def known_ones(raw):
    if isinstance(raw, int):
        return raw
    return int(''.join('1' if b == '1' else '0' for b in raw.lower()), 2)


def markers(d, index):
    first = index == 0
    last = index == d['i_frame_beats'] - 1
    row_first = index % d['i_row_beats'] == 0
    row_last = index % d['i_row_beats'] == d['i_row_beats'] - 1 or last
    return dict(first=int(first), last=int(last), row_first=int(row_first), row_last=int(row_last),
                end_of_stream=int(last and d['i_emit_end_of_stream']),
                stream_datatype=d['i_datatype'], stream_channel_id=d['i_channel_id'],
                stream_context_id=d['i_context_id'])


def configuration_error(p):
    if any(p[n] is None for n in CONFIG):
        return 1
    if p['i_frame_beats'] == 0:
        return 2
    if p['i_row_beats'] == 0:
        return 3
    if p['i_row_beats'] > p['i_frame_beats']:
        return 4
    if p['i_lane_enable'] == 0:
        return 5
    return 0


def format_beat(c, d, index, ports):
    p = {n: number(v) for n, v in ports.items()}
    expected = markers(d, index)
    lanes = known_ones(ports['i_lane_mask'])
    keep = known_ones(ports['i_keep'])
    lane_bytes = c.DATA_WIDTH // 8 // c.NUM_LANES
    checked = ('i_lane_mask', 'i_keep', 'i_error') + tuple('i_' + n for n in CLAIMS if d['i_mode'])
    faults = {1} if any(p[n] is None for n in checked) else set()
    if not lanes:
        faults.add(2)
    if any(bool(lanes >> k & 1) != bool(keep >> (k * lane_bytes) & ((1 << lane_bytes) - 1))
           for k in range(c.NUM_LANES)):
        faults.add(3)
    if d['i_mode']:
        faults.update(n + 4 for n, field in enumerate(CLAIMS) if p['i_' + field] != expected[field])
    effective = lanes & d['i_lane_enable']
    out_keep = sum(1 << b for b in range(c.DATA_WIDTH // 8)
                   if keep >> b & 1 and effective >> (b // lane_bytes) & 1)
    raw_data = ports['i_data']
    data = 0
    for b in range(c.DATA_WIDTH // 8):
        if out_keep >> b & 1:
            byte = raw_data >> (8 * b) & 255 if isinstance(raw_data, int) else number(
                raw_data[c.DATA_WIDTH - 8 * b - 8:c.DATA_WIDTH - 8 * b])
            if byte is None:
                data = None
                break
            data |= byte << (8 * b)
    result = dict(o_data=data, o_keep=out_keep, o_lane_mask=effective,
                  o_stream_error=int(p['i_error'] != 0 or bool(faults)),
                  o_format_error_code=min(faults, default=0))
    for name, value in expected.items():
        key = name.removeprefix('stream_')
        result['o_' + key] = value
    return result, faults


class StreamFormatterModel:
    def __init__(self, c):
        self.c = c
        self.total_in = self.total_out = self.discarded = 0
        self.reset()

    def reset(self):
        self.discarded += int(getattr(self, 'pending', None) is not None)
        self.pending = None
        self.active = False
        self.descriptor = None
        self.accepted = self.emitted = self.error = self.format_seen = self.input_seen = 0
        self.events = dict.fromkeys(EVENTS, 0)

    def evaluate(self, ports):
        p = {n: number(v) for n, v in ports.items()}
        run = p['i_rstb'] == 1
        normal = run and p['i_flush'] == 0
        busy = self.active or self.pending is not None
        accepting = normal and self.active and self.accepted < self.descriptor['i_frame_beats']
        presented = accepting and p['i_valid'] == 1
        beat, faults = format_beat(self.c, self.descriptor, self.accepted, ports) if presented else (None, set())
        room = self.pending is None or p['i_ready'] == 1
        out = dict.fromkeys(OUTPUTS, 0)
        out.update(o_config_ready=int(normal and not busy and not self.error), o_busy=int(busy),
                   o_idle=int(not busy and not self.error), o_error=int(bool(self.error)),
                   o_config_error_code=self.error, o_beats_accepted=self.accepted,
                   o_beats_emitted=self.emitted, o_format_error_seen=self.format_seen,
                   o_input_error_seen=self.input_seen,
                   o_ready=int(accepting and (room if self.c.REGISTER_OUTPUTS else p['i_ready'] == 1)),
                   o_valid=int(normal and self.pending is not None) if self.c.REGISTER_OUTPUTS else int(presented))
        out.update({n: v if run else 0 for n, v in self.events.items()})
        if out['o_valid']:
            out.update(self.pending if self.c.REGISTER_OUTPUTS else beat)
        config = bool(out['o_config_ready'] and p['i_config_valid'] == 1)
        error = configuration_error(p) if config else 0
        in_accept = bool(out['o_ready'] and p['i_valid'] == 1)
        out_accept = bool(out['o_valid'] and p['i_ready'] == 1)
        finish = bool(out_accept and out['o_last'])
        plan = dict(p=p, run=run, normal=normal, config=config, error=error,
                    start=config and not error, beat=beat, faults=faults, input=in_accept,
                    output=out_accept, finish=finish,
                    flush=run and p['i_flush'] == 1,
                    abort=run and p['i_flush'] == 1 and busy,
                    occupancy=int(self.pending is not None), active=self.active,
                    index=self.accepted, descriptor=self.descriptor,
                    output_error=out['o_stream_error'])
        return out, plan

    def step(self, ports, edge):
        _, q = self.evaluate(ports)
        p = q['p']
        if not edge:
            return q
        if p['i_rstb'] == 0:
            self.reset()
            return q
        if not q['run']:
            return q
        self.events = dict.fromkeys(EVENTS, 0)
        for key, port in (('start', 'o_frame_started'), ('input', 'o_input_accepted'),
                          ('output', 'o_output_accepted'), ('finish', 'o_frame_completed'),
                          ('abort', 'o_frame_aborted')):
            self.events[port] = int(q[key])
        self.events['o_completed_with_error'] = int(q['finish'] and
            (self.format_seen or self.input_seen or q['output_error']))
        if q['error'] and not self.error:
            self.error = q['error']
        elif q['normal'] and not self.active and self.pending is None and p['i_error_clear'] == 1:
            self.error = 0
        if q['flush']:
            self.discarded += int(self.pending is not None)
            self.active = False
            self.pending = None
            self.accepted = self.emitted = self.format_seen = self.input_seen = 0
        else:
            if q['start']:
                self.active = True
                self.descriptor = {n: p[n] for n in CONFIG}
                self.accepted = self.emitted = self.format_seen = self.input_seen = 0
            if q['output']:
                self.total_out += 1
                self.emitted += 1
                self.pending = None
            if q['input']:
                self.total_in += 1
                self.accepted += 1
                self.format_seen |= bool(q['faults'])
                self.input_seen |= p['i_error'] == 1
                if self.c.REGISTER_OUTPUTS:
                    self.pending = q['beat']
            if q['finish']:
                self.active = False
        assert self.total_in == self.total_out + self.discarded + int(self.pending is not None)
        return q
