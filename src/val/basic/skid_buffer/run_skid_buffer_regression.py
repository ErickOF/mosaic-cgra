"""Run bypass, late-stall capture, release and producer/control campaigns."""

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
DEPENDENCIES = tuple(ROOT/f'src/rtl/common/{name}.sv' for name in ('dff', 'mux', 'operand_isolation'))


def geometry(width, asynchronous):
    return f'w{width}_a{asynchronous}', dict(DATA_WIDTH=width, ASYNC_RESET=asynchronous)


WIDTHS = (1, 2, 3, 7, 8, 16, 31, 32, 33, 63, 64, 65, 127, 128, 129, 255, 256, 257)
PROFILES = tuple(geometry(width, asynchronous) for width, asynchronous in product(WIDTHS, (0, 1)))
INVALID = (
    *((f'data_width_{label}', dict(DATA_WIDTH=value))
      for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    *((f'async_reset_{label}', dict(ASYNC_RESET=value))
      for label, value in (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
)
PROBE_PARAMETERS = geometry(3, 0)[1]
PROBES = (
    *((f'{name}{suffix}:{state}:0', name, dict(ASYNC_RESET=asynchronous))
      for name, suffix, state, asynchronous in product(('i_rstb', 'i_valid', 'i_ready'), ('', '_empty'), 'xz', (0, 1))),
    *((f'{kind}:{state}:{bit}', 'accepted_data', dict(ASYNC_RESET=asynchronous))
      for kind, state, bit, asynchronous in product(('accepted_capture', 'accepted_bypass'), 'xz', range(3), (0, 1))),
    *((f'{kind}:0:0', 'producer_stability', dict(ASYNC_RESET=asynchronous))
      for kind, asynchronous in product(('producer_data', 'producer_valid', 'producer_pulse'), (0, 1))),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(args, build, rtl, parameters, seed, probe=''):
    prefix = '-Pskid_buffer.' if args.sim == 'icarus' else '-pvalue+skid_buffer.'
    flags = ' '.join(shlex.quote(f'{prefix}{name}={value}') for name, value in parameters.items())
    return run_simulation(args, ROOT, TEST_DIR, 'skid_buffer', 'test_skid_buffer', 'SkidBufferTest', build,
        ' '.join(map(str, (*DEPENDENCIES, rtl))), parameters=parameters, compile_args=f'{args.compile_args} {flags}',
        environment={**{f'SKID_BUFFER_{name}': str(value) for name, value in parameters.items()},
            'SKID_BUFFER_SEED': str(seed), 'SKID_BUFFER_RANDOM_CYCLES': str(args.random_cycles),
            'SKID_BUFFER_CHECK_INTERNALS': '1', 'SKID_BUFFER_ASSERTION_PROBE': probe})


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
                and cases[0].get('name') == 'SkidBufferTest'
                and cases[0].get('classname') == 'test_skid_buffer'
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
    args = parse_args('skid_buffer', __doc__, profiles=[name for name, _ in PROFILES], seed=20261019, rtl_category='basic')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    report_file = build/'summary.json'
    report_file.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, rtl=str(rtl),
        scope='selected_profiles' if args.case else 'representative_widths_and_reset_styles',
        specification='specs/basic/mosaic-skid-buffer/README.md',
        started_at_utc=datetime.now(timezone.utc).isoformat(), profiles=[], parameter_checks=[], assertion_probes=[],
        external_checks=dict.fromkeys(('hdl_sva', 'formal', 'commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp',
            'technology_synthesis', 'physical_timing', 'physical_power', 'forward_chain_timing', 'power_off_state_policy'), 'NOT_RUN'))
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
                passed_test(results, 'SkidBufferTest', 'test_skid_buffer')
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
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'skid_buffer', name, parameters,
            'skid_buffer_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, parameters in INVALID]
        summary['assertion_probes'] = assertion_probes(args, build, rtl)
        complete = (len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES))
            and len(summary['parameter_checks']) == len(INVALID) and len(summary['assertion_probes']) == len(PROBES))
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'], *summary['assertion_probes']), complete)
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
        print(f'Skid-buffer regression could not run: {error}', file=sys.stderr)
    finally:
        finish_summary(report_file, summary, 'Skid-buffer')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
