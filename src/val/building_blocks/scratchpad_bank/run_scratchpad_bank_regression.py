"""Run the ordered scratchpad-bank PyUVM matrix and strict parameter guards."""
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
from scratchpad_bank.config import DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in (
    'common/ecc_pkg',
    'building_blocks/scratchpad_bank_pkg', 'common/dff', 'common/counter', 'common/decoder',
    'common/operand_isolation', 'common/write_gate', 'basic/parity', 'basic/ecc',
    'basic/sram_wrapper_backend', 'basic/sram_wrapper', 'building_blocks/scratchpad_bank_counters'))
REUSED_PYTHON = tuple(ROOT / 'src/val/basic/ecc' / name for name in ('model.py', 'config.py', 'transaction.py'))
_shared_hashes = verification_hashes


def verification_hashes(test_dir):
    return _shared_hashes(test_dir) | {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in REUSED_PYTHON
    }


def profile(data=128, depth=1024, n=8, mode=0, latency=1, granule=8, scrub=1, reset=0):
    p = DEFAULTS | dict(DATA_WIDTH=data, DEPTH_WORDS=depth, MAX_OUTSTANDING=n,
                        PROTECTION_MODE=mode, BACKEND_READ_LATENCY=latency,
                        PARITY_GRANULARITY=granule, SCRUB_ON_CORRECT=scrub, ASYNC_RESET=reset)
    return f'd{data}_w{depth}_n{n}_p{mode}_l{latency}_g{granule}_s{scrub}_r{reset}', p


PROFILES = tuple(dict(
    [profile(data, depth, n, mode, reset=reset) for data, depth, n, mode, reset in
     product((32, 64, 128), (256, 1024), (1, 3, 4, 8), (0, 1, 2), (0, 1))] +
    [profile(data, 5, 3, 1, latency=2, granule=granule, reset=reset)
     for data in (32, 64, 128) for granule in dict.fromkeys((16, 32, data)) for reset in (0, 1)] +
    [profile(data, 3, 3, 2, latency=2, scrub=0, reset=reset)
     for data, reset in product((32, 64, 128), (0, 1))] +
    [profile(data, depth, n, mode, latency=latency, reset=reset)
     for (data, depth, n, latency), mode, reset in
     product(((8, 1, 1, 1), (16, 3, 2, 2), (256, 5, 3, 3)), (0, 1, 2), (0, 1))]
).items())
POSITIVES = ('DEPTH_WORDS', 'TAG_WIDTH', 'MAX_OUTSTANDING', 'BACKEND_READ_LATENCY')
INVALID = tuple((f'{name.lower()}_{label}', {name: value}) for name in POSITIVES
    for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'data_{label}', dict(DATA_WIDTH=value)) for label, value in
    (('zero', 0), ('negative', -8), ('one', 1), ('nine', 9), ('nonpower', 24), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'{name.lower()}_{label}', {name: value}) for name in ('SCRUB_ON_CORRECT', 'ASYNC_RESET')
    for label, value in (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'protection_{label}', dict(PROTECTION_MODE=value)) for label, value in
    (('reserved', 3), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'granule_{label}', dict(PARITY_GRANULARITY=value)) for label, value in
    (('zero', 0), ('negative', -8), ('one', 1), ('nine', 9), ('nondivisor', 24), ('large', 256), ('x', "32'bx"), ('z', "32'bz"))) + (
    ('insufficient_credits', dict(MAX_OUTSTANDING=1, BACKEND_READ_LATENCY=2)),
    ('storage_overflow', dict(DEPTH_WORDS=1073741824)),
    ('table_overflow', dict(MAX_OUTSTANDING=1073741824)),
    ('ecc_width_limit', dict(DATA_WIDTH=512, PROTECTION_MODE=2)),
)


def simulate(args, build, rtl, parameters, seed, probe=''):
    prefix = '-Pscratchpad_bank.' if args.sim == 'icarus' else '-pvalue+scratchpad_bank.'
    flags = ' '.join(shlex.quote(f'{prefix}{key}={value}') for key, value in parameters.items())
    return run_simulation(args, ROOT, TEST_DIR, 'scratchpad_bank',
        'test_scratchpad_bank', 'ScratchpadBankTest', build, ' '.join(map(str, (*DEPENDENCIES, rtl))),
        parameters=parameters, compile_args=f'{args.compile_args} {flags}', environment={
            **{f'SCRATCHPAD_BANK_{key}': str(value) for key, value in parameters.items()},
            'SCRATCHPAD_BANK_SEED': str(seed), 'SCRATCHPAD_BANK_RANDOM_CYCLES': str(args.random_cycles),
            'SCRATCHPAD_BANK_CHECK_INTERNALS': '1', 'SCRATCHPAD_BANK_INSTRUMENTATION': '1',
            'SCRATCHPAD_BANK_ASSERTION_PROBE': probe})


