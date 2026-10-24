"""Observed, checked functional bins; unavailable signoff stays explicit."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector
from loop_controller.model import decode, number


class LoopControllerCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events = Counter()
        self.depths = set()
        self.modes = set()
        self.comparisons = set()
        self.zeros = set()
        self.intervals = set()
        self.carries = set()
        self.totals = set()
        self.errors = set()
        self.faults = set()
        self.unknowns = set()
        self.completions = set()
        self.flush_states = set()
        self.reset_states = set()
        self.random_cycles = self.tokens = self.samples = 0
        self.accounting = Counter()
        self.advance_levels = set()
        self.control_opcodes = set()
        self.selection_checks = self.level_holds = self.unknown_control_decodes = 0

    def record(self, obs, m, o):
        p = {n: number(v) for n, v in obs.ports.items()}
        if obs.item.fault:
            self.faults.add(obs.item.fault)
        self.samples += 1
        self.random_cycles += obs.item.random
        for name, value in p.items():
            if name.startswith('i_') and value is None:
                self.unknowns.add(name)
        for name, value in o.items():
            if name.startswith('o_event_') or name.endswith(('_accepted', '_rejected')):
                self.events[name] += bool(value)
        if m.error:
            self.errors.add(m.error)
        if p['i_rstb'] == 0:
            self.reset_states.add(m.state)
        if p['i_flush'] == 1:
            self.flush_states.add(m.state)
        if m.candidate is not None and p['i_rstb'] == 1 and p['i_flush'] == 0:
            n, error = decode(m.candidate, self.config)
            if not error:
                self.depths.add(n['depth'])
                self.totals.add(n['total'])
                self.intervals.add(n['initiation_interval'])
                for k in range(n['depth']):
                    self.modes.add((k, n['level_mode'][k], int(n['step'][k] < 0)))
                    if n['level_mode'][k] == 1:
                        self.comparisons.add((k, n['compare'][k]))
                    if n['trip_count'][k] == 0:
                        self.zeros.add(k)
        if o['o_iteration_valid'] and p['i_iteration_ready'] == 1:
            self.tokens += 1
            self.accounting['transferred'] += 1
        if o['o_event_outer_wrap']:
            self.carries |= {k for k in range(self.config.MAX_LOOP_DEPTH) if o['o_event_outer_wrap'] >> k & 1}
        if o['o_completion_valid'] and p['i_completion_ready'] == 1:
            self.completions.add((o['o_completion_status'], o['o_completion_event_enable']))
            self.accounting['completed_tokens'] += o['o_completion_iterations']
            self.accounting['records'] += 1
        self.accounting['starts'] += bool(o['o_start_accepted'])
        if p['i_flush'] == 1 or p['i_rstb'] == 0:
            if m.state != 'idle':
                self.accounting['discarded_runs'] += 1
                self.accounting['discarded_tokens'] += m.accepted

    def report(self):
        c = self.config
        required = ('o_config_accepted', 'o_config_rejected', 'o_start_accepted',
                    'o_start_rejected', 'o_control_rejected', 'o_event_iteration_transfer',
                    'o_event_iteration_stall', 'o_event_run_complete')
        goals = {n: self.events[n] > 0 for n in required}
        goals.update(every_depth=self.depths == set(range(1, c.MAX_LOOP_DEPTH + 1)),
            zero_at_every_level=self.zeros == set(range(c.MAX_LOOP_DEPTH)),
            required_intervals={v for v in (1, 2, 3, 8, 255) if v < 1 << c.II_WIDTH} <= self.intervals,
            every_carry=set(range(max(0, c.MAX_LOOP_DEPTH - 1))) <= self.carries,
            counted_both_signs={(k, 0, s) for k in range(c.MAX_LOOP_DEPTH) for s in range(2)} <= self.modes,
            errors={1, 2, 3, 4, 5, 6, 8, 12, 13} <= self.errors,
            unknown_controls=len(self.unknowns) >= 10,
            natural_event_enable={(0, 0), (0, 1)} <= self.completions,
            random_campaign=self.random_cycles == c.random_cycles,
            checked_tokens=self.tokens > 20,
            flush_live='issue' in self.flush_states,
            reset_live='issue' in self.reset_states)
        if c.MAX_LOOP_DEPTH > 1:
            goals['inactive_error'] = 11 in self.errors
        if c.LINEAR_COUNT_WIDTH // c.MAX_LOOP_DEPTH + 1 < min(c.TRIP_COUNT_WIDTH, c.INDEX_WIDTH - 1):
            goals['product_error'] = 9 in self.errors
        goals['exact_maximum_total'] = (1 << c.LINEAR_COUNT_WIDTH) - 1 in self.totals
        if c.NUM_EVENTS == 1 or c.NUM_EVENTS & (c.NUM_EVENTS - 1):
            goals['event_error'] = 10 in self.errors
        if c.SUPPORT_BOUNDED_MODE:
            goals['all_comparisons_per_level'] = {(k, cmp) for k in range(c.MAX_LOOP_DEPTH) for cmp in range(4)} <= self.comparisons
            goals['bounded_error'] = 7 in self.errors
        if c.SUPPORT_SUSPEND:
            goals['pause_resume'] = all(self.events[n] for n in ('o_event_pause', 'o_event_resume'))
        if c.SUPPORT_ABORT:
            goals['aborted_event_enable'] = {(1, 0), (1, 1)} <= self.completions
        if c.check_internals:
            goals['every_depth_and_advance_level'] = {
                (depth, level) for depth in range(1, c.MAX_LOOP_DEPTH + 1)
                for level in range(depth)
            } <= self.advance_levels
            goals['held_level_update_mask'] = self.level_holds > 0
            goals['control_decode_and_fail_closed'] = (
                ({0, 2, 3} | ({1} if c.SUPPORT_SUSPEND else set())) <= self.control_opcodes
                and self.unknown_control_decodes > 0
            )
            goals['invariant_injection'] = (14 if c.PROTECT_STATE else 15) in self.errors
            if c.PROTECT_STATE:
                goals['parity_injection'] = 14 in self.errors
                goals['all_protected_banks'] = {'candidate', 'config', 'state'} <= self.faults
        return dict(status='PASS' if all(goals.values()) else 'FAIL', framework='PyUVM',
            parameters=c.parameters, seed=c.seed, goals=goals, samples=self.samples,
            random_transactions=self.random_cycles, tokens=self.tokens, events=dict(self.events),
            depths=sorted(self.depths), modes=sorted(self.modes), comparisons=sorted(self.comparisons),
            zero_levels=sorted(self.zeros), intervals=sorted(self.intervals), carries=sorted(self.carries),
            injected_faults=sorted(self.faults), error_classes=sorted(self.errors), unknown_fields=sorted(self.unknowns),
            completions=sorted(self.completions), flush_states=sorted(self.flush_states),
            reset_states=sorted(self.reset_states), accounting=dict(self.accounting),
            hdl_assertions='PASS' if c.hdl_assertions else 'NOT_RUN',
            selection_assertions='PASS' if c.check_internals else 'NOT_RUN',
            selection_checks=self.selection_checks, level_holds=self.level_holds,
            advance_levels=sorted(self.advance_levels), control_opcodes=sorted(self.control_opcodes),
            unknown_control_decodes=self.unknown_control_decodes,
            external_checks=dict.fromkeys(('formal', 'commercial_lint', 'cdc', 'rdc', 'dft',
                'vc_lp', 'technology_synthesis', 'physical_timing', 'physical_power'), 'NOT_RUN'))
