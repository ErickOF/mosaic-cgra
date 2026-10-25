"""Python-only numerical/elastic campaigns with reproducible generated images."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lib'))
from mosaic_uvm.regression import (campaign_status, finish_summary, license_unavailable,
    parameter_guard, parse_args, passed_test, require_simulator, run_simulation, verification_hashes)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from exp_unit.config import DEFAULTS
from exp_unit.test_model import ModelTests

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in (
    'building_blocks/generated/exp_unit_tables_pkg', 'building_blocks/exp_unit_pkg',
    'building_blocks/scalar_alu_pkg', 'common/mux', 'building_blocks/multiplier',
    'building_blocks/scalar_alu', 'building_blocks/polynomial_unit_round',
    'common/dff', 'common/counter', 'common/operand_isolation', 'common/decoder',
    'basic/fifo', 'basic/parity', 'basic/ecc', 'building_blocks/event_barrier_state',
    'building_blocks/event_barrier_queue', 'building_blocks/exp_unit_interpolate',
    'building_blocks/exp_unit_rom', 'building_blocks/exp_unit_stage'))
GEOMETRIES = (
    (5, 2, 12, 6, 8, 12, 8, 8, 4, 2),
    (8, 4, 24, 12, 16, 16, 12, 8, 4, 3),
    (16, 8, 40, 20, 24, 24, 20, 16, 12, 6),
    (16, 12, 32, 20, 24, 32, 24, 16, 8, 4),
    (32, 16, 64, 28, 32, 48, 40, 32, 16, 8),
    (32, 16, 64, 20, 24, 24, 20, 32, 12, 6),
    (16, 12, 20, 8, 16, 16, 12, 8, 4, 3),
    (8, 4, 40, 28, 16, 16, 12, 8, 4, 3),
)


def profile(geometry=2, protection=0, reset=0, depth=5, queue=2, e=1, exp2=1, interpolation=1):
    parameters = DEFAULTS | dict(zip(tuple(DEFAULTS)[:10], GEOMETRIES[geometry], strict=True))
    parameters.update(TABLE_PROTECTION=protection, ASYNC_RESET=reset, PIPELINE_DEPTH=depth,
                      OUTPUT_QUEUE_DEPTH=queue, SUPPORT_EXP_E=e, SUPPORT_EXP2=exp2,
                      SUPPORT_INTERPOLATION=interpolation)
    if geometry in (0, 1):
        parameters.update(CONTEXT_ID_WIDTH=2, REQUEST_TAG_WIDTH=3)
    name = f'g{geometry}_p{protection}_r{reset}_l{depth}_q{queue}_features{e}{exp2}{interpolation}'
    return name, parameters


PROFILES = tuple(dict(
    [profile(geometry, protection, reset, (5, 6, 8)[geometry % 3], (1, 2, 3)[geometry % 3])
     for geometry, protection, reset in product(range(7), (0, 1, 2), (0, 1))] +
    [profile(1, 2, reset, 5, 1, e, exp2, interpolation)
     for (e, exp2), interpolation, reset in product(((1, 0), (0, 1), (1, 1)), (0, 1), (0, 1))]
    + [profile(), profile(7, 0, 0, 5, 3), profile(7, 2, 1, 8, 1)]
).items())
POSITIVES = tuple(n for n in DEFAULTS if n not in
    ('SUPPORT_EXP_E', 'SUPPORT_EXP2', 'SUPPORT_INTERPOLATION', 'TABLE_PROTECTION', 'ASYNC_RESET'))
INVALID = tuple((f'{name.lower()}_{label}', {name: value}) for name in POSITIVES
    for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'{name.lower()}_{label}', {name: value})
    for name in ('SUPPORT_EXP_E', 'SUPPORT_EXP2', 'SUPPORT_INTERPOLATION', 'ASYNC_RESET')
    for label, value in (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + (
    ('input_fraction', dict(INPUT_FRACTION_WIDTH=16)),
    ('range_fraction', dict(RANGE_FRACTION_WIDTH=40)),
    ('output_fraction', dict(OUTPUT_FRACTION_WIDTH=16)),
    ('internal_headroom', dict(INTERNAL_WIDTH=21)),
    ('table_remainder', dict(TABLE_ADDRESS_WIDTH=8, RANGE_FRACTION_WIDTH=8)),
    ('table_family', dict(TABLE_ADDRESS_WIDTH=9)),
    ('table_precision', dict(INTERNAL_WIDTH=80, INTERNAL_FRACTION_WIDTH=65)),
    ('constant_precision', dict(LOG2E_FRACTION_WIDTH=65)),
    ('ecc_width', dict(INTERNAL_WIDTH=257)),
    ('pipeline_four', dict(PIPELINE_DEPTH=4)),
    ('no_base', dict(SUPPORT_EXP_E=0, SUPPORT_EXP2=0)),
    ('range_overflow', dict(RANGE_WIDTH=28)),
    ('invalid_protection', dict(TABLE_PROTECTION=3)),
    ('unknown_protection', dict(TABLE_PROTECTION="32'bx")),
    ('negative_protection', dict(TABLE_PROTECTION=-1)),
    ('storage_overflow', dict(OUTPUT_QUEUE_DEPTH=1073741824)),
)


def run_profile(task):
    """Keep each simulator, parameter set and evidence directory independent."""
    args, build, rtl, index, name, parameters = task
    print('Running', name, flush=True)
    prefix = '-Pexp_unit.' if args.sim == 'icarus' else '-pvalue+exp_unit.'
    flags = ' '.join(shlex.quote(f'{prefix}{key}={value}') for key, value in parameters.items())
    result, log, results, coverage = run_simulation(args, ROOT, TEST_DIR, 'exp_unit',
        'test_exp_unit', 'ExpUnitTest', build / name, ' '.join(map(str, (*DEPENDENCIES, rtl))),
        parameters=parameters, compile_args=f'{args.compile_args} {flags}', environment={
            **{f'EXP_UNIT_{key}': str(value) for key, value in parameters.items()},
            'EXP_UNIT_SEED': str(args.seed + index), 'EXP_UNIT_RANDOM_CYCLES': str(args.random_cycles),
            'EXP_UNIT_CHECK_INTERNALS': '1', 'EXP_UNIT_HDL_ASSERTIONS': '0'})
    row = dict(name=name, parameters=parameters, status='FAIL', log=str(log))
    try:
        if result.returncode:
            raise ValueError(f'make exited {result.returncode}')
        passed_test(results, 'ExpUnitTest', 'test_exp_unit')
        data = json.loads(coverage.read_text())
        if (data['status'] != 'PASS' or data['parameters'] != parameters or not data['goals'] or
            not all(data['goals'].values()) or data['hdl_assertions'] != 'NOT_RUN' or
            data['internal_storage_assertions'] != 'PASS' or data['seed'] != args.seed + index or
            data['random_transactions'] != args.random_cycles):
            raise ValueError('Coverage evidence mismatch')
        accounting = data['accounting']
        if (accounting['accepted'] <= 0 or accounting['outstanding'] != 0 or
            accounting['accepted'] != accounting['delivered'] + accounting['discarded']):
            raise ValueError('Ownership accounting mismatch')
        row.update(data, name=name, log=str(log), coverage=str(coverage))
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        row['error'] = str(error)
        if license_unavailable(log.read_text()):
            row['status'] = 'NOT_RUN'
        print('\n'.join(log.read_text().splitlines()[-22:]), flush=True)
    print(name, row['status'], flush=True)
    return row


def source_hashes(rtl):
    """Bind results to unchanged RTL, Python checks, tools and numerical artifacts."""
    return dict(rtl_sha256=hashlib.sha256(rtl.read_bytes()).hexdigest(),
        dependency_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                           for p in DEPENDENCIES},
        verification_sha256=verification_hashes(TEST_DIR),
        artifact_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (ROOT / 'tools/generate_exp_unit.py', ROOT / 'requirements.txt',
                      ROOT / 'tools/characterize_exp_unit.py', TEST_DIR / 'accuracy.json',
                      ROOT / 'src/rtl/building_blocks/generated/exp_unit_tables.json')})


def main():
    args = parse_args('exp_unit', __doc__, profiles=[name for name, _ in PROFILES],
                      seed=20261021, rtl_category='building_blocks')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    output = build / 'summary.json'
    output.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, profiles=[], parameter_checks=[],
        validation_mode='Python-only', synthesis='Design Compiler (deferred)',
        started_at_utc=datetime.now(timezone.utc).isoformat(), scope='selected_profiles' if args.case else 'representative_exp_unit_profiles',
        external_checks=dict.fromkeys(('formal', 'commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp',
            'technology_synthesis', 'physical_timing', 'physical_power', 'application_accuracy'), 'NOT_RUN'))
    try:
        initial_hashes = source_hashes(rtl)
        summary.update(initial_hashes)
        with (build / 'python_model_tests.log').open('w') as log:
            checks = unittest.TextTestRunner(stream=log).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(ModelTests))
        summary['python_model_checks'] = dict(
            status='PASS' if checks.wasSuccessful() else 'FAIL', tests=checks.testsRun)
        if not checks.wasSuccessful():
            raise ValueError('Python numerical model checks failed')
        subprocess.run([sys.executable, str(ROOT / 'tools/generate_exp_unit.py'), '--check'], check=True)
        summary['generated_artifacts'] = 'PASS'
        accuracy = build / 'accuracy.json'
        subprocess.run([sys.executable, str(ROOT / 'tools/characterize_exp_unit.py'),
                        '--output', str(accuracy)], check=True)
        if accuracy.read_bytes() != (TEST_DIR / 'accuracy.json').read_bytes():
            raise ValueError('Scalar accuracy differs from the versioned artifact')
        summary['scalar_accuracy'] = dict(status='PASS', report=str(accuracy))
        require_simulator(args)
        jobs = int(os.getenv('EXP_UNIT_JOBS', '4' if args.sim == 'icarus' else '1'))
        if not 1 <= jobs <= 32:
            raise ValueError('EXP_UNIT_JOBS must be between 1 and 32')
        summary['jobs'] = jobs
        tasks = [(args, build, rtl, index, name, parameters)
                 for index, (name, parameters) in enumerate(PROFILES)
                 if not args.case or name in args.case]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles'] = list(pool.map(run_profile, tasks))
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'exp_unit', name, values,
            'exp_unit_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, values in INVALID]
        complete = len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary['parameter_checks']) == len(INVALID)
        summary['sources_stable'] = source_hashes(rtl) == initial_hashes
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'],
            summary['python_model_checks'], summary['scalar_accuracy']),
            complete and summary['sources_stable'])
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        summary['error'] = str(error)
        print(error, file=sys.stderr)
    finally:
        finish_summary(output, summary, 'Exp-unit')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