def run_profile(task):
    args, build, rtl, index, name, parameters = task
    print('Running', name, flush=True)
    result, log, results, coverage = simulate(args, build / name, rtl, parameters, args.seed + index)
    row = dict(name=name, parameters=parameters, status='FAIL', log=str(log))
    try:
        if result.returncode:
            raise ValueError(f'make exited {result.returncode}')
        passed_test(results, 'ScratchpadBankTest', 'test_scratchpad_bank')
        data = json.loads(coverage.read_text())
        if (data['status'] != 'PASS' or data['parameters'] != parameters or not data['goals'] or
            not all(data['goals'].values()) or
            data['internal_storage_assertions'] != 'PASS' or data['backend_checks'] <= 0 or
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


WRITE_PROBES = tuple((byte, state, reg, reset) for byte in (0, 127) for state in 'xz'
               for reg, reset in product((0, 1, 2), (0, 1)))

READ_PROBES = tuple((state, reset) for state in 'xz' for reset in (0, 1))
PROBES = (*WRITE_PROBES, *READ_PROBES)

def assertion_probes(args, build, rtl):
    rows = []
    for byte, state, reg, reset in WRITE_PROBES:
        result, log, results, _ = simulate(
            args, build / 'assertion_probes' / f'byte{byte}_{state}_p{reg}_r{reset}', rtl,
            DEFAULTS | {'ASYNC_RESET': reset, 'PROTECTION_MODE': reg}, args.seed, f'{byte}:{state}')
        diagnostic = log.read_text()
        rejected = result.returncode != 0 and f'SCRATCHPAD_BANK_PROTOCOL: selected write byte {byte // 8}' in diagnostic
        if results.exists():
            try:
                cases = ET.parse(results).findall('.//testcase')
                rejected &= (len(cases) == 1 and cases[0].get('name') == 'ScratchpadBankTest'
                             and cases[0].get('classname') == 'test_scratchpad_bank'
                             and cases[0].find('failure') is not None)
            except ET.ParseError:
                rejected = False
        status = 'NOT_RUN' if license_unavailable(diagnostic) else 'PASS' if rejected else 'FAIL'
        rows.append(dict(byte=byte, state=state, protection=reg, asynchronous_reset=reset, status=status, log=str(log)))
        print('Data assertion', byte, state, reg, reset, status, flush=True)
    for state, reset in READ_PROBES:
        result, log, results, _ = simulate(args, build / 'assertion_probes' / f'read_{state}_r{reset}',
            rtl, DEFAULTS | {'ASYNC_RESET': reset}, args.seed, f'read:{state}')
        diagnostic = log.read_text()
        rejected = result.returncode != 0 and 'SCRATCHPAD_BANK_PROTOCOL: unknown initialized read data' in diagnostic
        try:
            cases = ET.parse(results).findall('.//testcase')
            rejected &= len(cases) == 1 and cases[0].get('name') == 'ScratchpadBankTest' and cases[0].get('classname') == 'test_scratchpad_bank' and cases[0].find('failure') is not None
        except (OSError, ET.ParseError):
            rejected = False
        status = 'NOT_RUN' if license_unavailable(diagnostic) else 'PASS' if rejected else 'FAIL'
        rows.append(dict(kind='initialized_read', state=state, asynchronous_reset=reset, status=status, log=str(log)))
        print('Initialized-read assertion', state, reset, status, flush=True)
    return rows


def main():
    args = parse_args('scratchpad_bank', __doc__, profiles=[name for name, _ in PROFILES],
                      seed=20261023, rtl_category='building_blocks')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    output = build / 'summary.json'
    output.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, profiles=[], parameter_checks=[], assertion_probes=[],
        started_at_utc=datetime.now(timezone.utc).isoformat(), scope='selected_profiles' if args.case else 'representative_scratchpad_bank_profiles',
        synthesis_tool='Design Compiler (deferred)',
        external_checks=dict.fromkeys(('formal', 'commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp',
            'technology_synthesis', 'physical_timing', 'physical_power', 'application_accuracy'), 'NOT_RUN'))
    try:
        summary['rtl_sha256'] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary['dependency_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in DEPENDENCIES}
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        require_simulator(args)
        jobs = int(os.getenv('SCRATCHPAD_BANK_JOBS', '4' if args.sim == 'icarus' else '1'))
        if not 1 <= jobs <= 32:
            raise ValueError('SCRATCHPAD_BANK_JOBS must be between 1 and 32')
        summary['jobs'] = jobs
        tasks = [(args, build, rtl, index, name, parameters)
                 for index, (name, parameters) in enumerate(PROFILES)
                 if not args.case or name in args.case]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles'] = list(pool.map(run_profile, tasks))
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'scratchpad_bank', name, values,
            'scratchpad_bank_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, values in INVALID]
        summary['assertion_probes'] = assertion_probes(args, build, rtl)
        complete = len(summary['assertion_probes']) == len(PROBES) and len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary['parameter_checks']) == len(INVALID)
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'],
                                             *summary['assertion_probes']), complete)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        summary['error'] = str(error)
        print(error, file=sys.stderr)
    finally:
        finish_summary(output, summary, 'Scratchpad-bank')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
