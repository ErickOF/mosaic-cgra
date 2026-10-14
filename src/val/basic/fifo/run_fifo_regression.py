"""Run width/depth/reset/threshold profiles, strict guards and protocol probes."""

from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lib'))
from mosaic_uvm.regression import (
    campaign_status, finish_summary, license_unavailable, parameter_guard, parse_args,
    passed_test, require_simulator, run_simulation, verification_hashes,
)


ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / path for path in ('src/rtl/common/dff.sv', 'src/rtl/common/operand_isolation.sv'))
NAMES = ('DATA_WIDTH', 'DEPTH', 'ASYNC_RESET', 'ALMOST_FULL_LEVEL', 'ALMOST_EMPTY_LEVEL')
PROFILES = tuple((f'w{width}_d{depth}_{style}', width, depth, asynchronous,
                  depth - 1 if depth > 1 else 1, 1 if depth > 1 else 0)
                 for width, depth in product((1, 8, 32, 64, 128, 256), (1, 2, 3, 4, 5, 8, 16, 31))
                 for style, asynchronous in (('sync', 0), ('async', 1)))
PROFILES += tuple((f'threshold_d{depth}_{style}', 32, depth, asynchronous, 1, depth - 1)
                  for depth in (2, 3, 4, 5, 8, 16, 31) for style, asynchronous in (('sync', 0), ('async', 1)))
PROFILES += tuple((f'middle_d{depth}_{style}', 8, depth, asynchronous, depth // 2, depth // 2 - 1)
                  for depth in (8, 31) for style, asynchronous in (('sync', 0), ('async', 1)))
INVALID = (
    *((f'{name.lower()}_{label}', {name: value}) for name in ('DATA_WIDTH', 'DEPTH')
      for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    *((f'async_reset_{label}', {'ASYNC_RESET': value}) for label, value in
      (('two', 2), ('negative', -1), ('oversized', "33'h100000000"), ('x', "32'bx"), ('z', "32'bz"))),
    *((f'{name.lower()}_{label}', {name: value})
      for name, values in (('ALMOST_FULL_LEVEL', (('zero', 0), ('negative', -1), ('above_depth', 5))),
                           ('ALMOST_EMPTY_LEVEL', (('negative', -1), ('equal_depth', 4))))
      for label, value in (*values, ('x', "32'bx"), ('z', "32'bz"))),
)
PROBES = tuple((f'{style}_{field}_{state}', asynchronous, f'{field}:{state}', field)
               for style, asynchronous in (('sync', 0), ('async', 1))
               for field, state in product(('i_rstb', 'i_valid', 'i_ready'), 'xz'))
PROBES += tuple((f'{style}_{field}', asynchronous, f'{field}:1', 'input_stability')
                for style, asynchronous in (('sync', 0), ('async', 1))
                for field in ('producer_data', 'producer_valid'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(args, build, rtl, parameters, seed, *, probe=''):
    prefix = '-Pfifo.' if args.sim == 'icarus' else '-pvalue+fifo.'
    flags = ' '.join(shlex.quote(f'{prefix}{name}={value}') for name, value in parameters.items())
    return run_simulation(args, ROOT, TEST_DIR, 'fifo', 'test_fifo', 'FifoTest', build,
        ' '.join(map(str, (*DEPENDENCIES, rtl))), parameters=parameters, compile_args=f'{args.compile_args} {flags}',
        environment={**{f'FIFO_{name}': str(value) for name, value in parameters.items()},
                     'FIFO_SEED': str(seed), 'FIFO_RANDOM_CYCLES': str(args.random_cycles),
                     'FIFO_CHECK_INTERNALS': '1', 'FIFO_ASSERTION_PROBE': probe})


def assertion_probes(args, build, rtl):
    reports = []
    for name, asynchronous, probe, expected in PROBES:
        parameters = dict(zip(NAMES, (8, 3, asynchronous, 2, 1)))
        result, log, results, _ = simulate(args, build / 'assertion_probes' / name, rtl, parameters, args.seed, probe=probe)
        diagnostic = log.read_text(encoding='utf-8')
        detected = False
        try:
            cases = ET.parse(results).findall('.//testcase')
            detected = (result.returncode != 0 and len(cases) == 1 and cases[0].get('name') == 'FifoTest'
                        and cases[0].get('classname') == 'test_fifo' and cases[0].find('failure') is not None
                        and cases[0].find('skipped') is None
                        and f'AssertionError: Protocol assertion failed: {expected}' in diagnostic)
        except (OSError, ET.ParseError):
            pass
        reports.append(dict(name=name, status='PASS' if detected else 'NOT_RUN' if license_unavailable(diagnostic) else 'FAIL',
                            expected_assertion=expected, expected_test_failure=detected, log=str(log)))
        print(f"Assertion {name}: {reports[-1]['status']}", flush=True)
    return reports


def main():
    args = parse_args('fifo', __doc__, profiles=[profile[0] for profile in PROFILES], seed=20261013, rtl_category='basic')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    report_file = build / 'summary.json'
    report_file.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, rtl=str(rtl),
        scope='selected_profiles' if args.case else 'width_depth_reset_and_threshold_matrix',
        specification='specs/basic/mosaic-fifo/README.md', started_at_utc=datetime.now(timezone.utc).isoformat(),
        profiles=[], parameter_checks=[], assertion_probes=[],
        external_checks=dict.fromkeys(('hdl_sva', 'formal', 'commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp',
            'technology_synthesis', 'physical_timing', 'physical_power', 'reset_release_integration'), 'NOT_RUN'))
    try:
        summary['rtl_sha256'] = digest(rtl)
        summary['dependency_sha256'] = {str(path.relative_to(ROOT)): digest(path) for path in DEPENDENCIES}
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary['status'] = 'FAIL'
        for index, (name, *values) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            parameters = dict(zip(NAMES, values))
            print(f'Running {name}, seed={args.seed + index}', flush=True)
            result, log, results, coverage_file = simulate(args, build / name, rtl, parameters, args.seed + index)
            report = dict(name=name, status='FAIL', parameters=parameters, log=str(log))
            try:
                if result.returncode:
                    raise ValueError(f'make exited with status {result.returncode}')
                passed_test(results, 'FifoTest', 'test_fifo')
                coverage = json.loads(coverage_file.read_text(encoding='utf-8'))
                if (coverage['status'] != 'PASS' or coverage['parameters'] != parameters or not coverage['goals']
                        or not all(coverage['goals'].values()) or coverage['structural_assertions'] != 'PASS'):
                    raise ValueError('Coverage, structural assertions or elaborated parameters did not match')
                if coverage['seed'] != args.seed + index or coverage['random_transactions'] != args.random_cycles:
                    raise ValueError('Campaign random settings did not match')
                report.update(coverage, name=name, log=str(log), coverage=str(coverage_file))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                report['error'] = str(error)
                if license_unavailable(log.read_text(encoding='utf-8')):
                    report['status'] = 'NOT_RUN'
                print('\n'.join(log.read_text().splitlines()[-25:]), flush=True)
            summary['profiles'].append(report)
            print(f"{name}: {report['status']}", flush=True)
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'fifo', name, parameters,
            'fifo_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, parameters in INVALID]
        summary['assertion_probes'] = assertion_probes(args, build, rtl)
        complete = (len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES))
                    and len(summary['parameter_checks']) == len(INVALID) and len(summary['assertion_probes']) == len(PROBES))
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'], *summary['assertion_probes']), complete)
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
        print(f'FIFO regression could not run: {error}', file=sys.stderr)
    finally:
        finish_summary(report_file, summary, 'FIFO')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
