"""Execute Python-driven controller and released-bank integration campaigns."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
import os
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lib'))
from mosaic_uvm.regression import (campaign_status, finish_summary, license_unavailable,
    parameter_guard, parse_args, passed_test, require_simulator, run_simulation, verification_hashes)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scratchpad_controller.config import DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{n}.sv' for n in (
    'building_blocks/scratchpad_bank_pkg', 'building_blocks/scratchpad_controller_pkg',
    'common/dff', 'common/counter', 'building_blocks/scratchpad_controller_counters',
    'common/priority_encoder', 'common/decoder', 'basic/round_robin_arbiter'))
BANK_SOURCES = tuple(ROOT / f'src/rtl/{n}.sv' for n in (
    'common/ecc_pkg',
    'common/operand_isolation', 'common/write_gate', 'basic/parity', 'basic/ecc',
    'basic/sram_wrapper_backend', 'basic/sram_wrapper', 'building_blocks/scratchpad_bank_counters',
    'building_blocks/scratchpad_bank'))


def profile(b=2, c=2, d=32, n=3, mode=0, stripe=1, depth=4, reset=0, enforce=1, allow=0, tag=8):
    p = DEFAULTS | dict(NUM_BANKS=b, NUM_CLIENTS=c, DATA_WIDTH=d, MAX_OUTSTANDING_PER_CLIENT=n,
        MAP_MODE=mode, INTERLEAVE_BYTES=d // 8 * stripe, BANK_DEPTH_WORDS=depth,
        ASYNC_RESET=reset, ENFORCE_PERMISSIONS=enforce, DEFAULT_ALLOW=allow, CLIENT_TAG_WIDTH=tag)
    return f'b{b}_c{c}_d{d}_n{n}_m{mode}_s{stripe}_w{depth}_r{reset}_e{enforce}_a{allow}_t{tag}', p


PROFILES = tuple(dict([
    profile(b, c, (32, 64, 128)[(bi + ci + mode) % 3], (1, 3, 4, 8)[(bi + ci) % 4],
        mode, (1, 2, 4)[(bi + ci + mode) % 3], reset=(bi + ci + mode) % 2)
    for (bi, b), (ci, c), mode in product(enumerate((2, 4, 8, 16)), enumerate((1, 2, 4, 8)), (0, 1))
] + [profile(b, c, d=32, n=n, stripe=stripe, depth=6, reset=reset)
     for b, c, n, stripe, reset in ((1, 1, 1, 1, 0), (1, 3, 3, 2, 1), (3, 1, 3, 2, 0),
        (3, 3, 3, 1, 1), (5, 2, 4, 2, 0), (3, 2, 2, 1, 0))] +
    [profile(b=1, c=1, d=8, n=1, depth=1), profile(b=3, c=3, d=16, n=3, depth=3),
     profile(enforce=0, allow=0), profile(enforce=0, allow=1, reset=1),
     profile(enforce=1, allow=1), profile(b=4, c=3, n=3, mode=1, tag=1, reset=1)] +
    [('default', DEFAULTS)]).items())
INTEGRATION = tuple((f'integration_p{mode}_r{reset}_m{mapping}',
    profile(b=3 if mapping == 0 else 2, c=3, d=32, n=3, mode=mapping, reset=reset)[1], mode)
    for mode, reset, mapping in product((0, 1, 2), (0, 1), (0, 1)))
POSITIVE = ('NUM_BANKS', 'NUM_CLIENTS', 'BANK_DEPTH_WORDS', 'CLIENT_TAG_WIDTH', 'MAX_OUTSTANDING_PER_CLIENT')
INVALID = tuple((f'{n.lower()}_{label}', {n: value}) for n in POSITIVE for label, value in
    (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'data_{label}', dict(DATA_WIDTH=value)) for label, value in
    (('zero', 0), ('negative', -8), ('one', 1), ('nine', 9), ('nonpower', 24), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'{n.lower()}_{label}', {n: value}) for n in ('ENFORCE_PERMISSIONS', 'DEFAULT_ALLOW', 'ASYNC_RESET', 'MAP_MODE')
    for label, value in (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'stripe_{label}', dict(INTERLEAVE_BYTES=value)) for label, value in
    (('zero', 0), ('negative', -1), ('nonpower', 24), ('small', 8), ('large', 32768), ('x', "32'bx"), ('z', "32'bz"))) + (
    ('xor_nonpower', dict(NUM_BANKS=3, MAP_MODE=1)),
    ('indivisible_stripe', dict(BANK_DEPTH_WORDS=3, INTERLEAVE_BYTES=32)),
    ('capacity_overflow', dict(NUM_BANKS=1073741824)),
    ('slots_overflow', dict(MAX_OUTSTANDING_PER_CLIENT=1073741824)),
    ('tags_overflow', dict(CLIENT_TAG_WIDTH=1073741824)),
    ('crossbar_overflow', dict(NUM_CLIENTS=1073741824)),
)


def simulate(args, build, rtl, parameters, seed, integration=False, protection=0, probe=''):
    top = 'scratchpad_controller_system_tb' if integration else 'scratchpad_controller'
    prefix = f'-P{top}.' if args.sim == 'icarus' else f'-pvalue+{top}.'
    overrides = parameters | (dict(PROTECTION_MODE=protection) if integration else {})
    flags = ' '.join(shlex.quote(f'{prefix}{k}={v}') for k, v in overrides.items())
    sources = (*DEPENDENCIES, rtl, *BANK_SOURCES, TEST_DIR / 'scratchpad_controller_system_tb.sv') if integration else (*DEPENDENCIES, rtl)
    return run_simulation(args, ROOT, TEST_DIR, top, 'test_scratchpad_controller',
        'ScratchpadControllerTest', build, ' '.join(map(str, sources)), parameters=parameters,
        compile_args=f'{args.compile_args} {flags}', environment={
            **{f'SCRATCHPAD_CONTROLLER_{k}': str(v) for k, v in parameters.items()},
            'SCRATCHPAD_CONTROLLER_SEED': str(seed),
            'SCRATCHPAD_CONTROLLER_RANDOM_CYCLES': str(args.random_cycles),
            'SCRATCHPAD_CONTROLLER_INTEGRATION': str(int(integration)),
            'SCRATCHPAD_CONTROLLER_PROTECTION': str(protection), 'SCRATCHPAD_CONTROLLER_PROBE': probe})


def run_profile(task):
    args, build, rtl, index, name, parameters, integration, protection = task
    print('Running', name, flush=True)
    result, log, results, coverage = simulate(args, build / name, rtl, parameters, args.seed + index,
                                             integration, protection)
    row = dict(name=name, parameters=parameters, status='FAIL', log=str(log))
    try:
        if result.returncode:
            raise ValueError(f'make exited {result.returncode}')
        passed_test(results, 'ScratchpadControllerTest', 'test_scratchpad_controller')
        data = json.loads(coverage.read_text())
        if (data['status'] != 'PASS' or data['parameters'] != parameters or not data['goals'] or
                not all(data['goals'].values()) or data['seed'] != args.seed + index or
                data['random_transactions'] != args.random_cycles or data['integration'] != integration or
                data['protection'] != protection):
            raise ValueError('Coverage evidence mismatch')
        a = data['accounting']
        if a['accepted'] <= 0 or a['outstanding'] or a['accepted'] != a['retired'] + a['canceled']:
            raise ValueError('Ownership accounting mismatch')
        row.update(data, name=name, log=str(log), coverage=str(coverage))
    except (OSError, ValueError, KeyError, ET.ParseError) as error:
        row['error'] = str(error)
        if license_unavailable(log.read_text()):
            row['status'] = 'NOT_RUN'
        print('\n'.join(log.read_text().splitlines()[-32:]), flush=True)
    print(name, row['status'], flush=True)
    return row


def main():
    names = [n for n, _ in PROFILES] + [n for n, _, _ in INTEGRATION]
    args = parse_args('scratchpad_controller', __doc__, profiles=names, seed=20261023,
                      rtl_category='building_blocks')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    output = build / 'summary.json'
    output.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, profiles=[],
        parameter_checks=[], assertion_probes=[], started_at_utc=datetime.now(timezone.utc).isoformat(),
        scope='selected_profiles' if args.case else 'scratchpad_controller_profiles',
        synthesis_tool='Design Compiler (deferred)',
        external_checks=dict.fromkeys(('lint', 'formal', 'cdc', 'rdc', 'dft', 'vc_lp',
                                       'synthesis', 'physical_timing', 'physical_power'), 'NOT_RUN'))
    try:
        summary['rtl_sha256'] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary['dependency_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                        for p in (*DEPENDENCIES, *BANK_SOURCES)}
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        reused = [ROOT / 'src/val/building_blocks/scratchpad_bank' / n
                  for n in ('config.py', 'model.py', 'transaction.py')]
        reused += [ROOT / 'src/val/basic/ecc' / n for n in ('config.py', 'model.py', 'transaction.py')]
        summary['verification_sha256'].update({str(p.relative_to(ROOT)):
            hashlib.sha256(p.read_bytes()).hexdigest() for p in reused})
        require_simulator(args)
        jobs = int(os.getenv('SCRATCHPAD_CONTROLLER_JOBS', '4' if args.sim == 'icarus' else '1'))
        if not 1 <= jobs <= 16:
            raise ValueError('SCRATCHPAD_CONTROLLER_JOBS must be between 1 and 16')
        summary['jobs'] = jobs
        cases = [(n, p, False, 0) for n, p in PROFILES] + [(n, p, True, mode) for n, p, mode in INTEGRATION]
        tasks = [(args, build, rtl, index, n, p, integration, mode)
                 for index, (n, p, integration, mode) in enumerate(cases) if not args.case or n in args.case]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles'] = list(pool.map(run_profile, tasks))
        if not args.case:
            summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'scratchpad_controller', n, p,
                'scratchpad_controller_parameters_must_be_valid', dependencies=DEPENDENCIES) for n, p in INVALID]
            for kind, state, reset in product(('write', 'read'), 'xz', (0, 1)):
                probe = f'{kind}_{state}'
                result, log, results, _ = simulate(args, build / 'assertion_probes' / f'{probe}_r{reset}',
                    rtl, profile(reset=reset)[1], args.seed, probe=probe)
                diagnostic = f'SCRATCHPAD_CONTROLLER_PROTOCOL: unknown {"selected write data" if kind == "write" else "successful read data"}'
                status = 'FAIL'
                try:
                    cases = ET.parse(results).findall('.//testcase')
                    if (result.returncode and diagnostic in log.read_text() and len(cases) == 1 and
                        cases[0].get('name') == 'ScratchpadControllerTest' and
                        cases[0].get('classname') == 'test_scratchpad_controller' and cases[0].find('failure') is not None):
                        status = 'PASS'
                except (OSError, ET.ParseError):
                    pass
                summary['assertion_probes'].append(dict(probe=probe, reset=reset, status=status, log=str(log)))
        rows = summary['profiles'] + summary['parameter_checks'] + summary['assertion_probes']
        summary['status'] = campaign_status(rows, bool(summary['profiles']))
    except (OSError, ValueError) as error:
        summary.update(status='FAIL', error=str(error))
    finish_summary(output, summary, 'Scratchpad-controller')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
