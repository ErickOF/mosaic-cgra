"""Observed mode/lifecycle/flow/protection bins and closed ownership ledgers."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector
from lut_unit.model import code_width


class LutUnitCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.errors = set()
        self.banks = set()
        self.addresses = set()
        self.modes = set()
        self.unknowns = set()
        self.fault_bits = set()
        self.fault_kinds = set()
        self.result_occupancies = set()
        self.program_occupancies = set()
        self.random_cycles = self.samples = 0
        self.accounting = {}
        self.previous_accept = self.previous_finish = False

    def record(self, obs, m, a):
        self.samples += 1
        self.random_cycles += obs.item.random
        v = a['v']
        accepted = bool(a['lookup'])
        if accepted and self.previous_accept:
            self.events['consecutive_accepts'] += 1
        if a['finish'] and self.previous_finish:
            self.events['consecutive_completions'] += 1
        self.previous_accept = accepted
        self.previous_finish = a['finish']
        if obs.item.fault:
            kind, bank, address, mask = obs.item.fault
            self.fault_kinds.add(kind)
            if kind == 'table' and mask.bit_count() == 1:
                self.fault_bits.add(mask.bit_length() - 1)
        for n, value in v.items():
            if n.startswith('i_') and value is None:
                self.unknowns.add(n)
        for n, value in m.events.items():
            if value:
                self.events[n] += 1
        if m.error:
            self.errors.add(m.error)
        self.result_occupancies.add(len(m.results))
        self.program_occupancies.add(len(m.programs))
        if a['lookup']:
            packet, corrected, bad, access = a['lookup']
            self.banks.add(packet['bank'])
            self.modes.add((v['i_lookup_interpolate'], v['i_lookup_output_signed'], -1 if v['i_lookup_round_mode'] is None else v['i_lookup_round_mode']))
            if packet['predicated']:
                self.events['predicated'] += 1
            if v['i_program_valid'] == 1 and a['program']:
                self.events['concurrent_channels'] += 1
        if a['program']:
            packet = a['program'][0]
            if packet['command'] == 2 and not packet['error'] and packet['version'] == 0:
                self.events['version_wrap'] += 1
            if packet['command'] == 0 and not packet['error']:
                self.addresses.add((packet['bank'], packet['address']))

    def report(self):
        c = self.config
        required = ('o_event_lookup_accept', 'o_event_lookup_complete', 'o_event_lookup_stall',
            'o_event_result_stall', 'o_event_clip_low', 'o_event_clip_high',
            'o_event_program_write', 'o_event_program_read', 'o_event_program_commit',
            'o_event_program_invalidate', 'o_flushed', 'predicated',
            'consecutive_accepts', 'consecutive_completions', 'concurrent_channels')
        goals = {n: self.events[n] > 0 for n in required}
        goals.update(every_bank=set(range(c.NUM_BANKS)) <= self.banks,
            every_program_address={(b, a) for b in range(c.NUM_BANKS) for a in range(1 << c.ADDRESS_WIDTH)} <= self.addresses,
            errors={1, 3, 5, 7, 8} <= self.errors,
            result_full=c.LOOKUP_RESPONSE_DEPTH in self.result_occupancies,
            program_full=c.PROGRAM_RESPONSE_DEPTH in self.program_occupancies,
            random_campaign=self.random_cycles == c.random_cycles,
            closed_lookup_ledger=self.accounting.get('lookups', 0) == self.accounting.get('results', 0) + self.accounting.get('discarded', 0),
            closed_program_ledger=self.accounting.get('programs', 0) == self.accounting.get('responses', 0) + self.accounting.get('program_discarded', 0),
            unknown_controls=len(self.unknowns) >= 12)
        if c.NUM_BANKS == 1 or c.NUM_BANKS & (c.NUM_BANKS - 1):
            goals['bank_range_error'] = 2 in self.errors
        if c.SUPPORT_INTERPOLATION:
            goals['interpolation'] = self.events['o_event_interpolate'] > 0
            goals['rounding_signedness'] = {(1, s, r) for s in range(2) for r in range(2)} <= self.modes
        else:
            goals['unsupported_interpolation'] = 4 in self.errors
        if c.TABLE_VERSION_WIDTH <= 2 and (not c.TRACK_PROGRAM_COVERAGE or c.ADDRESS_WIDTH <= 4):
            goals['version_wrap'] = self.events['version_wrap'] > 0
        if c.TRACK_PROGRAM_COVERAGE:
            goals['incomplete_commit'] = 6 in self.errors
        if c.check_internals and c.BUFFER_PROTECTION:
            goals['every_codeword_bit'] = self.fault_bits == set(range(code_width(c.OUTPUT_WIDTH, c.BUFFER_PROTECTION)))
            goals['uncorrectable'] = self.events['o_event_table_uncorrectable'] > 0 and 10 in self.errors
            goals['protected_ownership'] = {'metadata', 'queue'} <= self.fault_kinds and 11 in self.errors
            if c.BUFFER_PROTECTION == 2:
                goals['corrected'] = self.events['o_event_table_corrected'] > 0 and 9 in self.errors
        return dict(status='PASS' if all(goals.values()) else 'FAIL', framework='PyUVM',
            parameters=c.parameters, seed=c.seed, goals=goals, events=dict(self.events),
            error_classes=sorted(self.errors), observed_modes=sorted(self.modes),
            programmed_addresses=len(self.addresses), fault_bits=sorted(self.fault_bits),
            fault_kinds=sorted(self.fault_kinds), unknown_fields=sorted(self.unknowns),
            result_occupancies=sorted(self.result_occupancies), program_occupancies=sorted(self.program_occupancies),
            accounting=self.accounting, samples=self.samples, random_transactions=self.random_cycles,
            hdl_assertions='PASS' if c.hdl_assertions else 'NOT_RUN',
            external_checks=dict.fromkeys(('formal', 'commercial_lint', 'cdc', 'rdc', 'dft',
                'vc_lp', 'technology_synthesis', 'physical_timing', 'physical_power'), 'NOT_RUN'))
