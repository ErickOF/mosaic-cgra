"""Native programmable-table, interpolation, lifecycle and protection campaigns."""
from datetime import datetime, timezone
import hashlib
from itertools import product
import json
from pathlib import Path
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lib'))
from mosaic_uvm.regression import (campaign_status, finish_summary, license_unavailable,
    parameter_guard, parse_args, passed_test, require_simulator, run_simulation, verification_hashes)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lut_unit.config import DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in (
    'building_blocks/lut_unit_pkg', 'common/dff', 'common/decoder',
    'common/operand_isolation', 'basic/fifo', 'basic/parity', 'basic/ecc',
    'building_blocks/event_barrier_state', 'building_blocks/event_barrier_queue',
    'building_blocks/lut_unit_bank'))


def profile(a, w, f, banks, protection, reset, interpolation=1, coverage=1, pipeline=2, lq=2, pq=2):
    parameters = DEFAULTS | dict(ADDRESS_WIDTH=a, OUTPUT_WIDTH=w, INDEX_FRACTION_WIDTH=f,
        NUM_BANKS=banks, BUFFER_PROTECTION=protection, ASYNC_RESET=reset,
        SUPPORT_INTERPOLATION=interpolation, TRACK_PROGRAM_COVERAGE=coverage,
        LOOKUP_PIPELINE_DEPTH=pipeline, LOOKUP_RESPONSE_DEPTH=lq, PROGRAM_RESPONSE_DEPTH=pq,
        TABLE_VERSION_WIDTH=2, TABLE_ID_WIDTH=5, QUALITY_ID_WIDTH=2, CONTEXT_ID_WIDTH=3, LOOKUP_TAG_WIDTH=4)
    return f'a{a}_w{w}_f{f}_b{banks}_p{protection}_r{reset}_i{interpolation}_c{coverage}_s{pipeline}_lq{lq}_pq{pq}', parameters


PROFILES = tuple(dict([('default', DEFAULTS)] +
    [profile(a, w, f, b, p, r) for (a, w, f, b), p, r in product(
        ((4, 8, 4, 1), (6, 16, 8, 2), (8, 32, 12, 4), (10, 16, 8, 8)), range(3), range(2))] +
    [profile(2, 8, 3, 3, p, r, i, c, 3, 3, 5) for p, r, i, c in product(range(3), range(2), range(2), range(2))] +
    [profile(1, 257, 3, 1, 2, r, 1, 1, 1, 1, 1) for r in range(2)]).items())
BOOLEANS = ('SUPPORT_INTERPOLATION', 'TRACK_PROGRAM_COVERAGE', 'ASYNC_RESET')
INVALID = tuple((f'{name.lower()}_{label}', {name: value}) for name in DEFAULTS
    if name not in (*BOOLEANS, 'BUFFER_PROTECTION')
    for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'{name.lower()}_{label}', {name: value}) for name in BOOLEANS
    for label, value in (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + (
    ('version_one', dict(TABLE_VERSION_WIDTH=1)),
    ('protection_three', dict(BUFFER_PROTECTION=3)),
    ('protection_negative', dict(BUFFER_PROTECTION=-1)),
    ('protection_x', dict(BUFFER_PROTECTION="32'bx")),
    ('protection_z', dict(BUFFER_PROTECTION="32'bz")),
    ('address_overflow', dict(ADDRESS_WIDTH=32)),
    ('packed_overflow', dict(OUTPUT_WIDTH=1073741824)),
    ('bank_overflow', dict(NUM_BANKS=1073741824)),
)


def main():
    args = parse_args('lut_unit', __doc__, profiles=[n for n, _ in PROFILES],
                      seed=20261022, rtl_category='building_blocks')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    output = build / 'summary.json'
    output.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, profiles=[],
        parameter_checks=[], started_at_utc=datetime.now(timezone.utc).isoformat(),
        scope='selected_profiles' if args.case else 'representative_lut_unit_profiles')
    try:
        summary['rtl_sha256'] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary['dependency_sha256'] = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                                       for p in DEPENDENCIES}
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        require_simulator(args)
        for index, (name, parameters) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            print('Running', name, flush=True)
            prefix = '-Plut_unit.' if args.sim == 'icarus' else '-pvalue+lut_unit.'
            flags = ' '.join(shlex.quote(f'{prefix}{key}={value}') for key, value in parameters.items())
            result, log, results, coverage = run_simulation(args, ROOT, TEST_DIR, 'lut_unit',
                'test_lut_unit', 'LutUnitTest', build / name,
                ' '.join(map(str, (*DEPENDENCIES, rtl))), parameters=parameters,
                compile_args=f'{args.compile_args} {flags}', environment={
                    **{f'LUT_UNIT_{key}': str(value) for key, value in parameters.items()},
                    'LUT_UNIT_SEED': str(args.seed + index),
                    'LUT_UNIT_RANDOM_CYCLES': str(args.random_cycles),
                    'LUT_UNIT_CHECK_INTERNALS': '1', 'LUT_UNIT_HDL_ASSERTIONS': '1'})
            row = dict(name=name, parameters=parameters, status='FAIL', log=str(log))
            try:
                if result.returncode:
                    raise ValueError(f'make exited {result.returncode}')
                passed_test(results, 'LutUnitTest', 'test_lut_unit')
                data = json.loads(coverage.read_text())
                if (data['status'] != 'PASS' or data['parameters'] != parameters or
                    not data['goals'] or not all(data['goals'].values()) or
                    data['hdl_assertions'] != 'PASS' or
                    data['seed'] != args.seed + index or data['random_transactions'] != args.random_cycles):
                    raise ValueError('Coverage evidence mismatch')
                row.update(data, name=name, log=str(log), coverage=str(coverage))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                row['error'] = str(error)
                if license_unavailable(log.read_text()):
                    row['status'] = 'NOT_RUN'
                print('\n'.join(log.read_text().splitlines()[-25:]), flush=True)
            summary['profiles'].append(row)
            print(name, row['status'], flush=True)
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'lut_unit', name, values,
            'lut_unit_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, values in INVALID]
        complete = len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary['parameter_checks']) == len(INVALID)
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks']), complete)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        summary['error'] = str(error)
        print(error, file=sys.stderr)
    finally:
        finish_summary(output, summary, 'LUT-unit')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
