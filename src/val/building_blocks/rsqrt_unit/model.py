"""Unbounded-integer rsqrt model, independent of RTL pipeline and datapath signals."""
from enum import IntEnum
from rsqrt_unit.images import seeds
from polynomial_unit.model import encode, number, rounded, signed
from reciprocal_unit.model import protected_seed


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
    NEGATIVE = 9
    EPSILON = 10


def known_request(c, request):
    if any(v is None for k, v in request.items() if k != 'epsilon'):
        return False
    active_epsilon = (c.SUPPORT_EPSILON and request['add_epsilon'] and request['predicate']
        and request['iterations'] <= c.MAX_ITERATIONS and not (request['input_signed'] and
        request['operand'] & (1 << (c.INPUT_WIDTH - 1))))
    return not active_epsilon or request['epsilon'] is not None


def evaluate(c, request, faults=None):
    operand, input_signed, output_signed, add, epsilon, count, mode, predicate, context, tag = (
        request[k] for k in ('operand', 'input_signed', 'output_signed', 'add_epsilon',
            'epsilon', 'iterations', 'round_mode', 'predicate', 'context_id', 'tag'))
    response = dict(data=0, output_signed=output_signed, iterations=count, quality_id=count,
        context_id=context, tag=tag, epsilon_applied=0, negative_input=0, zero_input=0,
        overflow=0, underflow=0, saturated=0, rounded=0, approximate=0, predicated=0,
        error=0, error_code=0)
    stats = dict(active=False, ties=set(), directions=set(), rounds=[], normalized=0,
        half_exponent=0, parity=0, address=0, corrected=False, fatal=False,
        effective=0, epsilon_added=False, steps=[])
    if count > c.MAX_ITERATIONS or (add and not c.SUPPORT_EPSILON):
        response.update(iterations=0, quality_id=0, error=1,
            error_code=int(Error.ITERATIONS if count > c.MAX_ITERATIONS else Error.EPSILON))
        return response, stats
    if not predicate:
        response['predicated'] = 1
        return response, stats
    if input_signed and signed(operand, c.INPUT_WIDTH) < 0:
        response.update(negative_input=1, error=1, error_code=int(Error.NEGATIVE))
        return response, stats
    magnitude = operand + (epsilon if add else 0)
    response['epsilon_applied'] = int(bool(add and epsilon))
    stats.update(effective=magnitude, epsilon_added=bool(add and epsilon))
    if not magnitude:
        response.update(zero_input=1, error=1, error_code=int(Error.ZERO))
        if c.ZERO_RESULT_MODE:
            response['data'] = (1 << (c.OUTPUT_WIDTH - output_signed)) - 1
        return response, stats
    def rescale(value, shift, label):
        result, inexact, tie = rounded(value, shift, mode)
        response['rounded'] |= int(inexact)
        stats['rounds'].append((label, inexact, tie))
        if tie:
            stats['ties'].add((label, mode))
        return result
    p = magnitude.bit_length() - 1
    exponent = p - c.INPUT_FRACTION_WIDTH
    half, parity = divmod(exponent, 2)
    mantissa = rescale(magnitude, p - c.INTERNAL_FRACTION_WIDTH, 'normalization')
    clamped = mantissa >= 1 << (c.INTERNAL_FRACTION_WIDTH + 1)
    if clamped:
        mantissa = (1 << (c.INTERNAL_FRACTION_WIDTH + 1)) - 1
        response['rounded'] = 1
    n = mantissa << parity
    region = (mantissa - (1 << c.INTERNAL_FRACTION_WIDTH)) >> (
        c.INTERNAL_FRACTION_WIDTH - c.SEED_MANTISSA_ADDRESS_WIDTH)
    address = (parity << c.SEED_MANTISSA_ADDRESS_WIDTH) | region
    y = seeds(c.INTERNAL_WIDTH, c.INTERNAL_FRACTION_WIDTH, c.SEED_MANTISSA_ADDRESS_WIDTH)[address]
    fault = (faults or {}).get(address, 0)
    if fault is None:
        stats['fatal'] = True
    else:
        y, stats['corrected'], stats['fatal'] = protected_seed(
            y, c.INTERNAL_WIDTH, c.SEED_PROTECTION, fault)
    stats.update(active=True, normalized=n, half_exponent=half, parity=parity,
        address=address, leading=p, mantissa=mantissa, mantissa_clamped=clamped,
        exponent=exponent)
    for _ in range(count):
        squared = rescale(y * y, c.INTERNAL_FRACTION_WIDTH, 'square')
        product = rescale(n * squared, c.INTERNAL_FRACTION_WIDTH, 'normalized_product')
        correction = (3 << c.INTERNAL_FRACTION_WIDTH) - product
        next_y = rescale(y * correction, c.INTERNAL_FRACTION_WIDTH + 1, 'update')
        stats['directions'].add((next_y > y) - (next_y < y))
        stats['steps'].append((squared, product, correction, next_y))
        if (min(squared, correction, next_y) <= 0 or
            max(squared, product, correction, next_y) >= 1 << c.INTERNAL_WIDTH):
            stats['fatal'] = True
        y = next_y
    shift = c.OUTPUT_FRACTION_WIDTH - c.INTERNAL_FRACTION_WIDTH - half
    scaled = rescale(y, -shift, 'output')
    limit = (1 << (c.OUTPUT_WIDTH - output_signed)) - 1
    response['overflow'] = response['saturated'] = int(scaled > limit)
    response['data'] = min(scaled, limit)
    response['underflow'] = int(response['data'] == 0)
    response['approximate'] = 1
    stats['output_shift'] = shift
    return response, stats


def request_from_ports(ports):
    return {k.removeprefix('i_request_'): number(v)
        for k, v in ports.items() if k.startswith('i_request_') and k != 'i_request_valid'}
