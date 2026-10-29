"""Fast independent ABI, bounds, descriptor and generator qualification tests."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import random
import tomllib
import unittest
from mosaic_blocks.system.model import RegionModel, crc32c, record, payload

ROOT=Path(__file__).resolve().parents[4]
spec=importlib.util.spec_from_file_location('system_generator_model',ROOT/'src/gen/system/generate.py')
generator=importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)

class ModelTests(unittest.TestCase):
    def setUp(self):
        self.d=tomllib.loads((ROOT/'src/gen/system/rtl.toml').read_text())
        self.c=json.loads((ROOT/'src/gen/system/generated/manifest.json').read_text())

    def test_crc_known_vector(self):
        self.assertEqual(crc32c(b'123456789'),0xe3069283)

    def test_record_bytes_and_crc(self):
        value=record(self.c,0,payload(self.c,0,dict(i_runtime_command=0)))
        self.assertEqual(len(value),256)
        self.assertEqual(value[:4],b'MSYS')
        expected=int.from_bytes(value[28:32],'little')
        clean=value[:28]+bytes(4)+value[32:]
        self.assertEqual(crc32c(clean),expected)
        self.assertNotEqual(crc32c(clean[:-1]+b'\1'),expected)

    def test_field_bounds(self):
        with self.assertRaises(ValueError): payload(self.c,0,dict(i_runtime_command=32))
        with self.assertRaises(ValueError): payload(self.c,0,dict(unknown=1))
        with self.assertRaises(ValueError): record(self.c,0,owner=65536)
        with self.assertRaises(ValueError): record(self.c,127)

    def test_schema_profiles(self):
        for n in (1,2):
            for width in (64,128):
                for depth in (1,8):
                    generator.validate(self.d|dict(clusters=n,memory_data_width=width,command_depth=depth))

    def test_profile_serialization(self):
        for clusters,width in ((1,64),(1,128),(2,128)):
            descriptor=self.d|dict(clusters=clusters,memory_data_width=width)
            self.assertEqual(tomllib.loads(generator.profile_text(descriptor)),descriptor)

    def test_unsupported_features(self):
        for key in ('hardware_runtime','async_clocks','power_gating','dvfs','coherence',
                    'translation','trace','direct_results','system_clock_gating'):
            with self.subTest(feature=key),self.assertRaises(ValueError):
                generator.validate(self.d|{key:True})
        for key,value in [('profile','System-ASIC'),('control_protocol','AXI4-Lite'),
            ('memory_protocol','AXI4'),('max_active_kernels',2),('clusters',4),('buffers',0),
            ('memory_data_width',256),('event_depth',0),('memory_timeout',True),('command_depth',9)]:
            with self.subTest(parameter=key),self.assertRaises(ValueError):
                generator.validate(self.d|{key:value})

    def test_register_map_exclusive(self):
        addresses=set()
        for field in self.c['register_map'].values():
            for index in range(field['words']):
                address=field['offset']+4*index
                self.assertNotIn(address,addresses)
                self.assertEqual(address%4,0)
                self.assertLess(address,65536)
                addresses.add(address)

    def test_region_arithmetic(self):
        m=RegionModel()
        for base,size in [(0,4096),((1<<64)-256,512),(0x100001,64),(0x100000,0)]:
            with self.assertRaises(ValueError): m.register(0,base,size,5,3,1,3)
        m.register(0,0x100000,4096,5,3,1,3)
        with self.assertRaises(ValueError): m.register(1,0x100100,4096,9,3,1,3)
        with self.assertRaises(ValueError): m.register(0,0x100000,4096,5,3,1,3)

    def test_region_replacement_owner(self):
        model=RegionModel()
        model.register(0,0x100000,4096,5,3,1,3)
        with self.assertRaises(ValueError):
            model.register(0,0x100000,4096,9,3,2,3)
        model.register(0,0x100000,4096,9,3,2,3,actor=1,admin=True)
        self.assertEqual(model.regions[0]['owner'],9)

    def test_region_permissions_and_fences(self):
        m=RegionModel(); m.register(0,0x100000,4096,5,3,1,1)
        self.assertFalse(m.authorize(0,0x100000,16,False,5,3,1))
        m.regions[0]['state']='dma'
        self.assertTrue(m.authorize(0,0x100000,4096,False,5,3,1))
        for owner,kernel,generation,address,size,write in [(9,3,1,0x100000,16,False),
            (5,9,1,0x100000,16,False),(5,3,2,0x100000,16,False),
            (5,3,1,0x100000,16,True),(5,3,1,0x100fff,2,False)]:
            self.assertFalse(m.authorize(0,address,size,write,owner,kernel,generation))

    def test_random_bounded_regions(self):
        rng=random.Random(20261029)
        m=RegionModel()
        for slot in range(8):
            m.register(slot,0x100000+slot*0x1000,0x1000,5+slot,3,1,3)
            m.regions[slot]['state']='dma'
        for _ in range(1000):
            slot=rng.randrange(8); r=m.regions[slot]; offset=rng.randrange(-16,4112)
            size=rng.choice((8,16,256))
            self.assertEqual(m.authorize(slot,r['base']+offset,size,False,r['owner'],3,1),
                0<=offset and offset+size<=4096)

    def test_manifest_schema_complete(self):
        for table in ('REGISTER_BLOCK_TABLE','REGISTER_FIELD_TABLE','ADDRESS_REGION_TABLE',
            'REQUESTER_PERMISSION_TABLE','KERNEL_SLOT_TABLE','PACKAGE_SLOT_TABLE',
            'BUFFER_DESCRIPTOR_TABLE','DMA_CHANNEL_TABLE','MEMORY_REQUESTER_TABLE',
            'MEMORY_PORT_ROUTE_TABLE','EVENT_ROUTE_TABLE','INTERRUPT_ROUTE_TABLE',
            'COUNTER_SELECT_TABLE','ERROR_SOURCE_TABLE','CLOCK_DOMAIN_TABLE','RESET_DOMAIN_TABLE',
            'POWER_DOMAIN_TABLE','RESET_ORDER_TABLE','POWER_SEQUENCE_TABLE','TEST_MODE_TABLE'):
            self.assertIn(table,self.c['tables'])
