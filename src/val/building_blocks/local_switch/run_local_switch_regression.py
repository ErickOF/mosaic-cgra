"""Native static-route and sparse multicast campaigns with strict parameter guards."""
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
from local_switch.config import DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(ROOT / f'src/rtl/{name}.sv' for name in (
    'building_blocks/local_switch_pkg', 'common/dff', 'common/mux',
    'common/operand_isolation', 'basic/register_slice'))


def mask_for(i, o, sparse):
    return sum(1 << (out * i + source) for out in range(o) for source in range(i)
        if not sparse or out == 0 or source == out % i or
           (out % 2 == 0 and source == (out + 1) % i))


def profile(i=4, o=4, d=128, m=32, c=8, mask=None, multicast=1, reset=0):
    if mask is None:
        mask = (1 << (i * o)) - 1
    parameters = DEFAULTS | dict(NUM_INPUTS=i, NUM_OUTPUTS=o, DATA_WIDTH=d,
        METADATA_WIDTH=m, CONTEXT_ID_WIDTH=c, CONNECTIVITY_MASK=mask,
        SUPPORT_MULTICAST=multicast, ASYNC_RESET=reset)
    return f'i{i}_o{o}_d{d}_m{m}_c{c}_edges{mask:x}_mc{multicast}_r{reset}', parameters


PROFILES = tuple(dict(
    [profile(i, o, d, mask=mask_for(i, o, sparse), multicast=mc, reset=r)
        for (i, o), d, sparse, mc, r in product(((1, 1), (2, 3), (4, 4), (4, 8), (8, 8)),
            (32, 64, 128), (False, True), (0, 1), (0, 1))] +
    [profile(i, o, d, m, c, mask, mc, r) for (i, o, d, m, c, mask), mc, r in product(
        ((1, 1, 1, 1, 1, 1), (3, 5, 13, 7, 3, mask_for(3, 5, True)),
         (3, 2, 7, 3, 2, 9)), (0, 1), (0, 1))]
).items())
INVALID = tuple((f'{name.lower()}_{label}', {name: value}) for name in (
    'NUM_INPUTS', 'NUM_OUTPUTS', 'DATA_WIDTH', 'METADATA_WIDTH', 'CONTEXT_ID_WIDTH')
    for label, value in (('zero', 0), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + tuple(
    (f'{name.lower()}_{label}', {name: value}) for name in ('SUPPORT_MULTICAST', 'ASYNC_RESET')
    for label, value in (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz"))) + (
    ('short_mask', dict(CONNECTIVITY_MASK="15'h7fff")),
    ('long_mask', dict(CONNECTIVITY_MASK="17'h1ffff")),
    ('unknown_mask', dict(CONNECTIVITY_MASK="16'hxxxx")),
    ('z_mask', dict(CONNECTIVITY_MASK="16'hzzzz")),
    ('disconnected_output', dict(CONNECTIVITY_MASK="16'hf0ff")),
    ('matrix_overflow', dict(NUM_INPUTS=1073741824)),
    ('input_width_overflow', dict(DATA_WIDTH=1073741824)),
    ('output_width_overflow', dict(NUM_INPUTS=1, NUM_OUTPUTS=4, DATA_WIDTH=1073741824,
                                   CONNECTIVITY_MASK="4'hf")),
)


def main():
    args = parse_args('local_switch', __doc__, profiles=[name for name, _ in PROFILES],
                      seed=20261021, rtl_category='building_blocks')
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    output = build / 'summary.json'
    output.unlink(missing_ok=True)
    summary = dict(status='NOT_RUN', framework='PyUVM', simulator=args.sim, profiles=[], parameter_checks=[],
        started_at_utc=datetime.now(timezone.utc).isoformat(), scope='selected_profiles' if args.case else 'representative_local_switch_profiles',
        external_checks=dict.fromkeys(('formal', 'commercial_lint', 'cdc', 'rdc', 'dft', 'vc_lp',
            'technology_synthesis', 'physical_timing', 'physical_power'), 'NOT_RUN'))
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
            prefix = '-Plocal_switch.' if args.sim == 'icarus' else '-pvalue+local_switch.'
            overrides = parameters | dict(CONNECTIVITY_MASK=f"{parameters['NUM_INPUTS'] * parameters['NUM_OUTPUTS']}'h{parameters['CONNECTIVITY_MASK']:x}")
            flags = ' '.join(shlex.quote(f'{prefix}{key}={value}') for key, value in overrides.items())
            result, log, results, coverage = run_simulation(args, ROOT, TEST_DIR, 'local_switch',
                'test_local_switch', 'LocalSwitchTest', build / name, ' '.join(map(str, (*DEPENDENCIES, rtl))),
                parameters=parameters, compile_args=f'{args.compile_args} {flags}', environment={
                    **{f'LOCAL_SWITCH_{key}': str(value) for key, value in parameters.items()},
                    'LOCAL_SWITCH_SEED': str(args.seed + index), 'LOCAL_SWITCH_RANDOM_CYCLES': str(args.random_cycles),
                    'LOCAL_SWITCH_CHECK_INTERNALS': '1', 'LOCAL_SWITCH_HDL_ASSERTIONS': '1'})
            row = dict(name=name, parameters=parameters, status='FAIL', log=str(log))
            try:
                if result.returncode:
                    raise ValueError(f'make exited {result.returncode}')
                passed_test(results, 'LocalSwitchTest', 'test_local_switch')
                data = json.loads(coverage.read_text())
                if (data['status'] != 'PASS' or data['parameters'] != parameters or not data['goals'] or
                    not all(data['goals'].values()) or data['hdl_assertions'] != 'PASS' or
                    data['internal_storage_assertions'] != 'PASS' or data['seed'] != args.seed + index or
                    data['random_transactions'] != args.random_cycles):
                    raise ValueError('Coverage evidence mismatch')
                accounting = data['accounting']
                for kind, rows in accounting.items():
                    for item in rows:
                        retired = item['completed'] if kind == 'items' else item['delivered']
                        if item['pending'] != 0 or item['accepted'] != retired + item['discarded']:
                            raise ValueError('Copy/item ownership accounting mismatch')
                row.update(data, name=name, log=str(log), coverage=str(coverage))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                row['error'] = str(error)
                if license_unavailable(log.read_text()):
                    row['status'] = 'NOT_RUN'
                print('\n'.join(log.read_text().splitlines()[-22:]), flush=True)
            summary['profiles'].append(row)
            print(name, row['status'], flush=True)
        summary['parameter_checks'] = [parameter_guard(args, build, rtl, 'local_switch', name, values,
            'local_switch_parameters_must_be_valid', dependencies=DEPENDENCIES) for name, values in INVALID]
        complete = len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES)) and len(summary['parameter_checks']) == len(INVALID)
        summary['status'] = campaign_status((*summary['profiles'], *summary['parameter_checks']), complete)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        summary['error'] = str(error)
        print(error, file=sys.stderr)
    finally:
        finish_summary(output, summary, 'Local-switch')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
