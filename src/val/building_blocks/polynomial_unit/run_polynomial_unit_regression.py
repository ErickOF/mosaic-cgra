"""Python-only polynomial profiles, strict parameter guards and source provenance."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import shlex
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lib'))
from mosaic_uvm.regression import (campaign_status, finish_summary, license_unavailable,
    parameter_guard, parse_args, passed_test, require_simulator, run_simulation, verification_hashes)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from polynomial_unit.defaults import DEFAULTS
from polynomial_unit.test_model import ModelTests

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in (
    'common/ecc_pkg',
    'building_blocks/polynomial_unit_pkg', 'common/dff', 'common/operand_isolation',
    'common/decoder', 'common/mux', 'basic/fifo', 'basic/parity', 'basic/ecc',
    'building_blocks/event_barrier_state', 'building_blocks/event_barrier_queue',
    'building_blocks/lut_unit_bank', 'building_blocks/multiplier',
    'building_blocks/polynomial_unit_round', 'building_blocks/polynomial_unit_horner',
    'building_blocks/polynomial_unit_scale'))


def profile(name, **overrides):
    return name, DEFAULTS | overrides


PROFILES = (
    profile('default'),
    *(profile(f'features_a{arch}_p{protect}_c{coverage}_r{reset}', INPUT_WIDTH=8,
        COEFFICIENT_WIDTH=24, ACCUMULATOR_WIDTH=24, OUTPUT_WIDTH=8, FRACTION_WIDTH=4,
        MAX_DEGREE=3, NUM_BANKS=3, BANK_VERSION_WIDTH=2, EVALUATION_ARCH=arch,
        COEFFICIENT_PROTECTION=protect, TRACK_COEFFICIENT_COVERAGE=coverage,
        ASYNC_RESET=reset, OUTPUT_QUEUE_DEPTH=3, PROGRAM_RESPONSE_DEPTH=3)
        for arch, protect, coverage, reset in product((0, 1), (0, 1, 2), (0, 1), (0, 1))),
    *(profile(f'degree{d}_a{arch}_p{protect}', INPUT_WIDTH=i, COEFFICIENT_WIDTH=k,
        ACCUMULATOR_WIDTH=a, OUTPUT_WIDTH=o, FRACTION_WIDTH=f, MAX_DEGREE=d,
        NUM_BANKS=b, BANK_VERSION_WIDTH=2, RESULT_SHIFT_WIDTH=(a - 1).bit_length() + 1,
        EVALUATION_ARCH=arch, COEFFICIENT_PROTECTION=protect, OUTPUT_QUEUE_DEPTH=q,
        PROGRAM_RESPONSE_DEPTH=q, ASYNC_RESET=(d + arch + protect) % 2)
        for (d, i, k, a, o, f, b, q), arch, protect in product((
            (1, 8, 12, 24, 8, 4, 1, 1), (2, 16, 18, 32, 16, 8, 2, 2),
            (3, 32, 24, 64, 32, 16, 4, 3), (4, 16, 18, 32, 16, 12, 3, 3),
            (8, 16, 18, 64, 32, 8, 8, 2)), (0, 1), (0, 1, 2))),
)
POSITIVE = tuple(k for k in DEFAULTS if k not in (
    'EVALUATION_ARCH', 'COEFFICIENT_PROTECTION', 'TRACK_COEFFICIENT_COVERAGE', 'ASYNC_RESET'))
INVALID = (
    *((f'{name}_{label}', {name: value}) for name in POSITIVE
      for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    *((f'{name}_{label}', {name: value}) for name in ('EVALUATION_ARCH',
        'TRACK_COEFFICIENT_COVERAGE', 'ASYNC_RESET', 'COEFFICIENT_PROTECTION')
      for label, value in (('invalid', 3), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    ('version_one', dict(BANK_VERSION_WIDTH=1)),
    ('fraction_input', dict(FRACTION_WIDTH=16)),
    ('fraction_coefficient', dict(COEFFICIENT_WIDTH=12)),
    ('fraction_accumulator', dict(ACCUMULATOR_WIDTH=12)),
    ('small_accumulator', dict(ACCUMULATOR_WIDTH=17)),
    ('short_shift', dict(RESULT_SHIFT_WIDTH=5)),
    ('storage_overflow', dict(NUM_BANKS=1073741824)),
    ('degree_overflow', dict(MAX_DEGREE=1073741824)),
    ('width_overflow', dict(ACCUMULATOR_WIDTH=1073741824)),
)


def run_profile(task):
    args, build, rtl, index, name, parameters = task
    print('Running', name, flush=True)
    prefix = '-Ppolynomial_unit.' if args.sim == 'icarus' else '-pvalue+polynomial_unit.'
    flags = ' '.join(shlex.quote(f'{prefix}{k}={v}') for k, v in parameters.items())
    result, log, results, coverage = run_simulation(
        args, ROOT, TEST_DIR, 'polynomial_unit', 'test_polynomial_unit', 'PolynomialUnitTest',
        build / name, ' '.join(map(str, (*DEPENDENCIES, rtl))), parameters=parameters,
        compile_args=f'{args.compile_args} {flags}', environment={
            **{f'POLYNOMIAL_UNIT_{k}': str(v) for k, v in parameters.items()},
            'POLYNOMIAL_UNIT_SEED': str(args.seed + index),
            'POLYNOMIAL_UNIT_RANDOM_CYCLES': str(args.random_cycles),
        })
    row = dict(name=name, parameters=parameters, status='FAIL', log=str(log))
    try:
        if result.returncode:
            raise ValueError(f'make exited {result.returncode}')
        passed_test(results, 'PolynomialUnitTest', 'test_polynomial_unit')
        data = json.loads(coverage.read_text())
        if (data['status'] != 'PASS' or data['parameters'] != parameters or
            not data['goals'] or not all(data['goals'].values()) or
            data['seed'] != args.seed + index or data['random_transactions'] != args.random_cycles or
            data['hdl_assertions'] != 'NOT_RUN'):
            raise ValueError('Coverage evidence mismatch')
        row.update(data, name=name, log=str(log), coverage=str(coverage))
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        row['error'] = str(error)
        if license_unavailable(log.read_text()):
            row['status'] = 'NOT_RUN'
        print('\n'.join(log.read_text().splitlines()[-30:]), flush=True)
    print(name, row['status'], flush=True)
    return row


def main():
    args = parse_args('polynomial_unit', __doc__, profiles=[n for n, _ in PROFILES],
                      seed=20261023, rtl_category='building_blocks')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    output = build / 'summary.json'
    output.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, profiles=[],
        parameter_checks=[], started_at_utc=datetime.now(timezone.utc).isoformat(),
        validation_mode='Python-only', synthesis='Design Compiler (deferred)',
        scope='selected_profiles' if args.case else 'representative_parameter_matrix')
    try:
        summary['rtl_sha256'] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary['dependency_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in DEPENDENCIES}
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        summary['image_sha256'] = hashlib.sha256((TEST_DIR / 'identity_image.json').read_bytes()).hexdigest()
        with (build / 'python_model_tests.log').open('w') as log:
            result = unittest.TextTestRunner(stream=log).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(ModelTests))
        summary['python_model_checks'] = dict(
            status='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun)
        if not result.wasSuccessful():
            raise ValueError('Python numerical model checks failed')
        require_simulator(args)
        jobs = int(os.getenv('POLYNOMIAL_UNIT_JOBS', '4' if args.sim == 'icarus' else '1'))
        if not 1 <= jobs <= 32:
            raise ValueError('POLYNOMIAL_UNIT_JOBS must be between 1 and 32')
        summary['jobs'] = jobs
        tasks = [(args, build, rtl, index, name, p) for index, (name, p) in enumerate(PROFILES)
                 if not args.case or name in args.case]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles'] = list(pool.map(run_profile, tasks))
        groups = {}
        for row in summary['profiles']:
            key = json.dumps({k: v for k, v in row['parameters'].items()
                              if k not in ('EVALUATION_ARCH', 'ASYNC_RESET')}, sort_keys=True)
            groups.setdefault(key, []).append(row)
        summary['architecture_equivalence'] = []
        for key, rows in groups.items():
            if {row['parameters']['EVALUATION_ARCH'] for row in rows} == {0, 1}:
                equal = all(row['status'] == 'PASS' for row in rows) and len({
                    row.get('arithmetic_signature') for row in rows}) == 1
                summary['architecture_equivalence'].append(dict(
                    parameters=json.loads(key), profiles=[row['name'] for row in rows],
                    status='PASS' if equal else 'FAIL'))
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'polynomial_unit', name,
            p, 'polynomial_unit_parameters_must_be_valid', dependencies=DEPENDENCIES)
            for name, p in INVALID]
        complete = len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES))
        complete &= len(summary['parameter_checks']) == len(INVALID)
        stable = summary['rtl_sha256'] == hashlib.sha256(rtl.read_bytes()).hexdigest() and all(
            summary['dependency_sha256'][str(p.relative_to(ROOT))] ==
            hashlib.sha256(p.read_bytes()).hexdigest() for p in DEPENDENCIES) and (
            summary['verification_sha256'] == verification_hashes(TEST_DIR))
        stable &= summary['image_sha256'] == hashlib.sha256(
            (TEST_DIR / 'identity_image.json').read_bytes()).hexdigest()
        summary['sources_stable'] = stable
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'],
            *summary['architecture_equivalence']), complete and stable)
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
        print(error, file=sys.stderr)
    finally:
        finish_summary(output, summary, 'Polynomial unit')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
