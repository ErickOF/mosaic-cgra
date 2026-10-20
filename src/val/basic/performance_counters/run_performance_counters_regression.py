"""Run weighted-counter geometries, static variants and live protocol probes."""

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
DEPENDENCIES = tuple(ROOT / f'src/rtl/common/{name}.sv' for name in ('dff', 'operand_isolation'))
DEFAULTS = dict(COUNTER_WIDTH=48, NUM_COUNTERS=10, NUM_EVENTS=16, INCREMENT_WIDTH=16,
    SATURATE=1, HAS_SNAPSHOT=1, HAS_THRESHOLD=1, ASYNC_RESET=0)


def profile(width, counters, events, increment, saturate, snapshot, threshold, asynchronous):
    parameters = dict(zip(DEFAULTS, (width, counters, events, increment, saturate, snapshot, threshold, asynchronous)))
    return (f'w{width}_c{counters}_e{events}_i{increment}_s{saturate}_n{snapshot}_t{threshold}_a{asynchronous}', parameters)


PROFILES = (
    *(profile(*geometry, *flags) for geometry in ((1, 1, 1, 1), (5, 3, 5, 8), (8, 4, 4, 3)) for flags in product((0, 1), repeat=4)),
    *(profile(*geometry, s, 1, 1, a) for geometry in ((16, 10, 16, 16), (32, 5, 10, 40)) for s, a in product((0, 1), repeat=2)),
    *(profile(*geometry, s, 1, 1, 0) for geometry in ((64, 8, 3, 65), (129, 2, 1, 131)) for s in (0, 1)),
    ('default', DEFAULTS),
)
INVALID = (
    *((f'{name.lower()}_{label}', {name: value}) for name in ('COUNTER_WIDTH', 'NUM_COUNTERS', 'NUM_EVENTS', 'INCREMENT_WIDTH')
      for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    *((f'{name.lower()}_{label}', {name: value}) for name in ('SATURATE', 'HAS_SNAPSHOT', 'HAS_THRESHOLD', 'ASYNC_RESET')
      for label, value in (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
)
PROBE_PARAMETERS = dict(COUNTER_WIDTH=5, NUM_COUNTERS=3, NUM_EVENTS=3, INCREMENT_WIDTH=8,
    SATURATE=1, HAS_SNAPSHOT=1, HAS_THRESHOLD=1, ASYNC_RESET=0)
PROBES = (
    *((f'{field}:{state}:{bit}', field if field != 'i_read_index' else 'i_read_index_unknown', {})
      for field, positions in (
          ('i_rstb', range(1)), ('i_global_enable', range(1)), ('i_freeze', range(1)),
          ('i_counter_enable', range(3)), ('i_clear', range(3)), ('i_event_select', range(6)),
          ('i_event_valid', range(1)), ('i_event_increment', range(8)),
          ('i_threshold_enable', range(3)), ('i_threshold_value', range(15)),
          ('i_snapshot', range(1)), ('i_read_enable', range(1)), ('i_read_snapshot', range(1)), ('i_read_index', range(2)))
      for state, bit in product('xz', positions)),
    *((f'{kind}:{freeze}:0', 'configuration_boundary', {}) for kind in ('configuration_boundary', 'threshold_boundary') for freeze in (0, 1)),
    ('i_read_index_range:0:0', 'i_read_index_range', {}),
    *((f'unsupported_snapshot:{field}:0', 'unsupported_snapshot', dict(HAS_SNAPSHOT=0)) for field in ('i_snapshot', 'i_read_snapshot')),
    *((f'unsupported_threshold:{field}:0', 'unsupported_threshold', dict(HAS_THRESHOLD=0)) for field in ('i_threshold_enable', 'i_threshold_value')),
    *((f'i_rstb:{state}:0', 'i_rstb', dict(ASYNC_RESET=1)) for state in 'xz'),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(args, build, rtl, parameters, seed, probe=''):
    prefix = '-Pperformance_counters.' if args.sim == 'icarus' else '-pvalue+performance_counters.'
    flags = ' '.join(shlex.quote(f'{prefix}{name}={value}') for name, value in parameters.items())
    return run_simulation(args, ROOT, TEST_DIR, 'performance_counters', 'test_performance_counters', 'PerformanceCountersTest', build,
        ' '.join(map(str, (*DEPENDENCIES, rtl))), parameters=parameters, compile_args=f'{args.compile_args} {flags}',
        environment={**{f'PERFORMANCE_COUNTERS_{name}': str(value) for name, value in parameters.items()},
            'PERFORMANCE_COUNTERS_SEED': str(seed), 'PERFORMANCE_COUNTERS_RANDOM_CYCLES': str(args.random_cycles),
            'PERFORMANCE_COUNTERS_CHECK_INTERNALS': '1', 'PERFORMANCE_COUNTERS_ASSERTION_PROBE': probe})


def assertion_probes(args, build, rtl):
    reports = []
    for index, (probe, expected, overrides) in enumerate(PROBES):
        name = f'{index:03d}_{probe.replace(":", "_")}'
        result, log, results, _ = simulate(args, build/'assertion_probes'/name, rtl,
            PROBE_PARAMETERS | overrides, args.seed, probe)
        diagnostic = log.read_text(encoding='utf-8')
        try:
            cases = ET.parse(results).findall('.//testcase')
            rejected = (result.returncode != 0 and len(cases) == 1
                and cases[0].get('name') == 'PerformanceCountersTest'
                and cases[0].get('classname') == 'test_performance_counters'
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
    args = parse_args('performance_counters', __doc__, profiles=[name for name, _ in PROFILES], seed=20261013, rtl_category='basic')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    report_file = build/'summary.json'
    report_file.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, rtl=str(rtl),
        scope='selected_profiles' if args.case else 'representative_geometries_and_static_variants',
        specification='specs/basic/mosaic-performance-counters/README.md',
        event_namespace='opaque integration-provided slots; no architectural IDs assigned',
        started_at_utc=datetime.now(timezone.utc).isoformat(), profiles=[], parameter_checks=[], assertion_probes=[],
        external_checks=dict.fromkeys(('hdl_sva', 'formal', 'commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp',
            'technology_synthesis', 'physical_timing', 'physical_power', 'canonical_contracts',
            'tile_event_definitions', 'execution_trace_attribution'), 'NOT_RUN'))
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
                passed_test(results, 'PerformanceCountersTest', 'test_performance_counters')
                coverage = json.loads(coverage_file.read_text(encoding='utf-8'))
                if (coverage['status'] != 'PASS' or coverage['parameters'] != parameters or not coverage['goals']
                        or not all(coverage['goals'].values()) or coverage['elaboration_assertions'] != 'PASS'
                        or coverage['internal_state_and_isolation'] != 'PASS'):
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
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'performance_counters', name, parameters,
            'performance_counters_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, parameters in INVALID]
        summary['assertion_probes'] = assertion_probes(args, build, rtl)
        complete = (len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES))
            and len(summary['parameter_checks']) == len(INVALID) and len(summary['assertion_probes']) == len(PROBES))
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'], *summary['assertion_probes']), complete)
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
        print(f'Performance counters regression could not run: {error}', file=sys.stderr)
    finally:
        finish_summary(report_file, summary, 'Performance counters')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
