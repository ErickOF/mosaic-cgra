"""Unbounded integer oracle: signed magnitude rounding and complete Horner order."""
from copy import deepcopy
from enum import IntEnum


class Error(IntEnum):
    NONE = 0
    UNKNOWN = 1
    BANK = 2
    UNCOMMITTED = 3
    COMMITTED = 4
    INDEX = 5
    DEGREE = 6
    DOMAIN = 7
    SHIFT = 8
    INCOMPLETE = 9
    BUSY = 10
    RANGE = 11
    COEFFICIENT = 12
    CORRECTED = 13
    INTERNAL = 14


def number(raw):
    return int(raw, 2) if set(raw.lower()) <= {'0', '1'} else None


def signed(value, width):
    return value - (1 << width) if value & (1 << (width - 1)) else value


def rounded(value, shift, nearest):
    if shift <= 0:
        return value << -shift, False, False
    quotient, remainder = divmod(abs(value), 1 << shift)
    tie = remainder == 1 << (shift - 1)
    if nearest and (2 * remainder > 1 << shift or (tie and quotient % 2)):
        quotient += 1
    return (-quotient if value < 0 else quotient), bool(remainder), tie


def clamp(value, width):
    limited = max(-(1 << (width - 1)), min((1 << (width - 1)) - 1, value))
    return limited, limited != value


def encode(value, width, protection):
    value &= (1 << width) - 1
    if not protection:
        return value, width
    if protection == 1:
        return value | ((value.bit_count() % 2) << width), width + 1
    parity = 1
    while 1 << parity < width + parity + 1:
        parity += 1
    hamming = width + parity
    code = 0
    index = 0
    for position in range(1, hamming + 1):
        if position & (position - 1):
            code |= ((value >> index) & 1) << (position - 1)
            index += 1
    for bit in range(parity):
        check = sum((code >> (p - 1)) & 1 for p in range(1, hamming + 1)
                    if p & (1 << bit)) % 2
        code |= check << ((1 << bit) - 1)
    return code | ((code.bit_count() % 2) << hamming), hamming + 1


def decode_word(value, width, protection, fault=0):
    code, bits = encode(value, width, protection)
    code ^= fault
    if not protection:
        return signed(code & ((1 << width) - 1), width), False, False
    if protection == 1:
        return signed(code & ((1 << width) - 1), width), False, bool(code.bit_count() % 2)
    syndrome = 0
    for position in range(1, bits):
        if code >> (position - 1) & 1:
            syndrome ^= position
    odd = code.bit_count() % 2
    bad = bool(syndrome and (not odd or syndrome >= bits))
    corrected = bool(odd and not bad)
    if corrected:
        code ^= 1 << (syndrome - 1 if syndrome else bits - 1)
    result = 0
    index = 0
    for position in range(1, bits):
        if position & (position - 1):
            result |= ((code >> (position - 1)) & 1) << index
            index += 1
    return signed(result, width), corrected, bad


def bank(c):
    return dict(valid=0, version=0, polynomial_id=0, quality_id=0, degree=0,
                x_min=0, x_max=0, range_policy=0, round_mode=0, result_shift=0,
                coverage=set(), coefficients=[None] * (c.MAX_DEGREE + 1), fault=0)


def evaluate(c, banks, faults, request):
    """Return exact response fields and mathematical coverage, without RTL signals."""
    b, x, predicate, context, tag = (request[k] for k in
        ('bank', 'x', 'predicate', 'context_id', 'tag'))
    result = dict(data=0, bank=b, bank_version=0, polynomial_id=0, quality_id=0,
                  context_id=context, tag=tag, clipped_low=0, clipped_high=0,
                  internal_saturated=0, output_saturated=0, inexact=0,
                  predicated=0, error=0, error_code=0)
    stats = dict(ties=set(), saturated_stages=set(), stages=0, reads=[])
    if b >= c.NUM_BANKS or not banks[b]['valid']:
        result.update(error=1, error_code=int(Error.BANK if b >= c.NUM_BANKS else Error.UNCOMMITTED))
        return result, stats
    n = banks[b]
    result.update(bank_version=n['version'], polynomial_id=n['polynomial_id'], quality_id=n['quality_id'])
    if not predicate:
        result['predicated'] = 1
        return result, stats
    x = signed(x, c.INPUT_WIDTH)
    if x < n['x_min'] or x > n['x_max']:
        if n['range_policy']:
            result.update(error=1, error_code=int(Error.RANGE))
            return result, stats
        result['clipped_low'], result['clipped_high'] = int(x < n['x_min']), int(x > n['x_max'])
        x = max(n['x_min'], min(n['x_max'], x))
    def coefficient(index, position):
        value = n['coefficients'][index]
        if value is None:
            return 0, False, True
        copy = position if c.EVALUATION_ARCH else 0
        stats['reads'].append((copy, index))
        return decode_word(value, c.COEFFICIENT_WIDTH, c.COEFFICIENT_PROTECTION,
                           faults.get((b, copy, index), 0))
    a, corrected, bad = coefficient(n['degree'], 0)
    for position, index in enumerate(range(n['degree'] - 1, -1, -1), 1):
        if bad:
            break
        coeff, corrected, bad = coefficient(index, position)
        if bad:
            break
        scaled, inexact, tie = rounded(a * x, c.FRACTION_WIDTH, n['round_mode'])
        if tie:
            stats['ties'].add((n['round_mode'], int(a * x < 0)))
        a, saturated = clamp(scaled + coeff, c.ACCUMULATOR_WIDTH)
        result['inexact'] |= int(inexact)
        result['internal_saturated'] |= int(saturated)
        if saturated:
            stats['saturated_stages'].add(position)
        stats['stages'] += 1
    if bad:
        result.update(error=1, error_code=int(Error.COEFFICIENT))
        return result, stats
    value, inexact, tie = rounded(a, n['result_shift'], n['round_mode'])
    value, saturated = clamp(value, c.OUTPUT_WIDTH)
    result.update(data=value & ((1 << c.OUTPUT_WIDTH) - 1),
                  inexact=int(result['inexact'] or inexact), output_saturated=int(saturated))
    return result, stats


