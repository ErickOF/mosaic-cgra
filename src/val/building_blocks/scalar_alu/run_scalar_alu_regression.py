"""Run the scalar ALU width/feature matrix and strict integration assertions."""

from datetime import UTC, datetime
import hashlib
from itertools import product
import json
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'lib'))
from mosaic_uvm.regression import (
    campaign_status,
    finish_summary,
    license_unavailable,
    parameter_guard,
    parse_args,
    passed_test,
    require_simulator,
    run_simulation,
    verification_hashes,
)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scalar_alu.config import DEFAULTS

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
DEPENDENCIES = tuple(
    ROOT / f'src/rtl/{name}.sv'
    for name in ('building_blocks/scalar_alu_pkg', 'common/operand_isolation', 'common/mux')
)
PROFILES = tuple(
    (f'w{w}_s{s}_m{m}', DEFAULTS | dict(DATA_WIDTH=w, SUPPORT_SATURATION=s, SUPPORT_MINMAX=m))
    for w, s, m in product((1, 2, 3, 4, 5, 8, 16, 32, 64), range(2), range(2))
)
INVALID = (
    *(
        (f'width_{label}', dict(DATA_WIDTH=value))
        for label, value in (
            ('zero', 0),
            ('negative', -1),
            ('x', "32'bx"),
            ('z', "32'bz"),
            ('packed_overflow', 536870904),
            ('wide_overflow', "64'd4294967296"),
        )
    ),
    *(
        (f'{name.lower()}_{label}', {name: value})
        for name, (label, value) in product(
            ('SUPPORT_SATURATION', 'SUPPORT_MINMAX'),
            (('two', 2), ('negative', -1), ('x', "32'bx"), ('z', "32'bz")),
        )
    ),
    *(
        (f'opcode_width_{label}', dict(OPCODE_WIDTH=value))
        for label, value in (
            ('zero', 0),
            ('narrow', 4),
            ('wide', 6),
            ('negative', -1),
            ('x', "32'bx"),
            ('z', "32'bz"),
        )
    ),
)
PROBES = tuple(
    (f'{name}:{state}:{op}:{pred}', name)
    for name, op, pred in (
        ('i_operand_a', 0, 0),
        ('i_operand_b', 0, 0),
        ('i_operand_a', 5, 0),
        ('i_operand_a', 16, 0),
        ('i_operand_b', 17, 0),
        ('i_operand_a', 15, 1),
        ('i_operand_b', 15, 0),
        ('i_operand_b', 8, 0),
        ('i_operand_a', 11, 0),
        ('i_operand_b', 18, 0),
    )
    for state in 'xz'
)


def simulate(args, build, rtl, parameters, seed, probe=''):
    prefix = '-Pscalar_alu.' if args.sim == 'icarus' else '-pvalue+scalar_alu.'
    flags = ' '.join(shlex.quote(f'{prefix}{key}={value}') for key, value in parameters.items())
    return run_simulation(
        args,
        ROOT,
        TEST_DIR,
        'scalar_alu',
        'test_scalar_alu',
        'ScalarAluTest',
        build,
        ' '.join(map(str, (*DEPENDENCIES, rtl))),
        parameters=parameters,
        compile_args=f'{args.compile_args} {flags}',
        environment={
            **{f'SCALAR_ALU_{key}': str(value) for key, value in parameters.items()},
            'SCALAR_ALU_SEED': str(seed),
            'SCALAR_ALU_RANDOM_CYCLES': str(args.random_cycles),
            'SCALAR_ALU_CHECK_INTERNALS': '1',
            'SCALAR_ALU_HDL_ASSERTIONS': '1',
            'SCALAR_ALU_ASSERTION_PROBE': probe,
        },
    )


