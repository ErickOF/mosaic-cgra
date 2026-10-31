"""Known ABI vectors and negative tests for independent conservation checks."""
import tempfile
from pathlib import Path
import unittest
from runtime_controller.config import CODES, WIDTHS, pack, unpack, profile
from runtime_controller.model import Ledger, Obligation, key
from runtime_controller_contract import validate
from generate import generate


class ModelTests(unittest.TestCase):
    def test_identity_known_vector(self):
        value = pack('identity', owner_id=0x1234, kernel_id=0x5678, descriptor_id=0x9abc,
                     descriptor_generation=0xdef0, package_id=0x11223344,
                     mapping_id=0x55667788, allocation_generation=0x99aa, epoch=0xbb)
        self.assertEqual(value, 0xbb99aa5566778811223344def09abc56781234)

    def test_variant_precompiled_mask_vector(self):
        value = pack('variant', package_id=1, mapping_id=2, cluster_mask=0xa, cluster_count=2)
        self.assertEqual(value, (2 << 80) | (0xa << 64) | (2 << 32) | 1)

    def test_round_trip_all_records(self):
        from runtime_controller_contract import LAYOUTS
        for name, fields in LAYOUTS.items():
            values = {field: (1 << width) - 1 for field, width in fields}
            self.assertEqual(unpack(name, pack(name, **values)), values)

    def test_packing_does_not_truncate(self):
        for values in (dict(owner_id=-1), dict(owner_id=65536), dict(typo=1)):
            with self.assertRaises(ValueError):
                pack('identity', **values)

    def test_static_defaults(self):
        p = profile(RUNTIME_PROFILE=0, NUM_CLUSTERS=1)
        self.assertEqual(p['MAX_ACTIVE_KERNELS'], 1)
        self.assertEqual(p['MAX_PACKAGE_VARIANTS'], 1)
        validate(p)

    def test_bounds_and_unsupported_generation(self):
        for changes in (dict(NUM_CLUSTERS=0), dict(MAX_PENDING_KERNELS=0),
                        dict(MAX_ACTIVE_KERNELS=5), dict(ENABLE_MIGRATION=1),
                        dict(RUNTIME_PROFILE=2), dict(ASYNC_RESET=1),
                        dict(OWNER_ID_TABLE=0), dict(RUNTIME_TAG_WIDTH=8),
                        dict(AGE_COUNTER_WIDTH=2), dict(ENABLE_QOS=2)):
            with self.assertRaises(ValueError):
                validate(changes)

    def test_unknown_generation_parameter(self):
        with self.assertRaises(ValueError):
            validate(dict(TYPO=1))

    def test_manifest_contains_real_source_closure(self):
        with tempfile.TemporaryDirectory() as directory:
            result = generate(profile(NUM_CLUSTERS=2), Path(directory) / 'profile.json')
            self.assertEqual(len(result['clusters']), 2)
            self.assertEqual(result['action_model']['outstanding'], 1)
            self.assertIn('src/rtl/basic/round_robin_arbiter.sv', result['source_sha256'])
            self.assertEqual(result['layouts']['identity']['epoch']['lsb'], 144)

    def test_key_includes_generation_and_owner(self):
        self.assertNotEqual(key(pack('identity', owner_id=1)), key(pack('identity', owner_id=2)))
        self.assertNotEqual(key(pack('identity', descriptor_generation=1)),
                            key(pack('identity', descriptor_generation=2)))

    def make_ledger(self):
        ledger = Ledger(profile())
        ident = pack('identity', owner_id=1, kernel_id=1, descriptor_id=2, descriptor_generation=1,
                     package_id=3, mapping_id=4, allocation_generation=1)
        descriptor = dict(owner_id=1, tag=10, variant_count=1,
                          variant_records=pack('variant', package_id=3, mapping_id=4, cluster_mask=1),
                          resource_record=pack('resource'), qos_record=0, power_record=0,
                          lifecycle_record=0)
        ledger.records[key(ident)] = Obligation(descriptor)
        action = unpack('action', pack('action', identity=ident, command=CODES['command']['ALLOCATE'],
                                      cluster_mask=1, tag=1, resources=descriptor['resource_record']))
        return ledger, ident, action

    def test_wrong_identity_does_not_retire_action(self):
        ledger, ident, action = self.make_ledger()
        ledger.command(6, action)
        ack = unpack('ack', pack('ack', identity=ident ^ 1, command=action['command'], tag=1,
                                cluster_mask=1))
        self.assertFalse(ledger.response(6, ack))
        self.assertTrue(ledger.pending)

    def test_tag_reuse_detected(self):
        ledger, ident, action = self.make_ledger()
        ledger.command(6, action)
        ack = unpack('ack', pack('ack', identity=ident, command=action['command'], tag=1, cluster_mask=1))
        ledger.response(6, ack)
        with self.assertRaises(AssertionError):
            ledger.command(6, action)

    def test_result_requires_admission(self):
        ledger, ident, _ = self.make_ledger()
        with self.assertRaises(AssertionError):
            ledger.result(unpack('notice', pack('notice', identity=ident, tag=10)))

    def test_result_cannot_release_live_resources(self):
        ledger, ident, _ = self.make_ledger()
        record = ledger.records[key(ident)]
        record.admitted = record.admission_seen = record.array_owned = True
        with self.assertRaises(AssertionError):
            ledger.result(unpack('notice', pack('notice', identity=ident, tag=10)))

    def test_admission_exactly_once(self):
        ledger, ident, _ = self.make_ledger()
        notice = unpack('notice', pack('notice', identity=ident, tag=10,
                                      status=CODES['notice_status']['REJECTED']))
        ledger.admission(notice)
        with self.assertRaises(AssertionError):
            ledger.admission(notice)

    def test_terminal_exactly_once(self):
        ledger, ident, _ = self.make_ledger()
        record = ledger.records[key(ident)]
        record.admitted = record.admission_seen = True
        notice = unpack('notice', pack('notice', identity=ident, tag=10))
        ledger.result(notice)
        with self.assertRaises(AssertionError):
            ledger.result(notice)