def program(c, banks, pending, faults, command, fatal):
    """Prepare one atomic software operation using pre-edge bank references."""
    b, op, index = (command[k] for k in ('bank', 'command', 'coefficient_index'))
    n = deepcopy(banks[b]) if b < c.NUM_BANKS else bank(c)
    error = Error.NONE
    if b >= c.NUM_BANKS:
        error = Error.BANK
    elif op == 0:
        error = Error.COMMITTED if n['valid'] else Error.INDEX if index > c.MAX_DEGREE else Error.NONE
    elif op == 1:
        error = Error.INDEX if index > c.MAX_DEGREE else Error.NONE
    elif op == 2:
        error = (Error.INTERNAL if fatal else Error.COMMITTED if n['valid'] else
                 Error.BUSY if any(r['tracked'] and r['result']['bank'] == b for r in pending) else
                 Error.DEGREE if command['degree'] > c.MAX_DEGREE else
                 Error.DOMAIN if signed(command['x_min'], c.INPUT_WIDTH) > signed(command['x_max'], c.INPUT_WIDTH) else
                 Error.SHIFT if abs(signed(command['result_shift'], c.RESULT_SHIFT_WIDTH)) >= c.ACCUMULATOR_WIDTH else
                 Error.INCOMPLETE if c.TRACK_COEFFICIENT_COVERAGE and not
                 set(range(command['degree'] + 1)) <= n['coverage'] else Error.NONE)
    else:
        if any(r['tracked'] and r['result']['bank'] == b for r in pending):
            error = Error.BUSY
    data = 0
    corrected = False
    bad = False
    if not error:
        if op == 0:
            n['coefficients'][index] = command['coefficient_data']
            n['coverage'].add(index)
        elif op == 1:
            if n['coefficients'][index] is None:
                bad = True
            else:
                value, corrected, bad = decode_word(n['coefficients'][index],
                    c.COEFFICIENT_WIDTH, c.COEFFICIENT_PROTECTION, faults.get((b, 0, index), 0))
                data = value & ((1 << c.COEFFICIENT_WIDTH) - 1) if not bad else 0
            if bad:
                error = Error.COEFFICIENT
                if n['valid']:
                    n['fault'] = 1
        elif op == 2:
            n.update(valid=1, version=(n['version'] + 1) % (1 << c.BANK_VERSION_WIDTH))
            for field in ('degree', 'range_policy', 'round_mode', 'polynomial_id', 'quality_id'):
                n[field] = command[field]
            for field in ('x_min', 'x_max'):
                n[field] = signed(command[field], c.INPUT_WIDTH)
            n['result_shift'] = signed(command['result_shift'], c.RESULT_SHIFT_WIDTH)
        else:
            coefficients, version = n['coefficients'], n['version']
            n = bank(c) | dict(coefficients=coefficients, version=version)
    response = dict(command=op, bank=b, coefficient_index=index, coefficient_data=data,
                    degree=n['degree'], x_min=n['x_min'] & ((1 << c.INPUT_WIDTH) - 1),
                    x_max=n['x_max'] & ((1 << c.INPUT_WIDTH) - 1), range_policy=n['range_policy'],
                    round_mode=n['round_mode'], result_shift=n['result_shift'] & ((1 << c.RESULT_SHIFT_WIDTH) - 1),
                    version=n['version'], polynomial_id=n['polynomial_id'], quality_id=n['quality_id'],
                    bank_valid=n['valid'], error=int(bool(error)), error_code=int(error))
    return response, n, corrected, bad
