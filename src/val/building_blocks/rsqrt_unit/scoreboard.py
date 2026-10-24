"""Check public ready/valid and exact results with independent token/credit ledgers."""
from collections import deque
from pyuvm import ConfigDB, uvm_analysis_export, uvm_scoreboard
from rsqrt_unit.images import image
from rsqrt_unit.model import Error, evaluate, number, request_from_ports, known_request
from rsqrt_unit.ports import OUTPUTS

EVENTS = ('request_accept', 'result_complete', 'request_stall', 'result_stall',
          'epsilon', 'normalize', 'seed_lookup', 'iteration', 'negative_input', 'zero_input', 'overflow',
          'underflow', 'seed_corrected', 'seed_uncorrectable')
CONTROLS = ('i_rstb', 'i_flush', 'i_drain', 'i_error_clear', 'i_request_valid', 'i_result_ready')


class RsqrtScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.analysis_export = uvm_analysis_export('analysis_export', self)
        self.analysis_export.write = self.write
        self.tick = self.released = 0
        self.faults = {}
        self.external_fault = 0
        self.pending = deque()
        self.reset()
        self.pre = None
        self.edge_observed = False

    def discard(self):
        self.coverage.discarded += len(self.pending)
        self.pending.clear()
        self.queue = []
        self.pipeline = [None] * self.c.lanes

    def reset(self):
        self.discard()
        self.released = 0
        self.error = self.fatal = 0
        self.events = dict.fromkeys(EVENTS, 0)
        self.flushed = 0
        self.external_fault = 0

    def running(self, p):
        return number(p['i_rstb']) == 1 and (not self.c.ASYNC_RESET or self.released >= 2)

    def combinational(self, p):
        c = self.c
        running = self.running(p)
        raw = bool(self.external_fault == Error.OWNERSHIP)
        active = running and number(p['i_flush']) != 1 and not self.fatal and not raw
        pop = active and bool(self.queue) and number(p['i_result_ready']) == 1
        capacity = len(self.queue) < c.OUTPUT_QUEUE_DEPTH or pop
        moves = [False] * c.lanes
        ready = [False] * c.lanes
        for lane in reversed(range(c.lanes)):
            token = self.pipeline[lane]
            downstream = capacity if lane == c.lanes - 1 else ready[lane + 1]
            if c.EVALUATION_ARCH:
                moves[lane] = active and token is not None and downstream
            else:
                moves[lane] = active and token is not None and (
                    token['phase'] < 3 + 3 * token['result']['iterations'] or capacity)
            ready[lane] = token is None or moves[lane]
            if not c.EVALUATION_ARCH:
                ready[lane] = token is None or (moves[lane] and
                    token['phase'] == 3 + 3 * token['result']['iterations'])
        seed_bad = False
        for lane, moving in enumerate(moves):
            if moving:
                token = self.pipeline[lane]
                if token['phase'] == 2 and token['stats']['active']:
                    _, stats = evaluate(c, token['request'], self.faults)
                    token['stats']['fatal'] = stats['fatal']
                    token['stats']['corrected'] = stats['corrected']
                    seed_bad |= stats['fatal']
        fatal_now = running and (bool(self.external_fault) or seed_bad)
        known = known_request(c, request_from_ports(p))
        request_ready = active and number(p['i_drain']) == 0 and not fatal_now and ready[0]
        request_ready &= number(p['i_request_valid']) != 1 or known
        take = request_ready and number(p['i_request_valid']) == 1
        finish = moves[-1] and (c.EVALUATION_ARCH or
            self.pipeline[-1]['phase'] == 3 + 3 * self.pipeline[-1]['result']['iterations'])
        return dict(running=running, active=active, raw=raw, moves=moves, pop=pop,
            take=take, ready=int(request_ready), finish=finish, fatal_now=fatal_now,
            seed_bad=seed_bad, known=known)

    def compare(self, obs):
        p = obs.ports
        c = self.c
        comb = self.combinational(p)
        run = comb['running']
        work = bool(self.pending)
        expected = dict(o_request_ready=comb['ready'],
            o_result_valid=int(comb['active'] and bool(self.queue) and not comb['fatal_now']),
            o_busy=int(run and work), o_idle=int(run and not work),
            o_quiescent=int(run and not work and not self.fatal and
                all(number(p[k]) == 0 for k in ('i_flush', 'i_drain', 'i_request_valid',
                                                'i_error_clear'))),
            o_drain_done=int(run and number(p['i_drain']) == 1 and not work),
            o_output_queue_occupancy=len(self.queue) if run else 0,
            o_flushed=int(run and self.flushed), o_error=int(run and bool(self.error)),
            o_error_code=int(self.error) if run else 0, o_fatal_error=int(run and self.fatal))
        if self.external_fault == Error.OWNERSHIP and obs.stage in ('pre', 'edge'):
            # A deposited ownership fault changes the corrupted register before
            # containment. Do not infer its pre-containment occupancy as legal work.
            for key in ('o_busy', 'o_idle', 'o_output_queue_occupancy', 'o_quiescent',
                        'o_drain_done', 'o_error', 'o_error_code', 'o_fatal_error'):
                expected.pop(key)
        result = self.queue[0]['result'] if expected['o_result_valid'] else {
            k: 0 for k in ('data', 'output_signed', 'iterations', 'quality_id', 'context_id', 'tag',
                'epsilon_applied', 'negative_input', 'zero_input', 'overflow', 'underflow', 'saturated', 'rounded',
                'approximate', 'predicated', 'error', 'error_code')}
        expected |= {'o_result_' + k: v for k, v in result.items()}
        expected |= {'o_event_' + k: int(run and v) for k, v in self.events.items()}
        seed = image(c.INTERNAL_WIDTH, c.INTERNAL_FRACTION_WIDTH, c.SEED_MANTISSA_ADDRESS_WIDTH)
        expected['o_seed_image_id'] = seed['image_id']
        if self.external_fault != Error.IMAGE:
            expected['o_seed_checksum'] = seed['checksum']
        for name, value in expected.items():
            assert number(p[name]) == value, (
                f'{obs.item.get_name()} {obs.stage} {name}: {p[name]} expected {value}; '
                f'pending={len(self.pending)} tick={self.tick}')
        assert all(number(p[name]) is not None for name in OUTPUTS)
        if run and obs.stage in ('pre', 'edge'):
            epsilon = normal = lookup = multiply = iteration = 0
            for lane, moving in enumerate(comb['moves']):
                if not moving:
                    continue
                token = self.pipeline[lane]
                if token['phase'] == 0:
                    epsilon |= token['stats']['epsilon_added'] << lane
                if not token['stats']['active']:
                    continue
                phase = token['phase']
                normal |= (phase == 1) << lane
                lookup |= (phase == 2) << lane
                enabled = 3 <= phase < 3 + 3 * token['result']['iterations']
                multiply |= enabled << lane
                iteration |= (enabled and (phase - 3) % 3 == 2) << lane
                if phase == 2:
                    assert number(obs.internals['addresses'][lane]) == token['stats']['address']
            for name, value in (('epsilon_access', epsilon), ('normalize_access', normal), ('seed_access', lookup),
                                ('multiply_enable', multiply), ('iteration_commit', iteration)):
                assert number(obs.internals[name]) == value, f'{obs.item.get_name()} {name}: {obs.internals} expected {value}'
        return comb

    def advance(self, obs, comb):
        p = obs.ports
        c = self.c
        self.tick += 1
        if number(p['i_rstb']) == 0:
            self.reset()
            return
        self.released += int(number(p['i_rstb']) == 1)
        self.events = dict.fromkeys(EVENTS, 0)
        self.flushed = 0
        detected = 0
        work = bool(self.pending)
        flushing = comb['running'] and number(p['i_flush']) == 1
        if comb['active']:
            self.events.update(request_accept=int(comb['take']),
                result_complete=int(comb['finish'] and not comb['fatal_now']),
                request_stall=int(number(p['i_request_valid']) == 1 and not comb['ready']),
                result_stall=int(bool(self.queue) and not comb['fatal_now'] and
                                 number(p['i_result_ready']) == 0))
            for lane, moving in enumerate(comb['moves']):
                if not moving:
                    continue
                token = self.pipeline[lane]
                stats = token['stats']
                phase = token['phase']
                if phase == 0:
                    self.events['epsilon'] |= stats['epsilon_added']
                    if token['result']['zero_input']:
                        detected = Error.ZERO
                if stats['active']:
                    self.events['normalize'] |= phase == 1
                    self.events['seed_lookup'] |= phase == 2
                    self.events['iteration'] |= (3 <= phase <
                        3 + 3 * token['result']['iterations'] and (phase - 3) % 3 == 2)
                    if phase == 2:
                        self.events['seed_corrected'] |= stats['corrected']
                        self.events['seed_uncorrectable'] |= stats['fatal']
                        if stats['corrected']:
                            detected = Error.CORRECTED
                if comb['finish'] and not comb['fatal_now'] and lane == c.lanes - 1:
                    for field in ('negative_input', 'zero_input', 'overflow', 'underflow'):
                        self.events[field] = token['result'][field]
            if comb['take']:
                request = request_from_ports(p)
                result, stats = evaluate(c, request, self.faults)
                token = dict(request=request, result=result, stats=stats,
                    phase=0, accepted=self.tick, label=obs.item.get_name())
                if result['error'] and not result['zero_input']:
                    detected = result['error_code']
                self.new_token = token
        if not flushing and number(p['i_rstb']) != 0 and (any(number(p[k]) is None for k in CONTROLS) or
            (number(p['i_request_valid']) == 1 and not comb['known'])):
            detected = Error.UNKNOWN
            self.coverage.unknowns += 1
        if comb['fatal_now'] and not self.fatal:
            detected = self.external_fault or Error.SEED
            self.fatal = 1
            self.coverage.fatal_events += 1
        if (flushing or (number(p['i_error_clear']) == 1 and not work and
            all(number(p[k]) == 0 for k in ('i_request_valid', 'i_flush', 'i_drain')))) and not self.fatal:
            self.error = 0
        if detected and not self.error:
            self.error = detected
        for key, value in self.events.items():
            self.coverage.events[key] += value
        if flushing or self.fatal:
            self.flushed = int(flushing and work)
            self.coverage.flushes += self.flushed
            self.discard()
            return
        if comb['pop']:
            token = self.queue.pop(0)
            assert self.pending.popleft() is token, 'Response reordering or duplication'
            self.coverage.returned += 1
        for lane in reversed(range(c.lanes)):
            if comb['moves'][lane]:
                token = self.pipeline[lane]
                self.pipeline[lane] = None
                if lane == c.lanes - 1 and comb['finish']:
                    self.queue.append(token)
                    self.coverage.complete(token, self.tick - token['accepted'])
                elif c.EVALUATION_ARCH:
                    token['phase'] += 1
                    self.pipeline[lane + 1] = token
                else:
                    token['phase'] += 1
                    self.pipeline[0] = token
        if comb['take']:
            token = self.new_token
            assert self.pipeline[0] is None
            self.pipeline[0] = token
            self.pending.append(token)
            self.coverage.accepted += 1
        self.coverage.max_occupancy = max(self.coverage.max_occupancy, len(self.queue))

    def write(self, obs):
        if obs.stage == 'pre':
            self.edge_observed = False
            if obs.item.fault:
                kind, *values = obs.item.fault
                if kind == 'release':
                    self.faults.clear()
                    if self.external_fault in (Error.IMAGE, Error.INTERNAL):
                        self.external_fault = 0
                elif kind == 'seed':
                    from rsqrt_unit.model import encode
                    from rsqrt_unit.images import seeds
                    address, value = values
                    original, width = encode(seeds(self.c.INTERNAL_WIDTH,
                        self.c.INTERNAL_FRACTION_WIDTH, self.c.SEED_MANTISSA_ADDRESS_WIDTH)[address],
                        self.c.INTERNAL_WIDTH, self.c.SEED_PROTECTION)
                    self.faults[address] = None if isinstance(value, str) else value ^ original
                    self.coverage.fault_masks.add((address, 'x' if isinstance(value, str) else value ^ original))
                else:
                    self.external_fault = (Error.IMAGE if kind == 'identity' else
                        Error.INTERNAL if kind == 'internal' else Error.OWNERSHIP)
                    self.coverage.ownership_faults.add(kind)
            if self.c.ASYNC_RESET and number(obs.ports['i_rstb']) == 0:
                self.reset()
            self.pre = obs
            self.compare(obs)
            self.coverage.random_cycles += int(obs.item.random)
            self.coverage.labels.add(obs.item.get_name().split(':', 1)[1])
        elif obs.stage == 'edge':
            assert obs.item.edge and not self.edge_observed
            self.edge_observed = True
            comb = self.compare(obs)
            self.advance(obs, comb)
        elif obs.stage == 'post':
            assert self.edge_observed == obs.item.edge
            self.compare(obs)
        else:
            self.compare(obs)
            assert obs.ports == obs.item.observation.ports, 'Outputs changed between clock edges'

    def check_phase(self):
        assert not self.pending and not self.queue and not any(self.pipeline)
        assert self.coverage.accepted == self.coverage.returned + self.coverage.discarded
