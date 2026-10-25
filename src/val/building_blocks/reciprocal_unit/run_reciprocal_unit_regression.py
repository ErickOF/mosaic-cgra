"""Python-only reciprocal profiles, strict parameter guards and source provenance."""
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
from reciprocal_unit.defaults import DEFAULTS
from reciprocal_unit.test_model import ModelTests
from reciprocal_unit.characterize import characterize

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in (
    'building_blocks/reciprocal_unit_pkg', 'building_blocks/scalar_alu_pkg',
    'common/dff', 'common/reset_synchronizer', 'common/operand_isolation',
    'common/decoder', 'common/priority_encoder', 'common/mux', 'basic/fifo',
    'basic/parity', 'basic/ecc', 'building_blocks/event_barrier_state',
    'building_blocks/event_barrier_queue', 'building_blocks/multiplier',
    'building_blocks/scalar_alu', 'building_blocks/polynomial_unit_round',
    'building_blocks/protected_seed_rom', 'building_blocks/reciprocal_unit_normalize', 'building_blocks/reciprocal_unit_seed',
    'building_blocks/reciprocal_unit_newton', 'building_blocks/reciprocal_unit_scale'))


def profile(name, **overrides):
    return name, DEFAULTS | overrides


PROFILES = (
    profile('default'),
    profile('default_unrolled', EVALUATION_ARCH=1),
    *(profile(f'features_a{arch}_p{protect}_z{zero}_r{reset}', INPUT_WIDTH=8,
        INPUT_FRACTION_WIDTH=4, INTERNAL_WIDTH=16, INTERNAL_FRACTION_WIDTH=12,
        OUTPUT_WIDTH=8, OUTPUT_FRACTION_WIDTH=4, SEED_ADDRESS_WIDTH=3,
        MAX_ITERATIONS=2, OUTPUT_QUEUE_DEPTH=3, EVALUATION_ARCH=arch,
        SEED_PROTECTION=protect, ZERO_RESULT_MODE=zero, ASYNC_RESET=reset)
        for arch, protect, zero, reset in product((0, 1), (0, 1, 2), (0, 1), (0, 1))),
    *(profile(f'geometry{index}_a{arch}', INPUT_WIDTH=i, INPUT_FRACTION_WIDTH=fi,
        INTERNAL_WIDTH=w, INTERNAL_FRACTION_WIDTH=f, OUTPUT_WIDTH=o,
        OUTPUT_FRACTION_WIDTH=fo, SEED_ADDRESS_WIDTH=a, MAX_ITERATIONS=m,
        OUTPUT_QUEUE_DEPTH=q, EVALUATION_ARCH=arch, SEED_PROTECTION=p,
        ASYNC_RESET=index % 2, ZERO_RESULT_MODE=index % 2)
        for (index, i, fi, w, f, o, fo, a, m, q, p), arch in product((
            (0, 8, 4, 16, 12, 8, 4, 4, 0, 1, 0),
            (1, 16, 8, 24, 20, 16, 12, 6, 1, 3, 1),
            (2, 32, 16, 32, 24, 32, 16, 8, 3, 3, 2),
            (3, 32, 12, 16, 12, 8, 4, 4, 3, 1, 1),
            (4, 16, 12, 48, 40, 32, 16, 8, 2, 3, 2),
            (5, 8, 4, 16, 6, 16, 8, 2, 1, 2, 2),
            (6, 4, 2, 8, 4, 4, 2, 1, 2, 1, 0)), (0, 1))),
)
POSITIVE = tuple(k for k in DEFAULTS if k not in (
    'MAX_ITERATIONS', 'EVALUATION_ARCH', 'ZERO_RESULT_MODE', 'SEED_PROTECTION', 'ASYNC_RESET'))
