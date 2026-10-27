"""Python-only generated Cluster-MVP campaign; synthesis remains a later DC step."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
TEST_DIR = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT/'src/val/lib'),str(TEST_DIR.parent),str(ROOT/'src/gen/cluster')]
from mosaic_uvm.regression import (campaign_status, finish_summary, parse_args, passed_test,
    require_simulator, run_simulation, verification_hashes, license_unavailable, parameter_guard)
from cluster.test_model import ModelTests
from sources import SOURCES
import generate

PROFILES = ('mvp','permuted','gating_off','small_scratchpad','four_by_four_smoke','partial_commit')


def descriptor_for(name):
    import tomllib
    d=tomllib.loads((ROOT/'src/gen/cluster/mvp.toml').read_text())
    if name=='permuted':
        for tile,logical in zip(d['tiles'],(37,9,201,88)):
            tile['id']=logical
        d['tiles'][0]['class'],d['tiles'][3]['class']='MST','BCT'
        d['cluster_id']=17
    elif name=='gating_off': d['clock_gating']=False
    elif name=='small_scratchpad':
        d.update(scratchpad_banks=2,scratchpad_bank_words=32)
    elif name=='four_by_four_smoke':
        d.update(rows=4,cols=4,tiles=[dict(id=100+r*4+c, row=r,col=c,
            **{'class':'MST' if (r,c)==(2,1) else 'BCT'}) for r in range(4) for c in range(4)])
    return d


def write_toml(path, d):
    lines=[]
    for key,value in d.items():
        if key=='tiles': continue
        encoded=str(value).lower() if isinstance(value,bool) else json.dumps(value)
        lines.append(f'{key} = {encoded}')
    for tile in d['tiles']:
        lines.append('\n[[tiles]]')
        lines.extend(f'{key} = {json.dumps(value)}' for key,value in tile.items())
    path.write_text('\n'.join(lines)+'\n')


def hashes():
    files=[ROOT/f'src/rtl/{name}.sv' for name in SOURCES]
    files += list((ROOT/'src/gen/cluster').glob('*.py'))
    files += [ROOT/'src/gen/cluster/mvp.toml']
    return dict(source_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in files},verification_sha256=verification_hashes(TEST_DIR))


def run_profile(task):
    args,build,index,name=task
    target=build/name
    target.mkdir(parents=True,exist_ok=True)
    descriptor=target/'descriptor.toml'
    write_toml(descriptor,descriptor_for(name))
    artifacts=target/'architecture'
    top=target/'cluster.sv'
    contract=generate.generate(descriptor,top,artifacts)
    sources=' '.join(str(ROOT/f'src/rtl/{s}.sv') for s in SOURCES)+' '+str(top)
    smoke=name.endswith('_smoke')
    test_class=('ClusterSmokeTest' if smoke else
        'ClusterCommitFaultTest' if name=='partial_commit' else 'ClusterTest')
    result,log,results,coverage=run_simulation(args,ROOT,TEST_DIR,'cluster','test_cluster',
        test_class,target/'simulation',sources,parameters=contract['descriptor'],environment={
            'CLUSTER_ARTIFACTS':str(artifacts),'CLUSTER_SEED':str(args.seed+index),
            'CLUSTER_RANDOM_CYCLES':str(args.random_cycles),'CLUSTER_MODE':'smoke' if smoke else 'partial' if name=='partial_commit' else 'full'})
    row=dict(name=name,status='FAIL',log=str(log),scope='control smoke' if smoke else 'full integration')
    try:
        if result.returncode: raise ValueError(f'make exited {result.returncode}')
        passed_test(results,test_class,'test_cluster')
        data=json.loads(coverage.read_text())
        if (data['status']!='PASS' or not data['goals'] or not all(data['goals'].values()) or
            data['parameters']!=contract['descriptor'] or data['seed']!=args.seed+index or
            data['random_cycles']!=args.random_cycles or
            data['manifest_sha256']!=contract['manifest_sha256'] or
            data['hdl_assertions']!='NOT_RUN'):
            raise ValueError('Coverage, manifest or seed mismatch')
        row.update(data,coverage=str(coverage))
    except (OSError,ValueError,KeyError,ET.ParseError) as error:
        row['error']=str(error)
        if license_unavailable(log.read_text()): row['status']='NOT_RUN'
        print('\n'.join(log.read_text().splitlines()[-22:]),flush=True)
    print(name,row['status'],flush=True)
    return row


def main():
    args=parse_args('cluster',__doc__,profiles=PROFILES,seed=20261026,rtl_category='mosaic_blocks')
    build=args.build_dir.resolve()
    build.mkdir(parents=True,exist_ok=True)
    summary=dict(status='NOT_RUN',framework='PyUVM',simulator=args.sim,profiles=[],parameter_checks=[],
        validation_mode='Python-only',synthesis='Design Compiler (deferred)',lint='NOT_RUN',
        started_at_utc=datetime.now(timezone.utc).isoformat())
    try:
        before=hashes()
        summary.update(before)
        with (build/'python_model_tests.log').open('w') as log:
            result=unittest.TextTestRunner(stream=log).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(ModelTests))
        summary['python_model_checks']=dict(status='PASS' if result.wasSuccessful() else 'FAIL',
                                            tests=result.testsRun)
        if not result.wasSuccessful(): raise ValueError('Python model checks failed')
        require_simulator(args)
        jobs=int(os.getenv('CLUSTER_JOBS','2' if args.sim=='icarus' else '1'))
        if not 1<=jobs<=8: raise ValueError('CLUSTER_JOBS must be between 1 and 8')
        selected=[n for n in PROFILES if not args.case or n in args.case]
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            summary['profiles']=list(pool.map(run_profile,[(args,build,i,n) for i,n in enumerate(selected)]))
        dependencies=tuple(ROOT/f'src/rtl/{name}.sv' for name in SOURCES)
        # Python drives strict elaboration guards; these are not synthesis or lint.
        invalid=(('tiles_zero',dict(NUM_TILES=0)),('tiles_over',dict(NUM_TILES=65)),
                 ('timeout_short',dict(TIMEOUT_CYCLES=1)),
                 ('protection_invalid',dict(CONTROL_PROTECTION=3)))
        summary['parameter_checks']=[parameter_guard(args,build,
            ROOT/'src/rtl/mosaic_blocks/cluster_control.sv','cluster_control',label,p,
            'cluster_control_parameters_must_be_valid',dependencies=tuple(
                s for s in dependencies if s.name!='cluster_control.sv')) for label,p in invalid]
        for label,value in (('allocation_owner_two',2),('allocation_owner_negative',-1),
                            ('allocation_owner_x',"32'bx"),('allocation_owner_z',"32'bz")):
            summary['parameter_checks'].append(parameter_guard(args,build,
                ROOT/'src/rtl/mosaic_blocks/configuration_network.sv','configuration_network',label,
                dict(USE_ALLOCATION_OWNER=value),'configuration_network_parameters_must_be_valid',
                dependencies=tuple(s for s in dependencies if s.name!='configuration_network.sv')))
        summary['sources_stable']=before==hashes()
        summary['status']=campaign_status((*summary['profiles'],*summary['parameter_checks'],
            summary['python_model_checks']),summary['sources_stable'] and len(summary['profiles'])==len(selected))
    except (OSError,ValueError,KeyError) as error:
        summary['error']=str(error)
    finally:
        finish_summary(build/'summary.json',summary,'Cluster')
    return 0 if summary['status']=='PASS' else 1

if __name__=='__main__': sys.exit(main())
