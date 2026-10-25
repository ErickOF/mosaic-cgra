"""Python-only banked scratchpad simulation and strict parameter campaign."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import shlex
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lib'))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mosaic_uvm.regression import (campaign_status, finish_summary, parameter_guard,
    parse_args, passed_test, require_simulator, run_simulation, verification_hashes)
from banked_scratchpad.defaults import DEFAULTS
from banked_scratchpad.dependencies import DEPENDENCIES as NAMES
from banked_scratchpad.test_model import ModelTests
ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{n}.sv' for n in NAMES)


def profile(name, **changes):
    return name, DEFAULTS | changes


PROFILES = (
    profile('default'),
    *(profile(f'banks{b}_width{w}', NUM_BANKS=b, DATA_WIDTH=w,
        BANK_DEPTH_WORDS=32, INTERLEAVE_BYTES=w // 8, MAP_MODE=(b + w // 32) % 2)
      for b in (2, 4, 8, 16, 32) for w in (32, 64, 128, 256)),
    *(profile(f'capacity{size}k', BANK_DEPTH_WORDS=size * 1024 // 64)
      for size in (16, 32, 128, 256, 512)),
    *(profile(f'protection{mode}_control{ctrl}', PROTECTION_MODE=mode, CONTROL_PROTECTION=ctrl,
        NUM_BANKS=4, BANK_DEPTH_WORDS=32, NUM_CLIENTS=3, MAX_OUTSTANDING_PER_CLIENT=4)
      for mode, ctrl in ((1, 0), (2, 0), (1, 1), (2, 2))),
    *(profile(f'outstanding{n}', MAX_OUTSTANDING_PER_CLIENT=n, NUM_BANKS=4, BANK_DEPTH_WORDS=32)
      for n in (1, 4, 16)),
    profile('blocked_xor', NUM_BANKS=4, BANK_DEPTH_WORDS=32, INTERLEAVE_BYTES=32, MAP_MODE=1),
    profile('odd_geometry', NUM_BANKS=3, BANK_DEPTH_WORDS=15, NUM_REGIONS=3, NUM_CLIENTS=3),
    profile('one', NUM_BANKS=1, NUM_CLIENTS=1, NUM_REGIONS=1, BANK_DEPTH_WORDS=16,
        MAX_OUTSTANDING_PER_CLIENT=1, BACKEND_READ_LATENCY=3),
    profile('byte_data', DATA_WIDTH=8, INTERLEAVE_BYTES=1, NUM_BANKS=2, BANK_DEPTH_WORDS=16),
    profile('regions_off', ENFORCE_REGIONS=0, BANK_DEPTH_WORDS=32),
    profile('permissions_off', ENFORCE_BANK_PERMISSIONS=0, BANK_DEPTH_WORDS=32),
    profile('double_buffer_off', SUPPORT_DOUBLE_BUFFER=0, BANK_DEPTH_WORDS=32),
    profile('power', SUPPORT_BANK_POWER_GATING=1, BANK_DEPTH_WORDS=32),
    profile('retention', SUPPORT_BANK_POWER_GATING=1, SUPPORT_BANK_RETENTION=1,
        PROTECTION_MODE=2, CONTROL_PROTECTION=1, ASYNC_RESET=1, BANK_DEPTH_WORDS=32),
    profile('generation_wrap', REGION_GENERATION_WIDTH=3, BANK_DEPTH_WORDS=32),
    profile('parity16', PROTECTION_MODE=1, PARITY_GRANULARITY=16, BANK_DEPTH_WORDS=32),
    profile('no_scrub', PROTECTION_MODE=2, SCRUB_ON_CORRECT=0, BANK_DEPTH_WORDS=32),
    profile('latency4', BACKEND_READ_LATENCY=4, ASYNC_RESET=1, BANK_DEPTH_WORDS=32),
)
POSITIVE = ('DATA_WIDTH', 'NUM_BANKS', 'BANK_DEPTH_WORDS', 'NUM_CLIENTS', 'CLIENT_TAG_WIDTH',
    'MAX_OUTSTANDING_PER_CLIENT', 'INTERLEAVE_BYTES', 'BACKEND_READ_LATENCY', 'NUM_REGIONS',
    'OWNER_ID_WIDTH', 'KERNEL_ID_WIDTH', 'REGION_GENERATION_WIDTH', 'BUFFER_GROUP_WIDTH',
    'PARITY_GRANULARITY')
BOOLS = ('ENFORCE_REGIONS', 'ENFORCE_BANK_PERMISSIONS', 'DEFAULT_ALLOW', 'SUPPORT_DOUBLE_BUFFER',
    'SCRUB_ON_CORRECT', 'SUPPORT_BANK_POWER_GATING', 'SUPPORT_BANK_RETENTION', 'ASYNC_RESET')
INVALID = (
    *((f'{k.lower()}_{label}', {k: value}) for k in POSITIVE for label, value in
      (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    *((f'{k.lower()}_{label}', {k: value}) for k in BOOLS for label, value in
      (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    *((f'{k.lower()}_{label}', {k: value}) for k in ('PROTECTION_MODE', 'CONTROL_PROTECTION')
      for label, value in (('three', 3), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    ('map_x', dict(MAP_MODE="32'bx")), ('map_z', dict(MAP_MODE="32'bz")),
    ('map2', dict(MAP_MODE=2)), ('xor_odd', dict(NUM_BANKS=3, MAP_MODE=1)),
    ('width7', dict(DATA_WIDTH=7)), ('width24', dict(DATA_WIDTH=24)),
    ('stripe3', dict(INTERLEAVE_BYTES=3)), ('stripe_small', dict(INTERLEAVE_BYTES=4)),
    ('stripe_nondivisor', dict(INTERLEAVE_BYTES=32, BANK_DEPTH_WORDS=3)),
    ('retention_no_gating', dict(SUPPORT_BANK_RETENTION=1)),
    ('ecc_width', dict(DATA_WIDTH=512, INTERLEAVE_BYTES=64, PROTECTION_MODE=2)),
    ('parity_granule', dict(PROTECTION_MODE=1, PARITY_GRANULARITY=7)),
)


def hashes(rtl):
    return dict(rtl_sha256=hashlib.sha256(rtl.read_bytes()).hexdigest(),
        dependency_sha256={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in DEPENDENCIES}, verification_sha256=verification_hashes(TEST_DIR))


def run_profile(task):
    args, build, rtl, index, name, p = task
    print('Running', name, flush=True)
    prefix = '-Pbanked_scratchpad.' if args.sim == 'icarus' else '-pvalue+banked_scratchpad.'
    flags = ' '.join(shlex.quote(f'{prefix}{k}={v}') for k, v in p.items())
    result, log, results, coverage = run_simulation(args, ROOT, TEST_DIR, 'banked_scratchpad',
        'test_banked_scratchpad', 'BankedScratchpadTest', build / name,
        ' '.join(map(str, (*DEPENDENCIES, rtl))), parameters=p,
        compile_args=f'{args.compile_args} {flags}', environment={
            **{f'BANKED_SCRATCHPAD_{k}': str(v) for k, v in p.items()},
            'BANKED_SCRATCHPAD_SEED': str(args.seed + index),
            'BANKED_SCRATCHPAD_RANDOM_CYCLES': str(args.random_cycles)})
    row = dict(name=name, parameters=p, status='FAIL', log=str(log))
    try:
        if result.returncode:
            raise ValueError(f'make exited {result.returncode}')
        passed_test(results, 'BankedScratchpadTest', 'test_banked_scratchpad')
        data = json.loads(coverage.read_text())
        if (data['status'] != 'PASS' or data['parameters'] != p or not data['goals'] or
            not all(data['goals'].values()) or data['random_transactions'] != args.random_cycles or
            data['seed'] != args.seed + index):
            raise ValueError('Coverage/configuration mismatch')
        row.update(data, name=name, log=str(log), coverage=str(coverage))
    except (OSError, ValueError) as error:
        row['error'] = str(error)
        print('\n'.join(log.read_text().splitlines()[-28:]), flush=True)
    print(name, row['status'], flush=True)
    return row


def main():
    args = parse_args('banked_scratchpad', __doc__, profiles=[n for n, _ in PROFILES],
        rtl_category='mosaic_blocks', seed=20261026)
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, profiles=[],
        parameter_checks=[], validation_mode='Python-only', synthesis='Design Compiler (deferred)')
    try:
        before = hashes(rtl)
        summary.update(before)
        with (build / 'python_model_tests.log').open('w') as log:
            result = unittest.TextTestRunner(stream=log).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(ModelTests))
        summary['python_model_checks'] = dict(status='PASS' if result.wasSuccessful() else 'FAIL',
            tests=result.testsRun)
        if not result.wasSuccessful():
            raise ValueError('Independent Python model tests failed')
        require_simulator(args)
        tasks = [(args, build, rtl, i, name, p) for i, (name, p) in enumerate(PROFILES)
            if not args.case or name in args.case]
        jobs = int(os.getenv('BANKED_SCRATCHPAD_JOBS', '4' if args.sim == 'icarus' else '1'))
        if not 1 <= jobs <= 32:
            raise ValueError('BANKED_SCRATCHPAD_JOBS must be between 1 and 32')
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles'] = list(pool.map(run_profile, tasks))
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'banked_scratchpad',
            name, p, 'banked_scratchpad_parameters_must_be_valid', dependencies=DEPENDENCIES)
            for name, p in INVALID]
        summary['sources_stable'] = before == hashes(rtl)
        complete = len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES))
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'],
            summary['python_model_checks']), complete and summary['sources_stable'])
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
    finally:
        finish_summary(build / 'summary.json', summary, 'Banked scratchpad')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
