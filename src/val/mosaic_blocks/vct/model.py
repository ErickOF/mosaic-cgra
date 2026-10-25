"""Independent integer oracle, slice-valid architectural storage and context codec."""
from collections import deque
from bct.model import arithmetic as alu, signed
from vct.layout import FIELDS


def dimensions(p):
    return p | dict(LN=p['NUM_LANES'], EL=p['ELEMENT_WIDTH'], A=p['ACC_WIDTH'],
        D=p['NUM_LANES'] * p['ACC_WIDTH'], NI=p['DATA_INPUT_PORTS'], NO=p['DATA_OUTPUT_PORTS'],
        CI=max(1, (p['CONTEXT_DEPTH'] - 1).bit_length()),
        RA=max(1, (p['VRF_DEPTH'] - 1).bit_length()),
        PA=max(1, (p['PREDICATE_DEPTH'] - 1).bit_length()),
        VA=max(1, (p['VECTOR_ACC_DEPTH'] - 1).bit_length()),
        CA=max(1, (p['SCALAR_ACC_DEPTH'] - 1).bit_length()),
        SP=p['ACC_WIDTH'] // p['WRITE_SLICE_WIDTH'],
        SM=p['NUM_LANES'] * (p['ACC_WIDTH'] // p['WRITE_SLICE_WIDTH']),
        SA=max(1, (p['ACC_WIDTH'] // p['WRITE_SLICE_WIDTH'] - 1).bit_length()),
        LI=(p['NUM_LANES'] - 1).bit_length(),
        DW=max(1, p['RDU_TOTAL_DELAY_ENTRIES'].bit_length()),
        SW=(p['DATA_INPUT_PORTS'] + 7).bit_length())


def layout(p):
    offset = 0
    result = {}
    for name, expression in FIELDS:
        width = eval(expression, {'__builtins__': {}}, dimensions(p))
        result[name] = offset, width
        offset += width
    return result


def pack(p, context):
    value = 0
    for name, (offset, width) in layout(p).items():
        field = context.get(name, 0)
        if not 0 <= field < 1 << width:
            raise ValueError(f'{name} does not fit {width} bits')
        value |= field << offset
    return value


def unpack(p, value):
    return {n: value >> o & ((1 << w) - 1) for n, (o, w) in layout(p).items()}


def sources(p):
    n = p['DATA_INPUT_PORTS']
    return dict(rf=n, immediate=n + 2, zero=n + 3, vacc=n + 4, sacc=n + 5,
                bypass=n + 6, previous=n + 7)


def lane_width(p, fmt):
    return (p['ELEMENT_WIDTH'], 2 * p['ELEMENT_WIDTH'], p['ACC_WIDTH'],
            p['ELEMENT_WIDTH'], p['ACC_WIDTH'])[fmt]


def payload(values, width):
    return sum((value & ((1 << width) - 1)) << (lane * width)
               for lane, value in enumerate(values))


def operands_used(ctx):
    return (not (ctx['fu'] == 0 and ctx['opcode'] == 17) and not (ctx['fu'] == 0 and ctx['opcode'] == 15 and not ctx['select_mask'] & ctx['lane_mask']),
            ctx['fu'] == 2 or ctx['fu'] == 0 and ctx['opcode'] not in (5, 16) and (ctx['opcode'] != 15 or ctx['lane_mask'] & ~ctx['select_mask']),
            ctx['fu'] == 0 and ctx['opcode'] == 21 or ctx['accumulate'])


def compute(p, ctx, a, b, acc, mask):
    """Return formatted data, comparison mask and arithmetic flags using integers."""
    ln, e, aw = p['NUM_LANES'], p['ELEMENT_WIDTH'], p['ACC_WIDTH']
    em, am = (1 << e) - 1, (1 << aw) - 1
    sign, sat, fu, op = ctx['signed_mode'], ctx['saturate'], ctx['fu'], ctx['opcode']
    preds = overflows = saturated = value = 0
    def clip(raw, width):
        low, high = (-(1 << (width - 1)), (1 << (width - 1)) - 1) if sign else (0, (1 << width) - 1)
        output = min(high, max(low, raw)) if sat else raw
        return output & ((1 << width) - 1), int(not low <= raw <= high), int(sat and output != raw)
    av = [a >> (l * e) & em for l in range(ln)]
    bv = [b >> (l * e) & em for l in range(ln)]
    aa = [signed(v, e) if sign else v for v in av]
    bb = [signed(v, e) if sign else v for v in bv]
    active = [l for l in range(ln) if mask >> l & 1]
    if fu == 0:
        values = [0] * ln
        for l in active:
            if op < 20:
                v, flags = alu(p | dict(DATA_WIDTH=e), dict(opcode=op, signed_a=sign,
                    saturate=sat, select_condition=ctx['select_mask'] >> l & 1), av[l], bv[l])
                pred, ov, ss = flags[0], flags[5], flags[6]
            else:
                raw = aa[l] * bb[l]
                if op == 21:
                    cv = acc >> (l * aw) & am
                    raw += signed(cv, aw) if sign else cv
                    v, ov, ss = clip(raw, aw)
                else:
                    v, ov, ss = raw & ((1 << (2 * e)) - 1), 0, 0
                pred = 0
            values[l] = v
            preds |= pred << l
            overflows |= ov << l
            saturated |= ss << l
        value = payload(values, lane_width(p, ctx['result_format']))
    elif fu in (1, 2):
        if fu == 2: raw = sum(aa[l] * bb[l] for l in active)
        elif op == 0: raw = sum(aa[l] for l in active)
        elif op == 1: raw = min(aa[l] for l in active)
        elif op == 2: raw = max(aa[l] for l in active)
        elif op == 3:
            raw = em
            for l in active: raw &= av[l]
        elif op == 4:
            raw = 0
            for l in active: raw |= av[l]
        else: raise ValueError('Illegal reduction')
        if ctx['accumulate']: raw += signed(acc & am, aw) if sign else acc & am
        if ctx['accumulate'] or fu == 2:
            value, ov, ss = clip(raw, aw)
            overflows, saturated = mask if ov else 0, mask if ss else 0
        else: value = raw & (am if ctx['result_format'] == 4 else em)
    elif fu == 3:
        width = lane_width(p, ctx['result_format'])
        value = payload([a & ((1 << width) - 1) if l in active else 0 for l in range(ln)], width)
    elif fu == 4:
        width = lane_width(p, ctx['format_a'])
        raw = a >> (ctx['extract_lane'] * width) & ((1 << width) - 1)
        if ctx['format_a'] == 1 and sign: raw = signed(raw, width)
        value = raw & ((1 << lane_width(p, ctx['result_format'])) - 1)
    elif fu == 5:
        width = lane_width(p, ctx['result_format'])
        value = a & ((1 << width) - 1) if ctx['result_format'] >= 3 else payload(
            [a >> (l * width) & ((1 << width) - 1) if l in active else 0 for l in range(ln)], width)
    return (value if mask else 0), preds, overflows, saturated


class Architecture:
    """Public ingress queues and independent masked storage at architectural commit."""
    def __init__(self, p):
        self.p = p
        self.reset()

    def reset(self):
        self.inputs = [deque() for _ in range(self.p['DATA_INPUT_PORTS'])]
        self.predicates = deque()
        self.operations = deque()
        self.outputs = [deque() for _ in range(self.p['DATA_OUTPUT_PORTS'])]
        self.predicate_outputs = deque()
        self.rf = [0] * self.p['VRF_DEPTH']
        self.rf_valid = [0] * self.p['VRF_DEPTH']
        self.vacc = [dict() for _ in range(self.p['VECTOR_ACC_DEPTH'])]
        self.sacc = {}
        self.pred = [dict() for _ in range(self.p['PREDICATE_DEPTH'])]
        self.bypass = self.previous = None
        self.bypass_format = None
        self.context = None
        self.mask_value = self.mask_valid = 0

    def activate(self, c):
        d = dimensions(self.p)
        self.mask_valid &= ~c['invalidate_mask']
        for address in range(self.p['VRF_DEPTH']):
            self.rf_valid[address] &= ~(c['invalidate_rf'] >> (address * d['SM']))
        for name, storage, lanes in (('vacc', self.vacc, d['LN']), ('predicate', self.pred, d['LN'])):
            for address, state in enumerate(storage):
                for lane in list(state):
                    if c[f'invalidate_{name}'] >> (address * lanes + lane) & 1: del state[lane]
        for address, state in enumerate(self.vacc):
            for lane in range(d['LN']):
                if c['clear_vacc'] >> (address * d['LN'] + lane) & 1: state[lane] = 0
        for address in range(self.p['SCALAR_ACC_DEPTH']):
            if c['invalidate_sacc'] >> address & 1: self.sacc.pop(address, None)
            if c['clear_sacc'] >> address & 1: self.sacc[address] = 0
        if c['invalidate_bypass']:
            self.bypass = None
            self.previous = None
        self.context = c

    def source(self, index, c, mask):
        p, s = self.p, sources(self.p)
        if index < p['DATA_INPUT_PORTS']:
            assert self.inputs[index], f'Issue without input {index}'
            return self.inputs[index][0][0]
        if index in (s['rf'], s['rf'] + 1):
            side = 'a' if index == s['rf'] else 'b'
            address, offset = c[f'rf_read_{side}'], c[f'read_slice_{side}'] * p['WRITE_SLICE_WIDTH']
            width = lane_width(p, c[f'format_{side}'])
            values = []
            for lane in range(p['NUM_LANES']):
                group = ((1 << (width // p['WRITE_SLICE_WIDTH'])) - 1) << (
                    lane * (p['ACC_WIDTH'] // p['WRITE_SLICE_WIDTH']) + c[f'read_slice_{side}'])
                if mask >> lane & 1:
                    assert self.rf_valid[address] & group == group, 'Invalid VRF slice issued'
                values.append(self.rf[address] >> (lane * p['ACC_WIDTH'] + offset) & ((1 << width) - 1))
            return payload(values, width)
        if index == s['immediate']: return c['immediate']
        if index == s['zero']: return 0
        if index == s['vacc']:
            state = self.vacc[c['vacc_write']]
            assert all(l in state for l in range(p['NUM_LANES']) if mask >> l & 1)
            return payload([state.get(l, 0) for l in range(p['NUM_LANES'])], p['ACC_WIDTH'])
        if index == s['sacc']:
            assert c['sacc_write'] in self.sacc
            return self.sacc[c['sacc_write']]
        if index in (s['bypass'], s['previous']):
            state = self.bypass if index == s['bypass'] else self.previous
            assert state is not None
            return state
        raise AssertionError(f'Unknown source {index}')
