"""Python-only system, host/memory BFMs, focused core and strict guard campaign."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tomllib
import unittest
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'src/val'),str(HERE.parent),str(ROOT/'src/val/lib')]
spec=importlib.util.spec_from_file_location('campaign_system_generator',ROOT/'src/gen/system/generate.py')
generator=importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)
from mosaic_uvm.regression import (parse_args,require_simulator,run_simulation,passed_test,
    verification_hashes,parameter_guard,finish_summary,campaign_status)
PROFILES=('minimal','single','mvp','mem64','maxqueues')


def hashes():
    paths=list((ROOT/'src/rtl').rglob('*.sv'))
    paths += list((ROOT/'src/val').rglob('*.py'))
    paths += list((ROOT/'src/gen').rglob('*.py'))
    paths += [ROOT/'src/gen/system/rtl.toml',ROOT/'src/gen/array/mvp.toml',ROOT/'src/gen/cluster/mvp.toml']
    return dict(source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(set(paths))},verification_sha256=verification_hashes(HERE))


def run_profile(task):
    args,build,name=task
    d=tomllib.loads((ROOT/'src/gen/system/rtl.toml').read_text())
    if name=='minimal':
        d.update(clusters=1,command_depth=1,event_depth=1,buffers=1,memory_data_width=64)
    if name in ('single','mem64'):
        d.update(clusters=1,command_depth=1,event_depth=1,buffers=3)
    if name=='mem64': d['memory_data_width']=64
    if name=='maxqueues': d.update(buffers=8,command_depth=8,event_depth=32)
    target=build/name
    target.mkdir(parents=True,exist_ok=True)
    descriptor=target/'descriptor.toml'
    descriptor.write_text(generator.profile_text(d))
    artifacts=target/'architecture'
    contract=generator.generate(descriptor,target/'system.sv',artifacts)
    sources=' '.join((artifacts/'sources.f').read_text().splitlines())
    result,log,xml,coverage=run_simulation(args,ROOT,HERE,'system','test_system','SystemTest',
        target/'simulation',sources,parameters=d,environment=dict(SYSTEM_ARTIFACTS=str(artifacts),
            SYSTEM_SEED=str(args.seed+PROFILES.index(name)),SYSTEM_RANDOM_CYCLES=str(args.random_cycles),
            SYSTEM_MODE='smoke' if name=='minimal' else 'full'))
    row=dict(name=name,status='FAIL',log=str(log))
    try:
        if result.returncode: raise ValueError(f'make exited {result.returncode}')
        passed_test(xml,'SystemTest','test_system')
        data=json.loads(coverage.read_text())
        if data['status']!='PASS' or not all(data['goals'].values()):
            raise ValueError('Missing required system coverage')
        if (data['manifest_sha256']!=contract['manifest_sha256'] or data['parameters']!=d or
            data['seed']!=args.seed+PROFILES.index(name) or data['random_cycles']!=args.random_cycles or
            data['hdl_assertions']!='NOT_RUN'):
            raise ValueError('Coverage provenance mismatch')
        row.update(data,coverage=str(coverage),wrapper_sha256=contract['generated_rtl_sha256'])
    except (ValueError,KeyError,OSError) as error:
        row['error']=str(error)
        print('\n'.join(log.read_text().splitlines()[-24:]),flush=True)
    print(name,row['status'],flush=True)
    return row


def run_core(args,build):
    target=build/'core'
    flag='-P' if args.sim=='icarus' else '-pvalue+'
    sources=' '.join((ROOT/'src/gen/system/generated/sources.f').read_text().splitlines())
    result,log,xml,coverage=run_simulation(args,ROOT,HERE,'system_core','test_system_core','SystemCoreTest',
        target,sources,parameters=dict(MEMORY_TIMEOUT=128),
        compile_args=args.compile_args+f' {flag}system_core.MEMORY_TIMEOUT=128',
        environment=dict(SYSTEM_SEED=str(args.seed+100),SYSTEM_RANDOM_CYCLES=str(args.random_cycles),
            SYSTEM_MODE='core'))
    row=dict(name='core',status='FAIL',log=str(log))
    try:
        if result.returncode: raise ValueError(f'make exited {result.returncode}')
        passed_test(xml,'SystemCoreTest','test_system_core')
        data=json.loads(coverage.read_text())
        if data['status']!='PASS' or not all(data['goals'].values()) or data['seed']!=args.seed+100:
            raise ValueError('Missing focused core coverage/provenance')
        row.update(data,coverage=str(coverage),peer_scope='explicit Python array peers; core only')
    except (ValueError,KeyError,OSError) as error:
        row['error']=str(error)
        print('\n'.join(log.read_text().splitlines()[-30:]),flush=True)
    print('core',row['status'],flush=True)
    return row


def main():
    args=parse_args('system',__doc__,profiles=PROFILES,seed=20261029,rtl_category='mosaic_blocks')
    build=args.build_dir.resolve(); build.mkdir(parents=True,exist_ok=True)
    summary=dict(status='NOT_RUN',framework='PyUVM',simulator=args.sim,profiles=[],parameter_checks=[],
        validation_mode='Python-only',synthesis='Design Compiler (deferred)',lint='NOT_RUN')
    try:
        before=hashes(); summary.update(before)
        from mosaic_blocks.system.test_model import ModelTests
        with (build/'python_model_tests.log').open('w') as log:
            models=unittest.TextTestRunner(stream=log).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(ModelTests))
        summary['python_model_checks']=dict(status='PASS' if models.wasSuccessful() else 'FAIL',tests=models.testsRun)
        if not models.wasSuccessful(): raise ValueError('Python reference model tests failed')
        require_simulator(args)
        selected=[name for name in PROFILES if not args.case or name in args.case]
        with ThreadPoolExecutor(max_workers=2) as pool:
            summary['profiles']=list(pool.map(run_profile,[(args,build,name) for name in selected]))
        summary['core']=run_core(args,build)
        dependencies=tuple(ROOT/p for p in
            (ROOT/'src/gen/system/generated/sources.f').read_text().splitlines()
            if p!='src/rtl/mosaic_blocks/system_core.sv')
        invalid=[('zero_clusters',dict(NUM_CLUSTERS=0)),('excess_clusters',dict(NUM_CLUSTERS=3)),
            ('unknown_clusters',dict(NUM_CLUSTERS="32'bx")),('zero_buffers',dict(NUM_BUFFERS=0)),
            ('excess_buffers',dict(NUM_BUFFERS=9)),('zero_commands',dict(COMMAND_DEPTH=0)),
            ('excess_commands',dict(COMMAND_DEPTH=9)),('zero_events',dict(EVENT_DEPTH=0)),
            ('excess_events',dict(EVENT_DEPTH=33)),('bad_memory_width',dict(MEM_DATA_WIDTH=32)),
            ('excess_memory_width',dict(MEM_DATA_WIDTH=256)),('unknown_memory_width',dict(MEM_DATA_WIDTH="32'bx")),
            ('short_timeout',dict(MEMORY_TIMEOUT=15)),('excess_timeout',dict(MEMORY_TIMEOUT=0x1000000)),
            ('small_sram',dict(SRAM_BYTES=511)),('excess_sram',dict(SRAM_BYTES=65537)),
            ('unknown_hash',dict(SYSTEM_HASH="256'bx"))]
        for name,values in invalid:
            summary['parameter_checks'].append(parameter_guard(args,build,
                ROOT/'src/rtl/mosaic_blocks/system_core.sv','system_core',name,values,
                'system_core_parameters_must_be_valid',dependencies=dependencies))
        summary['sources_stable']=before==hashes()
        summary['status']=campaign_status([*summary['profiles'],summary['core'],
            *summary['parameter_checks'],summary['python_model_checks']],summary['sources_stable'])
    except (OSError,ValueError,KeyError) as error:
        summary['error']=str(error)
    finally:
        finish_summary(build/'summary.json',summary,'System')
    return 0 if summary['status']=='PASS' else 1

if __name__=='__main__': sys.exit(main())
