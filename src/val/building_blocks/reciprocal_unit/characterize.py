"""Reproducible numerical quality evidence; physical metrics remain unmeasured."""
import argparse
import json
import platform
from pathlib import Path
from types import SimpleNamespace
from reciprocal_unit.defaults import DEFAULTS
from reciprocal_unit.images import image
from reciprocal_unit.model import evaluate
from reciprocal_unit.sequences import address_operands


def characterize(parameters, *, exhaustive=False):
    # Protection does not alter healthy numerical values. Characterize the plain
    # image, then verify protected-mode equality in RTL campaigns and codec tests.
    c = SimpleNamespace(**(parameters | {'SEED_PROTECTION': 0}))
    complete = exhaustive or c.INPUT_WIDTH <= 8
    encoded_one = 1 << (c.INPUT_FRACTION_WIDTH + c.OUTPUT_FRACTION_WIDTH)
    groups = []
    for count in range(c.MAX_ITERATIONS + 1):
        for mode in (0, 1):
            for interpretation in ('unsigned', 'signed_positive', 'signed_negative'):
                negative = interpretation == 'signed_negative'
                signed_mode = interpretation != 'unsigned'
                maximum = (1 << (c.INPUT_WIDTH - int(signed_mode))) - int(not negative)
                if complete:
                    magnitudes = range(1, maximum + 1)
                else:
                    magnitudes = sorted({1, maximum} | {
                        max(1, maximum * k // 2048) for k in range(1, 2049)} | {
                        n for n in address_operands(c) if n <= maximum})
                absolute = []
                relative = []
                by_leading = {}
                status_magnitudes = {'overflow': [], 'underflow': []}
                violations = []
                previous = None
                max_unclamped_relative = 0.0
                for magnitude in magnitudes:
                    operand = (-magnitude if negative else magnitude) & ((1 << c.INPUT_WIDTH) - 1)
                    response, _ = evaluate(c, dict(operand=operand, signed=int(signed_mode),
                        iterations=count, round_mode=mode, predicate=1, context_id=0, tag=0))
                    result = response['data']
                    if negative:
                        result = (-result) & ((1 << c.OUTPUT_WIDTH) - 1)
                    numerator = abs(result * magnitude - encoded_one)
                    absolute.append(numerator / (magnitude * (1 << c.OUTPUT_FRACTION_WIDTH)))
                    relative.append(numerator / encoded_one)
                    if not response['saturated']:
                        max_unclamped_relative = max(max_unclamped_relative, relative[-1])
                    p = str(magnitude.bit_length() - 1)
                    by_leading[p] = max(by_leading.get(p, 0.0), relative[-1])
                    for status in status_magnitudes:
                        if response[status]:
                            status_magnitudes[status].append(magnitude)
                    if previous is not None and result > previous and len(violations) < 8:
                        violations.append(magnitude)
                    previous = result
                absolute.sort()
                relative.sort()
                def stats(values):
                    return dict(maximum=values[-1], mean=sum(values) / len(values),
                        p50=values[(len(values) - 1) // 2],
                        p95=values[(len(values) - 1) * 95 // 100],
                        p99=values[(len(values) - 1) * 99 // 100])
                groups.append(dict(iterations=count, quality_id=count, round_mode=mode,
                    interpretation=interpretation, samples=len(absolute),
                    nonzero_input_magnitude_interval=[2.0 ** -c.INPUT_FRACTION_WIDTH,
                        maximum * 2.0 ** -c.INPUT_FRACTION_WIDTH],
                    absolute_error=stats(absolute), relative_error=stats(relative),
                    max_unclamped_relative_error=max_unclamped_relative,
                    relative_error_by_leading_one=by_leading,
                    monotonicity='violations observed' if violations else
                        'nonincreasing on exhaustive interval' if complete else 'nonincreasing on samples',
                    monotonicity_first_violations=violations,
                    status_magnitude_samples={k: dict(count=len(v), minimum=min(v) if v else None,
                        maximum=max(v) if v else None) for k, v in status_magnitudes.items()},
                    latency=3 + 2 * (c.MAX_ITERATIONS if c.EVALUATION_ARCH else count),
                    initiation_interval=1 if c.EVALUATION_ARCH else 3 + 2 * count))
    # A conservative no-clamp bound includes seed quantization, two rounding
    # points per Newton step, normalization quantization, and final output LSB.
    epsilon = 2.0 ** -c.INTERNAL_FRACTION_WIDTH
    bound = 1 / ((1 << (c.SEED_ADDRESS_WIDTH + 1)) + 1) + epsilon
    bounds = []
    for count in range(c.MAX_ITERATIONS + 1):
        normalization_bound = bound + (1 + bound) * 2 * epsilon
        bounds.append(dict(iterations=count, normalized_relative_bound=bound,
            unclamped_absolute_bound=(2.0 ** c.INPUT_FRACTION_WIDTH) * normalization_bound +
                2.0 ** -c.OUTPUT_FRACTION_WIDTH))
        bound = bound * bound + 4 * epsilon
    # Representative positive-sum normalization, like the reciprocal stage of
    # Softmax. Include a separately rounded multiply and compare ideal weights.
    weights = [1, 2, 3, 4, 5]
    total = sum(weights)
    if total >= 1 << c.INPUT_WIDTH:
        weights = [1, 1, 1]
        total = 3
    applications = []
    for count in range(c.MAX_ITERATIONS + 1):
        response, _ = evaluate(c, dict(operand=total, signed=0, iterations=count,
            round_mode=1, predicate=1, context_id=0, tag=0))
        probabilities = [round(w * response['data'] / (1 << c.INPUT_FRACTION_WIDTH)) /
                         (1 << c.OUTPUT_FRACTION_WIDTH) for w in weights]
        applications.append(dict(iterations=count, weights=weights,
            output_probabilities=probabilities, maximum_absolute_probability_error=max(
                abs(p - w / total) for p, w in zip(probabilities, weights)),
            probability_sum_error=abs(sum(probabilities) - 1),
            reciprocal_saturated=bool(response['saturated']),
            scope='positive-sum normalization with separately rounded fixed-point multiply'))
    return dict(parameters=parameters, characterization='exhaustive_nonzero_inputs' if complete
        else 'deterministic_magnitude_and_seed_boundary_samples', python=platform.python_version(),
        method='unbounded-integer model; exact integer error numerator; float reporting',
        image=image(c.INTERNAL_WIDTH, c.INTERNAL_FRACTION_WIDTH, c.SEED_ADDRESS_WIDTH),
        groups=groups, conservative_unclamped_bounds=bounds, application_checks=applications,
        physical_metrics=dict(area='NOT_RUN', energy='NOT_RUN', synthesis='Design Compiler (deferred)'),
        qualification='numerical evidence only; application acceptance target is integration-owned')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = json.dumps(characterize(DEFAULTS, exhaustive=True), indent=2) + '\n'
    if args.check:
        assert args.output.read_text() == result, 'Default characterization differs from checked-in artifact'
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result)


if __name__ == '__main__':
    main()
