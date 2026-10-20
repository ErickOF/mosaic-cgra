"""Run multi-port storage, edge-ordering and strict illegal-access campaigns."""

from datetime import datetime, timezone
import hashlib
from itertools import combinations, product
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
DEPENDENCIES = (ROOT/'src/rtl/common/decoder.sv',)


def geometry(width, depth, reads, writes):
    return f'w{width}_d{depth}_r{reads}_w{writes}', dict(DATA_WIDTH=width, DEPTH=depth,
        NUM_READ_PORTS=reads, NUM_WRITE_PORTS=writes)


WIDTHS = (1, 8, 16, 32, 64)
DEPTHS = (1, 2, 3, 4, 5, 16, 31, 32)
PROFILES = tuple(dict(
    [geometry(WIDTHS[(d+r+w) % len(WIDTHS)], depth, reads, writes)
     for d, depth in enumerate(DEPTHS) for r, reads in enumerate((1, 2, 4)) for w, writes in enumerate((1, 2))]
    + [geometry(width, 32, 2, 1) for width in WIDTHS]
    + [geometry(65, 5, 4, 2), geometry(129, 3, 2, 2), geometry(7, 5, 3, 3)]).items())
INVALID = tuple((f'{name.lower()}_{label}', {name: value})
    for name in ('DATA_WIDTH', 'DEPTH', 'NUM_READ_PORTS', 'NUM_WRITE_PORTS')
    for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz")))
PROBE_PARAMETERS = geometry(3, 3, 4, 2)[1]
PROBES = (
    *((f'{name}:{state}:{bit}', expected if divisor is None else f'{expected}:{bit//divisor}', {})
      for name, count, expected, divisor in (
          ('i_read_enable', 4, 'read_enable', None), ('i_write_enable', 2, 'write_enable', None),
          ('i_read_address', 8, 'read_address', 2), ('i_write_address', 4, 'write_address', 2),
          ('i_write_data', 6, 'write_data', 3)) for state, bit in product('xz', range(count))),
    *((f'i_{kind}_address:range:{port},{address}', f'{kind}_address:{port}', dict(DEPTH=depth))
      for depth in (1, 3, 5) for kind, ports in (('read', 4), ('write', 2))
      for port in range(ports) for address in range(depth, 1 << max(1, (depth-1).bit_length()))),
    *((f'write_conflict:{address}:{(1 << a) | (1 << b)}', 'write_conflict', dict(NUM_WRITE_PORTS=3))
      for address in range(3) for a, b in combinations(range(3), 2)),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(args, build, rtl, parameters, seed, probe=''):
    prefix = '-Pregister_file.' if args.sim == 'icarus' else '-pvalue+register_file.'
    flags = ' '.join(shlex.quote(f'{prefix}{name}={value}') for name, value in parameters.items())
    return run_simulation(args, ROOT, TEST_DIR, 'register_file', 'test_register_file', 'RegisterFileTest', build,
        ' '.join(map(str, (*DEPENDENCIES, rtl))), parameters=parameters, compile_args=f'{args.compile_args} {flags}',
        environment={**{f'REGISTER_FILE_{name}': str(value) for name, value in parameters.items()},
            'REGISTER_FILE_SEED': str(seed), 'REGISTER_FILE_RANDOM_CYCLES': str(args.random_cycles),
            'REGISTER_FILE_CHECK_INTERNALS': '1', 'REGISTER_FILE_ASSERTION_PROBE': probe})


def assertion_probes(args, build, rtl):
    reports = []
    for index, (probe, expected, overrides) in enumerate(PROBES):
        name = f'{index:03d}_{probe.replace(":", "_").replace(",", "_")}'
        result, log, results, _ = simulate(args, build/'assertion_probes'/name, rtl,
            PROBE_PARAMETERS | overrides, args.seed, probe)
        diagnostic = log.read_text(encoding='utf-8')
        try:
            cases = ET.parse(results).findall('.//testcase')
            rejected = (result.returncode != 0 and len(cases) == 1
                and cases[0].get('name') == 'RegisterFileTest'
                and cases[0].get('classname') == 'test_register_file'
                and cases[0].find('failure') is not None
                and f'AssertionError: Protocol assertion failed: {expected}' in diagnostic)
        except (OSError, ET.ParseError):
            rejected = False
        report = dict(name=name, expected_assertion=expected, expected_test_failure=rejected, log=str(log),
            status='NOT_RUN' if license_unavailable(diagnostic) else 'PASS' if rejected else 'FAIL')
        reports.append(report)
        print(f"Assertion {name}: {report['status']}", flush=True)
        if not rejected and report['status'] != 'NOT_RUN':
            print('\n'.join(diagnostic.splitlines()[-18:]), flush=True)
    return reports


def main():
    args = parse_args('register_file', __doc__, profiles=[name for name, _ in PROFILES], seed=20261019, rtl_category='basic')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    report_file = build/'summary.json'
    report_file.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, rtl=str(rtl),
        scope='selected_profiles' if args.case else 'representative_widths_depths_and_port_counts',
        specification='specs/basic/mosaic-register-file/README.md',
        started_at_utc=datetime.now(timezone.utc).isoformat(), profiles=[], parameter_checks=[], assertion_probes=[],
        external_checks=dict.fromkeys(('hdl_sva', 'formal', 'commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp',
            'technology_synthesis', 'physical_timing', 'physical_power', 'initialization_policy', 'power_off_state_policy'), 'NOT_RUN'))
    try:
        summary['rtl_sha256'] = digest(rtl)
        summary['dependency_sha256'] = {str(path.relative_to(ROOT)): digest(path) for path in DEPENDENCIES}
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary['status'] = 'FAIL'
        for index, (name, parameters) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            print(f'Running {name}, seed={args.seed + index}', flush=True)
            result, log, results, coverage_file = simulate(args, build/name, rtl, parameters, args.seed + index)
            report = dict(name=name, status='FAIL', parameters=parameters, log=str(log))
            try:
                if result.returncode:
                    raise ValueError(f'make exited with status {result.returncode}')
                passed_test(results, 'RegisterFileTest', 'test_register_file')
                coverage = json.loads(coverage_file.read_text(encoding='utf-8'))
                if (coverage['status'] != 'PASS' or coverage['parameters'] != parameters or not coverage['goals']
                        or not all(coverage['goals'].values()) or coverage['elaboration_assertions'] != 'PASS'
                        or coverage['internal_storage_assertions'] != 'PASS'):
                    raise ValueError('Coverage or elaborated geometry did not match')
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
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'register_file', name, parameters,
            'register_file_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, parameters in INVALID]
        summary['assertion_probes'] = assertion_probes(args, build, rtl)
        complete = (len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES))
            and len(summary['parameter_checks']) == len(INVALID) and len(summary['assertion_probes']) == len(PROBES))
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'], *summary['assertion_probes']), complete)
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
        print(f'Register-file regression could not run: {error}', file=sys.stderr)
    finally:
        finish_summary(report_file, summary, 'Register-file')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
