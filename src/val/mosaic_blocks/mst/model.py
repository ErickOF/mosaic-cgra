"""Integer-only MST oracle, independent of RTL helper implementation."""
from mst.config import dimensions
from mst.layout import FIELDS


def fields(p, group):
    a = dimensions(p)
    if group in FIELDS:
        return [(n, eval(w, {'__builtins__': {}}, a)) for n, w in FIELDS[group]]
    identity = FIELDS['identity']
    extra = dict(
        stream=[('context_id', 'CI'), ('version', 'V'), ('identity', 'IDW'),
            ('keep', 'SY'), ('lanes', 'SY'), ('datatype', 'DT'), ('channel', 'ST'),
            *((n, '1') for n in ('first', 'last', 'row_first', 'row_last', 'eos', 'error')),
            ('element_log2', 'SZ'), ('lane_log2', 'SZ')],
        event=[('kind', '3'), ('context_id', 'CI'), ('kernel', 'K'), ('id', 'EI'),
            ('sequence_id', '16'), ('identity', 'IDW'), ('error', '1'), ('payload', '32')],
        context=[('schema', '8'), ('package_id', 'PK'), ('allocation', 'AL'),
            ('automatic_command', '1'), ('terminal', '1'), ('loads', 'NL'), ('stores', 'NS'),
            ('regions', 'NR'), ('descriptor', 'DESC')],
        descriptor=[('identity', 'IDW'), ('mode', 'MOW'), ('source', 'ENW'),
            ('destination', 'ENW'), ('format', 'FOW'), ('events', 'EVW'), ('control', 'CTW')])
    return [(n, eval(w, {'__builtins__': {}}, a)) for n, w in extra[group]]


def pack(p, group, values):
    result = shift = 0
    for name, width in fields(p, group):
        value = values.get(name, 0)
        if isinstance(value, dict):
            value = pack(p, 'endpoint' if name in ('source', 'destination') else name, value)
        result |= (value & ((1 << width) - 1)) << shift
        shift += width
    return result


def unpack(p, group, value):
    result = {}
    for name, width in fields(p, group):
        result[name] = value & ((1 << width) - 1)
        value >>= width
    return result


def positions(endpoint, mode, control, size):
    """Return affine position addresses using unbounded signed Python integers."""
    step = (1 << size) if mode == 0 else endpoint.get('inner_stride', 0)
    outer = endpoint.get('outer_stride', 0) if mode == 2 else 0
    return [endpoint.get('base', 0) + y * outer + x * step
            for y in range(control['outer_count']) for x in range(control['inner_count'])]


def convert(data, source_log2, destination_log2, lane_log2, *, signed_mode=0,
            saturate=0, reverse=0):
    s, d, count = 8 << source_log2, 8 << destination_log2, 1 << lane_log2
    lanes = []
    overflow = False
    for k in range(count):
        v = (data >> (k * s)) & ((1 << s) - 1)
        if signed_mode and v >> (s - 1):
            v -= 1 << s
        lo, hi = (-(1 << (d - 1)), (1 << (d - 1)) - 1) if signed_mode else (0, (1 << d) - 1)
        out = not lo <= v <= hi
        overflow |= out
        lanes.append((max(lo, min(v, hi)) if saturate else v) & ((1 << d) - 1))
    if reverse:
        lanes.reverse()
    return sum(v << (k * d) for k, v in enumerate(lanes)), overflow


def stream_beats(p, descriptor, values, *, source=False):
    """Canonical per-position packets. Partial positions never cross a boundary."""
    a = dimensions(p)
    f, ctl, endpoint = descriptor['format'], descriptor['control'], descriptor[
        'source' if source else 'destination']
    size = f['source_log2' if source else 'destination_log2'] + f['lane_log2']
    size_bytes = 1 << size
    chunks = (size_bytes + a['SY'] - 1) // a['SY']
    identity = pack(p, 'identity', descriptor['identity'])
    result = []
    for pos, value in enumerate(values):
        for chunk in range(chunks):
            keep = (1 << min(a['SY'], size_bytes - chunk * a['SY'])) - 1
            first = pos == 0 and chunk == 0
            last = pos == len(values) - 1 and chunk == chunks - 1
            meta = dict(context_id=descriptor['identity']['context_id'],
                version=descriptor['identity']['version'], identity=identity, keep=keep,
                lanes=keep, datatype=f.get('datatype', 0), channel=endpoint['channel'],
                first=int(first), last=int(last),
                row_first=int(pos % ctl['inner_count'] == 0 and chunk == 0),
                row_last=int(pos % ctl['inner_count'] == ctl['inner_count'] - 1 and
                             chunk == chunks - 1), eos=int(last and f.get('eos', 0)),
                element_log2=f['source_log2' if source else 'destination_log2'],
                lane_log2=f['lane_log2'])
            result.append(((value >> (chunk * a['D'])) & ((1 << a['D']) - 1),
                           pack(p, 'stream', meta)))
    return result
