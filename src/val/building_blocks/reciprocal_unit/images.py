"""Exact, deterministic midpoint ROM generator; no floating-point seed arithmetic."""
from functools import lru_cache
import json
from pathlib import Path


@lru_cache(maxsize=None)
def seeds(width, fraction, address):
    values = []
    for index in range(1 << address):
        denominator = (1 << (address + 1)) + 2 * index + 1
        quotient, remainder = divmod(1 << (fraction + address + 2), denominator)
        quotient += 2 * remainder > denominator or (2 * remainder == denominator and quotient % 2)
        values.append(min(quotient, (1 << width) - 1))
    return tuple(values)


@lru_cache(maxsize=None)
def image(width=24, fraction=20, address=6):
    values = seeds(width, fraction, address)
    data = b''.join(n.to_bytes(4, 'little') for n in (1, width, fraction, address))
    data += b''.join(n.to_bytes((width + 7) // 8, 'little') for n in values)
    checksum = 0x811c9dc5
    for byte in data:
        checksum = ((checksum ^ byte) * 0x01000193) & 0xffffffff
    return dict(generator='midpoint-reciprocal-v1', width=width, fraction=fraction,
                address_width=address, image_id=checksum ^ 0x52435001, checksum=checksum,
                checksum_algorithm='FNV-1a-32, little-endian metadata and seed words',
                seeds=list(values))


def verify_default_image():
    expected = json.dumps(image(), indent=2) + '\n'
    assert Path(__file__).with_name('seed_image.json').read_text() == expected
