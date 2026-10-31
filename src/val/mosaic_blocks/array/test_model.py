"""Independent allocation properties, packet layout and generated architecture checks."""
from copy import deepcopy
import random
import unittest
from mosaic_blocks.array.model import AllocationModel, stream_images
from mosaic_blocks.array.run_array_regression import descriptor_for, generator

class ModelTests(unittest.TestCase):
    def test_disjoint_allocations(self):
        m = AllocationModel(2)
        self.assertEqual(m.allocate(1, 1, 7, 99), 1)
        self.assertEqual(m.allocate(2, 2, 7, 100), 2)
        self.assertTrue(m.authorize(2, 2, 7, 100, 2))
        self.assertFalse(m.authorize(3, 2, 7, 100, 2))

    def test_overlap_and_stale_authorization(self):
        m = AllocationModel(2)
        generation = m.allocate(3, 4, 5, 6)
        for mask in (0, 1, 2, 3, 4):
            with self.subTest(mask=mask), self.assertRaises(ValueError): m.allocate(mask, 7, 8, 9)
        self.assertFalse(m.authorize(3, 4, 5, 6, generation+1))
        with self.assertRaises(ValueError): m.release(3, 9, 5, 6, generation)
        m.release(3, 4, 5, 6, generation)
        self.assertEqual(m.allocate(3, 4, 5, 6), generation+1)

    def test_random_whole_cluster_ownership(self):
        rng = random.Random(20261028)
        m = AllocationModel(2)
        for _ in range(500):
            if m.records and rng.randrange(2):
                mask = rng.choice(tuple(m.records))
                m.release(mask, *m.records[mask])
            else:
                mask = rng.randrange(1, 4)
                previous = m.records.copy()
                try: m.allocate(mask, rng.randrange(3), rng.randrange(8), rng.randrange(256))
                except ValueError: self.assertEqual(previous, m.records)
            masks = list(m.records)
            self.assertTrue(all(not (a & b) for i, a in enumerate(masks) for b in masks[i+1:]))

    def test_qualified_profiles(self):
        for name, count in [('single', 1), ('mvp', 2), ('permuted', 2), ('ungated', 2)]:
            with self.subTest(profile=name): self.assertEqual(generator.validate(descriptor_for(name)), count)

    def test_unsupported_features_fail_generation(self):
        for flag in ('power_gating', 'dvfs', 'migration', 'resizing', 'async_clocks'):
            d = descriptor_for('mvp'); d[flag] = True
            with self.subTest(flag=flag), self.assertRaises(ValueError): generator.validate(d)

    def test_invalid_identity_topology_and_timeout(self):
        cases = []
        for key, value in [('schema', 'unknown'), ('profile', 'Array-Balanced'), ('array_id', 256),
                           ('rows', 2), ('cols', 4), ('lifecycle_timeout', 0), ('clock_gating', 1)]:
            d = descriptor_for('mvp'); d[key] = value; cases.append(d)
        for key, value in [('id', 0), ('col', 0), ('row', 1), ('noc_ingress', 8)]:
            d = descriptor_for('mvp'); d['clusters'][1][key] = value; cases.append(d)
        d = descriptor_for('mvp'); d['unexpected'] = 1; cases.append(d)
        for d in cases:
            with self.subTest(descriptor=d), self.assertRaises(ValueError): generator.validate(d)

    def test_source_sink_route_certificates(self):
        import tomllib
        d = tomllib.loads((generator.HERE.parent/'cluster/mvp.toml').read_text())
        images = []
        for role in ('local', 'source', 'sink'):
            raw, info = stream_images(d, role=role, owner=5, kernel=3, package=11,
                                      allocation=1, context=0, count=6)
            self.assertGreater(raw[-2], 0)
            images.append(raw[-2])
        self.assertEqual(len(set(images)), 3)

    def test_packet_envelope_preserves_high_bits(self):
        rng = random.Random(11)
        for _ in range(100):
            data, metadata = rng.getrandbits(32), rng.getrandbits(512)
            frame = data | metadata << 32
            fragments = [(frame >> (128*i)) & ((1<<128)-1) for i in range(5)]
            rebuilt = sum(value << (128*i) for i, value in enumerate(fragments))
            self.assertEqual(rebuilt & 0xffffffff, data)
            self.assertEqual(rebuilt >> 32, metadata)
            self.assertEqual(rebuilt >> 544, 0)
