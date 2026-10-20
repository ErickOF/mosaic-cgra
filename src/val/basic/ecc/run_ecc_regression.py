"""Run practical SECDED widths, parity boundaries and strict elaboration guards."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'lib'))
from mosaic_uvm.regression import (
    campaign_status, finish_summary, license_unavailable, parameter_guard, parse_args,
    passed_test, require_simulator, run_simulation, verification_hashes,
)


ROOT=Path(__file__).resolve().parents[4]
TEST_DIR=Path(__file__).resolve().parent
DEPENDENCIES=tuple(ROOT/path for path in ('src/rtl/common/decoder.sv','src/rtl/common/operand_isolation.sv'))
PROFILES=tuple((f'width{width}',width) for width in (1,2,4,5,8,11,12,16,26,27,32,57,58,64,120,121,128,247,248,256))
INVALID=tuple((name,dict(DATA_WIDTH=value)) for name,value in (
    ('zero',0),('negative',-1),('above_maximum',257),('oversized',"33'h100000000"),
    ('host_integer_limit',2147483647),('x',"32'bx"),('z',"32'bz")))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(args,build,rtl,width,seed):
    prefix='-Pecc.' if args.sim=='icarus' else '-pvalue+ecc.'
    return run_simulation(args,ROOT,TEST_DIR,'ecc','test_ecc','EccTest',build,
        ' '.join(map(str,(*DEPENDENCIES,rtl))),parameters=dict(DATA_WIDTH=width),
        compile_args=f'{args.compile_args} '+shlex.quote(f'{prefix}DATA_WIDTH={width}'),
        environment=dict(ECC_DATA_WIDTH=str(width),ECC_SEED=str(seed),ECC_RANDOM_CYCLES=str(args.random_cycles),ECC_CHECK_INTERNALS='1'))


def main():
    args=parse_args('ecc',__doc__,profiles=[profile[0] for profile in PROFILES],seed=20261013,rtl_category='basic')
    build,rtl=args.build_dir.resolve(),args.rtl.resolve()
    build.mkdir(parents=True,exist_ok=True)
    report_file=build/'summary.json'
    report_file.unlink(missing_ok=True)
    summary=dict(status='NOT_RUN',framework='PyUVM',simulator=args.sim,rtl=str(rtl),
        scope='selected_profiles' if args.case else 'practical_widths_and_all_parity_boundaries',
        specification='specs/basic/mosaic-ecc/README.md',maximum_data_width=256,
        started_at_utc=datetime.now(timezone.utc).isoformat(),profiles=[],parameter_checks=[],
        external_checks=dict.fromkeys(('hdl_sva','formal','commercial_lint','cdc','rdc','dft','vc_lp','technology_synthesis',
            'physical_timing','physical_power','canonical_contracts','scrub_controller','partial_write_controller'),'NOT_RUN'))
    try:
        summary['rtl_sha256']=digest(rtl)
        summary['dependency_sha256']={str(path.relative_to(ROOT)):digest(path) for path in DEPENDENCIES}
        summary['verification_sha256']=verification_hashes(TEST_DIR)
        require_simulator(args)
        summary['status']='FAIL'
        for index,(name,width) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            print(f'Running {name}, seed={args.seed+index}',flush=True)
            result,log,results,coverage_file=simulate(args,build/name,rtl,width,args.seed+index)
            report=dict(name=name,status='FAIL',parameters=dict(DATA_WIDTH=width),log=str(log))
            try:
                if result.returncode:
                    raise ValueError(f'make exited with status {result.returncode}')
                passed_test(results,'EccTest','test_ecc')
                coverage=json.loads(coverage_file.read_text(encoding='utf-8'))
                if (coverage['status']!='PASS' or coverage['parameters']!=dict(DATA_WIDTH=width) or not coverage['goals']
                        or not all(coverage['goals'].values()) or coverage['structural_assertions']!='PASS'):
                    raise ValueError('Coverage or elaborated geometry did not match')
                if coverage['seed']!=args.seed+index or coverage['random_transactions']!=args.random_cycles:
                    raise ValueError('Random campaign settings did not match')
                report.update(coverage,name=name,log=str(log),coverage=str(coverage_file))
            except (OSError,ValueError,KeyError,ET.ParseError) as error:
                report['error']=str(error)
                if license_unavailable(log.read_text(encoding='utf-8')):
                    report['status']='NOT_RUN'
                print('\n'.join(log.read_text().splitlines()[-25:]),flush=True)
            summary['profiles'].append(report)
            print(f"{name}: {report['status']}",flush=True)
        summary['parameter_checks']=[parameter_guard(args,build,rtl,'ecc',name,parameters,
            'ecc_data_width_must_be_between_1_and_256',dependencies=DEPENDENCIES) for name,parameters in INVALID]
        complete=(len(summary['profiles'])==(len(set(args.case)) if args.case else len(PROFILES))
                  and len(summary['parameter_checks'])==len(INVALID))
        summary['status']=campaign_status((*summary['profiles'],*summary['parameter_checks']),complete)
    except (OSError,ValueError) as error:
        summary['error']=str(error)
        print(f'ECC regression could not run: {error}',file=sys.stderr)
    finally:
        finish_summary(report_file,summary,'ECC')
    return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':
    sys.exit(main())
