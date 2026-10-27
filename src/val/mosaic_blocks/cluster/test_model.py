"""Executable descriptor/ABI checks independent of any simulator results."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest

from cluster.model import (crc32c, images, expected_results, mesh_parameters,
                           MST_PARAMETERS, mst_pack, envelope)
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/'src/gen/cluster'))
import generate

class ModelTests(unittest.TestCase):
    def setUp(self):
        self.d = tomllib.loads((ROOT/'src/gen/cluster/mvp.toml').read_text())

    def test_explicit_placement(self):
        g = generate.validate(self.d)
        self.assertEqual(g['n'], 4)
        d = deepcopy(self.d)
        d['tiles'][0]['class'], d['tiles'][3]['class'] = 'MST', 'BCT'
        self.assertEqual(generate.validate(d)['n'], 4)
        self.assertEqual(g['capacity'], 65536)

    def test_missing_dependencies_rejected(self):
        for name in ('SFT','CPT','VCT','EMPTY','unknown'):
            d=deepcopy(self.d)
            d['tiles'][0]['class']=name
            with self.subTest(name=name), self.assertRaises(ValueError): generate.validate(d)

    def test_optional_features_rejected(self):
        for feature in ('express_links','predicate_network','power_gating','retention','dvfs',
                        'async_memory_clock','partitioning','global_noc'):
            with self.subTest(feature=feature), self.assertRaises(ValueError):
                generate.validate(self.d|{feature: True})

    def test_duplicate_namespaces(self):
        for name in ('id', 'row', 'col'):
            d=deepcopy(self.d)
            if name=='id': d['tiles'][1]['id']=0
            else:
                d['tiles'][1]['row']=d['tiles'][0]['row']
                d['tiles'][1]['col']=d['tiles'][0]['col']
            with self.subTest(name=name),self.assertRaises(ValueError): generate.validate(d)

    def test_geometry_guards(self):
        for field, value in (('rows',3),('cols',1),('context_depth',2),
                ('scratchpad_banks',3),('scratchpad_bank_words',0),('cluster_id',256),
                ('lifecycle_timeout',0),('clock_gating',2),('profile','Cluster-Balanced')):
            with self.subTest(field=field,value=value),self.assertRaises(ValueError):
                generate.validate(self.d|{field:value})

    def test_count_and_class_guards(self):
        d=deepcopy(self.d)
        d['tiles']=d['tiles'][:-1]
        with self.assertRaises(ValueError): generate.validate(d)
        d=deepcopy(self.d)
        d['tiles'][0]['class']='MST'
        with self.assertRaises(ValueError): generate.validate(d)

    def test_route_certificate_and_version(self):
        raw, info=images(self.d,owner=5,kernel=3,package=11,allocation=1,context=0,count=12)
        self.assertEqual(len(raw),6)
        self.assertNotEqual(info['proof'],0)
        self.assertEqual((raw[4] >> 40)&65535,9)
        self.assertEqual(raw[5] >> 64 & 65535,5)
        self.assertEqual(len(info['certificate']['routes']),8)

    def test_crc_reference(self):
        self.assertEqual(crc32c(int.from_bytes(b'123456789','little'),9),0xe3069283)
        self.assertNotEqual(crc32c(1,8),crc32c(1,16))

    def test_modular_chain(self):
        self.assertEqual(expected_results([0,1,0xffffffff,0x80000000]),[6,7,5,0x80000006])

    def test_metadata_disjoint_identity(self):
        value=envelope(self.d,owner=5,kernel=3,package=11,context=0,version=9,epoch=1,
                       common=(1<<255)|37,source=2)
        self.assertEqual(value>>64 & ((1<<256)-1),(1<<255)|37)
        self.assertEqual(value>>320 & 65535,5)
        self.assertEqual(value>>336 & 0xffffffff,11)
        self.assertEqual(value>>376,0)

    def test_native_identity_full_width(self):
        identity=dict(command=65535,generation=65535,owner=5,kernel=3,package_id=11,
            context_id=3,version=65535,allocation=65535,epoch=15)
        raw=mst_pack(MST_PARAMETERS,'identity',identity)
        self.assertLess(raw,1<<134)
        self.assertEqual(raw>>130,15)
        self.assertEqual(raw>>32 & 65535,5)

    def test_safe_width_evaluator(self):
        self.assertEqual(generate.arithmetic('(N*2)-1',dict(N=4)),7)
        for text in ('__import__("os")','N.__class__','[1][0]','1**5'):
            with self.subTest(text=text),self.assertRaises(ValueError):
                generate.arithmetic(text,dict(N=4))

    def test_generated_reproducibility(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp)
            a=generate.generate(ROOT/'src/gen/cluster/mvp.toml',base/'a/cluster.sv',base/'a')
            b=generate.generate(ROOT/'src/gen/cluster/mvp.toml',base/'b/cluster.sv',base/'b')
            self.assertEqual(a,b)
            self.assertEqual((base/'a/cluster.sv').read_bytes(),(base/'b/cluster.sv').read_bytes())
            ports=json.loads((base/'a/ports.json').read_text())
            self.assertEqual(ports['i_boundary_metadata'],['input',4096])
            self.assertEqual(len(a['config_endpoint_table']),6)
            self.assertNotIn('express_links', [e['type'] for e in a['config_endpoint_table']])

if __name__=='__main__': unittest.main()
