"""Mandatory checked goals and explicit Python-only qualification scope."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector
class TileShellCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.counts = Counter()
        self.cfg_commands = set()
        self.context_words = set()
        self.runtime_commands = set()
        self.errors = set()
        self.transfers = set()
        self.states = set()
        self.power_states = set()
        self.accounting = {}
        self.scenarios = set()

    def report(self):
        c = self.config
        goals = dict(configuration_commands=self.cfg_commands >= set(range(6)),
            runtime_commands=self.runtime_commands == set(range(8)),
            negative_commands=len(self.errors - {0}) >= 4,
            all_context_words=self.context_words >= {(context, word)
                for context in range(c.CONTEXT_DEPTH) for word in range(c.CONFIG_WORD_COUNT)},
            atomic_context=self.counts['atomic_context'] > 0,
            suspend=self.counts['suspended'] > 0,
            held_response=self.counts['held_response'] > 0,
            debug=self.counts['debug_response'] > 0,
            counters=self.counts['counter_checks'] >= 6,
            power=self.counts['power_response'] > 0,
            random_cycles=self.counts['random_cycles'] == c.random_cycles,
            accounting=bool(self.accounting) and self.accounting['outstanding'] == 0 and
                self.accounting['accepted'] == self.accounting['delivered'] + self.accounting['discarded'])
        groups = (('data_in', c.DATA_INPUT_PORTS), ('data_out', c.DATA_OUTPUT_PORTS),
                  ('predicate_in', c.PREDICATE_INPUT_PORTS), ('predicate_out', c.PREDICATE_OUTPUT_PORTS),
                  ('event_in', c.EVENT_INPUT_PORTS), ('event_out', c.EVENT_OUTPUT_PORTS))
        for group, ports in groups:
            goals[group] = all((group, p, 'accept') in self.transfers and
                              (group, p, 'deliver') in self.transfers for p in range(ports))
        for scenario in ('crc', 'stale_validation', 'completion_ordering', 'terminate',
                         'metadata', 'unknowns', 'reset_epoch', 'power_sequence', 'ownership', 'duplicate_completion', 'stall_reasons',
                         'gated_wakeup', 'reset_phases', 'validation_cancel', 'committed_validity'):
            goals[scenario] = scenario in self.scenarios
        if c.CONTEXT_VERSION_WIDTH <= 4:
            goals['version_wrap'] = 'version_wrap' in self.scenarios
        if c.SUPPORT_TRACE:
            goals['trace'] = self.counts['trace'] > 0
        if c.CONTROL_PROTECTION or c.CONTEXT_PROTECTION:
            goals['protection'] = 'protection' in self.scenarios
        return dict(status='PASS' if all(goals.values()) else 'FAIL', framework='PyUVM',
            parameters=c.parameters, seed=c.seed, goals=goals, counts=dict(self.counts),
            cfg_commands=sorted(self.cfg_commands), runtime_commands=sorted(self.runtime_commands),
            errors=sorted(self.errors), transfers=sorted(self.transfers), states=sorted(self.states),
            power_states=sorted(self.power_states), accounting=self.accounting,
            hdl_assertions='NOT_RUN', random_transactions=self.counts['random_cycles'],
            synthesis='Design Compiler (deferred)')
