"""Reference-model and production-contract checks without simulator assumptions."""
import unittest
from cpt.defaults import DEFAULTS
from cpt.model import Architecture, command, compare, context, event, pack, put, unpack, META, RECORD
from cpt_contract import profile

class ModelTests(unittest.TestCase):
    def test_profile_geometry(self):
        for depth in range(1,5):
            p=profile(MAX_LOOP_DEPTH=depth)
            self.assertEqual(p['CONFIG_WORD_COUNT'],(512+depth*133+63)//64)

    def test_capability_guards(self):
        for changes in (dict(FU_PROFILE=2),dict(SUPPORT_CHECKPOINT=1),dict(NUM_EVENT_NAMESPACES=2),
                        dict(PREDICATE_PROTECTION=1),dict(EVENT_RECORD_WIDTH=64),
                        dict(MAX_OUTSTANDING_ACTIONS=9)):
            with self.assertRaises(ValueError):profile(**changes)

    def test_local_profile(self):
        with self.assertRaises(ValueError):profile(FU_PROFILE=0)
        self.assertEqual(profile(FU_PROFILE=0,SUPPORT_CONTEXT_COORDINATION=0,
            SUPPORT_CLUSTER_LIFECYCLE=0,SUPPORT_TIMEOUT=0)['FU_PROFILE'],0)

    def test_context_not_truncated(self):
        p=profile();c=context(p)
        self.assertLess(pack(p,c),1 << (64*p['CONFIG_WORD_COUNT']))
        c['epoch']=1<<16
        with self.assertRaises(ValueError):pack(p,c)

    def test_metadata_roundtrip(self):
        values={name:(1<<bits)-1 for name,(_,bits) in META.items()}
        self.assertEqual(unpack(META,put(META,values)),values)

    def test_event_roundtrip(self):
        raw=event(profile(),68,tag=23,sequence=65535,payload=(1<<64)-1)
        d=unpack(RECORD,raw)
        self.assertEqual((d['tag'],d['sequence'],d['payload']),(23,65535,(1<<64)-1))
        self.assertEqual(raw&7,7)

    def test_signed_boundaries(self):
        self.assertTrue(compare(2,0x80000000,0x7fffffff,True))
        self.assertFalse(compare(2,0x80000000,0x7fffffff,False))
        self.assertTrue(compare(6,0,0xdead))
        self.assertTrue(compare(7,1,1))

    def evaluate(self,model,cls,op,a=0,b=0,**changes):
        data,meta=command(model.p,68,cls,op,a,b,**changes)
        return model.evaluate(data,meta)

    def test_predicate_invalidity(self):
        model=Architecture(profile())
        self.assertTrue(self.evaluate(model,0,3)['error'])
        self.evaluate(model,0,1,write_enable=1)
        self.assertFalse(self.evaluate(model,0,3)['error'])

    def test_masked_invalidation(self):
        model=Architecture(profile())
        self.evaluate(model,0,1,write_enable=1)
        self.evaluate(model,0,8,mask=1,write_enable=1)
        self.assertTrue(self.evaluate(model,0,3,mask=1)['error'])
        self.assertFalse(self.evaluate(model,0,3,mask=2)['error'])

    def test_valid_false_predicate(self):
        model=Architecture(profile())
        self.evaluate(model,0,0,write_enable=1)
        result=self.evaluate(model,0,3)
        self.assertEqual(result['predicate'],(0,255))

    def test_boolean_combinations(self):
        model=Architecture(profile())
        self.evaluate(model,0,2,0x55,write_enable=1,destination=0)
        self.evaluate(model,0,2,0xaa,write_enable=1,destination=1)
        self.assertEqual(self.evaluate(model,0,5)['data'],0)
        self.assertEqual(self.evaluate(model,0,6)['data'],255)
        self.assertEqual(self.evaluate(model,0,7)['data'],255)

    def test_typed_register(self):
        model=Architecture(profile())
        self.evaluate(model,7,1,99,register_type=2)
        self.assertEqual(self.evaluate(model,7,0,register_type=2)['data'],99)
        self.assertTrue(self.evaluate(model,7,0,register_type=1)['error'])
        self.evaluate(model,7,2)
        self.assertTrue(self.evaluate(model,7,0,register_type=2)['error'])

    def test_false_has_no_local_effect(self):
        model=Architecture(profile())
        data,meta=command(model.p,68,7,1,99)
        result=model.evaluate(data,meta,False)
        self.assertTrue(result['suppress'])
        self.assertEqual(model.registers,{})

    def test_lane_geometry(self):
        for lanes in (1,3,8,16):
            model=Architecture(profile(PREDICATE_LANES=lanes))
            self.assertEqual(self.evaluate(model,0,1)['data'],(1<<lanes)-1)

if __name__=='__main__':unittest.main()
