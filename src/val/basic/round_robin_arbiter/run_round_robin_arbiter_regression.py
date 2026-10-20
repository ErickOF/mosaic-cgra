"""Run cyclic selection, pending ownership, locks, errors and payload alignment."""

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
DEPENDENCIES = tuple(ROOT/f'src/rtl/common/{name}.sv' for name in ('dff', 'priority_encoder'))
FIXTURE_DEPENDENCIES = tuple(ROOT/f'src/rtl/common/{name}.sv' for name in ('mux', 'operand_isolation')) + (ROOT/'src/rtl/basic/register_slice.sv',)


def geometry(requesters, initial=0, lock=1, asynchronous=0):
    return f'n{requesters}_p{initial}_l{lock}_a{asynchronous}', dict(NUM_REQUESTERS=requesters,
        INITIAL_PRIORITY=initial, HAS_LOCK=lock, ASYNC_RESET=asynchronous)


COUNTS = (1, 2, 3, 4, 5, 8, 16, 31, 32, 33)
PROFILES = tuple(dict(
    [geometry(n, 0, lock, asynchronous) for n, lock, asynchronous in product(COUNTS, (0, 1), (0, 1))]
    + [geometry(n, initial, initial % 2, (initial//2) % 2) for n in COUNTS if n <= 16 for initial in range(1, n)]
    + [geometry(n, initial, lock, asynchronous) for n in (31, 32, 33) for initial in (n//2, n-1)
       for lock, asynchronous in product((0, 1), repeat=2)]).items())
INTEGRATION = tuple(('payload_'+name, parameters) for name, parameters in
    (geometry(n, n-1, 1, asynchronous) for n, asynchronous in product((1, 3, 5), (0, 1))))
CASES = tuple((name, parameters, False) for name, parameters in PROFILES) + tuple((name, parameters, True) for name, parameters in INTEGRATION)
INVALID = (
    *((f'num_requesters_{label}', dict(NUM_REQUESTERS=value)) for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    *((f'initial_{label}', dict(INITIAL_PRIORITY=value)) for label, value in (('negative', -1), ('range', 4), ('x', "32'bx"), ('z', "32'bz"))),
    *((f'{name.lower()}_{label}', {name: value}) for name in ('HAS_LOCK', 'ASYNC_RESET')
      for label, value in (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
)
PROBE_PARAMETERS = geometry(3)[1]
PROBES = (
    *((f'{name}:{state}:0', name, dict(HAS_LOCK=lock, ASYNC_RESET=asynchronous), False)
      for name, state, lock, asynchronous in product(('i_rstb', 'i_flush', 'i_accept'), 'xz', (0, 1), (0, 1))),
    *((f'{name}:{state}:{bit}', name, dict(ASYNC_RESET=asynchronous), False)
      for name, state, bit, asynchronous in product(('i_request', 'i_eligible', 'i_lock'), 'xz', range(3), (0, 1))),
    *((f'i_lock:{state}:{bit}', 'i_lock', dict(HAS_LOCK=0, ASYNC_RESET=asynchronous), False)
      for state, bit, asynchronous in product('xz', range(3), (0, 1))),
    *((f'{prefix}{name}:{state}:0', name, dict(ASYNC_RESET=asynchronous), False)
      for prefix, name, state, asynchronous in product(('pending_', 'owner_'), ('i_request', 'i_eligible', 'i_lock'), 'xz', (0, 1))),
    *((f'{kind}:0:0', 'pending_payload', dict(ASYNC_RESET=asynchronous), True)
      for kind, asynchronous in product(('pending_payload', 'payload_pulse'), (0, 1))),
    *((f'accepted_payload:{state}:0', 'accepted_payload', dict(ASYNC_RESET=asynchronous), True)
      for state, asynchronous in product('xz', (0, 1))),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(args, build, rtl, parameters, seed, probe='', *, fixture=False):
    top = 'round_robin_arbiter_payload_tb' if fixture else 'round_robin_arbiter'
    sources = (*DEPENDENCIES, *FIXTURE_DEPENDENCIES, rtl, TEST_DIR/'round_robin_arbiter_payload_tb.sv') if fixture else (*DEPENDENCIES, rtl)
    prefix = f'-P{top}.' if args.sim == 'icarus' else f'-pvalue+{top}.'
    flags = ' '.join(shlex.quote(f'{prefix}{name}={value}') for name, value in parameters.items())
    return run_simulation(args, ROOT, TEST_DIR, top, 'test_round_robin_arbiter', 'RoundRobinArbiterTest', build,
        ' '.join(map(str, sources)), parameters=parameters, compile_args=f'{args.compile_args} {flags}',
        environment={**{f'ROUND_ROBIN_ARBITER_{name}': str(value) for name, value in parameters.items()},
            'ROUND_ROBIN_ARBITER_SEED': str(seed), 'ROUND_ROBIN_ARBITER_RANDOM_CYCLES': str(args.random_cycles),
            'ROUND_ROBIN_ARBITER_PAYLOAD_FIXTURE': str(int(fixture)), 'ROUND_ROBIN_ARBITER_CHECK_INTERNALS': '1', 'ROUND_ROBIN_ARBITER_ASSERTION_PROBE': probe})


def assertion_probes(args, build, rtl):
    reports = []
    for index, (probe, expected, overrides, fixture) in enumerate(PROBES):
        name = f'{index:03d}_{probe.replace(":", "_").replace(",", "_")}'
        result, log, results, _ = simulate(args, build/'assertion_probes'/name, rtl,
            PROBE_PARAMETERS | overrides, args.seed, probe, fixture=fixture)
        diagnostic = log.read_text(encoding='utf-8')
        try:
            cases = ET.parse(results).findall('.//testcase')
            rejected = (result.returncode != 0 and len(cases) == 1
                and cases[0].get('name') == 'RoundRobinArbiterTest'
                and cases[0].get('classname') == 'test_round_robin_arbiter'
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
    args = parse_args('round_robin_arbiter', __doc__, profiles=[name for name, _, _ in CASES], seed=20261019, rtl_category='basic')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    report_file = build/'summary.json'
    report_file.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, rtl=str(rtl),
        scope='selected_profiles' if args.case else 'representative_requesters_priorities_features_and_payload_integration',
        specification='specs/basic/mosaic-round-robin-arbiter/README.md',
        started_at_utc=datetime.now(timezone.utc).isoformat(), profiles=[], parameter_checks=[], assertion_probes=[],
        external_checks=dict.fromkeys(('hdl_sva', 'formal', 'commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp',
            'technology_synthesis', 'physical_timing', 'physical_power', 'canonical_requester_ownership', 'lock_cancellation_policy'), 'NOT_RUN'))
    try:
        summary['rtl_sha256'] = digest(rtl)
        summary['dependency_sha256'] = {str(path.relative_to(ROOT)): digest(path) for path in DEPENDENCIES}
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        summary['fixture_dependency_sha256'] = {str(path.relative_to(ROOT)): digest(path) for path in FIXTURE_DEPENDENCIES}
        require_simulator(args)
        summary['status'] = 'FAIL'
        for index, (name, parameters, fixture) in enumerate(CASES):
            if args.case and name not in args.case:
                continue
            print(f'Running {name}, seed={args.seed + index}', flush=True)
            result, log, results, coverage_file = simulate(args, build/name, rtl, parameters, args.seed + index, fixture=fixture)
            report = dict(name=name, status='FAIL', parameters=parameters, log=str(log))
            try:
                if result.returncode:
                    raise ValueError(f'make exited with status {result.returncode}')
                passed_test(results, 'RoundRobinArbiterTest', 'test_round_robin_arbiter')
                coverage = json.loads(coverage_file.read_text(encoding='utf-8'))
                if (coverage['status'] != 'PASS' or coverage['parameters'] != parameters or coverage['payload_fixture'] != fixture or not coverage['goals']
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
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'round_robin_arbiter', name, parameters,
            'round_robin_arbiter_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, parameters in INVALID]
        summary['assertion_probes'] = assertion_probes(args, build, rtl)
        complete = (len(summary['profiles']) == (len(set(args.case)) if args.case else len(CASES))
            and len(summary['parameter_checks']) == len(INVALID) and len(summary['assertion_probes']) == len(PROBES))
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'], *summary['assertion_probes']), complete)
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
        print(f'Round-robin arbiter regression could not run: {error}', file=sys.stderr)
    finally:
        finish_summary(report_file, summary, 'Round-robin arbiter')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
