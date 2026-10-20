"""Run vector lane/slice storage, broadcast, concurrency and illegal-access campaigns."""

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
DEPENDENCIES = (ROOT/'src/rtl/common/decoder.sv', ROOT/'src/rtl/basic/register_file.sv')


def geometry(width, lanes, slice_width, depth, reads, writes, broadcast):
    return f'l{lanes}_w{width}_s{slice_width}_d{depth}_r{reads}_w{writes}_b{broadcast}', dict(
        LANE_WIDTH=width, NUM_LANES=lanes, WRITE_SLICE_WIDTH=slice_width, DEPTH=depth,
        NUM_READ_PORTS=reads, NUM_WRITE_PORTS=writes, HAS_BROADCAST=broadcast)


def representative_shape(lane_index, width_index, write_index):
    lanes, width, writes = (1, 2, 4, 8)[lane_index], (8, 16, 32)[width_index], (1, 2)[write_index]
    slices = tuple(value for value in (8, 16, 32) if value <= width and width % value == 0)
    slice_width = slices[(lane_index+write_index) % len(slices)]
    offset = lane_index+width_index+write_index
    return width, lanes, slice_width, (1, 3, 5, 16)[offset % 4], (1, 2, 4)[offset % 3], writes


BASE_GEOMETRIES = tuple(representative_shape(lane, width, write)
    for lane, width, write in product(range(4), range(3), range(2)))
PROFILES = tuple(dict(geometry(*shape, broadcast) for shape in
    (*BASE_GEOMETRIES, (32, 4, 8, 16, 2, 1), (1, 1, 1, 1, 1, 1), (12, 3, 3, 3, 3, 3), (8, 2, 8, 31, 4, 2))
    for broadcast in (0, 1)).items())
INVALID = (
    *((f'{name.lower()}_{label}', {name: value})
      for name in ('LANE_WIDTH', 'NUM_LANES', 'WRITE_SLICE_WIDTH', 'DEPTH', 'NUM_READ_PORTS', 'NUM_WRITE_PORTS')
      for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    *((f'has_broadcast_{label}', dict(HAS_BROADCAST=value))
      for label, value in (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))),
    ('nondivisible_lane', dict(LANE_WIDTH=7, WRITE_SLICE_WIDTH=2)),
    ('slice_exceeds_lane', dict(LANE_WIDTH=8, WRITE_SLICE_WIDTH=16)),
    ('nondivisible_slice', dict(LANE_WIDTH=16, WRITE_SLICE_WIDTH=3)),
)
PROBE_PARAMETERS = geometry(4, 2, 2, 3, 2, 2, 1)[1]
PROBES = (
    *((f'{name}:{state}:{bit}', expected if divisor is None else f'{expected}:{bit//divisor}', {})
      for name, count, expected, divisor in (
          ('i_read_enable', 2, 'read_enable', None), ('i_read_lane_enable', 4, 'read_lane_enable', 2),
          ('i_read_address', 4, 'read_address', 2), ('i_write_enable', 2, 'write_enable', None),
          ('i_write_mask', 8, 'write_mask', 4), ('i_write_broadcast', 2, 'write_broadcast', 1),
          ('i_write_address', 4, 'write_address', 2), ('i_write_data', 16, 'write_data', 8))
      for state, bit in product('xz', range(count))),
    *((f'broadcast_data:{state}:{bit}', f'write_data:{bit//4}', {}) for state, bit in product('xz', range(8))),
    *((f'i_{kind}_address:range:{port},{address}', f'{kind}_address:{port}', dict(DEPTH=depth))
      for depth in (1, 3, 5) for kind in ('read', 'write')
      for port in range(2) for address in range(depth, 1 << max(1, (depth-1).bit_length()))),
    *((f'write_conflict:0:{address},{s}', 'write_conflict', {}) for address, s in product(range(3), range(4))),
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(args, build, rtl, parameters, seed, probe=''):
    prefix = '-Pvector_register_file.' if args.sim == 'icarus' else '-pvalue+vector_register_file.'
    flags = ' '.join(shlex.quote(f'{prefix}{name}={value}') for name, value in parameters.items())
    return run_simulation(args, ROOT, TEST_DIR, 'vector_register_file', 'test_vector_register_file', 'VectorRegisterFileTest', build,
        ' '.join(map(str, (*DEPENDENCIES, rtl))), parameters=parameters, compile_args=f'{args.compile_args} {flags}',
        environment={**{f'VECTOR_REGISTER_FILE_{name}': str(value) for name, value in parameters.items()},
            'VECTOR_REGISTER_FILE_SEED': str(seed), 'VECTOR_REGISTER_FILE_RANDOM_CYCLES': str(args.random_cycles),
            'VECTOR_REGISTER_FILE_CHECK_INTERNALS': '1', 'VECTOR_REGISTER_FILE_ASSERTION_PROBE': probe})


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
                and cases[0].get('name') == 'VectorRegisterFileTest'
                and cases[0].get('classname') == 'test_vector_register_file'
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
    args = parse_args('vector_register_file', __doc__, profiles=[name for name, _ in PROFILES], seed=20261020, rtl_category='basic')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    report_file = build/'summary.json'
    report_file.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, rtl=str(rtl),
        scope='selected_profiles' if args.case else 'representative_lanes_widths_slices_depths_ports_and_broadcast',
        specification='specs/basic/mosaic-vector-register-file/README.md',
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
                passed_test(results, 'VectorRegisterFileTest', 'test_vector_register_file')
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
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'vector_register_file', name, parameters,
            'vector_register_file_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, parameters in INVALID]
        summary['assertion_probes'] = assertion_probes(args, build, rtl)
        complete = (len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES))
            and len(summary['parameter_checks']) == len(INVALID) and len(summary['assertion_probes']) == len(PROBES))
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks'], *summary['assertion_probes']), complete)
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
        print(f'Vector-register-file regression could not run: {error}', file=sys.stderr)
    finally:
        finish_summary(report_file, summary, 'Vector-register-file')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
