"""Run width/direction/timing profiles, strict guards and live protocol probes."""

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
DEPENDENCIES = tuple(ROOT / path for path in ('src/rtl/common/dff.sv', 'src/rtl/common/operand_isolation.sv'))
NAMES = ('DATA_WIDTH', 'USER_WIDTH', 'SUPPORT_SHIFT_LOW', 'SUPPORT_SHIFT_HIGH', 'REGISTER_OUTPUTS', 'ASYNC_RESET')
PROFILES = tuple((f'{name}_{direction}_{timing}', width, user, low, high, registered, asynchronous)
    for name, width, user in (('byte', 8, 1), ('three_byte', 24, 7), ('word', 32, 3),
                              ('wide', 64, 17), ('nominal', 128, 1), ('stress', 512, 32))
    for direction, low, high in (('both',1,1), ('low',1,0), ('high',0,1))
    for timing, registered, asynchronous in (('comb',0,0), ('sync',1,0), ('async',1,1)))
PROFILES += tuple((f'nominal_{direction}_comb_async_flag',128,1,low,high,0,1)
                  for direction,low,high in (('both',1,1),('low',1,0),('high',0,1)))
INVALID = (
    *((f'{name.lower()}_{value}',{name:value}) for name,values in (
        ('DATA_WIDTH',(0,-1,1,7,9,15)),('USER_WIDTH',(0,-1))) for value in values),
    *((f'{name.lower()}_{state}',{name:f"32'b{state}"}) for name,state in product(NAMES[:2], 'xz')),
    *((f'{name.lower()}_{label}',{name:value}) for name in NAMES[2:] for label,value in (
        ('two',2),('negative',-1),('oversized',"33'h100000000"),('x',"32'bx"),('z',"32'bz"))),
    ('no_direction',{'SUPPORT_SHIFT_LOW':0,'SUPPORT_SHIFT_HIGH':0}),
)
PROBES = tuple((f'{timing}_{field}_{state}',registered,asynchronous,f'{field}:{state}',field)
    for timing,registered,asynchronous in (('comb',0,0),('sync',1,0),('async',1,1))
    for field in ('i_rstb','i_flush','i_valid','i_ready','i_offset','i_shift_high','i_strb_lo','i_strb_hi',
                  'i_last','i_user','i_data_lo','i_data_hi') for state in 'xz')
PROBES += tuple((f'{timing}_producer_changes',registered,0,'input_stability:1','input_stability')
                for timing,registered in (('comb',0),('sync',1)))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def simulate(args, build, rtl, parameters, seed, *, probe=''):
    prefix = '-Pdata_aligner.' if args.sim == 'icarus' else '-pvalue+data_aligner.'
    flags = ' '.join(shlex.quote(f'{prefix}{name}={value}') for name,value in parameters.items())
    return run_simulation(args,ROOT,TEST_DIR,'data_aligner','test_data_aligner','DataAlignerTest',build,
        ' '.join(map(str,(*DEPENDENCIES,rtl))),parameters=parameters,compile_args=f'{args.compile_args} {flags}',
        environment={**{f'DATA_ALIGNER_{name}':str(value) for name,value in parameters.items()},
                     'DATA_ALIGNER_SEED':str(seed),'DATA_ALIGNER_RANDOM_CYCLES':str(args.random_cycles),
                     'DATA_ALIGNER_CHECK_INTERNALS':'1','DATA_ALIGNER_ASSERTION_PROBE':probe})


def assertion_probes(args, build, rtl):
    reports=[]
    for name,registered,asynchronous,probe,expected in PROBES:
        parameters=dict(zip(NAMES,(24,3,1,1,registered,asynchronous)))
        result,log,results,_=simulate(args,build/'assertion_probes'/name,rtl,parameters,args.seed,probe=probe)
        diagnostic=log.read_text(encoding='utf-8')
        detected=False
        try:
            cases=ET.parse(results).findall('.//testcase')
            detected=(result.returncode != 0 and len(cases)==1 and cases[0].get('name')=='DataAlignerTest'
                      and cases[0].get('classname')=='test_data_aligner' and cases[0].find('failure') is not None
                      and cases[0].find('skipped') is None and f'AssertionError: Protocol assertion failed: {expected}' in diagnostic)
        except (OSError,ET.ParseError):
            pass
        reports.append(dict(name=name,status='PASS' if detected else 'NOT_RUN' if license_unavailable(diagnostic) else 'FAIL',
                            expected_assertion=expected,expected_test_failure=detected,log=str(log)))
        print(f"Assertion {name}: {reports[-1]['status']}",flush=True)
    return reports


