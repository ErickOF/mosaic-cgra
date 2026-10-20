"""Run allocated delay histories, strict parameter guards and live protocol probes."""

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
def geometry(width, capacities, asynchronous):
    total = sum(capacities)
    field_width = max(1, total.bit_length())
    allocation = sum(capacity << (c*field_width) for c, capacity in enumerate(capacities))
    parameters = dict(DATA_WIDTH=width, NUM_CHANNELS=len(capacities), TOTAL_DELAY_ENTRIES=total,
        CHANNEL_CAPACITY=allocation, ASYNC_RESET=asynchronous)
    name = f'w{width}_c' + '-'.join(map(str, capacities)) + f'_a{asynchronous}'
    return name, parameters


SMALL_ALLOCATIONS = (
    *((total,) for total in range(4)),
    *((a, total-a) for total in range(4) for a in range(total+1)),
    *((a, b, 3-a-b) for a in range(4) for b in range(4-a)),
    (0, 0, 0),
)
PROFILES = (
    *(geometry(1, capacities, asynchronous) for capacities in SMALL_ALLOCATIONS for asynchronous in (0, 1)),
    *(geometry(width, capacities, asynchronous) for width in (8, 65)
      for capacities in ((4, 4), (6, 2), (0, 8), (8, 0), (2, 0, 5), (1, 3, 0), (16,)) for asynchronous in (0, 1)),
    *(geometry(32, (4, 4), asynchronous) for asynchronous in (0, 1)),
    *(geometry(3, capacities, asynchronous) for capacities in ((1, 2, 0, 3), (1, 1, 1, 1), (0, 0, 0, 0)) for asynchronous in (0, 1)),
    *(geometry(129, (1, 2), asynchronous) for asynchronous in (0, 1)),
)
INVALID = (
    *((f'{name.lower()}_{label}', {name: value}) for name in ('DATA_WIDTH', 'NUM_CHANNELS')
      for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    *((f'total_{label}', dict(TOTAL_DELAY_ENTRIES=value)) for label, value in (('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    *((f'async_reset_{label}', dict(ASYNC_RESET=value)) for label, value in (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    *((f'allocation_{label}', dict(CHANNEL_CAPACITY=value)) for label, value in (
        ('x', "8'bx"), ('z', "8'bz"), ('short', "7'h44"), ('long', "9'h044"), ('unsized', 68),
        ('sum_small', "8'h43"), ('sum_large', "8'h54"), ('field_out_of_range', "8'h90"))),
    ('zero_budget_nonzero_field', dict(TOTAL_DELAY_ENTRIES=0, CHANNEL_CAPACITY="2'b01")),
    ('nondefault_missing_allocation', dict(NUM_CHANNELS=4, TOTAL_DELAY_ENTRIES=2)),
)
PROBE_PARAMETERS = geometry(3, (2, 1, 0), 0)[1]
PROBES = (
    *((f'{field}:{state}:{bit}', field, {}) for field, positions in (
        ('i_rstb', range(1)), ('i_advance', range(1)), ('i_channel_enable', range(3)),
        ('i_flush', range(3)), ('i_delay', range(6)), ('i_input_valid', range(3)), ('i_input_data', range(9)))
      for state, bit in product('xz', positions)),
    *((f'i_rstb:{state}:0', 'i_rstb', dict(ASYNC_RESET=1)) for state in 'xz'),
    *((f'{kind}:0:0', 'bypass_stability', {}) for kind in ('bypass_data', 'bypass_valid')),
    *((f'delay_boundary:{advance}:{mode}', 'delay_boundary', {}) for advance in (0, 1) for mode in ('enabled', 'disabled')),
    ('unclocked_flush_boundary:0:0', 'delay_boundary', {}),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(args, build, rtl, parameters, seed, probe=''):
    prefix = '-Prdu.' if args.sim == 'icarus' else '-pvalue+rdu.'
    width = parameters['NUM_CHANNELS'] * max(1, parameters['TOTAL_DELAY_ENTRIES'].bit_length())
    literals = parameters | dict(CHANNEL_CAPACITY=f"{width}'h{parameters['CHANNEL_CAPACITY']:x}")
    flags = ' '.join(shlex.quote(f'{prefix}{name}={value}') for name, value in literals.items())
    return run_simulation(args, ROOT, TEST_DIR, 'rdu', 'test_rdu', 'RduTest', build,
        ' '.join(map(str, (*DEPENDENCIES, rtl))), parameters=parameters, compile_args=f'{args.compile_args} {flags}',
        environment={**{f'RDU_{name}': str(value) for name, value in parameters.items()},
            'RDU_SEED': str(seed), 'RDU_RANDOM_CYCLES': str(args.random_cycles),
            'RDU_CHECK_INTERNALS': '1', 'RDU_ASSERTION_PROBE': probe})


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
                and cases[0].get('name') == 'RduTest'
                and cases[0].get('classname') == 'test_rdu'
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
    args = parse_args('rdu', __doc__, profiles=[name for name, _ in PROFILES], seed=20261019, rtl_category='basic')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    report_file = build/'summary.json'
    report_file.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, rtl=str(rtl),
        scope='selected_profiles' if args.case else 'representative_widths_and_static_allocations',
        specification='specs/basic/mosaic-rdu/README.md',
        channel_namespace='generic ordered channel indices; mapper/context encodings are external',
        started_at_utc=datetime.now(timezone.utc).isoformat(), profiles=[], parameter_checks=[], assertion_probes=[],
        external_checks=dict.fromkeys(('hdl_sva', 'formal', 'commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp',
            'technology_synthesis', 'physical_timing', 'physical_power', 'canonical_contracts',
            'mapper_allocation_contract', 'context_activation_safe_points'), 'NOT_RUN'))
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
                passed_test(results, 'RduTest', 'test_rdu')
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
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'rdu', name, parameters,
            'rdu_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, parameters in INVALID]
        summary['assertion_probes'] = assertion_probes(args, build, rtl)
        complete = (len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES))
            and len(summary['parameter_checks']) == len(INVALID) and len(summary['assertion_probes']) == len(PROBES))
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'], *summary['assertion_probes']), complete)
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
        print(f'RDU regression could not run: {error}', file=sys.stderr)
    finally:
        finish_summary(report_file, summary, 'RDU')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
