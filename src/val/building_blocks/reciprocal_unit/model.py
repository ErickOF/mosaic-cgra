"""Unbounded integer numerical oracle, independent of DUT stages and signals."""
from enum import IntEnum
from reciprocal_unit.images import seeds
# These released Python helpers use divmod and an independent Hamming model.
from polynomial_unit.model import encode, decode_word, number, rounded, signed


class Error(IntEnum):
    NONE = 0
    UNKNOWN = 1
    ITERATIONS = 2
    ZERO = 3
    CORRECTED = 4
    SEED = 5
    INTERNAL = 6
    OWNERSHIP = 7
    IMAGE = 8


def protected_seed(value, width, protection, fault=0):
    result = 0
    corrected = bad = False
    for offset in range(0, width, 256):
        count = min(256, width - offset)
        mask = (fault >> ((offset // 256) * 266)) if protection == 2 else fault
        part, fix, error = decode_word((value >> offset) & ((1 << count) - 1),
                                      count, protection, mask)
        result |= (part & ((1 << count) - 1)) << offset
        bad |= error or (corrected and fix)
        corrected |= fix
    return result, corrected and not bad, bad


def evaluate(c, request, faults=None):
    """Return a complete response plus intermediate mathematical coverage facts."""
    operand, signed_mode, count, mode, predicate, context, tag = (
        request[k] for k in ('operand', 'signed', 'iterations', 'round_mode',
                            'predicate', 'context_id', 'tag'))
    response = dict(data=0, signed=signed_mode, iterations=count, quality_id=count,
        context_id=context, tag=tag, divide_by_zero=0, overflow=0, underflow=0,
        saturated=0, rounded=0, approximate=0, predicated=0, error=0, error_code=0)
    stats = dict(active=False, ties=set(), directions=set(), rounds=[], normalized=0,
                 exponent=0, address=0, corrected=False, fatal=False, steps=[])
    if count > c.MAX_ITERATIONS:
        response.update(iterations=0, quality_id=0, error=1, error_code=int(Error.ITERATIONS))
        return response, stats
    if not predicate:
        response['predicated'] = 1
        return response, stats
    if not operand:
        response.update(divide_by_zero=1, error=1, error_code=int(Error.ZERO))
        if c.ZERO_RESULT_MODE:
            response['data'] = (1 << (c.OUTPUT_WIDTH - int(bool(signed_mode)))) - 1
        return response, stats
    integer = signed(operand, c.INPUT_WIDTH) if signed_mode else operand
    magnitude = abs(integer)
    p = magnitude.bit_length() - 1
    exponent = p + 1 - c.INPUT_FRACTION_WIDTH
    def rescale(value, shift, label):
        value, inexact, tie = rounded(value, shift, mode)
        response['rounded'] |= int(inexact)
        stats['rounds'].append((label, inexact, tie))
        if tie:
            stats['ties'].add((label, mode))
        return value
    n = rescale(magnitude, p + 1 - c.INTERNAL_FRACTION_WIDTH, 'normalization')
    if n >= 1 << c.INTERNAL_FRACTION_WIDTH:
        n = (1 << c.INTERNAL_FRACTION_WIDTH) - 1
        response['rounded'] = 1
    address = (n - (1 << (c.INTERNAL_FRACTION_WIDTH - 1))) >> (
        c.INTERNAL_FRACTION_WIDTH - c.SEED_ADDRESS_WIDTH - 1)
    y = seeds(c.INTERNAL_WIDTH, c.INTERNAL_FRACTION_WIDTH, c.SEED_ADDRESS_WIDTH)[address]
    fault = (faults or {}).get(address, 0)
    if fault is None:
        stats['fatal'] = True
    else:
        y, stats['corrected'], stats['fatal'] = protected_seed(
            y, c.INTERNAL_WIDTH, c.SEED_PROTECTION, fault)
    stats.update(active=True, normalized=n, exponent=exponent, address=address,
                 leading=p, negative=integer < 0, magnitude=magnitude,
                 normalization_clamped=n == (1 << c.INTERNAL_FRACTION_WIDTH) - 1)
    for _ in range(count):
        t = rescale(n * y, c.INTERNAL_FRACTION_WIDTH, 'first')
        u = (1 << (c.INTERNAL_FRACTION_WIDTH + 1)) - t
        next_y = rescale(y * u, c.INTERNAL_FRACTION_WIDTH, 'second')
        stats['steps'].append((t, u, next_y))
        stats['directions'].add((next_y > y) - (next_y < y))
        if min(t, u, next_y) < 0 or max(t, u, next_y) >= 1 << c.INTERNAL_WIDTH:
            stats['fatal'] = True
        y = next_y
    shift = c.OUTPUT_FRACTION_WIDTH - c.INTERNAL_FRACTION_WIDTH - exponent
    scaled = rescale(y, -shift, 'output')
    limit = (1 << (c.OUTPUT_WIDTH - int(bool(signed_mode)))) - int(integer >= 0)
    response['overflow'] = response['saturated'] = int(scaled > limit)
    result = min(scaled, limit)
    response['underflow'] = int(result == 0)
    response['data'] = (-result if integer < 0 else result) & ((1 << c.OUTPUT_WIDTH) - 1)
    response['approximate'] = 1
    stats.update(output_shift=shift, scaled=scaled)
    return response, stats


def request_from_ports(ports):
    return {k.removeprefix('i_request_'): number(v)
            for k, v in ports.items() if k.startswith('i_request_') and k != 'i_request_valid'}
