"""Independent pre-edge integer ledger, wait sets and ordered release records.

Arbitration is expressed as circular lists; event mutations are set operations
on one immutable count snapshot. No private DUT state enters the prediction.
"""
from event_barrier.transaction import INPUTS, OUTPUTS, VALIDS


def number(value):
    if isinstance(value, int):
        return value
    return int(value, 2) if set(value.lower()) <= {'0', '1'} else None


def choose(requests, pointer, count):
    return next((k % count for k in range(pointer, pointer + count) if k % count in requests), None)


class EventBarrierModel:
    def __init__(self, c):
        self.c = c
        self.reset()

    def reset(self):
        c = self.c
        self.policy = None
        self.counts = [0] * c.NUM_EVENTS
        self.waits = [None] * c.NUM_WAIT_SLOTS
        self.barriers = [dict(enable=0, expected=0, arrived=0, context=0, tag=0,
                              event_enable=0, event=0, generation=0) for _ in range(c.NUM_BARRIERS)]
        self.results = []
        self.releases = []
        self.pointers = [0, 0, 0]
        self.error = 0
        self.fatal = 0
        self.pulses = dict.fromkeys(('o_config_accepted', 'o_config_rejected', 'o_post_accepted',
            'o_post_rejected', 'o_ack_accepted', 'o_ack_rejected', 'o_wait_armed', 'o_wait_rejected',
            'o_wait_canceled', 'o_wait_cancel_not_found', 'o_barrier_configured',
            'o_barrier_config_rejected', 'o_barrier_arrival_accepted', 'o_barrier_arrival_rejected',
            'o_flushed', 'o_event_post', 'o_event_ack', 'o_event_wait_complete',
            'o_event_barrier_arrival', 'o_event_barrier_release', 'o_event_duplicate_arrival',
            'o_event_mutation_stall'), 0)
        self.fault = False

    def evaluate(self, raw):
        c = self.c
        p = {name: number(raw[name]) for name in INPUTS}
        known = lambda *names: all(p[name] is not None for name in names)
        valid = lambda name: p[name] == 1
        out = dict.fromkeys(OUTPUTS, 0)
        out.update(self.pulses)
        enable = self.policy['enable'] if self.policy else 0
        context = self.policy['context'] if self.policy else 0
        pending = sum(1 << k for k, value in enumerate(self.counts) if value)
        maximum = (1 << c.EVENT_COUNT_WIDTH) - 1
        idle = not (pending or any(self.waits) or self.results or self.releases or
                    any(b['arrived'] for b in self.barriers))
        other = any(p[name] != 0 for name in VALIDS if name != 'i_config_valid')
        controls = known(*VALIDS, 'i_flush', 'i_error_clear', 'i_wait_result_ready',
                         'i_barrier_release_ready')
        healthy = valid('i_rstb') and not self.fatal and not self.fault
        run = healthy and controls and p['i_flush'] == 0
        plan = dict(p=p, run=run, error=0, events=[], mutation=None)
        out.update(o_policy_valid=int(self.policy is not None), o_active_context_id=context,
                   o_event_pending=pending,
                   o_event_saturated=sum(1 << k for k, n in enumerate(self.counts) if n == maximum),
                   o_event_count=sum(n << (k * c.EVENT_COUNT_WIDTH) for k, n in enumerate(self.counts)),
                   o_wait_slot_active=sum(1 << k for k, w in enumerate(self.waits) if w),
                   o_barrier_enable=sum(b['enable'] << k for k, b in enumerate(self.barriers)),
                   o_barrier_arrived=sum(b['arrived'] << (k * c.MAX_PARTICIPANTS)
                                         for k, b in enumerate(self.barriers)),
                   o_barrier_generation=sum(b['generation'] << (k * c.GENERATION_WIDTH)
                                            for k, b in enumerate(self.barriers)),
                   o_wait_result_occupancy=len(self.results), o_barrier_release_occupancy=len(self.releases),
                   o_idle=int(idle and p['i_flush'] == 0 and not other),
                   o_quiescent=int(run and idle and not other and not valid('i_config_valid')),
                   o_error=int(bool(self.error)), o_error_code=self.error, o_fatal_error=self.fatal)
        if run:
            if self.results:
                out['o_wait_result_valid'] = 1
                out.update({'o_wait_result_' + key: value for key, value in self.results[0].items()})
            if self.releases:
                out['o_barrier_release_valid'] = 1
                out.update({'o_barrier_release_' + key: value for key, value in self.releases[0].items()})
        if healthy and valid('i_flush'):
            plan['flush'] = True
            return out, plan
        if (not controls or p['i_rstb'] is None) and p['i_rstb'] != 0:
            plan['error'] = 10
        if not run:
            return out, plan
        out['o_config_ready'] = int(idle and not other)
        if valid('i_config_valid') and out['o_config_ready']:
            legal = known('i_config_context_id', 'i_config_event_enable')
            plan['config'] = legal
            plan['error'] = 0 if legal else 1
            return out, plan
        owner = lambda name: self.policy is not None and p[name] == context
        enabled_id = lambda name: p[name] is not None and p[name] < c.NUM_EVENTS and bool(enable & (1 << p[name]))
        post_legal = owner('i_post_context_id') and enabled_id('i_post_event_id')
        ack_legal = owner('i_ack_context_id') and enabled_id('i_ack_event_id') and p['i_ack_mode'] in (0, 1)
        ack_legal = ack_legal and bool(self.counts[p['i_ack_event_id']])
        slot = p['i_wait_slot']
        slot_range = slot is not None and slot < c.NUM_WAIT_SLOTS
        out['o_wait_ready'] = int(not slot_range or self.waits[slot] is None)
        arm = valid('i_wait_valid') and out['o_wait_ready']
        arm_legal = slot_range and known('i_wait_mode', 'i_wait_event_mask', 'i_wait_consume',
            'i_wait_context_id', 'i_wait_tag') and owner('i_wait_context_id')
        arm_legal = arm_legal and p['i_wait_mode'] in (0, 1) and bool(p['i_wait_event_mask']) and \
            p['i_wait_event_mask'] & ~enable == 0 and (not p['i_wait_consume'] or c.SUPPORT_WAIT_CONSUME)
        if arm:
            plan['arm'] = bool(arm_legal)
            if not arm_legal:
                plan['error'] = 4
        cancel_slot = p['i_wait_cancel_slot']
        cancel = None
        if c.SUPPORT_WAIT_CANCEL and known('i_wait_cancel_slot', 'i_wait_cancel_context_id',
                                           'i_wait_cancel_tag') and cancel_slot < c.NUM_WAIT_SLOTS:
            w = self.waits[cancel_slot]
            if w and owner('i_wait_cancel_context_id') and p['i_wait_cancel_context_id'] == w['context_id'] and p['i_wait_cancel_tag'] == w['tag']:
                cancel = cancel_slot
        result_space = len(self.results) < c.WAIT_RESULT_QUEUE_DEPTH or valid('i_wait_result_ready')
        matches = {}
        for k, w in enumerate(self.waits):
            if not w or valid('i_wait_cancel_valid') and cancel == k:
                continue
            available = pending & w['mask']
            if available and (w['mode'] == 0 or available == w['mask']):
                matches[k] = available & -available if w['mode'] == 0 else w['mask']
        selected = choose(matches if result_space else {}, self.pointers[0], c.NUM_WAIT_SLOTS)
        creators = []
        if selected is not None:
            creators.append(0)
        if cancel is not None and valid('i_wait_cancel_valid') and result_space:
            creators.append(1)
        creator = choose(creators, self.pointers[1], 2)
        bc = p['i_barrier_config_id']
        bc_range = bc is not None and bc < c.NUM_BARRIERS
        bcfg = self.barriers[bc] if bc_range else None
        bc_available = not bc_range or (not bcfg['arrived'] and not any(
            r['id'] == bc and r['generation'] == bcfg['generation'] for r in self.releases))
        out['o_barrier_config_ready'] = int(bc_available)
        bc_fire = valid('i_barrier_config_valid') and bc_available
        bc_legal = bc_range and known('i_barrier_config_enable', 'i_barrier_expected_mask',
            'i_barrier_context_id', 'i_barrier_tag', 'i_barrier_release_event_enable',
            'i_barrier_release_event_id') and owner('i_barrier_context_id')
        bc_legal = bc_legal and (not p['i_barrier_config_enable'] or bool(p['i_barrier_expected_mask'])) and \
            (not p['i_barrier_release_event_enable'] or c.SUPPORT_BARRIER_EVENTS and enabled_id('i_barrier_release_event_id'))
        if bc_fire:
            plan['barrier_config'] = bool(bc_legal)
        arrival = p['i_barrier_arrival_id']
        participant = p['i_barrier_participant_id']
        a_known = known('i_barrier_arrival_id', 'i_barrier_participant_id',
                        'i_barrier_arrival_generation', 'i_barrier_arrival_context_id')
        b = self.barriers[arrival] if a_known and arrival < c.NUM_BARRIERS else None
        a_valid = valid('i_barrier_arrival_valid')
        duplicate = stale = False
        a_legal = final = event = False
        new_arrived = 0
        if b and participant < c.MAX_PARTICIPANTS and a_valid:
            bit = 1 << participant
            duplicate = bool(b['arrived'] & bit)
            stale = p['i_barrier_arrival_generation'] != b['generation']
            new_arrived = b['arrived'] | bit
            a_legal = b['enable'] and owner('i_barrier_arrival_context_id') and \
                p['i_barrier_arrival_context_id'] == b['context'] and bool(b['expected'] & bit) and not duplicate and not stale
            final = new_arrived == b['expected']
            event = bool(b['event_enable'])
        blocked = bc_fire and bc == arrival
        release_space = len(self.releases) < c.BARRIER_RELEASE_QUEUE_DEPTH or valid('i_barrier_release_ready')
        request = []
        if valid('i_post_valid') and (not post_legal or self.counts[p['i_post_event_id']] < maximum):
            request.append(0)
        if valid('i_ack_valid'):
            request.append(1)
        if creator == 0 and self.waits[selected]['consume']:
            request.append(2)
        if a_valid and not blocked and a_legal and final and event and release_space and self.counts[b['event']] < maximum:
            request.append(3)
        mutation = choose(request, self.pointers[2], 4)
        plan['mutation'] = mutation
        out['o_post_ready'] = int(mutation == 0)
        out['o_ack_ready'] = int(mutation == 1)
        if mutation == 0:
            plan['post'] = bool(post_legal)
            if not post_legal:
                plan['error'] = 2
        if mutation == 1:
            plan['ack'] = bool(ack_legal)
            if not ack_legal:
                plan['error'] = 3
        if arm and not arm_legal:
            plan['error'] = 4
        completion = creator == 0 and (not self.waits[selected]['consume'] or mutation == 2)
        canceled = creator == 1
        if completion:
            w = self.waits[selected]
            plan['complete'] = selected
            plan['result'] = dict(slot=selected, mode=w['mode'], matched_mask=matches[selected],
                consumed_mask=matches[selected] if w['consume'] else 0,
                context_id=w['context_id'], tag=w['tag'], status=0)
        out['o_wait_cancel_ready'] = int(cancel is None or canceled)
        if canceled:
            w = self.waits[cancel]
            plan['cancel'] = cancel
            plan['result'] = dict(slot=cancel, mode=w['mode'], matched_mask=0, consumed_mask=0,
                                  context_id=w['context_id'], tag=w['tag'], status=1)
        if valid('i_wait_cancel_valid') and cancel is None:
            plan['cancel_miss'] = True
            plan['error'] = 5
        # Error priority follows the public deterministic channel order.
        if bc_fire and not bc_legal:
            plan['error'] = 6
        out['o_barrier_arrival_ready'] = int(not blocked and
            (not a_legal or not final or release_space and (not event or mutation == 3)))
        if a_valid and out['o_barrier_arrival_ready']:
            plan['arrival'] = bool(a_legal)
            plan['arrived'] = new_arrived
            plan['duplicate'] = duplicate
            if not a_legal:
                plan['error'] = 9 if stale else 8 if duplicate else 7
            elif final:
                plan['release'] = dict(id=arrival, generation=b['generation'], context_id=b['context'],
                    tag=b['tag'], participants=b['expected'], event_enable=int(event), event_id=b['event'] if event else 0)
        plan['stall'] = bool(valid('i_post_valid') and mutation != 0 or valid('i_ack_valid') and mutation != 1 or
            creator == 0 and self.waits[selected]['consume'] and not completion or
            a_valid and not blocked and a_legal and final and event and 'release' not in plan)
        return out, plan

    def step(self, raw, edge):
        p = {name: number(raw[name]) for name in INPUTS}
        if p['i_rstb'] == 0 and (edge or self.c.ASYNC_RESET):
            self.reset()
            return {'reset'}
        if not edge:
            return set()
        _, plan = self.evaluate(raw)
        p = plan['p']
        events = set()
        self.pulses = dict.fromkeys(self.pulses, 0)
        def pulse(name):
            self.pulses['o_' + name] = 1
            events.add(name)
        if self.fault:
            self.error, self.fatal = 11, 1
        if plan.get('flush'):
            self.counts = [0] * self.c.NUM_EVENTS
            self.waits = [None] * self.c.NUM_WAIT_SLOTS
            self.results.clear()
            self.releases.clear()
            for b in self.barriers:
                b['arrived'] = 0
                if b['enable']:
                    b['generation'] = (b['generation'] + 1) % (1 << self.c.GENERATION_WIDTH)
            self.pointers = [0, 0, 0]
            self.error = 0
            pulse('flushed')
            return events
        if not self.fatal:
            if p['i_error_clear'] == 1 and self.evaluate(raw)[0]['o_quiescent']:
                self.error = 0
            elif not self.error and plan['error']:
                self.error = plan['error']
        if not plan['run']:
            return events
        if self.results and p['i_wait_result_ready'] == 1:
            self.results.pop(0)
            events.add('result_pop')
        if self.releases and p['i_barrier_release_ready'] == 1:
            self.releases.pop(0)
            events.add('release_pop')
        if 'config' in plan:
            pulse('config_accepted' if plan['config'] else 'config_rejected')
            if plan['config']:
                self.policy = dict(context=p['i_config_context_id'], enable=p['i_config_event_enable'])
            return events
        if plan['mutation'] is not None:
            self.pointers[2] = (plan['mutation'] + 1) % 4
        if 'post' in plan:
            pulse('post_accepted' if plan['post'] else 'post_rejected')
            if plan['post']:
                self.counts[p['i_post_event_id']] += 1
                pulse('event_post')
        if 'ack' in plan:
            pulse('ack_accepted' if plan['ack'] else 'ack_rejected')
            if plan['ack']:
                k = p['i_ack_event_id']
                self.counts[k] = self.counts[k] - 1 if p['i_ack_mode'] == 0 else 0
                pulse('event_ack')
        if 'arm' in plan:
            pulse('wait_armed' if plan['arm'] else 'wait_rejected')
            if plan['arm']:
                self.waits[p['i_wait_slot']] = dict(mode=p['i_wait_mode'], mask=p['i_wait_event_mask'],
                    consume=p['i_wait_consume'], context_id=p['i_wait_context_id'], tag=p['i_wait_tag'])
        if 'complete' in plan:
            k = plan['complete']
            self.waits[k] = None
            self.pointers[0] = (k + 1) % self.c.NUM_WAIT_SLOTS
            self.pointers[1] = 1
            pulse('event_wait_complete')
            mask = plan['result']['consumed_mask']
            self.counts = [value - int(bool(mask & (1 << k))) for k, value in enumerate(self.counts)]
        if 'cancel' in plan:
            self.waits[plan['cancel']] = None
            self.pointers[1] = 0
            pulse('wait_canceled')
        if 'result' in plan:
            self.results.append(plan['result'])
        if plan.get('cancel_miss'):
            pulse('wait_cancel_not_found')
        if 'barrier_config' in plan:
            pulse('barrier_configured' if plan['barrier_config'] else 'barrier_config_rejected')
            if plan['barrier_config']:
                b = self.barriers[p['i_barrier_config_id']]
                b.update(enable=p['i_barrier_config_enable'], expected=p['i_barrier_expected_mask'],
                    arrived=0, context=p['i_barrier_context_id'], tag=p['i_barrier_tag'],
                    event_enable=p['i_barrier_release_event_enable'], event=p['i_barrier_release_event_id'])
        if 'arrival' in plan:
            pulse('barrier_arrival_accepted' if plan['arrival'] else 'barrier_arrival_rejected')
            if plan['arrival']:
                b = self.barriers[p['i_barrier_arrival_id']]
                b['arrived'] = plan['arrived']
                pulse('event_barrier_arrival')
            elif plan['duplicate']:
                pulse('event_duplicate_arrival')
        if 'release' in plan:
            r = plan['release']
            self.releases.append(r)
            b = self.barriers[r['id']]
            b['arrived'] = 0
            b['generation'] = (b['generation'] + 1) % (1 << self.c.GENERATION_WIDTH)
            if r['event_enable']:
                self.counts[r['event_id']] += 1
                pulse('event_post')
            pulse('event_barrier_release')
        if plan['stall']:
            pulse('event_mutation_stall')
        assert all(0 <= n < (1 << self.c.EVENT_COUNT_WIDTH) for n in self.counts)
        return events
