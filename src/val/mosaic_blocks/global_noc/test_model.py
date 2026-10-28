"""Independent known vectors, topology walks and conservation model self-checks."""
import unittest
from global_noc.model import Ledger, image
from global_noc.dependencies import profile
from global_noc_contract import crc32c, metadata, flow_words, route, signature, validate
from generate import graph

class ModelTests(unittest.TestCase):
    def test_crc_zero_length(self):self.assertEqual(crc32c([]),0)
    def test_crc_known_eight_bytes(self):self.assertEqual(crc32c([int.from_bytes(b'12345678','little')]),0x6087809A)
    def test_metadata(self):
        f=flow_words(flow_id=0x1234,generation=0xabcd,epoch=0x56,slot=0x78,source=0,destination=1)
        self.assertEqual(metadata(f,0x9abc),0x9abc7856abcd1234)
    def test_flow_identity(self):
        a=flow_words(flow_id=1,source=0,destination=1,owner=2,kernel=3,package=4)
        self.assertEqual(a[1],4<<32|3<<16|2)
    def test_signature_geometry(self):self.assertNotEqual(signature(profile()),signature(profile(NOC_X=3)))
    def test_generator_guards(self):
        for changes in (dict(ASYNC_ENDPOINT_MASK=1),dict(NUM_ENDPOINTS=3),
            dict(FLOW_CONTROL=0),dict(MAX_ACTIVE_FLOWS=0),dict(TRAFFIC_CLASS_TO_VC=0),
            dict(INPUT_VC_DEPTH=2,ENDPOINT_RX_VC_DEPTH=2),dict(ENABLE_TRACE=1)):
            with self.assertRaises(ValueError):validate(profile(**changes))
    def test_signature_epoch_and_fragment(self):
        base=signature(profile())
        self.assertNotEqual(base,signature(profile(LINK_EPOCH_WIDTH=3)))
        self.assertNotEqual(base,signature(profile(FRAGMENT_INDEX_WIDTH=5)))
    def test_image_length(self):
        p=profile();self.assertEqual(len(image(p,[])),2+p['NUM_ROUTERS']+4*p['MAX_ACTIVE_FLOWS'])
    def test_all_topology_routes(self):
        for x,y in ((1,1),(2,2),(3,2),(4,4),(8,8)):
            for routing in (0,1):
                p=profile(NOC_X=x,NOC_Y=y,ROUTING_ALGORITHM=routing)
                for src in range(x*y):
                    for dst in range(x*y):
                        path=route(src,dst,p)
                        self.assertEqual(len(path),abs(src%x-dst%x)+abs(src//x-dst//x))
                        node=src;axes=[]
                        for s,port,d in path:
                            self.assertEqual(s,node)
                            self.assertTrue(0<=d<x*y)
                            self.assertEqual(d-s,{1:-x,2:1,3:x,4:-1}[port])
                            if port in (2,4):self.assertEqual(d//x,s//x)
                            node=d;axes.append(0 if port in (2,4) else 1)
                        self.assertEqual(node,dst)
                        self.assertEqual(axes,sorted(axes,reverse=bool(routing)))
    def test_dependency_graphs(self):
        for x,y in ((1,1),(2,2),(3,2),(4,4),(8,8)):
            for routing in (0,1):self.assertTrue(graph(profile(NOC_X=x,NOC_Y=y,ROUTING_ALGORITHM=routing))['acyclic'])
    def test_ledger_delivery(self):
        l=Ledger();b=dict(data=123,user_metadata=1,destination_node=2,destination_endpoint=3)
        l.inject(b,0,1,0)
        l.eject(dict(data=123,user_metadata=1,source_node=0,source_endpoint=1),2,3,0)
        self.assertEqual(l.outstanding,0)
        with self.assertRaises(AssertionError):l.eject(dict(user_metadata=1),2,3,0)
    def test_ledger_corruption(self):
        l=Ledger();l.inject(dict(data=1,user_metadata=1,destination_node=0,destination_endpoint=0),0,0,0)
        with self.assertRaises(AssertionError):l.eject(dict(data=2,user_metadata=1,source_node=0,source_endpoint=0),0,0,0)
    def test_ledger_flush(self):
        l=Ledger();l.inject(dict(user_metadata=2,destination_node=1,destination_endpoint=0),0,0,0)
        self.assertEqual(l.flush(),1);self.assertEqual(l.outstanding,0)
