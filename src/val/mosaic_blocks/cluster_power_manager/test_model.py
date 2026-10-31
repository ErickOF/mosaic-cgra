"""Negative tests for the independent ABI/obligation/qualification checkers."""
from pathlib import Path
import tempfile
import unittest
from cluster_power_manager.config import pack, unpack, WIDTHS
from cluster_power_manager.model import (CommandLedger, PhysicalQualification, complete_drain,
                                        PHASE)
from cluster_power_manager_contract import profile, validate, UNSUPPORTED
from generate import generate


class ModelTests(unittest.TestCase):
    def test_identity_known_vector(self):
        value = pack('identity', cluster_id=0x12, owner_id=0x3456, kernel_id=0x789a,
                     package_id=0xbcdef012, allocation_generation=0x3456, epoch=0x78)
        self.assertEqual(value, 0x783456bcdef012789a345612)
        self.assertEqual(WIDTHS['identity'], 96)

    def test_all_records_round_trip(self):
        from cluster_power_manager_contract import LAYOUTS
        for name, fields in LAYOUTS.items():
            values = {n: (1 << w) - 1 for n, w in fields}
            self.assertEqual(unpack(name, pack(name, **values)), values)

    def test_pack_rejects_truncation_and_typos(self):
        for values in (dict(epoch=256), dict(epoch=-1), dict(owener_id=1)):
            with self.assertRaises((ValueError, KeyError)):
                pack('identity', **values)

    def test_guard_unsupported_physical_features(self):
        for name in UNSUPPORTED:
            with self.assertRaises(ValueError):
                validate(profile(**{name: 1}))

    def test_guard_unprotected_protected_profile(self):
        with self.assertRaises(ValueError):
            validate(profile(POWER_PROFILE=4))
        self.assertEqual(validate(profile(POWER_PROFILE=4, CONTROL_PROTECTION=2))['POWER_PROFILE'], 4)

    def test_guard_invalid_tables_and_counts(self):
        for changes in (dict(NUM_TILES=0), dict(EVENT_QUEUE_DEPTH=1),
                        dict(NUM_CLOCK_GROUPS=3, TILE_CLOCK_GROUP_TABLE=3),
                        dict(NUM_ISOLATION_GROUPS=3, BOUNDARY_ISOLATION_TABLE=3),
                        dict(OWNER_ID_WIDTH=8), dict(CLOCK_TIMEOUT_CYCLES=1 << 32)):
            with self.assertRaises(ValueError):
                validate(profile(**changes))

    def test_ledger_unsolicited_and_duplicate_terminal(self):
        ledger = CommandLedger()
        response = dict(identity=1, command=2, tag=3)
        with self.assertRaises(AssertionError):
            ledger.respond(response)
        ledger.accept(response)
        ledger.respond(response)
        with self.assertRaises(AssertionError):
            ledger.respond(response)

    def test_ledger_identity_and_tag_match(self):
        request = dict(identity=1, command=2, tag=3)
        for field in request:
            ledger = CommandLedger()
            ledger.accept(request)
            with self.assertRaises(AssertionError):
                ledger.respond(request | {field: request[field] ^ 1})

    def test_ledger_outstanding_capacity(self):
        ledger = CommandLedger()
        ledger.accept(dict(identity=1, command=2, tag=3))
        with self.assertRaises(AssertionError):
            ledger.accept(dict(identity=1, command=2, tag=4))

    def test_validation_wrong_fields_do_not_authorize(self):
        request = dict(identity=1, boot_generation=2, serial=3, tag=4, reload=0)
        ledger = CommandLedger()
        ledger.validation_request(request)
        response = {n: request[n] for n in ('identity', 'boot_generation', 'serial', 'tag')}
        for field in response:
            self.assertFalse(ledger.validation_response(response | {field: response[field] ^ 1,
                                                                   'status': 0, 'validity': 15}))
        self.assertTrue(ledger.validation_response(response | dict(status=0, validity=15)))
        self.assertFalse(ledger.validation_response(response | dict(status=0, validity=15)))

    def test_validation_serial_cannot_be_reused(self):
        ledger = CommandLedger()
        request = dict(identity=1, boot_generation=2, serial=3, tag=4)
        ledger.validation_request(request)
        with self.assertRaises(AssertionError):
            ledger.validation_request(request | dict(identity=2))

    def test_complete_drain_rejects_each_scalar_and_mask_bit(self):
        p = profile(NUM_TILES=2, NUM_BOUNDARY_ENDPOINTS=2)
        signals = dict.fromkeys(('i_cluster_quiescent', 'i_cluster_drain_done', 'i_scratchpad_idle',
            'i_memory_boundary_idle', 'i_local_network_idle', 'i_event_idle', 'i_configuration_idle',
            'i_counter_snapshot_idle', 'i_debug_idle', 'i_global_endpoint_drained'), 1)
        signals |= dict(i_cluster_busy=0, i_tile_busy_mask=0, i_tile_quiescent_mask=3,
                        i_tile_drain_done_mask=3, i_boundary_drained=3)
        self.assertTrue(complete_drain(signals, p))
        for name, value in signals.items():
            self.assertFalse(complete_drain(signals | {name: value ^ 1}, p), name)

    def test_qualification_rejects_premature_root(self):
        p = profile(ASYNC_PHYSICAL_STATUS=0)
        model = PhysicalQualification(p)
        signals = dict(o_transition_phase=PHASE['POWER'], i_power_good=1, i_power_switch_ack=1,
                       i_clock_source_ready=1, i_voltage_ready=1, o_cluster_clock_enable=0,
                       o_cluster_accept_enable=0)
        for _ in range(p['POWER_STABLE_CYCLES'] - 1):
            model.step(signals)
        # Leaving POWER must not substitute for the missing qualification sample.
        with self.assertRaises(AssertionError):
            model.step(signals | dict(o_transition_phase=PHASE['CLOCK'], o_cluster_clock_enable=1))

    def test_qualification_glitch_clears_consecutive_count(self):
        p = profile(ASYNC_PHYSICAL_STATUS=0)
        model = PhysicalQualification(p)
        signals = dict(o_transition_phase=PHASE['POWER'], i_power_good=1, i_power_switch_ack=1,
                       i_clock_source_ready=1, i_voltage_ready=1, o_cluster_clock_enable=0,
                       o_cluster_accept_enable=0)
        for _ in range(p['POWER_STABLE_CYCLES'] - 1):
            model.step(signals)
        model.step(signals | dict(i_power_good=0))
        self.assertEqual(model.power_streak, 0)
        for _ in range(p['POWER_STABLE_CYCLES']):
            model.step(signals)
        model.step(signals | dict(o_transition_phase=PHASE['CLOCK'], o_cluster_clock_enable=1))

    def test_generated_mapping_and_no_physical_energy_claim(self):
        with tempfile.TemporaryDirectory() as directory:
            result = generate(profile(NUM_TILES=3, NUM_CLOCK_GROUPS=2), Path(directory) / 'p.json')
        self.assertEqual([t['clock_group'] for t in result['tile_region_table']], [0, 1, 0])
        self.assertFalse(result['energy_table']['characterized'])
        self.assertIsNone(result['energy_table']['joules'])
        self.assertEqual(result['signoff']['synthesis'], 'Design Compiler (deferred)')
