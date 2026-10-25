"""Publish reproducible default-profile scalar accuracy on a quantized interval.

This characterizes the bit-accurate equations, not application-level accuracy or
physical PPA. Actual RTL conformance is checked separately by the PyUVM suite.
"""
import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import sys
import gmpy2 as g

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src/val/building_blocks'), str(ROOT / 'src/val/lib')]
from exp_unit.config import DEFAULTS, ExpUnitConfig
from exp_unit.model import direct_integer, identities, image, predict, rounded


def percentile(values, percent):
    return sorted(values)[(len(values) - 1) * percent // 100]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--minimum', type=int, default=-8)
    parser.add_argument('--maximum', type=int, default=0)
    parser.add_argument('--output', type=Path,
                        default=ROOT / 'src/val/building_blocks/exp_unit/accuracy.json')
    args = parser.parse_args()
    c = ExpUnitConfig(DEFAULTS, 20261021, 2000, False, False, Path('unused'))
    low, high = args.minimum << c.INPUT_FRACTION_WIDTH, args.maximum << c.INPUT_FRACTION_WIDTH
    assert -(1 << (c.INPUT_WIDTH - 1)) <= low <= high < (1 << (c.INPUT_WIDTH - 1))
    report = dict(schema_version=1, scope='default-profile scalar model characterization',
                  parameters=c.parameters, interval=[args.minimum, args.maximum],
                  interval_grid='Every representable fixed-point input in the interval',
                  reference='gmpy2 2.2.1 / MPFR 4.2.1, 512-bit nearest-even arithmetic',
                  compiler_permitted_interval=[args.minimum, args.maximum],
                  target='Measured per-mode scalar bounds below; no application metric claimed',
                  profiles=[], physical_area='NOT_RUN', physical_energy='NOT_RUN',
                  application_accuracy='NOT_RUN')
    report['sources'] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (Path(__file__).resolve(), ROOT / 'src/val/building_blocks/exp_unit/model.py',
                     ROOT / 'src/rtl/building_blocks/generated/exp_unit_tables.json')}
    with g.context(precision=512, round=g.RoundToNearest):
        reference = {base: {x: (g.exp2 if base else g.exp)(g.mpfr(x) / (1 << c.INPUT_FRACTION_WIDTH))
                           for x in range(low, high + 1)} for base in (0, 1)}
        for base, interp, mode, signed in product((0, 1), repeat=4):
            absolute, relative, quantized, values = [], [], [], []
            components = dict.fromkeys(('base_conversion', 'fractional_approximation',
                'endpoint_quantization', 'interpolation_rounding', 'output_quantization'), 0.0)
            for x in range(low, high + 1):
                ports = dict(i_request_operand=x % (1 << c.INPUT_WIDTH), i_request_base=base,
                    i_request_output_signed=signed, i_request_interpolate=interp,
                    i_request_round_mode=mode, i_request_predicate=1, i_request_context_id=0, i_request_tag=0)
                r, f = predict(c, ports)
                ideal = reference[base][x]
                observed = g.mpfr(r['o_result_data']) / (1 << c.OUTPUT_FRACTION_WIDTH)
                error = abs(observed - ideal)
                absolute.append(float(error))
                relative.append(float(error / ideal))
                n, d = (ideal * (1 << c.OUTPUT_FRACTION_WIDTH)).as_integer_ratio()
                ideal_bits = min((1 << (c.OUTPUT_WIDTH - signed)) - 1, rounded(int(n), int(d), mode)[0])
                quantized.append(abs(r['o_result_data'] - ideal_bits))
                values.append(r['o_result_data'])
                coordinate = g.mpfr(f['z']) / (1 << c.RANGE_FRACTION_WIDTH)
                converted = g.exp2(coordinate)
                exact_lower = g.exp2(g.mpfr(f['address']) / (1 << c.TABLE_ADDRESS_WIDTH))
                exact_upper = g.exp2(g.mpfr(f['address'] + 1) / (1 << c.TABLE_ADDRESS_WIDTH))
                fraction = g.mpfr(f['remainder']) / (1 << (c.RANGE_FRACTION_WIDTH - c.TABLE_ADDRESS_WIDTH)) if interp else g.mpfr(0)
                exact_linear = exact_lower + (exact_upper - exact_lower) * fraction
                table = image(c.TABLE_ADDRESS_WIDTH, c.INTERNAL_FRACTION_WIDTH)
                quantized_linear = g.mpfr(table[f['address']])
                if interp:
                    quantized_linear += (table[f['address'] + 1] - table[f['address']]) * fraction
                quantized_linear /= 1 << c.INTERNAL_FRACTION_WIDTH
                restored = g.mul_2exp(g.mpfr(f['mantissa']) / (1 << c.INTERNAL_FRACTION_WIDTH), f['k'])
                scaled_linear = g.mul_2exp(exact_linear, f['k'])
                scaled_quantized = g.mul_2exp(quantized_linear, f['k'])
                errors = (abs(converted - ideal), abs(scaled_linear - converted),
                          abs(scaled_quantized - scaled_linear), abs(restored - scaled_quantized),
                          abs(observed - restored))
                for name, value in zip(components, errors, strict=True):
                    components[name] = max(components[name], float(value))
            assert all(a <= b for a, b in zip(values, values[1:])), 'Nonmonotonic output'
            report['profiles'].append(dict(base=base, interpolate=interp, round_mode=mode,
                output_signed=signed, quality_id=r['o_result_quality_id'], input_count=len(values),
                maximum_absolute_error=max(absolute), mean_absolute_error=sum(absolute) / len(absolute),
                p50_absolute_error=percentile(absolute, 50), p95_absolute_error=percentile(absolute, 95),
                p99_absolute_error=percentile(absolute, 99), maximum_relative_error=max(relative),
                maximum_error_vs_ideal_quantized_lsb=max(quantized), component_maximum_absolute_error=components,
                monotonic_on_interval=True, zero_encodings=values.count(0),
                plateau_edges=sum(a == b for a, b in zip(values, values[1:])),
                minimum_output=min(values), maximum_output=max(values)))
    report['identities'] = identities(c)[0]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f'Exp-unit scalar characterization PASS: {args.output}')


if __name__ == '__main__':
    main()
