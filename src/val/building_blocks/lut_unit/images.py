"""Versioned synthetic image recipes; no mathematical-function accuracy claim."""
import argparse
import json
from pathlib import Path

RECIPE_VERSION = 1


def image_value(width, bank, address, kind=0):
    """Generate wrapping increasing, decreasing, or constant verification data."""
    mask = (1 << width) - 1
    if kind == 0:
        value = address * 7 + bank * 3
        if width > 256:
            value |= (address % 2) << (width - 1)
        return value & mask
    if kind == 1:
        return (mask - address * 5 - bank) & mask
    return 3 & mask


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--address-width', type=int, default=8)
    parser.add_argument('--output-width', type=int, default=16)
    parser.add_argument('--fraction-width', type=int, default=8)
    parser.add_argument('--banks', type=int, default=4)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.address_width <= 16 or min(args.output_width, args.fraction_width, args.banks) < 1:
        parser.error('Use address width 1..16 and positive data/fraction widths and bank count')
    image = dict(schema_version=1, recipe_version=RECIPE_VERSION, purpose='synthetic_verification',
        coordinate_format=dict(address_bits=args.address_width, fraction_bits=args.fraction_width),
        output_bits=args.output_width, banks=[dict(bank=b, table_id=b + 7, quality_id=b % 3,
            recipe=('wrapping_increasing', 'wrapping_decreasing', 'constant')[b % 3],
            entries=[image_value(args.output_width, b, a, b % 3) for a in range(1 << args.address_width)])
            for b in range(args.banks)])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(image, indent=2, sort_keys=True) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