def main():
    args=parse_args('data_aligner',__doc__,profiles=[profile[0] for profile in PROFILES],seed=20261013,rtl_category='basic')
    build,rtl=args.build_dir.resolve(),args.rtl.resolve()
    build.mkdir(parents=True,exist_ok=True)
    report_file=build/'summary.json'
    report_file.unlink(missing_ok=True)
    summary=dict(status='NOT_RUN',framework='PyUVM',simulator=args.sim,rtl=str(rtl),
        scope='selected_profiles' if args.case else 'width_direction_timing_matrix',
        specification='specs/basic/mosaic-data-aligner/README.md',encoding_scope='repository_local',
        started_at_utc=datetime.now(timezone.utc).isoformat(),profiles=[],parameter_checks=[],assertion_probes=[],
        external_checks=dict.fromkeys(('hdl_sva','formal','commercial_lint','cdc','rdc','dft','vc_lp','technology_synthesis',
            'physical_timing','physical_power','canonical_contracts','reset_release_integration'),'NOT_RUN'))
    try:
        summary['rtl_sha256']=digest(rtl)
        summary['dependency_sha256']={str(path.relative_to(ROOT)):digest(path) for path in DEPENDENCIES}
        summary['verification_sha256']=verification_hashes(TEST_DIR)
        require_simulator(args)
        summary['status']='FAIL'
        for index,(name,*values) in enumerate(PROFILES):
            if args.case and name not in args.case:
                continue
            parameters=dict(zip(NAMES,values))
            print(f'Running {name}, seed={args.seed+index}',flush=True)
            result,log,results,coverage_file=simulate(args,build/name,rtl,parameters,args.seed+index)
            report=dict(name=name,status='FAIL',parameters=parameters,log=str(log))
            try:
                if result.returncode:
                    raise ValueError(f'make exited with status {result.returncode}')
                passed_test(results,'DataAlignerTest','test_data_aligner')
                coverage=json.loads(coverage_file.read_text(encoding='utf-8'))
                if (coverage['status']!='PASS' or coverage['parameters']!=parameters or not coverage['goals']
                        or not all(coverage['goals'].values()) or coverage['structural_assertions']!='PASS'):
                    raise ValueError('Coverage, structure checks or elaborated parameters did not match')
                if coverage['seed']!=args.seed+index or coverage['random_transactions']!=args.random_cycles:
                    raise ValueError('Campaign random settings did not match')
                report.update(coverage,name=name,log=str(log),coverage=str(coverage_file))
            except (OSError,ValueError,KeyError,ET.ParseError) as error:
                report['error']=str(error)
                if license_unavailable(log.read_text(encoding='utf-8')):
                    report['status']='NOT_RUN'
                print('\n'.join(log.read_text().splitlines()[-25:]),flush=True)
            summary['profiles'].append(report)
            print(f"{name}: {report['status']}",flush=True)
        summary['parameter_checks']=[parameter_guard(args,build,rtl,'data_aligner',name,parameters,
            'data_aligner_parameters_must_be_valid',dependencies=DEPENDENCIES) for name,parameters in INVALID]
        summary['assertion_probes']=assertion_probes(args,build,rtl)
        complete=(len(summary['profiles'])==(len(set(args.case)) if args.case else len(PROFILES))
                  and len(summary['parameter_checks'])==len(INVALID) and len(summary['assertion_probes'])==len(PROBES))
        summary['status']=campaign_status((*summary['profiles'],*summary['parameter_checks'],*summary['assertion_probes']),complete)
    except (OSError,ValueError) as error:
        summary['error']=str(error)
        print(f'Data aligner regression could not run: {error}',file=sys.stderr)
    finally:
        finish_summary(report_file,summary,'Data aligner')
    return 0 if summary['status']=='PASS' else 1


if __name__=='__main__':
    sys.exit(main())
