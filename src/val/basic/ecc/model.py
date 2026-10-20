"""Conceptual-position arithmetic, independent of RTL reductions and masks."""

from functools import lru_cache
from types import MappingProxyType
from mosaic_uvm.logic import bits


def known(word):
    return not set(word) & {'x', 'z'}


def syndrome(config, received):
    # A received one at conceptual position u contributes binary column u.
    result = 0
    for position in range(1, config.hamming_width + 1):
        if received & (1 << (position - 1)):
            result ^= position
    return result


@lru_cache(maxsize=128)
def encode(config, data):
    word = sum(((data >> bit) & 1) << (position - 1) for bit, position in enumerate(config.data_positions))
    parity_column = syndrome(config, word)
    for parity in range(config.parity_bits):
        if parity_column & (1 << parity):
            word |= 1 << ((1 << parity) - 1)
    return word | ((word.bit_count() % 2) << config.hamming_width)


@lru_cache(maxsize=128)
def decode(config, received):
    check = syndrome(config, received)
    overall = received.bit_count() % 2
    repaired = received
    position = None
    if check == 0 and overall == 0:
        status = 'no_error'
    elif check == 0:
        status, position = 'corrected', config.hamming_width
    elif overall and check <= config.hamming_width:
        status, position = 'corrected', check - 1
    else:
        status = 'uncorrectable'
    if position is not None:
        repaired ^= 1 << position
    if status == 'uncorrectable':
        repaired = 0
    data = sum(((repaired >> (location - 1)) & 1) << bit for bit, location in enumerate(config.data_positions))
    result = dict(o_decoded_data=bits(data, config.width), o_corrected_codeword=bits(repaired, config.code_width),
                  o_syndrome=bits(check, config.parity_bits), o_overall_parity_error=str(overall),
                  o_no_error=str(int(status == 'no_error')), o_corrected=str(int(status == 'corrected')),
                  o_uncorrectable=str(int(status == 'uncorrectable')), o_scrub_required=str(int(status == 'corrected')),
                  o_error_position_valid=str(int(position is not None)), o_error_position=bits(position or 0, config.position_width))
    return MappingProxyType(result)


def check_unknown_encode(config, source, actual):
    observed = actual[::-1]
    for data_bit, position in enumerate(config.data_positions):
        value = source[-data_bit-1]
        if value in '01':
            assert observed[position-1] == value, 'Unknown encode contaminated a known systematic bit'
        else:
            assert observed[position-1] in 'xz', 'Unknown encode data was silently resolved'
    for parity in range(config.parity_bits):
        values = [source[-index-1] for index, position in enumerate(config.data_positions) if position & (1 << parity)]
        if all(value in '01' for value in values):
            assert observed[(1 << parity)-1] == str(sum(map(int, values)) % 2), 'Known encode parity set changed'


def check_unknown_decode(config, received, observed):
    values = received[::-1]
    for parity in range(config.parity_bits):
        selected = [values[position-1] for position in range(1, config.hamming_width + 1) if position & (1 << parity)]
        expected = 'x' if any(value in 'xz' for value in selected) else str(sum(map(int, selected)) % 2)
        assert observed['o_syndrome'][-parity-1] == expected, 'Unknown decode syndrome propagation changed'
    assert observed['o_overall_parity_error'] == 'x', 'Unknown overall parity was silently resolved'
    assert observed['o_no_error'] != '1' and observed['o_corrected'] != '1', 'Unknown decode was classified as known success'
    assert observed['o_scrub_required'] == observed['o_error_position_valid'] == observed['o_corrected'], 'Unknown status consistency failed'
    if observed['o_uncorrectable'] == '1':
        for name in ('o_decoded_data', 'o_corrected_codeword', 'o_error_position', 'o_error_position_valid', 'o_scrub_required'):
            assert set(observed[name]) == {'0'}, 'Uncorrectable unknown word was not fail closed'
    else:
        assert 'x' in ''.join(observed[name] for name in ('o_no_error', 'o_corrected', 'o_uncorrectable')), 'Unknown classification was silently resolved'
