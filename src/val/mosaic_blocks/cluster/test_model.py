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

    def event_inputs(self, **changes):
        values=dict(i_tile_valid=0,i_tile_payload=3,i_fault_valid=0,i_terminal_valid=0,
            i_memory_valid=0,i_memory_payload=11,i_fault_source=241,i_fault_code=17,
            i_clear_completion=0,i_owner_id=37,i_kernel_id=91,i_context_id=3,
            i_package_id=123,i_epoch=7,i_event_ready=0)
        return values|changes

    def test_event_pending_grant_and_critical_priority(self):
        from cluster.events_model import EventLedger
        m=EventLedger(4,1,[37,9,201,88])
        _,accepted,_=m.step(self.event_inputs(i_tile_valid=8,i_fault_valid=1))
        self.assertEqual(accepted,'fault')
        expected,accepted,_=m.step(self.event_inputs(i_tile_valid=15,i_tile_payload=3<<768,
                                                    i_event_ready=1))
        self.assertEqual(accepted,3)
        self.assertEqual(expected['o_tile_ready'],8)
        self.assertEqual(m.cursor,0)

    def test_event_snapshot_captures_original_identity(self):
        from cluster.events_model import EventLedger
        m=EventLedger(1,2,[17])
        m.step(self.event_inputs(i_tile_valid=1))
        out,_,_=m.step(self.event_inputs(i_owner_id=77,i_package_id=999))
        self.assertEqual(out['o_event_owner_id'],37)
        self.assertEqual(out['o_event_package_id'],123)
        self.assertEqual(out['o_event_source_id'],17)
        with self.assertRaises(AssertionError): m.drained()
        m.step(self.event_inputs(i_event_ready=1))
        m.drained()

    def test_event_full_queue_conserves_pop_and_push(self):
        from cluster.events_model import EventLedger
        m=EventLedger(1,1,[17])
        m.step(self.event_inputs(i_memory_valid=1))
        out,accepted,_=m.step(self.event_inputs(i_memory_valid=1))
        self.assertIsNone(accepted)
        self.assertEqual(out['o_memory_ready'],0)
        out,accepted,concurrent=m.step(self.event_inputs(i_memory_valid=1,i_event_ready=1))
        self.assertEqual(accepted,'memory')
        self.assertTrue(concurrent)
        self.assertEqual(len(m.queue),1)
        self.assertEqual(out['o_event_sequence'],0)
        self.assertEqual(m.queue[0]['sequence'],1)

    def test_event_clear_and_completion_are_atomic(self):
        from cluster.events_model import EventLedger
        m=EventLedger(1,4,[17])
        m.step(self.event_inputs(i_tile_valid=1,i_tile_payload=0))
        m.step(self.event_inputs(i_tile_valid=1,i_tile_payload=0,i_clear_completion=1))
        self.assertEqual(m.completed,1)
        self.assertFalse(m.duplicate)
        m.step(self.event_inputs(i_tile_valid=1,i_tile_payload=0))
        self.assertTrue(m.duplicate)

    def test_event_namespace_exhaustion_preserves_last_record(self):
        from cluster.events_model import EventLedger
        m=EventLedger(1,1,[17])
        m.sequence=0xffffffff
        m.step(self.event_inputs(i_memory_valid=1))
        out,accepted,_=m.step(self.event_inputs(i_memory_valid=1,i_event_ready=1))
        self.assertEqual(out['o_event_sequence'],0xffffffff)
        self.assertEqual(out['o_error'],1)
        self.assertIsNone(accepted)
        m.drained()

    def test_event_unknown_input_preserves_queued_record(self):
        from cluster.events_model import EventLedger
        m=EventLedger(1,2,[17])
        m.step(self.event_inputs(i_memory_valid=1))
        out,accepted,_=m.step(self.event_inputs(i_tile_valid=None))
        self.assertEqual(out['o_error'],1)
        self.assertEqual(out['o_event_payload'],11)
        self.assertIsNone(accepted)
        out,_,_=m.step(self.event_inputs())
        self.assertEqual(out['o_error'],1)

    def test_event_corrupt_transport_cannot_authorize_release(self):
        from cluster.events_model import EventLedger
        m=EventLedger(1,2,[17])
        m.step(self.event_inputs(i_memory_valid=1))
        m.step(self.event_inputs(),corruption='queue')
        out,_,_=m.step(self.event_inputs(i_event_ready=1))
        self.assertEqual(out['o_event_valid'],0)
        self.assertEqual(out['o_error'],1)
        self.assertEqual(out['o_empty'],0)
        with self.assertRaises(AssertionError): m.drained()

    def test_event_withdrawn_pending_owner_never_grants_another_source(self):
        from cluster.events_model import EventLedger
        m=EventLedger(4,1,[37,9,201,88])
        m.step(self.event_inputs(i_tile_valid=8,i_fault_valid=1))
        out,accepted,_=m.step(self.event_inputs(i_tile_valid=7,i_event_ready=1))
        self.assertIsNone(accepted)
        self.assertEqual(out['o_tile_ready'],0)
        out,accepted,_=m.step(self.event_inputs(i_tile_valid=15))
        self.assertIsNone(accepted)
        self.assertEqual(out['o_error'],1)

if __name__=='__main__': unittest.main()