INVALID = (
    *((f'{name}_{label}', {name: value}) for name in POSITIVE
      for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    *((f'{name}_{label}', {name: value}) for name in ('EVALUATION_ARCH',
        'ZERO_RESULT_MODE', 'ASYNC_RESET', 'SEED_PROTECTION')
      for label, value in (('invalid', 3), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    *((f'iterations_{label}', dict(MAX_ITERATIONS=value))
      for label, value in (('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    ('fraction_input', dict(INPUT_FRACTION_WIDTH=16)),
    ('fraction_output', dict(OUTPUT_FRACTION_WIDTH=16)),
    ('fraction_internal', dict(INTERNAL_WIDTH=21)),
    ('seed_fraction', dict(SEED_ADDRESS_WIDTH=20)),
    ('address_overflow', dict(SEED_ADDRESS_WIDTH=32)),
    ('storage_overflow', dict(SEED_ADDRESS_WIDTH=30, INTERNAL_WIDTH=48,
        INTERNAL_FRACTION_WIDTH=40)),
    ('iteration_overflow', dict(MAX_ITERATIONS=1073741824)),
    ('width_overflow', dict(INTERNAL_WIDTH=1073741824)),
    ('queue_overflow', dict(OUTPUT_QUEUE_DEPTH=1073741824)),
)


def run_profile(task):
    args, build, rtl, index, name, parameters = task
    print('Running', name, flush=True)
    prefix = '-Preciprocal_unit.' if args.sim == 'icarus' else '-pvalue+reciprocal_unit.'
    flags = ' '.join(shlex.quote(f'{prefix}{k}={v}') for k, v in parameters.items())
    result, log, results, coverage = run_simulation(
        args, ROOT, TEST_DIR, 'reciprocal_unit', 'test_reciprocal_unit', 'ReciprocalUnitTest',
        build / name, ' '.join(map(str, (*DEPENDENCIES, rtl))), parameters=parameters,
        compile_args=f'{args.compile_args} {flags}', environment={
            **{f'RECIPROCAL_UNIT_{k}': str(v) for k, v in parameters.items()},
            'RECIPROCAL_UNIT_SEED': str(args.seed + index),
            'RECIPROCAL_UNIT_RANDOM_CYCLES': str(args.random_cycles),
        })
    row = dict(name=name, parameters=parameters, status='FAIL', log=str(log))
    try:
        if result.returncode:
            raise ValueError(f'make exited {result.returncode}')
        passed_test(results, 'ReciprocalUnitTest', 'test_reciprocal_unit')
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
    args = parse_args('reciprocal_unit', __doc__, profiles=[n for n, _ in PROFILES],
                      seed=20261024, rtl_category='building_blocks')
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
        summary['model_dependency_sha256'] = hashlib.sha256((TEST_DIR.parent /
            'polynomial_unit/model.py').read_bytes()).hexdigest()
        summary['artifact_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in TEST_DIR.glob('*.json')}
        with (build / 'python_model_tests.log').open('w') as log:
            result = unittest.TextTestRunner(stream=log).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(ModelTests))
        summary['python_model_checks'] = dict(
            status='PASS' if result.wasSuccessful() else 'FAIL', tests=result.testsRun)
        if not result.wasSuccessful():
            raise ValueError('Python numerical model checks failed')
        expected_quality = characterize(DEFAULTS, exhaustive=True)
        serialized_quality = json.dumps(expected_quality, indent=2) + '\n'
        if (TEST_DIR / 'default_characterization.json').read_text() != serialized_quality:
            raise ValueError('Default characterization differs from the versioned artifact')
        quality_path = build / 'default_characterization.json'
        quality_path.write_text(serialized_quality)
        summary['default_characterization'] = dict(status='PASS', report=str(quality_path))
        require_simulator(args)
        jobs = int(os.getenv('RECIPROCAL_UNIT_JOBS', '4' if args.sim == 'icarus' else '1'))
        if not 1 <= jobs <= 32:
            raise ValueError('RECIPROCAL_UNIT_JOBS must be between 1 and 32')
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
        quality_groups = {}
        for row in summary['profiles']:
            key = json.dumps({k: value for k, value in row['parameters'].items() if k not in (
                'EVALUATION_ARCH', 'ASYNC_RESET', 'SEED_PROTECTION', 'ZERO_RESULT_MODE',
                'CONTEXT_ID_WIDTH', 'REQUEST_TAG_WIDTH')}, sort_keys=True)
            quality_groups.setdefault(key, []).append(row)
        summary['numerical_quality'] = []
        for index, rows in enumerate(quality_groups.values()):
            report = build / f'numerical_quality_{index}.json'
            report.write_text(json.dumps(characterize(rows[0]['parameters']), indent=2) + '\n')
            summary['numerical_quality'].append(dict(profiles=[row['name'] for row in rows],
                status='PASS', report=str(report)))
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'reciprocal_unit', name,
            p, 'reciprocal_unit_parameters_must_be_valid', dependencies=DEPENDENCIES)
            for name, p in INVALID]
        complete = len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES))
        complete &= len(summary['parameter_checks']) == len(INVALID)
        stable = summary['rtl_sha256'] == hashlib.sha256(rtl.read_bytes()).hexdigest() and all(
            summary['dependency_sha256'][str(p.relative_to(ROOT))] ==
            hashlib.sha256(p.read_bytes()).hexdigest() for p in DEPENDENCIES) and (
            summary['verification_sha256'] == verification_hashes(TEST_DIR))
        stable &= summary['model_dependency_sha256'] == hashlib.sha256((TEST_DIR.parent /
            'polynomial_unit/model.py').read_bytes()).hexdigest()
        stable &= summary['artifact_sha256'] == {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in TEST_DIR.glob('*.json')}
        summary['sources_stable'] = stable
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'],
            *summary['architecture_equivalence'], summary['default_characterization']), complete and stable)
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
        print(error, file=sys.stderr)
    finally:
        finish_summary(output, summary, 'Reciprocal unit')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
