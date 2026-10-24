"""Pinned, directed-rounding MPFR seed generation with exact integer certification."""
from functools import lru_cache
import json
from pathlib import Path
import gmpy2 as g

GENERATOR_VERSION = 1


@lru_cache(maxsize=None)
def seeds(width, fraction, address):
    assert g.version() == '2.2.1' and g.mpfr_version() == 'MPFR 4.2.1'
    precision = max(512, 4 * width + 4 * address + 64)
    values = []
    for parity in (0, 1):
        for region in range(1 << address):
            numerator = 1 << (2 * fraction + address + 1 - parity)
            denominator = (1 << (address + 1)) + 2 * region + 1
            with g.context(precision=precision, round=g.RoundDown):
                lower = g.sqrt(g.mpfr(numerator) / denominator)
            with g.context(precision=precision, round=g.RoundUp):
                upper = g.sqrt(g.mpfr(numerator) / denominator)
            with g.context(precision=precision, round=g.RoundToNearest):
                q = int(g.rint(lower))
                assert q == int(g.rint(upper)), 'Seed precision does not resolve rounding'
            # Certify the rounding decision against the exact squared half-ULPs.
            assert (2 * q - 1) ** 2 * denominator <= 4 * numerator
            assert (2 * q + 1) ** 2 * denominator >= 4 * numerator
            if (2 * q - 1) ** 2 * denominator == 4 * numerator:
                assert not q % 2
            if (2 * q + 1) ** 2 * denominator == 4 * numerator:
                assert not q % 2
            assert 0 < q < 1 << width
            values.append(q)
    return tuple(values)


@lru_cache(maxsize=None)
def image(width=28, fraction=22, address=6):
    values = seeds(width, fraction, address)
    data = b''.join(n.to_bytes(4, 'little') for n in (1, width, fraction, address))
    data += b''.join(n.to_bytes((width + 7) // 8, 'little') for n in values)
    checksum = 0x811c9dc5
    for byte in data:
        checksum = ((checksum ^ byte) * 0x01000193) & 0xffffffff
    return dict(generator='midpoint-rsqrt-v1', width=width, fraction=fraction,
        mantissa_address_width=address, gmpy2=g.version(), mpfr=g.mpfr_version(),
        precision=max(512, 4 * width + 4 * address + 64),
        rounding='nearest-even certified by directed MPFR intervals and exact squared half-ULPs',
        image_id=checksum ^ 0x52535101, checksum=checksum,
        checksum_algorithm='FNV-1a-32, little-endian metadata and seed words', seeds=list(values))


def verify_default_image():
    assert Path(__file__).with_name('seed_image.json').read_text() == json.dumps(image(), indent=2) + '\n'
