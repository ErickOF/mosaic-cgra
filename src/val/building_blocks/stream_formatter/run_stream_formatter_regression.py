"""Run the canonical stream-formatter PyUVM matrix and strict parameter guards."""
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
from stream_formatter.config import DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in (
    'building_blocks/stream_formatter_pkg', 'common/dff', 'common/counter',
    'common/lane_mask', 'common/operand_isolation', 'common/write_gate', 'basic/register_slice'))


def profile(data=128, lanes=4, count=8, registered=1, reset=0, narrow=False):
    p = DEFAULTS | dict(DATA_WIDTH=data, NUM_LANES=lanes, COUNT_WIDTH=count,
                        REGISTER_OUTPUTS=registered, ASYNC_RESET=reset)
    if narrow:
        p.update(DATATYPE_WIDTH=1, CHANNEL_ID_WIDTH=1, CONTEXT_ID_WIDTH=1)
    return f'd{data}_l{lanes}_c{count}_p{registered}_r{reset}_m{int(narrow)}', p


PROFILES = tuple(dict(
    [profile(data, lanes, 8, reg, reset) for (data, lanes), reg, reset in
     product(((32, 1), (64, 2), (64, 4), (128, 4), (128, 8)), (0, 1), (0, 1))] +
    [profile(data, lanes, count, reg, reset, True) for (data, lanes, count), reg, reset in
     product(((8, 1, 1), (24, 3, 3), (48, 3, 4), (16, 2, 2)), (0, 1), (0, 1))] +
    [profile(count=16, registered=reg, reset=reset) for reg, reset in product((0, 1), (0, 1))]
).items())
POSITIVES = ('NUM_LANES', 'COUNT_WIDTH', 'DATATYPE_WIDTH', 'CHANNEL_ID_WIDTH', 'CONTEXT_ID_WIDTH')
INVALID = tuple((f'{name.lower()}_{label}', {name: value}) for name in POSITIVES
    for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'data_{label}', dict(DATA_WIDTH=value)) for label, value in
    (('zero', 0), ('negative', -8), ('one', 1), ('nine', 9), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'{name.lower()}_{label}', {name: value}) for name in ('REGISTER_OUTPUTS', 'ASYNC_RESET')
    for label, value in (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'mode_{label}', dict(MODE_WIDTH=value)) for label, value in
    (('zero', 0), ('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + (
    ('unequal_lanes', dict(NUM_LANES=3)),
    ('nonbyte_lanes', dict(NUM_LANES=8, DATA_WIDTH=32)),
    ('more_lanes_than_bits', dict(NUM_LANES=256)),
    ('derived_width_overflow', dict(COUNT_WIDTH=1073741824)),
)


def simulate(args, build, rtl, parameters, seed, probe=''):
    prefix = '-Pstream_formatter.' if args.sim == 'icarus' else '-pvalue+stream_formatter.'
    flags = ' '.join(shlex.quote(f'{prefix}{key}={value}') for key, value in parameters.items())
    return run_simulation(args, ROOT, TEST_DIR, 'stream_formatter',
        'test_stream_formatter', 'StreamFormatterTest', build, ' '.join(map(str, (*DEPENDENCIES, rtl))),
        parameters=parameters, compile_args=f'{args.compile_args} {flags}', environment={
            **{f'STREAM_FORMATTER_{key}': str(value) for key, value in parameters.items()},
            'STREAM_FORMATTER_SEED': str(seed), 'STREAM_FORMATTER_RANDOM_CYCLES': str(args.random_cycles),
            'STREAM_FORMATTER_CHECK_INTERNALS': '1',
            'STREAM_FORMATTER_ASSERTION_PROBE': probe})


def run_profile(task):
    args, build, rtl, index, name, parameters = task
    print('Running', name, flush=True)
    result, log, results, coverage = simulate(args, build / name, rtl, parameters, args.seed + index)
    row = dict(name=name, parameters=parameters, status='FAIL', log=str(log))
    try:
        if result.returncode:
            raise ValueError(f'make exited {result.returncode}')
        passed_test(results, 'StreamFormatterTest', 'test_stream_formatter')
        data = json.loads(coverage.read_text())
        if (data['status'] != 'PASS' or data['parameters'] != parameters or not data['goals'] or
            not all(data['goals'].values()) or
            data['internal_storage_assertions'] != 'PASS' or data['isolation_checks'] <= 0 or
            data['seed'] != args.seed + index or
            data['random_transactions'] != args.random_cycles):
            raise ValueError('Coverage evidence mismatch')
        accounting = data['accounting']
        if (accounting['accepted'] <= 0 or accounting['outstanding'] != 0 or
            accounting['accepted'] != accounting['emitted'] + accounting['discarded']):
            raise ValueError('Ownership accounting mismatch')
        row.update(data, name=name, log=str(log), coverage=str(coverage))
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        row['error'] = str(error)
        if license_unavailable(log.read_text()):
            row['status'] = 'NOT_RUN'
        print('\n'.join(log.read_text().splitlines()[-22:]), flush=True)
    print(name, row['status'], flush=True)
    return row


PROBES = tuple((byte, state, reg, reset) for byte in (0, 15) for state in 'xz'
               for reg, reset in product((0, 1), (0, 1)))

def assertion_probes(args, build, rtl):
    rows = []
    for byte, state, reg, reset in PROBES:
        result, log, results, _ = simulate(
            args, build / 'assertion_probes' / f'byte{byte}_{state}_p{reg}_r{reset}', rtl,
            DEFAULTS | {'ASYNC_RESET': reset, 'REGISTER_OUTPUTS': reg}, args.seed, f'{byte}:{state}')
        diagnostic = log.read_text()
        rejected = result.returncode != 0 and 'STREAM_FORMATTER_PROTOCOL: unknown selected byte' in diagnostic
        if results.exists():
            try:
                cases = ET.parse(results).findall('.//testcase')
                rejected &= (len(cases) == 1 and cases[0].get('name') == 'StreamFormatterTest'
                             and cases[0].get('classname') == 'test_stream_formatter'
                             and cases[0].find('failure') is not None)
            except ET.ParseError:
                rejected = False
        status = 'NOT_RUN' if license_unavailable(diagnostic) else 'PASS' if rejected else 'FAIL'
        rows.append(dict(byte=byte, state=state, registered=reg, asynchronous_reset=reset, status=status, log=str(log)))
        print('Data assertion', byte, state, reg, reset, status, flush=True)
    return rows


def main():
    args = parse_args('stream_formatter', __doc__, profiles=[name for name, _ in PROFILES],
                      seed=20261022, rtl_category='building_blocks')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    output = build / 'summary.json'
    output.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, profiles=[], parameter_checks=[], assertion_probes=[],
        started_at_utc=datetime.now(timezone.utc).isoformat(), scope='selected_profiles' if args.case else 'representative_stream_formatter_profiles',
        synthesis_tool='Design Compiler (deferred)',
        external_checks=dict.fromkeys(('formal', 'commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp',
            'technology_synthesis', 'physical_timing', 'physical_power', 'application_accuracy'), 'NOT_RUN'))
    try:
        summary['rtl_sha256'] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary['dependency_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in DEPENDENCIES}
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        require_simulator(args)
        jobs = int(os.getenv('STREAM_FORMATTER_JOBS', '4' if args.sim == 'icarus' else '1'))
        if not 1 <= jobs <= 32:
            raise ValueError('STREAM_FORMATTER_JOBS must be between 1 and 32')
        summary['jobs'] = jobs
        tasks = [(args, build, rtl, index, name, parameters)
                 for index, (name, parameters) in enumerate(PROFILES)
                 if not args.case or name in args.case]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles'] = list(pool.map(run_profile, tasks))
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'stream_formatter', name, values,
            'stream_formatter_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, values in INVALID]
        summary['assertion_probes'] = assertion_probes(args, build, rtl)
        complete = len(summary['assertion_probes']) == len(PROBES) and len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary['parameter_checks']) == len(INVALID)
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'],
                                             *summary['assertion_probes']), complete)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        summary['error'] = str(error)
        print(error, file=sys.stderr)
    finally:
        finish_summary(output, summary, 'Stream-formatter')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
