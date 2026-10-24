"""MPFR numerical characterization and representative RMSNorm error accounting."""
import argparse
from functools import lru_cache
import json
import platform
from pathlib import Path
from types import SimpleNamespace
import gmpy2 as g
from rsqrt_unit.defaults import DEFAULTS
from rsqrt_unit.images import image
from rsqrt_unit.model import evaluate, rounded
from rsqrt_unit.sequences import address_operands


@lru_cache(maxsize=262144)
def reference(magnitude, fraction):
    with g.context(precision=512, round=g.RoundToNearest):
        return 1 / g.sqrt(g.mpfr(magnitude) / (1 << fraction))


def characterize(parameters, *, exhaustive=False):
    c = SimpleNamespace(**(parameters | {'SEED_PROTECTION': 0}))
    complete = exhaustive or c.INPUT_WIDTH <= 8
    maximum = (1 << c.INPUT_WIDTH) - 1
    directed = sorted({0, 1, maximum} | set(address_operands(c)) | {
        max(1, maximum * k // 1024) for k in range(1, 1025)})
    epsilon_values = (0, 1, maximum) if c.SUPPORT_EPSILON else (0,)
    groups = []
    for epsilon in epsilon_values:
        operands = range(1, maximum + 1) if complete and epsilon == 0 else directed
        for count in range(c.MAX_ITERATIONS + 1):
            for out in (0, 1):
                for mode in (0, 1):
                    absolute = []
                    relative = []
                    by_magnitude = {}
                    by_parity = {}
                    overflow = []
                    underflow = []
                    violations = []
                    previous = None
                    unclamped = 0.0
                    for operand in operands:
                        effective = operand + epsilon
                        if not effective:
                            continue
                        result, stats = evaluate(c, dict(operand=operand, input_signed=0,
                            output_signed=out, add_epsilon=int(bool(epsilon)), epsilon=epsilon,
                            iterations=count, round_mode=mode, predicate=1, context_id=0, tag=0))
                        with g.context(precision=512, round=g.RoundToNearest):
                            ideal = reference(effective, c.INPUT_FRACTION_WIDTH)
                            actual = g.mpfr(result['data']) / (1 << c.OUTPUT_FRACTION_WIDTH)
                            error = abs(actual - ideal)
                            absolute.append(float(error))
                            relative.append(float(error / ideal))
                        if not result['saturated']:
                            unclamped = max(unclamped, absolute[-1])
                        p = str(stats['leading'])
                        parity = str(stats['parity'])
                        by_magnitude[p] = max(by_magnitude.get(p, 0.0), relative[-1])
                        by_parity[parity] = max(by_parity.get(parity, 0.0), relative[-1])
                        if result['overflow']:
                            overflow.append(effective)
                        if result['underflow']:
                            underflow.append(effective)
                        if previous is not None and result['data'] > previous:
                            if len(violations) < 8:
                                violations.append(effective)
                        previous = result['data']
                    absolute.sort()
                    relative.sort()
                    def distribution(values):
                        return dict(maximum=values[-1], mean=sum(values) / len(values),
                            p50=values[(len(values) - 1) // 2],
                            p95=values[(len(values) - 1) * 95 // 100],
                            p99=values[(len(values) - 1) * 99 // 100])
                    groups.append(dict(iterations=count, quality_id=count, round_mode=mode,
                        output_signed=out, epsilon_encoded=epsilon, samples=len(absolute),
                        method='exhaustive nonzero operand encodings' if complete and epsilon == 0
                            else 'deterministic magnitude and seed-boundary samples',
                        absolute_error=distribution(absolute), relative_error=distribution(relative),
                        maximum_unclamped_absolute_error=unclamped,
                        relative_error_by_leading_one=by_magnitude,
                        relative_error_by_exponent_parity=by_parity,
                        monotonicity='violations observed' if violations else
                            'nonincreasing on exhaustive interval' if complete and epsilon == 0
                            else 'nonincreasing on samples', monotonicity_first_violations=violations,
                        overflow=dict(count=len(overflow), minimum=min(overflow) if overflow else None,
                            maximum=max(overflow) if overflow else None),
                        underflow=dict(count=len(underflow), minimum=min(underflow) if underflow else None,
                            maximum=max(underflow) if underflow else None),
                        latency=4 + 3 * (c.MAX_ITERATIONS if c.EVALUATION_ARCH else count),
                        initiation_interval=1 if c.EVALUATION_ARCH else 4 + 3 * count))
    # RMSNorm includes input quantization, a full-product sum-of-squares reduction,
    # its separate nearest-even conversion, epsilon, and the subsequent multiply.
    vector = [1, -2, 3, -4]
    scale = 1 << max(0, c.INPUT_FRACTION_WIDTH - 2)
    encoded = [x * scale for x in vector]
    sum_squares = sum(x * x for x in encoded)
    reduction = int(round(g.mpq(sum_squares, len(encoded) * (1 << c.INPUT_FRACTION_WIDTH))))
    applications = []
    for epsilon in ((0, 1) if c.SUPPORT_EPSILON else (0,)):
        for count in range(c.MAX_ITERATIONS + 1):
            result, _ = evaluate(c, dict(operand=reduction, input_signed=0, output_signed=0,
                add_epsilon=int(bool(epsilon)), epsilon=epsilon, iterations=count,
                round_mode=1, predicate=1, context_id=0, tag=0))
            outputs = [rounded(x * result['data'], c.INPUT_FRACTION_WIDTH, 1)[0] /
                       (1 << c.OUTPUT_FRACTION_WIDTH) for x in encoded]
            with g.context(precision=512, round=g.RoundToNearest):
                ideal_mean = g.mpfr(sum_squares) / (len(encoded) * (1 << (2 * c.INPUT_FRACTION_WIDTH)))
                ideal_inv = 1 / g.sqrt(ideal_mean + g.mpfr(epsilon) / (1 << c.INPUT_FRACTION_WIDTH))
                ideal_outputs = [g.mpfr(x) / (1 << c.INPUT_FRACTION_WIDTH) * ideal_inv for x in encoded]
                error = max(float(abs(g.mpfr(a) - b)) for a, b in zip(outputs, ideal_outputs))
                reduction_error = float(abs(g.mpfr(reduction) /
                    (1 << c.INPUT_FRACTION_WIDTH) - ideal_mean))
            applications.append(dict(iterations=count, epsilon_encoded=epsilon,
                input_vector_encoded=encoded, reduction_encoded=reduction,
                reduction_absolute_error=reduction_error, output_values=outputs,
                maximum_absolute_output_error=error, saturated=bool(result['saturated']),
                scope='RMSNorm example including reduction conversion and final multiply'))
    return dict(parameters=parameters, input_interval=[2.0 ** -c.INPUT_FRACTION_WIDTH,
        maximum * 2.0 ** -c.INPUT_FRACTION_WIDTH], negative_behavior='error before epsilon',
        zero_behavior='epsilon rescue or configured zero error result', python=platform.python_version(),
        reference='gmpy2 2.2.1 / MPFR 4.2.1, 512-bit nearest-even',
        image=image(c.INTERNAL_WIDTH, c.INTERNAL_FRACTION_WIDTH, c.SEED_MANTISSA_ADDRESS_WIDTH),
        groups=groups, application_checks=applications,
        physical_metrics=dict(area='NOT_RUN', energy='NOT_RUN', synthesis='Design Compiler (deferred)'),
        qualification='numerical evidence only; application acceptance targets are integration-owned')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = json.dumps(characterize(DEFAULTS, exhaustive=True), indent=2) + '\n'
    if args.check:
        assert args.output.read_text() == result, 'Characterization artifact differs'
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result)


if __name__ == '__main__':
    main()
