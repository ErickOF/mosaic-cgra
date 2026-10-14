"""Run data/granule geometries, full fault roles and strict elaboration guards."""

from datetime import datetime, timezone
import hashlib
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
DEPENDENCIES = (ROOT / 'src/rtl/common/operand_isolation.sv',)
PROFILES = tuple((f'w{width}_g{granule}', width, granule)
                 for width in (1, 2, 3, 4, 5, 8, 12, 16, 24, 31, 32, 48, 64, 96, 128, 192, 256)
                 for granule in range(1, width + 1) if width % granule == 0)
INVALID = (
    *((f'{name.lower()}_{label}', {name: value}) for name in ('DATA_WIDTH', 'PARITY_GRANULE_WIDTH')
      for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    ('nondivisible', dict(DATA_WIDTH=32, PARITY_GRANULE_WIDTH=3)),
    ('granule_larger_than_data', dict(DATA_WIDTH=8, PARITY_GRANULE_WIDTH=16)),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(args, build, rtl, parameters, seed):
    prefix = '-Pparity.' if args.sim == 'icarus' else '-pvalue+parity.'
    flags = ' '.join(shlex.quote(f'{prefix}{name}={value}') for name, value in parameters.items())
    return run_simulation(args, ROOT, TEST_DIR, 'parity', 'test_parity', 'ParityTest', build,
        ' '.join(map(str, (*DEPENDENCIES, rtl))), parameters=parameters, compile_args=f'{args.compile_args} {flags}',
        environment=dict(PARITY_DATA_WIDTH=str(parameters['DATA_WIDTH']), PARITY_GRANULE_WIDTH=str(parameters['PARITY_GRANULE_WIDTH']),
                         PARITY_SEED=str(seed), PARITY_RANDOM_CYCLES=str(args.random_cycles), PARITY_CHECK_INTERNALS='1'))


def main():
    args = parse_args('parity', __doc__, profiles=[profile[0] for profile in PROFILES], seed=20261013, rtl_category='basic')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    report_file = build / 'summary.json'
    report_file.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, rtl=str(rtl),
        scope='selected_profiles' if args.case else 'practical_widths_and_all_divisor_granules',
        specification='specs/basic/mosaic-parity/README.md', encoding_scope='specification_even_parity_and_granule_layout',
        started_at_utc=datetime.now(timezone.utc).isoformat(), profiles=[], parameter_checks=[],
        external_checks=dict.fromkeys(('hdl_sva', 'formal', 'commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp',
            'technology_synthesis', 'physical_timing', 'physical_power', 'canonical_contracts',
            'partial_write_controller', 'recovery_controller'), 'NOT_RUN'))
    try:
        summary['rtl_sha256'] = digest(rtl)
        summary['dependency_sha256'] = {str(path.relative_to(ROOT)): digest(path) for path in DEPENDENCIES}
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        require_simulator(args)
        summary['status'] = 'FAIL'
        for index, (name, width, granule) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            parameters = dict(DATA_WIDTH=width, PARITY_GRANULE_WIDTH=granule)
            print(f'Running {name}, seed={args.seed + index}', flush=True)
            result, log, results, coverage_file = simulate(args, build / name, rtl, parameters, args.seed + index)
            report = dict(name=name, status='FAIL', parameters=parameters, log=str(log))
            try:
                if result.returncode:
                    raise ValueError(f'make exited with status {result.returncode}')
                passed_test(results, 'ParityTest', 'test_parity')
                coverage = json.loads(coverage_file.read_text(encoding='utf-8'))
                if (coverage['status'] != 'PASS' or coverage['parameters'] != parameters or not coverage['goals']
                        or not all(coverage['goals'].values()) or coverage['elaboration_assertions'] != 'PASS'):
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
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'parity', name, parameters,
            'parity_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, parameters in INVALID]
        complete = (len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES))
                    and len(summary['parameter_checks']) == len(INVALID))
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks']), complete)
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
        print(f'Parity regression could not run: {error}', file=sys.stderr)
    finally:
        finish_summary(report_file, summary, 'Parity')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
