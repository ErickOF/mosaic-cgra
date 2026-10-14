"""Independent population-count parity oracle with exact four-state behavior."""

from mosaic_uvm.logic import bits


def known(word):
    return not set(word) & {'x', 'z'}


def group_parity(word):
    return str(word.count('1') % 2) if known(word) else 'x'


def generate(config, data):
    # Text chunks are MSB first: the final chunk naturally produces parity bit 0.
    return ''.join(group_parity(data[start:start + config.granule_width])
                   for start in range(0, config.width, config.granule_width))


def encode(config, data):
    return int(generate(config, bits(data, config.width)), 2) << config.width | data


def check(config, data, parity):
    errors = ''.join(group_parity(data[start:start + config.granule_width] + bit)
                     for start, bit in zip(range(0, config.width, config.granule_width), parity))
    any_error = '1' if '1' in errors else 'x' if 'x' in errors else '0'
    return dict(o_error_vector=errors, o_granule_valid=''.join('x' if bit == 'x' else str(1 - int(bit)) for bit in errors),
                o_any_error=any_error, o_no_error='x' if any_error == 'x' else str(1 - int(any_error)),
                o_checked_data=data if any_error == '0' else ('0' if any_error == '1' else 'x') * config.width)


def expected_fault_vector(config, faults):
    counts = [0] * config.parity_width
    for bit in faults:
        counts[config.granule(bit)] += 1
    return bits(sum((weight % 2) << granule for granule, weight in enumerate(counts)), config.parity_width)


def error_patterns(config):
    count = config.parity_width
    if count <= 8:
        return tuple(range(1 << count))
    maximum = (1 << count) - 1
    return tuple(sorted({0, maximum, sum(1 << bit for bit in range(0, count, 2))} |
        {1 << bit for bit in range(count)} | {maximum ^ (1 << bit) for bit in range(count)} |
        {(1 << population) - 1 for population in range(count + 1)}))


def transition(before, after):
    return 'hold' if before == after else 'rise' if before == 0 else 'fall' if after == 0 else 'change'
