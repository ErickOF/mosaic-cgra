"""Required state, transition, source, timer and control-order coverage."""

from collections import Counter
from mosaic_uvm.components import CoverageCollector
from tile_power_controller.model import number
from tile_power_controller.transaction import STATES as P, ERRORS as E


class PowerCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.counts = Counter()
        self.states, self.edges, self.errors = set(), set(), set()
        self.stalls, self.groups, self.sources, self.reset_states = set(), set(), set(), set()
        self.commands, self.wake_states, self.stall_groups = set(), set(), set()
        self.timers = Counter()
        self.model = None

    def sample(self, o, q, m):
        c, p = self.config, q['p']
        self.counts['random_transactions'] += int(o.item.random)
        self.counts['cycles'] += 1
        self.states.add(m.state)
        if q['new'] != m.state and q['run']:
            self.edges.add((m.state, q['new']))
        if not q['run']:
            self.reset_states.add(m.state)
            if o.item.reset_from is not None:
                self.reset_states.add(o.item.reset_from)
        if q['error']:
            self.errors.add(q['error'])
        for n, v in m.timers.items():
            self.timers[n] = max(self.timers[n], v)
        if p['i_stall_reason'] is not None:
            self.stalls.update(
                n for n in range(c.NUM_STALL_REASONS) if p['i_stall_reason'] >> n & 1
            )
        if p['i_clock_group_request'] is not None:
            self.groups.update(
                n for n in range(c.NUM_CLOCK_GROUPS) if p['i_clock_group_request'] >> n & 1
            )
        if p['i_wakeup_event'] is not None:
            self.sources.update(
                n for n in range(c.NUM_WAKE_SOURCES) if p['i_wakeup_event'] >> n & 1
            )
        if q['command_accept'] and p['i_command'] is not None:
            self.commands.add((m.state, p['i_command']))
        if p['i_wakeup_event'] is not None:
            self.wake_states.update(
                (m.state, n)
                for n in range(c.NUM_WAKE_SOURCES)
                if p['i_wakeup_event'] & m.policy['mask'] & (1 << n)
            )
        if p['i_stall_reason'] is not None and p['i_clock_group_request'] is not None:
            self.stall_groups.update(
                (reason, group)
                for reason in range(c.NUM_STALL_REASONS)
                for group in range(c.NUM_CLOCK_GROUPS)
                if p['i_stall_reason'] >> reason & 1 and p['i_clock_group_request'] >> group & 1
            )
        for n, hit in dict(
            config=q['config_good'],
            rejected_config=q['config_accept'] and not q['config_good'],
            command=q['command_accept'] and q['command_legal'],
            rejected_command=q['command_accept'] and not q['command_legal'],
            done=q['done'],
            wake=q['wake_started'],
            test=m.test,
            timeout=q['timeout'],
            fatal=m.fatal,
            disabled_wake=p['i_wakeup_event'] is not None
            and p['i_wakeup_event'] != 0
            and m.policy['mask'] == 0,
            mask_status=bool(m.pending and not (m.pending & m.policy['mask'])),
            config_priority=q['config_accept'] and p['i_command_valid'] == 1,
            held=not o.item.edge,
            unknown=not q['known'],
        ).items():
            self.counts[n] += int(hit)

    def report(self):
        c = self.config
        required = {
            'RESET',
            'ACTIVE',
            'STALLED',
            'IDLE',
            'DRAINING',
            'REINITIALIZING',
            'WAKEUP',
            'ERROR',
        }
        if c.SUPPORT_POWER_GATING:
            required |= {'ISOLATING', 'POWERING_DOWN', 'OFF', 'POWERING_UP'}
        if c.SUPPORT_RETENTION:
            required |= {'SAVING', 'RETENTION', 'RESTORING'}
        diagnoses = {
            'COMMAND',
            'CONTEXT',
            'CONFIG',
            'UNKNOWN',
            'DRAIN_TIMEOUT',
            'ACK',
            'TEST',
            'POWER_LOSS',
            'POWER_UP_TIMEOUT',
        }
        if c.SUPPORT_POWER_GATING:
            diagnoses |= {'POWER_DOWN_TIMEOUT'}
        if c.SUPPORT_RETENTION:
            diagnoses |= {'SAVE_TIMEOUT', 'RESTORE_TIMEOUT'}
        goals = {
            n: self.counts[n] > 0
            for n in (
                'config',
                'rejected_config',
                'command',
                'rejected_command',
                'done',
                'test',
                'timeout',
                'fatal',
                'disabled_wake',
                'mask_status',
                'config_priority',
                'unknown',
            )
        }
        goals |= {f'state_{n}': P[n] in self.states for n in sorted(required)}
        goals |= {f'reset_{n}': P[n] in self.reset_states for n in sorted(required)}
        goals |= {f'error_{n}': E[n] in self.errors for n in sorted(diagnoses)}
        goals |= dict(
            all_stalls=len(self.stalls) == c.NUM_STALL_REASONS,
            all_clock_groups=len(self.groups) == c.NUM_CLOCK_GROUPS,
            all_wake_sources=len(self.sources) == c.NUM_WAKE_SOURCES,
            idle_threshold=self.timers['idle'] == c.IDLE_ENTRY_CYCLES,
            power_qualification=self.timers['qualification'] == c.POWER_STABLE_CYCLES,
            random_cycles=self.counts['random_transactions'] == c.random_cycles,
            recovered=self.model.state == P['ACTIVE']
            and not self.model.error
            and not self.model.fatal,
        )
        stable_commands = ['ACTIVE', 'STALLED', 'IDLE']
        wake_states = ['IDLE']
        if c.SUPPORT_POWER_GATING:
            stable_commands.append('OFF')
            wake_states.append('OFF')
        if c.SUPPORT_RETENTION:
            stable_commands.append('RETENTION')
            wake_states.append('RETENTION')
        goals['state_by_command'] = all(
            (P[state], cmd) in self.commands for state in stable_commands for cmd in range(8)
        )
        goals['state_by_wake_source'] = all(
            (P[state], source) in self.wake_states
            for state in wake_states
            for source in range(c.NUM_WAKE_SOURCES)
        )
        goals['stall_by_group'] = len(self.stall_groups) == c.NUM_STALL_REASONS * c.NUM_CLOCK_GROUPS
        if c.WAKE_ON_EVENT:
            goals['event_wake'] = self.counts['wake'] > 0
        return dict(
            status='PASS' if all(goals.values()) else 'FAIL',
            goals=goals,
            parameters=c.parameters,
            seed=c.seed,
            random_transactions=self.counts['random_transactions'],
            counters=dict(self.counts),
            states=sorted(self.states),
            edges=sorted(self.edges),
            errors=sorted(self.errors),
            reset_states=sorted(self.reset_states),
            state_commands=sorted(self.commands),
            wake_sources_by_state=sorted(self.wake_states),
            stall_groups=sorted(self.stall_groups),
            timer_maxima=dict(self.timers),
            framework='PyUVM',
            validation_mode='Python-only',
            internal_timer_checks='PASS',
            hdl_assertions='NOT_RUN',
            power_aware_simulation='NOT_RUN',
            synthesis='Design Compiler (deferred)',
        )
