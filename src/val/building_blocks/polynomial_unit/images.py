"""Reproducible exact identity image; this is a validation recipe, not a fitted SFU."""
import json
from pathlib import Path
from polynomial_unit.defaults import DEFAULTS


def identity_image(parameters=DEFAULTS):
    p = parameters
    fractional = p['FRACTION_WIDTH']
    assert fractional < p['COEFFICIENT_WIDTH'] - 1
    width = min(p['INPUT_WIDTH'], p['OUTPUT_WIDTH'])
    return dict(schema_version=1, name='exact_identity', function='P(x) = x',
        polynomial_id=1, quality_id=0, degree=1, coefficient_order='ascending powers',
        coefficients=[0, 1 << fractional], x_min=-(1 << (width - 1)),
        x_max=(1 << (width - 1)) - 1, range_policy=0, round_mode=1, result_shift=0,
        formats={k: p[k] for k in ('INPUT_WIDTH', 'COEFFICIENT_WIDTH',
            'ACCUMULATOR_WIDTH', 'OUTPUT_WIDTH', 'FRACTION_WIDTH')},
        quantization='Exact binary coefficients; no fitting or external tool required.',
        accuracy=dict(method='Analytical: rescale((1 << F) * x) = x with no remainder.',
                      maximum_absolute_error=0, mean_absolute_error=0,
                      percentile_99_absolute_error=0, monotonic=True),
        application_scope='Exact identity validation only; no activation approximation claim.')


def serialized_image():
    return json.dumps(identity_image(), indent=2, sort_keys=True) + '\n'


def check_image():
    assert Path(__file__).with_name('identity_image.json').read_text() == serialized_image()
