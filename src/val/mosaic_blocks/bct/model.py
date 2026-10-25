"""Architectural integer oracle and context codec, independent of RTL values."""
from collections import deque
from bct.layout import FIELDS


def signed(value, width):
    return value - (1 << width) if value & (1 << (width - 1)) else value


def dimensions(p):
    ni = p['DATA_INPUT_PORTS']
    ac = max(1, p['ACCUMULATOR_COUNT'])
    return p | dict(D=p['DATA_WIDTH'], NI=ni, NO=p['DATA_OUTPUT_PORTS'], AC=ac,
        CI=max(1, (p['CONTEXT_DEPTH'] - 1).bit_length()),
        RA=max(1, (p['RF_DEPTH'] - 1).bit_length()),
        PA=max(1, (p['PREDICATE_DEPTH'] - 1).bit_length()),
        AA=max(1, (ac - 1).bit_length()),
        DW=max(1, p['RDU_TOTAL_DELAY_ENTRIES'].bit_length()),
        SW=(ni + 2 + p['IMMEDIATE_COUNT'] + 2 + ac + 2).bit_length())


def layout(p):
    offset = 0
    result = {}
    for name, expression in FIELDS:
        width = eval(expression, {'__builtins__': {}}, dimensions(p))
        result[name] = offset, width
        offset += width
    return result


def pack(p, context):
    result = 0
    for name, (offset, width) in layout(p).items():
        value = context.get(name, 0)
        if not 0 <= value < 1 << width:
            raise ValueError(f'{name} does not fit {width} bits: {value}')
        result |= value << offset
    return result


def unpack(p, image):
    return {n: (image >> offset) % (1 << width) for n, (offset, width) in layout(p).items()}


def sources(p):
    rf = p['DATA_INPUT_PORTS']
    immediate = rf + 2
    zero = immediate + p['IMMEDIATE_COUNT']
    acc = zero + 2
    bypass = acc + max(1, p['ACCUMULATOR_COUNT'])
    return dict(rf=rf, immediate=immediate, zero=zero, one=zero + 1,
                accumulator=acc, bypass=bypass, previous=bypass + 1, predicate=bypass + 2)


def arithmetic(p, c, a, b, acc=0, predicate=1):
    """Return result and compare/zero/negative/carry/borrow/overflow/saturation flags."""
    width = p['DATA_WIDTH']
    mask = (1 << width) - 1
    sa, sb, sat = c.get('signed_a', 0), c.get('signed_b', 0), c.get('saturate', 0)
    fu, op = c.get('fu', 0), c.get('opcode', 0)
    carry = borrow = overflow = saturated = comparison = 0
    if fu:
        narrow = p['MULTIPLY_OPERAND_WIDTH']
        left = signed(a % (1 << narrow), narrow) if sa else a % (1 << narrow)
        right = signed(b % (1 << narrow), narrow) if sb else b % (1 << narrow)
        product = left * right
        value = product
        if fu == 2:
            accumulator = signed(acc, width) if sa or sb else acc
            value += accumulator
            carry = int((product & mask) + acc > mask)
            overflow = int(bool(sa or sb) and not -(1 << (width - 1)) <= value < 1 << (width - 1))
    else:
        left, right = (signed(a, width), signed(b, width)) if sa else (a, b)
        if op == 0:
            value = left + right
            carry = int(a + b > mask)
        elif op == 1:
            value = left - right
            borrow = int(a < b)
        elif op == 2: value = a & b
        elif op == 3: value = a | b
        elif op == 4: value = a ^ b
        elif op == 5: value = mask ^ a
        elif op == 6: value = 0 if b >= width else a * 2 ** b
        elif op == 7: value = 0 if b >= width else a // 2 ** b
        elif op == 8: value = -int(bool(a & (1 << (width - 1)))) if b >= width else signed(a, width) // 2 ** b
        elif 9 <= op <= 14:
            comparison = int((left == right, left != right, left < right,
                              left <= right, left > right, left >= right)[op - 9])
            value = comparison
        elif op == 15: value = a if c.get('select_condition', 0) else b
        elif op == 16: value = a
        elif op == 17: value = b
        elif op == 18: value = min(left, right)
        elif op == 19: value = max(left, right)
        else: raise ValueError('Illegal ALU opcode')
        if op < 2:
            overflow = int(bool(sa) and not -(1 << (width - 1)) <= value < 1 << (width - 1))
    if sat:
        is_signed = bool(sa or sb) if fu else bool(sa)
        low, high = (-(1 << (width - 1)), (1 << (width - 1)) - 1) if is_signed else (0, mask)
        clipped = min(high, max(low, value))
        saturated = int(clipped != value)
        value = clipped
    result = value & mask
    negative = int(bool(result & (1 << (width - 1))))
    # Scalar ALU negative is raw sign; multiplier/MAC signed result behavior is
    # checked through the data and selected architectural comparison flag.
    flags = [comparison, int(result == 0), negative, carry, borrow, overflow, saturated]
    return result, flags


class Architecture:
    """Accepted operand queues and ordered operation/commit/output ownership."""
    def __init__(self, p):
        self.p = p
        self.reset()

    def reset(self):
        self.inputs = [deque() for _ in range(self.p['DATA_INPUT_PORTS'])]
        self.predicates = deque()
        self.operations = deque()
        self.outputs = [deque() for _ in range(self.p['DATA_OUTPUT_PORTS'])]
        self.predicate_outputs = deque()
        self.rf = {}
        self.pred = {}
        self.acc = {}
        self.bypass = self.previous = None
        self.context = None

    def activate(self, context):
        for mask_name, storage in (('invalidate_rf', self.rf), ('invalidate_predicate', self.pred),
                                   ('invalidate_accumulator', self.acc)):
            for address in list(storage):
                if context[mask_name] >> address & 1:
                    del storage[address]
        if context['invalidate_bypass']:
            self.bypass = None
        if context['invalidate_bypass']:
            self.previous = None
        for address in range(max(1, self.p['ACCUMULATOR_COUNT'])):
            if context['clear_accumulator'] >> address & 1:
                self.acc[address] = 0
        self.context = context

    def source(self, index, c):
        s = sources(self.p)
        if index < self.p['DATA_INPUT_PORTS']:
            assert self.inputs[index], f'Issue without accepted input {index}'
            return self.inputs[index][0][0]
        if index in (s['rf'], s['rf'] + 1):
            address = c['rf_read_a' if index == s['rf'] else 'rf_read_b']
            assert address in self.rf, f'Invalid RF source: {address}'
            return self.rf[address]
        if s['immediate'] <= index < s['zero']:
            return c['immediates'] >> ((index - s['immediate']) * self.p['DATA_WIDTH']) & ((1 << self.p['DATA_WIDTH']) - 1)
        if index == s['zero']: return 0
        if index == s['one']: return 1
        if s['accumulator'] <= index < s['bypass']:
            assert index - s['accumulator'] in self.acc
            return self.acc[index - s['accumulator']]
        if index == s['bypass']:
            assert self.bypass is not None
            return self.bypass
        if index == s['previous']:
            assert self.previous is not None
            return self.previous
        if index == s['predicate']:
            assert c['predicate_read'] in self.pred
            return self.pred[c['predicate_read']]
        raise AssertionError(f'Unknown source {index}')
