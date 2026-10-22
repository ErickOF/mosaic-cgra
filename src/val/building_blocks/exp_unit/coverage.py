"""Checked coverage bins and explicit external qualification boundaries."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector
from exp_unit.model import number


class ExpUnitCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.observations = Counter()
        self.segments = set()
        self.modes = set()
        self.inputs = set()
        self.queue_bins = set()
        self.pipeline_bins = set()
        self.signs = set()
        self.shifts = set()
        self.faults = set()
        self.unknowns = set()
        self.random_transactions = self.storage_checks = 0
        self.predicated = self.illegal = 0
        self.accounting = {}

    def record(self, events, obs, model, plan):
        self.events.update(events)
        # Coverage check_phase can run before the scoreboard's check_phase.
        # Snapshot checked accounting during sampling so report order is irrelevant.
        self.accounting = dict(accepted=model.accepted, delivered=model.delivered,
                               discarded=model.discarded, outstanding=model.occupancy)
        self.random_transactions += int(obs.item.random)
        self.queue_bins.add(len(model.queue))
        self.pipeline_bins.add(sum(token is not None for token in model.pipeline))
        if obs.item.fault:
            self.faults.add(str(obs.item.fault))
        for name, raw in obs.item.pre.ports.items():
            if name.startswith('i_') and number(raw) is None:
                self.unknowns.add(name)
        if 'request_accept' in events:
            r, fact = model.pipeline[0]
            self.predicated += r['o_result_predicated']
            self.illegal += r['o_result_error']
            if fact['active']:
                self.segments.add(fact['address'])
                self.modes.add((fact['base'], fact['interpolation'], fact['mode'], fact['signed']))
                self.inputs.add(fact['x'])
                self.signs.add((fact['x'] > 0) - (fact['x'] < 0))
                self.shifts.add((fact['net_shift'] > 0) - (fact['net_shift'] < 0))

    def report(self):
        c = self.config
        required = ('request_accept', 'result_complete', 'request_stall', 'result_stall',
                    'table_lookup', 'overflow', 'underflow', 'flush', 'reset', 'delivered')
        goals = {name: self.events[name] > 0 for name in required}
        goals['ownership_accounting'] = bool(self.accounting) and (
            self.accounting['accepted'] == self.accounting['delivered'] +
            self.accounting['discarded'] and self.accounting['outstanding'] == 0)
        bases = {base for base, enabled in ((0, c.SUPPORT_EXP_E), (1, c.SUPPORT_EXP2)) if enabled}
        interps = {0, 1} if c.SUPPORT_INTERPOLATION else {0}
        expected_modes = {(b, i, r, s) for b in bases for i in interps for r in (0, 1) for s in (0, 1)}
        goals.update(every_mode=self.modes == expected_modes,
                     every_segment=self.segments == set(range(1 << c.TABLE_ADDRESS_WIDTH)),
                     both_signs=self.signs == {-1, 0, 1}, predication=self.predicated > 0,
                     queue_occupancies=self.queue_bins == set(range(c.OUTPUT_QUEUE_DEPTH + 1)),
                     pipeline_occupancies=self.pipeline_bins == set(range(c.PIPELINE_DEPTH + 1)),
                     random_transactions=self.random_transactions == c.random_cycles,
                     unknown_injection=len(self.unknowns) >= 8)
        if c.INPUT_WIDTH <= 8:
            goals['exhaustive_input_interval'] = len(self.inputs) == 1 << c.INPUT_WIDTH
        if not c.SUPPORT_EXP_E or not c.SUPPORT_EXP2 or not c.SUPPORT_INTERPOLATION:
            goals['illegal_requests'] = self.illegal > 0
        if c.check_internals:
            goals['arithmetic_storage'] = self.storage_checks > 0
            goals['identity_fault'] = any('identity' in value for value in self.faults)
            if c.TABLE_PROTECTION:
                goals['table_faults'] = self.events['table_uncorrectable'] > 0
                goals['ownership_fault'] = any('stage' in value for value in self.faults)
            if c.TABLE_PROTECTION == 2:
                goals['corrected_table'] = self.events['table_corrected'] > 0
        return dict(status='PASS' if all(goals.values()) else 'FAIL', framework='PyUVM',
                    parameters=c.parameters, seed=c.seed, goals=goals, events=dict(self.events),
                    observations=dict(self.observations), random_transactions=self.random_transactions,
                    storage_checks=self.storage_checks, accounting=self.accounting,
                    hdl_assertions='PASS' if c.hdl_assertions else 'NOT_RUN',
                    internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
                    segments=sorted(self.segments), modes=sorted(self.modes), signs=sorted(self.signs),
                    shifts=sorted(self.shifts), fault_injections=sorted(self.faults),
                    external_checks=dict.fromkeys(('formal', 'commercial_lint', 'cdc', 'rdc',
                        'dft', 'vc_lp', 'physical_timing', 'physical_power', 'application_accuracy'), 'NOT_RUN'))
