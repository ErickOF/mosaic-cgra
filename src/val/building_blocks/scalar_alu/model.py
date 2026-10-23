"""Independent integer oracle with explicit masking and signed interpretation."""

from enum import IntEnum
from mosaic_uvm.logic import bits
from scalar_alu.transaction import OUTPUTS


class Opcode(IntEnum):
    ADD = 0
    SUB = 1
    AND = 2
    OR = 3
    XOR = 4
    NOT = 5
    SLL = 6
    SRL = 7
    SRA = 8
    EQ = 9
    NE = 10
    LT = 11
    LE = 12
    GT = 13
    GE = 14
    SELECT = 15
    PASS_A = 16
    PASS_B = 17
    MIN = 18
    MAX = 19


def known(word):
    return set(word) <= {'0', '1'}


def uses_signed(op):
    return op in (0, 1, 11, 12, 13, 14, 18, 19)


def signed_value(value, width):
    return value - (1 << width) if value & (1 << (width - 1)) else value


def predict(c, ports):
    result = dict.fromkeys(OUTPUTS, 0)

    def response(event):
        return ({name: bits(value, c.widths[name]) for name, value in result.items()}, event)

    if ports['i_enable'] == '0':
        return response(dict(kind='disabled'))
    reason = None
    op = int(ports['i_opcode'], 2) if known(ports['i_opcode']) else None
    if ports['i_enable'] != '1':
        reason = 'unknown_enable'
    elif op is None:
        reason = 'unknown_opcode'
    elif op >= 20:
        reason = 'reserved'
    elif op >= 18 and not c.minmax:
        reason = 'minmax_disabled'
    elif not known(ports['i_saturate']):
        reason = 'unknown_saturate'
    elif ports['i_saturate'] == '1' and (op > 1 or not c.saturation):
        reason = 'unsupported_saturation'
    elif uses_signed(op) and not known(ports['i_signed']):
        reason = 'unknown_signed'
    elif op == 15 and not known(ports['i_predicate']):
        reason = 'unknown_predicate'
    if reason:
        result['o_illegal_operation'] = 1
        return response(dict(kind='illegal', cause=reason, opcode=op))
    need_a = op != 17 and (op != 15 or ports['i_predicate'] == '1')
    need_b = op not in (5, 16) and (op != 15 or ports['i_predicate'] == '0')
    for name, required in (('i_operand_a', need_a), ('i_operand_b', need_b)):
        assert not required or known(ports[name]), f'SCALAR_ALU_PROTOCOL: {name}'
    a = int(ports['i_operand_a'], 2) if known(ports['i_operand_a']) else 0
    b = int(ports['i_operand_b'], 2) if known(ports['i_operand_b']) else 0
    signed = ports['i_signed'] == '1' and uses_signed(op)
    left, right = (signed_value(v, c.width) if signed else v for v in (a, b))
    low = -(1 << (c.width - 1)) if signed else 0
    high = (1 << (c.width - 1)) - 1 if signed else c.mask
    value = predicate = 0
    raw = None
    if op in (0, 1):
        raw = left + right if op == 0 else left - right
        result['o_carry'] = int(op == 0 and a + b > c.mask)
        result['o_borrow'] = int(op == 1 and a < b)
        result['o_overflow'] = int(signed and not low <= raw <= high)
        value = raw
        if ports['i_saturate'] == '1' and not low <= value <= high:
            value = min(high, max(low, value))
            result['o_saturated'] = 1
    elif op == 2:
        value = a & b
    elif op == 3:
        value = a | b
    elif op == 4:
        value = a ^ b
    elif op == 5:
        value = c.mask ^ a
    elif op in (6, 7, 8):
        if b >= c.width:
            value = c.mask if op == 8 and a & (1 << (c.width - 1)) else 0
        elif op == 6:
            value = a * (1 << b)
        elif op == 7:
            value = a // (1 << b)
        else:
            # Floor division is constructed explicitly, without host signed shifts.
            mathematical = signed_value(a, c.width)
            quotient, remainder = divmod(abs(mathematical), 1 << b)
            value = -quotient - int(bool(remainder)) if mathematical < 0 else quotient
    elif op in (9, 10, 11, 12, 13, 14):
        predicate = int(
            {
                9: left == right,
                10: left != right,
                11: left < right,
                12: left <= right,
                13: left > right,
                14: left >= right,
            }[op]
        )
        value = predicate
    elif op == 15:
        value = a if ports['i_predicate'] == '1' else b
    elif op == 16:
        value = a
    elif op == 17:
        value = b
    elif op in (18, 19):
        value = min(left, right) if op == 18 else max(left, right)
    value &= c.mask
    result.update(
        o_result=value,
        o_predicate=predicate,
        o_zero=int(value == 0),
        o_negative=(value >> (c.width - 1)) & 1,
    )
    event = dict(
        kind='legal',
        opcode=op,
        signed=int(signed),
        a=a,
        b=b,
        raw=raw,
        saturate=int(ports['i_saturate']),
        low=low,
        high=high,
        value=value,
        predicate=predicate,
    )
    return response(event)