def assertion_probes(args, build, rtl):
    rows = []
    for index, (probe, name) in enumerate(PROBES):
        result, log, results, _ = simulate(
            args,
            build / 'assertion_probes' / f'{index:02d}',
            rtl,
            DEFAULTS | dict(DATA_WIDTH=3),
            args.seed,
            probe,
        )
        rejected = result.returncode != 0 and f'SCALAR_ALU_PROTOCOL: {name}' in log.read_text()
        if results.exists():
            try:
                cases = ET.parse(results).findall('.//testcase')
                rejected &= (
                    len(cases) == 1
                    and cases[0].find('failure') is not None
                    and cases[0].get('name') == 'ScalarAluTest'
                    and cases[0].get('classname') == 'test_scalar_alu'
                )
            except ET.ParseError:
                rejected = False
        status = (
            'NOT_RUN' if license_unavailable(log.read_text()) else 'PASS' if rejected else 'FAIL'
        )
        rows.append(dict(probe=probe, expected_assertion=name, status=status, log=str(log)))
        print('Assertion', probe, status, flush=True)
    return rows


def main():
    args = parse_args(
        'scalar_alu',
        __doc__,
        profiles=[name for name, _ in PROFILES],
        seed=20261022,
        rtl_category='building_blocks',
    )
    build, rtl = args.build_dir.resolve(), args.rtl.resolve()
    build.mkdir(parents=True, exist_ok=True)
    output = build / 'summary.json'
    output.unlink(missing_ok=True)
    summary = dict(
        status='NOT_RUN',
        framework='PyUVM',
        simulator=args.sim,
        profiles=[],
        parameter_checks=[],
        assertion_probes=[],
        started_at_utc=datetime.now(UTC).isoformat(),
        specification='specs/building-blocks/mosaic-scalar-alu/README.md',
        external_checks=dict.fromkeys(
            (
                'formal',
                'commercial_lint',
                'cdc',
                'rdc',
                'dft',
                'vc_lp',
                'technology_synthesis',
                'sequential_equivalence',
                'physical_timing',
                'physical_power',
                'mosaic_contracts',
            ),
            'NOT_RUN',
        ),
    )
    try:
        summary['rtl_sha256'] = hashlib.sha256(rtl.read_bytes()).hexdigest()
        summary['dependency_sha256'] = {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in DEPENDENCIES
        }
        summary['verification_sha256'] = verification_hashes(TEST_DIR)
        require_simulator(args)
        for index, (name, p) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            print('Running', name, flush=True)
            result, log, results, coverage = simulate(args, build / name, rtl, p, args.seed + index)
            row = dict(name=name, parameters=p, status='FAIL', log=str(log))
            try:
                if result.returncode:
                    raise ValueError(f'make exited {result.returncode}')
                passed_test(results, 'ScalarAluTest', 'test_scalar_alu')
                data = json.loads(coverage.read_text())
                if (
                    data['status'] != 'PASS'
                    or data['parameters'] != p
                    or not data['goals']
                    or not all(data['goals'].values())
                    or data['random_transactions'] != args.random_cycles
                    or data['seed'] != args.seed + index
                    or data['native_hdl_assertions'] != 'PASS'
                ):
                    raise ValueError('Coverage evidence mismatch')
                row.update(data, name=name, log=str(log), coverage=str(coverage))
            except (OSError, ValueError, KeyError, ET.ParseError) as error:
                row['error'] = str(error)
                if license_unavailable(log.read_text()):
                    row['status'] = 'NOT_RUN'
                print('\n'.join(log.read_text().splitlines()[-22:]), flush=True)
            summary['profiles'].append(row)
            print(name, row['status'], flush=True)
        summary['parameter_checks'] = [
            parameter_guard(
                args,
                build,
                rtl,
                'scalar_alu',
                name,
                p,
                'scalar_alu_parameters_must_be_valid',
                dependencies=DEPENDENCIES,
            )
            for name, p in INVALID
        ]
        summary['assertion_probes'] = assertion_probes(args, build, rtl)
        complete = (
            len(summary['profiles']) == (len(set(args.case)) if args.case else len(PROFILES))
            and len(summary['parameter_checks']) == len(INVALID)
            and len(summary['assertion_probes']) == len(PROBES)
        )
        summary['status'] = campaign_status(
            (*summary['profiles'], *summary['parameter_checks'], *summary['assertion_probes']),
            complete,
        )
    except (OSError, ValueError) as error:
        summary['error'] = str(error)
        print(error, file=sys.stderr)
    finally:
        finish_summary(output, summary, 'Scalar ALU')
    return 0 if summary['status'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
