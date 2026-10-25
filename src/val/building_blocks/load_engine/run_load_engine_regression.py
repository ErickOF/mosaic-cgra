"""Run the ordered load-engine PyUVM matrix and strict parameter guards."""
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
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lib'))
from mosaic_uvm.regression import (campaign_status, finish_summary, license_unavailable,
    parameter_guard, parse_args, passed_test, require_simulator, run_simulation, verification_hashes)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from load_engine.config import DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in (
    'building_blocks/agu_pkg', 'building_blocks/dma_engine_pkg', 'building_blocks/load_engine_pkg',
    'common/dff', 'common/counter', 'common/operand_isolation', 'common/decoder', 'common/write_gate',
    'building_blocks/dma_engine_bounds', 'building_blocks/agu', 'building_blocks/load_engine_counters'))


def profile(w=32, d=128, count=8, element=16, n=8, reset=0, meta=False):
    parameters = DEFAULTS | dict(ADDR_WIDTH=w, DATA_WIDTH=d, COUNT_WIDTH=count,
        MAX_ELEMENT_BYTES=element, MAX_OUTSTANDING=n, ASYNC_RESET=reset)
    if meta:
        parameters.update(SPACE_ID_WIDTH=1, CHANNEL_ID_WIDTH=1, CONTEXT_ID_WIDTH=2)
    name = f'w{w}_d{d}_c{count}_e{element}_n{n}_r{reset}_m{int(meta)}'
    return name, parameters


PROFILES = tuple(dict(
    [profile(w, d, 8, d // 8, n, reset) for w, d, n, reset in
        product((32, 64), (32, 64, 128), (1, 2, 3, 4, 8, 16), (0, 1))] +
    [profile(w, d, count, element, n, reset, True) for (w, d, count, element, n), reset in
        product(((1, 8, 2, 1, 1), (8, 24, 4, 2, 3), (8, 8, 8, 1, 2)), (0, 1))] +
    [profile(count=16, reset=reset) for reset in (0, 1)]
).items())
POSITIVES = ('ADDR_WIDTH', 'COUNT_WIDTH', 'MAX_OUTSTANDING', 'SPACE_ID_WIDTH',
             'CHANNEL_ID_WIDTH', 'CONTEXT_ID_WIDTH')
INVALID = tuple((f'{name.lower()}_{label}', {name: value}) for name in POSITIVES
    for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'data_{label}', dict(DATA_WIDTH=value)) for label, value in
    (('zero', 0), ('negative', -8), ('one', 1), ('nine', 9), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'element_{label}', dict(MAX_ELEMENT_BYTES=value)) for label, value in
    (('zero', 0), ('negative', -1), ('three', 3), ('too_large', 32), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'reset_{label}', dict(ASYNC_RESET=value)) for label, value in
    (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'mode_{label}', dict(MODE_WIDTH=value)) for label, value in
    (('zero', 0), ('one', 1), ('three', 3), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + (
    ('address_element', dict(ADDR_WIDTH=1)),
    ('storage_overflow', dict(MAX_OUTSTANDING=1073741824)),
)


def run_profile(task):
    args, build, rtl, index, name, parameters = task
    print('Running', name, flush=True)
    prefix = '-Pload_engine.' if args.sim == 'icarus' else '-pvalue+load_engine.'
    flags = ' '.join(shlex.quote(f'{prefix}{key}={value}') for key, value in parameters.items())
    result, log, results, coverage = run_simulation(args, ROOT, TEST_DIR, 'load_engine',
        'test_load_engine', 'LoadEngineTest', build / name, ' '.join(map(str, (*DEPENDENCIES, rtl))),
        parameters=parameters, compile_args=f'{args.compile_args} {flags}', environment={
            **{f'LOAD_ENGINE_{key}': str(value) for key, value in parameters.items()},
            'LOAD_ENGINE_SEED': str(args.seed + index), 'LOAD_ENGINE_RANDOM_CYCLES': str(args.random_cycles),
            'LOAD_ENGINE_CHECK_INTERNALS': '1', 'LOAD_ENGINE_HDL_ASSERTIONS': '1'})
    row = dict(name=name, parameters=parameters, status='FAIL', log=str(log))
    try:
        if result.returncode:
            raise ValueError(f'make exited {result.returncode}')
        passed_test(results, 'LoadEngineTest', 'test_load_engine')
        data = json.loads(coverage.read_text())
        if (data['status'] != 'PASS' or data['parameters'] != parameters or not data['goals'] or
            not all(data['goals'].values()) or data['hdl_assertions'] != 'PASS' or
            data['internal_storage_assertions'] != 'PASS' or data['write_gate_checks'] <= 0 or
            data['seed'] != args.seed + index or
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


def main():
    args = parse_args('load_engine', __doc__, profiles=[name for name, _ in PROFILES],
                      seed=20261021, rtl_category='building_blocks')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    output = build / 'summary.json'
    output.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, profiles=[], parameter_checks=[],
        started_at_utc=datetime.now(timezone.utc).isoformat(), scope='selected_profiles' if args.case else 'representative_load_engine_profiles',
        external_checks=dict.fromkeys(('formal', 'commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp',
            'technology_synthesis', 'physical_timing', 'physical_power', 'application_accuracy'), 'NOT_RUN'))
    try:
        summary['rtl_sha256'] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary['dependency_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in DEPENDENCIES}
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        require_simulator(args)
        jobs = int(os.getenv('LOAD_ENGINE_JOBS', '4' if args.sim == 'icarus' else '1'))
        if not 1 <= jobs <= 32:
            raise ValueError('LOAD_ENGINE_JOBS must be between 1 and 32')
        summary['jobs'] = jobs
        tasks = [(args, build, rtl, index, name, parameters)
                 for index, (name, parameters) in enumerate(PROFILES)
                 if not args.case or name in args.case]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles'] = list(pool.map(run_profile, tasks))
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'load_engine', name, values,
            'load_engine_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, values in INVALID]
        complete = len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary['parameter_checks']) == len(INVALID)
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks']), complete)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        summary['error'] = str(error)
        print(error, file=sys.stderr)
    finally:
        finish_summary(output, summary, 'Load-engine')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
