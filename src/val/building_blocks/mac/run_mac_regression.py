"""Scalar MAC numerical, enabled-edge timing and integration-assertion campaign."""
from datetime import datetime, UTC
import hashlib
from itertools import product
import json
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lib'))
from mosaic_uvm.regression import (campaign_status, finish_summary, license_unavailable,
    parameter_guard, parse_args, passed_test, require_simulator, run_simulation,
    verification_hashes)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from mac.config import DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in
                     ('common/dff', 'common/operand_isolation', 'building_blocks/dot_product'))
HDL_CHECKER = TEST_DIR.parent / 'dot_product/dot_product_assertions.sv'


def profile(operand, width, latency, asynchronous, saturation=1, maximum=4):
    name = f'w{operand}_a{width}_sat{saturation}_l{latency}_r{asynchronous}_m{maximum}'
    return name, dict(OPERAND_WIDTH=operand, ACC_WIDTH=width, SUPPORT_SATURATION=saturation,
                      LATENCY=latency, MAX_LATENCY=maximum, ASYNC_RESET=asynchronous)


PROFILES = tuple(dict(
    [profile(8, 32, latency, reset, sat)
     for latency, reset, sat in product(range(5), (0, 1), (0, 1))] +
    [profile(*geometry, latency, reset) for geometry, latency, reset in product(
        ((16, 32), (16, 64), (32, 64)), (0, 1, 2, 4), (0, 1))] +
    [profile(*geometry, latency, reset) for geometry, latency, reset in product(
        ((1, 2), (2, 4), (3, 9), (5, 13)), (0, 2, 4), (0, 1))] +
    [profile(3, 7, latency, reset, 0)
     for latency, reset in product((0, 1, 2, 4), (0, 1))] +
    [profile(2, 4, latency, reset, maximum=latency)
     for latency, reset in product((1, 6), (0, 1))]
).items())
INVALID = (
    *((f'{name.lower()}_{label}', {name: value}) for name, (label, value) in product(
        ('OPERAND_WIDTH', 'ACC_WIDTH', 'MAX_LATENCY'),
        (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz")))),
    *((f'{name.lower()}_{label}', {name: value}) for name, (label, value) in product(
        ('SUPPORT_SATURATION', 'ASYNC_RESET'),
        (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz")))),
    *((f'latency_{label}', dict(LATENCY=value)) for label, value in
      (('negative', -1), ('above_maximum', 5), ('x', "32'bx"), ('z', "32'bz"))),
    ('insufficient_accumulator', dict(ACC_WIDTH=15)),
    ('width_one_insufficient_accumulator', dict(OPERAND_WIDTH=1, ACC_WIDTH=1)),
    ('custom_maximum', dict(MAX_LATENCY=1, LATENCY=2)),
    ('product_width_overflow', dict(OPERAND_WIDTH=1073741824)),
    ('pipeline_width_overflow', dict(ACC_WIDTH=1073741824)),
)
PROBES = tuple((f'{name}:{state}', name, dict(LATENCY=latency, ASYNC_RESET=reset))
               for latency, reset, name, state in product((0, 2), (0, 1),
                   ('i_rstb', 'i_clock_enable', 'i_valid', 'i_operand_a',
                    'i_operand_b', 'i_accumulator'), 'xz')
               if latency or name not in ('i_rstb', 'i_clock_enable'))


def simulate(args, build, rtl, parameters, seed, probe=''):
    prefix = '-Pmac.' if args.sim == 'icarus' else '-pvalue+mac.'
    flags = ' '.join(shlex.quote(f'{prefix}{name}={value}') for name, value in parameters.items())
    return run_simulation(args, ROOT, TEST_DIR, 'mac', 'test_mac', 'MacTest', build,
        ' '.join(map(str, (*DEPENDENCIES, rtl))), parameters=parameters,
        compile_args=f'{args.compile_args} {flags}', environment={
            **{f'MAC_{name}': str(value) for name, value in parameters.items()},
            'MAC_SEED': str(seed), 'MAC_RANDOM_CYCLES': str(args.random_cycles),
            'MAC_CHECK_INTERNALS': '1', 'MAC_HDL_ASSERTIONS': '1', 'MAC_ASSERTION_PROBE': probe})


def assertion_probes(args, build, rtl):
    reports = []
    for index, (probe, expected, overrides) in enumerate(PROBES):
        name = f'{index:02d}_{probe.replace(":", "_")}'
        result, log, results, _ = simulate(args, build / 'assertion_probes' / name, rtl,
            DEFAULTS | dict(OPERAND_WIDTH=2, ACC_WIDTH=4) | overrides, args.seed, probe)
        diagnostic = log.read_text()
        rejected = result.returncode != 0 and f'Protocol assertion failed: {expected}' in diagnostic
        if results.exists():
            try:
                cases = ET.parse(results).findall('.//testcase')
                rejected &= (len(cases) == 1 and cases[0].find('failure') is not None and
                             cases[0].get('name') == 'MacTest' and
                             cases[0].get('classname') == 'test_mac')
            except ET.ParseError:
                rejected = False
        status = 'NOT_RUN' if license_unavailable(diagnostic) else 'PASS' if rejected else 'FAIL'
        reports.append(dict(name=name, expected_assertion=expected, status=status, log=str(log)))
        print('Assertion', name, status, flush=True)
        if status == 'FAIL':
            print('\n'.join(diagnostic.splitlines()[-20:]), flush=True)
    return reports


def main():
    args = parse_args('mac', __doc__, profiles=[name for name, _ in PROFILES],
                      seed=20261022, rtl_category='building_blocks')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    output = build / 'summary.json'
    output.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, profiles=[],
                   parameter_checks=[], assertion_probes=[],
                   scope='selected_profiles' if args.case else 'representative_mac_profiles',
                   specification='specs/building-blocks/mosaic-mac/README.md',
                   started_at_utc=datetime.now(UTC).isoformat(),
                   external_checks=dict.fromkeys(('formal', 'commercial_lint', 'cdc', 'rdc', 'dft',
                       'vc_lp', 'technology_synthesis', 'sequential_equivalence', 'physical_timing',
                       'physical_power', 'mosaic_contracts'), 'NOT_RUN'))
    try:
        summary['rtl_sha256'] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary['dependency_sha256'] = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (*DEPENDENCIES, HDL_CHECKER)}
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        require_simulator(args)
        for index, (name, parameters) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            print('Running', name, flush=True)
            result, log, results, coverage = simulate(
                args, build / name, rtl, parameters, args.seed + index)
            row = dict(name=name, status='FAIL', parameters=parameters, log=str(log))
            try:
                if result.returncode:
                    raise ValueError(f'make exited {result.returncode}')
                passed_test(results, 'MacTest', 'test_mac')
                data = json.loads(coverage.read_text())
                if (data['status'] != 'PASS' or data['parameters'] != parameters or
                    not data['goals'] or not all(data['goals'].values()) or
                    data['internal_storage_assertions'] != 'PASS' or
                    data['hdl_arithmetic_assertions'] != 'PASS' or
                    data['random_transactions'] != args.random_cycles or
                    data['seed'] != args.seed + index):
                    raise ValueError('Coverage evidence mismatch')
                row.update(data, name=name, log=str(log), coverage=str(coverage))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                row['error'] = str(error)
                if license_unavailable(log.read_text()):
                    row['status'] = 'NOT_RUN'
                print('\n'.join(log.read_text().splitlines()[-22:]), flush=True)
            summary['profiles'].append(row)
            print(name, row['status'], flush=True)
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'mac', name, parameters,
            'mac_parameters_must_be_valid', dependencies=DEPENDENCIES)
            for name, parameters in INVALID]
        summary['assertion_probes'] = assertion_probes(args, build, rtl)
        expected_profiles = len(set(args.case)) if args.case else len(PROFILES)
        complete = (len(summary['profiles']) == expected_profiles and
                    len(summary['parameter_checks']) == len(INVALID) and
                    len(summary['assertion_probes']) == len(PROBES))
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'],
                                             *summary['assertion_probes']), complete)
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
        print(error, file=sys.stderr)
    finally:
        finish_summary(output, summary, 'MAC')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
