"""Directed lifecycle contracts plus seeded adversarial multi-owner traffic."""
import random
from pyuvm import uvm_sequence
from runtime_controller.config import CODES, WIDTHS, pack, unpack
from runtime_controller.model import key, lane
from runtime_controller.peers import Peers
from runtime_controller.transaction import INPUTS, RuntimeItem

CMD, EP, ACK = (CODES[n] for n in ('command', 'endpoint', 'ack_status'))
STATE, NOTICE, ERR = (CODES[n] for n in ('kernel_state', 'notice_status', 'error'))
POL, EV = (CODES[n] for n in ('policy_command', 'event_type'))


class RuntimeSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('runtime_contracts')
        self.c = config
        self.p = config.parameters
        self.rng = random.Random(config.seed)
        self.peers = Peers(self.rng)
        self.ports = dict.fromkeys(INPUTS, 0)
        self.ports |= dict(i_clock_ready=1, i_power_good=1, i_admission_ready=1,
                          i_result_ready=1, i_policy_response_ready=1, i_runtime_event_ready=1)
        self.last = None
        self.next_id = 0
        self.policy_tag = 0
        self.event_sequences = {}

    async def step(self, **changes):
        self.ports.update(changes)
        self.peers.present = self.last
        self.peers.drive(self.ports)
        item = RuntimeItem(self.ports)
        await self.start_item(item)
        await self.finish_item(item)
        self.peers.observe(item.pre)
        self.last = item.post
        return item

    async def wait(self, predicate, *, limit=5000, description='condition'):
        for _ in range(limit):
            if self.last is not None and predicate():
                return
            await self.step()
        raise AssertionError((f'Timeout waiting for {description}', self.last,
                              self.scoreboard.admissions[-2:], self.scoreboard.actions[-3:]))

    def record(self, kernel):
        if self.last is None:
            return None
        for s in range(self.p['MAX_PENDING_KERNELS']):
            if self.last['o_record_valid'] >> s & 1:
                identity = lane(self.last['o_record_identity'], s, WIDTHS['identity'])
                if unpack('identity', identity)['kernel_id'] == kernel:
                    return dict(slot=s, identity=identity,
                                state=lane(self.last['o_record_state'], s, 5),
                                mask=lane(self.last['o_record_cluster_mask'], s, 16),
                                metrics=lane(self.last['o_record_snapshot_metrics'], s, 256))
        return None

    def notice_for(self, kernel, *, result=False):
        records = self.scoreboard.results if result else self.scoreboard.admissions
        return next((n for n in reversed(records)
                     if unpack('identity', n['identity'])['kernel_id'] == kernel), None)

    async def running(self, kernel):
        await self.wait(lambda: (r := self.record(kernel)) and r['state'] == STATE['RUNNING'],
                        description=f'kernel {kernel} running')
        return self.record(kernel)

    async def result(self, kernel, status=NOTICE['SUCCEEDED'], error=None):
        await self.wait(lambda: self.notice_for(kernel, result=True), description=f'result {kernel}')
        result = self.notice_for(kernel, result=True)
        assert result['status'] == status, result
        if error is not None:
            assert result['error'] == error, result
        return result

    def descriptor(self, *, mask=None, owner=None, flags=None, variants=None, **changes):
        self.next_id += 1
        k = self.next_id
        if mask is None:
            mask = 1 << ((k - 1) % self.p['NUM_CLUSTERS'])
        if variants is None:
            variants = [mask]
        records = []
        for v, cluster_mask in enumerate(variants):
            records.append(pack('variant', package_id=0x10000 + k, mapping_id=v + 1,
                                cluster_mask=cluster_mask, cluster_count=cluster_mask.bit_count(),
                                required_capabilities=1, architecture_id=self.p['ARCHITECTURE_ID'],
                                proof_id=self.p['PROTOCOL_PROOF_ID']))
        services = 63 if self.p['ENABLE_POWER_POLICY'] else 31
        if flags is None:
            flags = 0x8e | int(bool(self.p['ENABLE_SAFE_SUSPEND']))
        return dict(owner_id=owner or self.c.owners[(k - 1) % len(self.c.owners)],
                    kernel_id=k, descriptor_id=k + 100, descriptor_generation=1,
                    contract_version=1, integrity_valid=1, admission_class=0, priority=0,
                    deadline=0, estimated_cycles=20, required_clusters=mask.bit_count(),
                    preferred_clusters=mask.bit_count(), required_capabilities=1,
                    variant_count=len(records), variant_records=sum(v << (i * 256)
                                                                 for i, v in enumerate(records)),
                    resource_record=pack('resource', services=services,
                                         event_mask=1 << ((k - 1) % self.p['MAX_EVENT_NAMESPACES']),
                                         counter_mask=1 << ((k - 1) % 16),
                                         memory_bandwidth=10, noc_bandwidth=10, power=10),
                    qos_record=pack('qos'), power_record=pack('power', budget=100,
                        profile_mask=(1 << self.p['MAX_POWER_PROFILES']) - 1),
                    lifecycle_record=pack('lifecycle', flags=flags, resume_cookie=0x12345678),
                    tag=1000 + k) | changes

    async def submit(self, descriptor):
        ports = {'i_submit_' + name: value for name, value in descriptor.items()}
        for _ in range(5000):
            item = await self.step(i_submit_valid=1, **ports)
            if item.pre['o_submit_ready']:
                break
        else:
            raise AssertionError('Submission never accepted')
        await self.step(i_submit_valid=0)
        return descriptor['kernel_id']

    async def event(self, kernel, event_type, *, identity=None, sequence=None, source=None,
                    cluster_mask=None):
        r = self.record(kernel)
        identity = r['identity'] if identity is None else identity
        source = self.p['NUM_CLUSTERS'] if source is None else source
        event_key = (identity, source)
        expected = self.event_sequences.get(event_key, 0)
        sequence = expected if sequence is None else sequence
        if sequence == expected:
            self.event_sequences[event_key] = expected + 1
        bits = pack('event', identity=identity, event_type=EV[event_type], source=source,
                    cluster_mask=r['mask'] if cluster_mask is None else cluster_mask,
                    sequence_id=sequence, timestamp=self.last['o_time'])
        while True:
            item = await self.step(i_event_valid=1, i_event_record=bits)
            if item.pre['o_event_ready']:
                break
        await self.step(i_event_valid=0)

    async def snapshot(self, kernel, generation, metrics, *, critical=0, identity=None, validity=15):
        identity = self.record(kernel)['identity'] if identity is None else identity
        bits = pack('snapshot', identity=identity, generation=generation,
                    timestamp=self.last['o_time'], validity=validity, metrics=metrics, critical=critical)
        while True:
            item = await self.step(i_snapshot_valid=1, i_snapshot_record=bits)
            if item.pre['o_snapshot_ready']:
                break
        await self.step(i_snapshot_valid=0)

    async def policy(self, command, kernel=None, *, wait=True, **changes):
        self.policy_tag += 1
        identity = self.record(kernel)['identity'] if kernel is not None else 0
        request = dict(identity=identity, command=POL[command], authorized=1, tag=self.policy_tag)
        bits = pack('policy', **(request | changes))
        for _ in range(5000):
            item = await self.step(i_policy_valid=1, i_policy_record=bits)
            if item.pre['o_policy_ready']:
                break
        else:
            raise AssertionError('Policy never accepted')
        await self.step(i_policy_valid=0)
        tag = self.policy_tag
        if wait:
            await self.wait(lambda: any(r['tag'] == tag for r in self.scoreboard.policy_replies),
                            description=f'policy reply {tag}')
            return next(r for r in self.scoreboard.policy_replies if r['tag'] == tag)
        return tag

    async def complete(self, kernel):
        await self.running(kernel)
        await self.event(kernel, 'COMPUTE_DONE')
        for _ in range(4):
            await self.step()
        assert self.notice_for(kernel, result=True) is None, 'Compute event completed external writes'
        await self.event(kernel, 'EXTERNAL_DONE')
        return await self.result(kernel)

    async def quiescent(self):
        await self.wait(lambda: self.last['o_quiescent'], description='quiescence')
        assert not self.last['o_recovery_required']
        assert self.last['o_clock_enable'] == 0

    async def reset(self):
        await self.step(i_rstb=0, i_submit_valid=0, i_policy_valid=0, i_event_valid=0,
                        i_snapshot_valid=0, i_reconcile_valid=0)
        await self.step()
        await self.step(i_rstb=1)
        assert self.last['o_recovery_required'] and not self.last['o_submit_ready']

    async def reconcile(self):
        await self.step(i_reconcile_valid=1, i_reconcile_clean=1,
                        i_reconcile_manifest=0x4d52540100000001,
                        i_reconcile_cluster_busy_mask=0, i_reconcile_service_busy=0,
                        i_reconcile_tag_base=0, i_reconcile_allocation_base=0,
                        i_reconcile_epoch_base=0)
        await self.step(i_reconcile_valid=0)
        assert not self.last['o_recovery_required'] and self.last['o_submit_ready']

    async def body(self):
        await self.reset()
        await self.step(i_reconcile_valid=1, i_reconcile_clean=1,
                        i_reconcile_cluster_busy_mask=1,
                        i_reconcile_manifest=0x4d52540100000001)
        assert self.last['o_recovery_required'] and not self.last['o_submit_ready']
        await self.step(i_reconcile_valid=0)
        await self.reconcile()
        self.coverage.hit('reset_requires_remote_clean_proof')
        k = await self.submit(self.descriptor())
        await self.complete(k)
        await self.quiescent()
        self.coverage.hit('acknowledged_launch_visibility_and_reverse_release')
        await self.rejections()
        await self.queue_and_cancel()
        await self.failures_and_timeouts()
        await self.events_and_snapshots()
        await self.policies_and_suspend()
        await self.concurrency_and_backpressure()
        await self.immediate_and_early_terminals()
        await self.bounded_queues_and_readiness()
        await self.observability()
        await self.scheduler_and_budgets()
        await self.exclusive_resource_conflicts()
        await self.partial_fault_and_reset()
        await self.random_traffic()
        await self.protection_and_exhaustion()

    async def rejections(self):
        cases = [dict(owner_id=0xffff), dict(contract_version=2), dict(integrity_valid=0),
                 dict(priority=self.p['NUM_PRIORITY_LEVELS']), dict(variant_count=0),
                 dict(required_clusters=0), dict(preferred_clusters=0),
                 dict(resource_record=pack('resource', services=0)),
                 dict(power_record=pack('power', budget=1, profile_mask=1)),
                 dict(qos_record=pack('qos', flags=1)),
                 dict(lifecycle_record=pack('lifecycle', flags=0x20)),
                 dict(power_record=pack('power', budget=100, profile_mask=1, energy_budget=1))]
        if not self.p['ENABLE_QOS']:
            cases.append(dict(admission_class=1))
        for changes in cases:
            descriptor = self.descriptor(**changes)
            k = await self.submit(descriptor)
            await self.wait(lambda: self.notice_for(k), description='descriptor rejection')
            rejection = self.notice_for(k)
            assert rejection['status'] == NOTICE['REJECTED'] and rejection['error'] != ERR['NONE']
            assert self.notice_for(k, result=True) is None
            await self.quiescent()
        # Both the proof and exact precompiled mapping must belong to this platform.
        for field, value in [('proof_id', self.p['PROTOCOL_PROOF_ID'] + 1),
                             ('architecture_id', self.p['ARCHITECTURE_ID'] + 1),
                             ('required_capabilities', 0x80000000), ('cluster_mask', 0)]:
            descriptor = self.descriptor()
            variant = unpack('variant', descriptor['variant_records'])
            variant[field] = value
            if field == 'required_capabilities':
                # Available capabilities may include this bit; mismatch the descriptor instead.
                descriptor['required_capabilities'] = 3
                variant[field] = 1
            descriptor['variant_records'] = pack('variant', **variant)
            k = await self.submit(descriptor)
            await self.wait(lambda: self.notice_for(k))
            assert self.notice_for(k)['status'] == NOTICE['REJECTED']
            await self.quiescent()
        self.coverage.hit('malformed_unknown_owner_proof_and_unsupported_descriptor_rejection')

    async def queue_and_cancel(self):
        self.peers.block.add(EP['ARRAY'])
        first = await self.submit(self.descriptor(mask=1))
        await self.wait(lambda: self.last['o_array_runtime_valid'])
        held = self.last['o_array_runtime_record']
        tag = await self.policy('CANCEL', first, wait=False)
        for _ in range(8):
            await self.step()
            assert self.last['o_array_runtime_valid'] and self.last['o_array_runtime_record'] == held
        self.peers.block.clear()
        await self.wait(lambda: self.notice_for(first))
        assert self.notice_for(first)['status'] == NOTICE['CANCELED']
        await self.wait(lambda: any(r['tag'] == tag for r in self.scoreboard.policy_replies))
        assert self.notice_for(first, result=True) is None
        await self.quiescent()
        self.coverage.hit('cancel_retains_stalled_command_until_matching_terminal_and_rollback')
        # Occupy a cluster and cancel a disjoint descriptor that cannot be admitted.
        running = await self.submit(self.descriptor(mask=1))
        await self.running(running)
        queued = await self.submit(self.descriptor(mask=1))
        await self.wait(lambda: self.record(queued)['state'] == STATE['WAIT_RESOURCES'])
        reply = await self.policy('CANCEL', queued)
        assert reply['status'] == ACK['OK']
        await self.wait(lambda: self.notice_for(queued))
        assert self.notice_for(queued)['status'] == NOTICE['CANCELED']
        assert self.notice_for(queued, result=True) is None
        # Same live owner/kernel with a different descriptor identity must reject.
        original = self.scoreboard.ledger.records[key(self.record(running)['identity'])].descriptor
        duplicate = self.descriptor(owner=original['owner_id'], kernel_id=running)
        duplicate_id = duplicate['descriptor_id']
        await self.submit(duplicate)
        await self.wait(lambda: any(unpack('identity', n['identity'])['descriptor_id'] == duplicate_id
                                   for n in self.scoreboard.admissions))
        rejection = next(n for n in self.scoreboard.admissions
                         if unpack('identity', n['identity'])['descriptor_id'] == duplicate_id)
        assert rejection['status'] == NOTICE['REJECTED'] and rejection['error'] == ERR['DUPLICATE']
        await self.complete(running)
        await self.quiescent()
        self.coverage.hit('resource_wait_cancel_duplicate_identity_and_exactly_once_admission')

    async def failures_and_timeouts(self):
        points = [(EP['ARRAY'], 'ALLOCATE')]
        services = range(6) if self.p['ENABLE_POWER_POLICY'] else range(5)
        points += [(ep, 'RESERVE') for ep in services]
        points += [(EP['CONFIG'], cmd) for cmd in ('LOAD', 'VALIDATE', 'PREPARE')]
        points += [(EP['ARRAY'], 'COMMIT'), (EP['DMA'], 'ACTIVATE'), (EP['ARRAY'], 'START')]
        if self.p['ENABLE_POWER_POLICY']:
            points.append((EP['POWER'], 'WAKE'))
        for failed_ep, failed_cmd in points:
            injected = []
            def fail(ep, action):
                if not injected and ep == failed_ep and action['command'] == CMD[failed_cmd]:
                    injected.append(action['tag'])
                    return dict(status=ACK['NO_EFFECT'], error=ERR['BACKEND'])
            self.peers.rule = fail
            k = await self.submit(self.descriptor())
            await self.wait(lambda: self.notice_for(k))
            if self.notice_for(k)['status'] == NOTICE['ADMITTED']:
                await self.result(k, NOTICE['FAILED'], ERR['BACKEND'])
            else:
                assert self.notice_for(k)['status'] == NOTICE['FAILED']
            assert len(injected) == 1
            await self.quiescent()
        self.peers.rule = None
        self.coverage.hit('no_effect_failure_at_each_launch_boundary_rolls_back_reverse_order')
        for command in ('LOAD', 'START'):
            self.peers.delay = lambda ep, action: 32 if action['command'] == CMD[command] else 1
            lifecycle = pack('lifecycle', flags=0x8e, action_timeout=12)
            k = await self.submit(self.descriptor(lifecycle_record=lifecycle))
            await self.wait(lambda: self.last['o_action_timed_out'], description='action timeout')
            action = self.last['o_action_record']
            mask = self.last['o_cluster_reserved_mask']
            assert mask and self.last['o_recovery_required']
            for _ in range(5):
                await self.step()
                assert self.last['o_action_timed_out'] and self.last['o_action_record'] == action
                assert self.last['o_cluster_reserved_mask'] == mask
                assert self.notice_for(k, result=True) is None
            await self.result(k, NOTICE['FAILED'], ERR['TIMEOUT'])
            await self.quiescent()
        self.peers.delay = None
        self.coverage.hit('timeout_keeps_tag_and_resources_late_success_rolls_back_or_aborts')

    async def events_and_snapshots(self):
        k = await self.submit(self.descriptor())
        await self.running(k)
        original = self.record(k)['identity']
        changed = unpack('identity', original)
        changed['owner_id'] ^= 0x8000
        await self.event(k, 'COMPUTE_DONE', identity=pack('identity', **changed))
        await self.event(k, 'INPUT_READY')
        await self.event(k, 'INPUT_READY', sequence=0)
        await self.step()
        assert self.record(k)['state'] == STATE['RUNNING']
        if self.p['ENABLE_COUNTER_FEEDBACK']:
            await self.snapshot(k, 1, 0x123456789abcdef)
            await self.wait(lambda: self.record(k)['metrics'] == 0x123456789abcdef)
            await self.snapshot(k, 1, 0xbad, critical=1)
            await self.snapshot(k, 2, 0xbad, identity=pack('identity', **changed), critical=1)
            await self.snapshot(k, 2, 0xbad, validity=7, critical=1)
            for _ in range(3):
                await self.step()
            assert self.record(k)['metrics'] == 0x123456789abcdef
            await self.snapshot(k, 3, 0xabcdef, critical=1)
            await self.wait(lambda: self.record(k)['metrics'] == 0xabcdef)
            await self.snapshot(k, 4, 0x3333)
            for _ in range(3):
                await self.step()
            assert self.record(k)['metrics'] == 0xabcdef
            for _ in range(self.p['POLICY_SAMPLE_INTERVAL']):
                await self.step()
            await self.snapshot(k, 4, 0x3333)
            await self.wait(lambda: self.record(k)['metrics'] == 0x3333)
            self.coverage.hit('coherent_snapshot_identity_generation_validity_and_critical_override')
        if self.peers.last:
            self.peers.foreign.append(self.peers.last)
            for _ in range(4):
                await self.step()
            assert self.record(k)['state'] == STATE['RUNNING']
        await self.complete(k)
        await self.quiescent()
        self.coverage.hit('foreign_duplicate_events_and_terminal_responses_cannot_complete_or_release')
        k = await self.submit(self.descriptor())
        await self.running(k)
        await self.event(k, 'INPUT_READY', sequence=1)
        await self.wait(lambda: self.last['o_recovery_required'])
        assert self.record(k)['state'] == STATE['ERROR']
        mask = self.last['o_cluster_reserved_mask']
        for _ in range(4):
            await self.step()
            assert self.last['o_cluster_reserved_mask'] == mask
        reply = await self.policy('FORCE_ABORT', k, destructive=1)
        assert reply['status'] == ACK['OK']
        await self.result(k, NOTICE['FAILED'], ERR['SEQUENCE'])
        await self.quiescent()
        self.coverage.hit('event_sequence_gap_containment_requires_authorized_destructive_recovery')

    async def policies_and_suspend(self):
        reply = await self.policy('DISABLE', authorized=0)
        assert reply['error'] == ERR['AUTHORIZATION'] and self.last['o_submit_ready']
        reply = await self.policy('DISABLE')
        assert reply['status'] == ACK['OK']
        d = self.descriptor()
        for _ in range(4):
            item = await self.step(i_submit_valid=1, **{'i_submit_' + n: v for n, v in d.items()})
            assert not item.pre['o_submit_ready']
        await self.step(i_submit_valid=0)
        await self.policy('ENABLE')
        k = await self.submit(self.descriptor())
        await self.running(k)
        reply = await self.policy('QUERY', k, authorized=0)
        assert reply['error'] == ERR['AUTHORIZATION']
        reply = await self.policy('QUERY', k)
        assert reply['status'] == ACK['OK'] and reply['state'] == STATE['RUNNING']
        reply = await self.policy('CANCEL', k)
        assert reply['error'] == ERR['UNSUPPORTED']
        if self.p['ENABLE_SAFE_SUSPEND']:
            old = self.record(k)
            reply = await self.policy('REQUEST_SUSPEND', k)
            assert reply['status'] == ACK['OK'] and self.record(k)['state'] == STATE['SUSPENDED']
            assert self.last['o_cluster_reserved_mask'] & old['mask'] == old['mask']
            reply = await self.policy('REQUEST_RESUME', k, resume_cookie=0)
            assert reply['error'] == ERR['IDENTITY']
            reply = await self.policy('REQUEST_RESUME', k, resume_cookie=0x12345678)
            assert reply['status'] == ACK['OK']
            current = self.record(k)
            assert unpack('identity', current['identity'])['epoch'] > unpack('identity', old['identity'])['epoch']
            await self.event(k, 'COMPUTE_DONE', identity=old['identity'])
            for _ in range(3):
                await self.step()
            assert self.record(k)['state'] == STATE['RUNNING']
            self.coverage.hit('safe_preserved_suspend_cookie_resume_fresh_epoch_and_old_event_quarantine')
        else:
            reply = await self.policy('REQUEST_SUSPEND', k)
            assert reply['error'] == ERR['UNSUPPORTED']
        await self.complete(k)
        await self.quiescent()
        self.coverage.hit('authorized_policy_enable_disable_query_and_destructive_cancel_bounds')

    async def concurrency_and_backpressure(self):
        count = self.p['MAX_ACTIVE_KERNELS']
        kernels = []
        for c in range(count):
            kernels.append(await self.submit(self.descriptor(mask=1 << c,
                admission_class=int(bool(self.p['ENABLE_QOS'])))))
        for k in kernels:
            await self.running(k)
        assert self.last['o_active_count'] == count
        assert self.last['o_cluster_reserved_mask'] == (1 << count) - 1
        # Slow all consumers while events and terminal cleanup continue. Diagnostic
        # output must never be used as a release prerequisite.
        await self.step(i_result_ready=0, i_runtime_event_ready=0, i_policy_response_ready=0)
        for k in kernels:
            await self.event(k, 'COMPUTE_DONE')
            await self.event(k, 'EXTERNAL_DONE')
        await self.wait(lambda: self.last['o_cluster_reserved_mask'] == 0,
                        description='release while results backpressured')
        for _ in range(8):
            await self.step()
        assert self.last['o_result_valid'] and not self.last['o_quiescent']
        await self.step(i_result_ready=1, i_runtime_event_ready=1, i_policy_response_ready=1)
        for k in kernels:
            await self.result(k)
        await self.quiescent()
        self.coverage.hit('disjoint_concurrent_reservations_and_held_results_do_not_delay_resource_release')
        # All descriptor inputs change after acceptance; queued immutable records
        # must still return the original identities, package selection and tags.
        self.peers.block.add(6)
        k = await self.submit(self.descriptor())
        await self.wait(lambda: self.last['o_array_runtime_valid'])
        saved = self.last['o_array_runtime_record']
        poison = self.descriptor(owner=0xffff)
        for _ in range(6):
            await self.step(**{'i_submit_' + n: v for n, v in poison.items()})
            assert self.last['o_array_runtime_record'] == saved
        self.peers.block.clear()
        await self.complete(k)
        await self.quiescent()
        self.coverage.hit('immutable_descriptor_snapshot_and_stable_action_backpressure')

    async def random_traffic(self):
        self.peers.random_ready = True
        kernels = []
        completed = set()
        remaining = self.c.random_cycles
        since = self.coverage.cycles
        while self.coverage.cycles - since < remaining:
            if len(kernels) < self.p['MAX_ACTIVE_KERNELS'] and self.rng.randrange(6) == 0:
                mask = 1 << (len(kernels) % self.p['NUM_CLUSTERS'])
                k = await self.submit(self.descriptor(mask=mask,
                    priority=self.rng.randrange(self.p['NUM_PRIORITY_LEVELS'])))
                kernels.append(k)
            for k in list(kernels):
                r = self.record(k)
                if r and r['state'] == STATE['RUNNING'] and k not in completed and self.rng.randrange(4) == 0:
                    await self.event(k, 'COMPUTE_DONE')
                    await self.event(k, 'EXTERNAL_DONE')
                    completed.add(k)
                if self.notice_for(k, result=True):
                    kernels.remove(k)
            await self.step(i_admission_ready=int(self.rng.randrange(4) != 0),
                            i_result_ready=int(self.rng.randrange(4) != 0),
                            i_runtime_event_ready=int(self.rng.randrange(3) != 0))
        await self.step(i_admission_ready=1, i_result_ready=1, i_runtime_event_ready=1)
        for _ in range(10000):
            for k in list(kernels):
                r = self.record(k)
                if r and r['state'] == STATE['RUNNING'] and k not in completed:
                    await self.event(k, 'COMPUTE_DONE')
                    await self.event(k, 'EXTERNAL_DONE')
                    completed.add(k)
                if self.notice_for(k, result=True):
                    kernels.remove(k)
            if not kernels:
                break
            await self.step()
        assert not kernels, ('Random campaign failed to drain', kernels)
        self.peers.random_ready = False
        await self.quiescent()
        self.coverage.random_transactions = remaining
        self.coverage.hit('seeded_random_latency_backpressure_multi_owner_lifecycles')

    async def scheduler_and_budgets(self):
        if self.p['MAX_PENDING_KERNELS'] >= 5 and self.p['NUM_PRIORITY_LEVELS'] > 1 and \
                self.p['HIGH_PRIORITY_BURST_LIMIT'] <= 2 and self.p['AGE_ESCALATION_CYCLES'] >= 4096:
            blocker = await self.submit(self.descriptor(mask=1))
            await self.running(blocker)
            low = await self.submit(self.descriptor(mask=1, priority=0))
            high = [await self.submit(self.descriptor(mask=1,
                    priority=self.p['NUM_PRIORITY_LEVELS'] - 1)) for _ in range(3)]
            await self.complete(blocker)
            expected = high[:self.p['HIGH_PRIORITY_BURST_LIMIT']] + [low] + \
                high[self.p['HIGH_PRIORITY_BURST_LIMIT']:]
            start = len(self.scoreboard.admissions)
            # A new admission can appear during the preceding kernel's cleanup.
            for k in expected:
                await self.running(k)
                unresolved = [n for n in self.scoreboard.admissions
                              if unpack('identity', n['identity'])['kernel_id'] in [low, *high]
                              and not self.notice_for(unpack('identity', n['identity'])['kernel_id'], result=True)]
                assert unresolved and unpack('identity', unresolved[0]['identity'])['kernel_id'] == k
                await self.complete(k)
            await self.quiescent()
            self.coverage.hit('eligible_priority_burst_limit_forces_lower_rank_with_round_robin_ties')
        if self.p['MAX_PENDING_KERNELS'] >= 3 and self.p['NUM_PRIORITY_LEVELS'] > 1 and \
                self.p['AGE_ESCALATION_CYCLES'] <= 16:
            blocker = await self.submit(self.descriptor(mask=1))
            await self.running(blocker)
            low = await self.submit(self.descriptor(mask=1, priority=0))
            for _ in range(self.p['AGE_ESCALATION_CYCLES'] * self.p['NUM_PRIORITY_LEVELS']):
                await self.step()
            high = await self.submit(self.descriptor(mask=1, priority=self.p['NUM_PRIORITY_LEVELS'] - 1))
            await self.complete(blocker)
            await self.running(low)
            assert self.notice_for(high) is None
            await self.complete(low)
            await self.complete(high)
            await self.quiescent()
            self.coverage.hit('saturating_aging_promotes_old_eligible_low_priority_kernel')
        if self.p['NUM_CLUSTERS'] >= 2 and self.p['MAX_ACTIVE_KERNELS'] >= 2:
            owner = self.c.owners[0]
            first = self.descriptor(mask=1, owner=owner)
            resources = unpack('resource', first['resource_record'])
            resources['memory_bandwidth'] = self.p['MEMORY_BANDWIDTH_CAPACITY'] * 3 // 4
            first['resource_record'] = pack('resource', **resources)
            k1 = await self.submit(first)
            await self.running(k1)
            second = self.descriptor(mask=2, owner=owner)
            resources = unpack('resource', second['resource_record'])
            resources['memory_bandwidth'] = self.p['MEMORY_BANDWIDTH_CAPACITY'] * 3 // 4
            second['resource_record'] = pack('resource', **resources)
            k2 = await self.submit(second)
            for _ in range(12):
                await self.step()
            assert self.record(k2)['state'] == STATE['WAIT_RESOURCES']
            reply = await self.policy('UPDATE_BOUNDS', identity=pack('identity', owner_id=owner),
                                      priority_limit=self.p['NUM_PRIORITY_LEVELS'] - 1,
                                      power_budget=1, bandwidth_budget=self.p['MEMORY_BANDWIDTH_CAPACITY'])
            assert reply['error'] == ERR['BUDGET']
            await self.complete(k1)
            await self.complete(k2)
            await self.quiescent()
            self.coverage.hit('aggregate_bandwidth_admission_and_owner_bounds_cannot_revoke_live_reservations')
        if self.p['MAX_PACKAGE_VARIANTS'] >= 2 and self.p['MAX_ACTIVE_KERNELS'] >= 2:
            first = await self.submit(self.descriptor(mask=1))
            await self.running(first)
            second = await self.submit(self.descriptor(mask=1, variants=[1, 2]))
            await self.running(second)
            assert self.record(second)['mask'] == 2
            await self.complete(second)
            await self.complete(first)
            await self.quiescent()
            self.coverage.hit('selects_free_exact_precompiled_alternate_without_online_mapping')

    async def partial_fault_and_reset(self):
        used = []
        def partial(ep, action):
            if ep == EP['DMA'] and action['command'] == CMD['RESERVE'] and not used:
                used.append(1)
                return dict(status=ACK['UNCERTAIN'], error=ERR['PARTIAL'])
        self.peers.rule = partial
        k = await self.submit(self.descriptor(mask=1))
        await self.wait(lambda: self.record(k)['state'] == STATE['ERROR'])
        held = self.last['o_cluster_reserved_mask']
        for _ in range(6):
            await self.step()
            assert self.last['o_cluster_reserved_mask'] == held and self.last['o_recovery_required']
        reply = await self.policy('FORCE_ABORT', k, destructive=0)
        assert reply['error'] == ERR['UNSUPPORTED']
        self.peers.rule = None
        await self.policy('FORCE_ABORT', k, destructive=1)
        await self.wait(lambda: self.notice_for(k))
        assert self.notice_for(k)['status'] == NOTICE['FAILED']
        await self.quiescent()
        self.coverage.hit('partial_backend_effects_are_contained_until_authorized_drain_and_release')
        # A live fault excludes this physical cluster from subsequent mappings.
        k = await self.submit(self.descriptor(mask=1))
        await self.running(k)
        await self.event(k, 'FAULT')
        await self.result(k, NOTICE['FAILED'], ERR['FAULTED'])
        assert self.last['o_cluster_fault_mask'] & 1
        if self.p['NUM_CLUSTERS'] >= 2 and self.p['MAX_PACKAGE_VARIANTS'] >= 2 and \
                self.p['ENABLE_FAULT_AWARE_ALLOCATION']:
            alt = await self.submit(self.descriptor(mask=1, variants=[1, 2]))
            await self.running(alt)
            assert self.record(alt)['mask'] == 2
            await self.complete(alt)
            self.coverage.hit('fault_aware_allocation_uses_healthy_precompiled_variant')
        await self.quiescent()
        # A controller-only reset leaves a separately modeled remote owner busy.
        await self.reset()
        self.peers.recover_system()
        await self.reconcile()
        self.peers.block.add(EP['CONFIG'])
        k = await self.submit(self.descriptor(mask=1))
        await self.wait(lambda: self.last['o_cluster_reserved_mask'] == 1 and
                        self.last['o_service_valid'] != 0)
        before = len(self.scoreboard.actions)
        await self.reset()
        await self.step(i_reconcile_valid=1, i_reconcile_clean=1,
                        i_reconcile_cluster_busy_mask=1, i_reconcile_service_busy=1)
        for _ in range(4):
            await self.step()
            assert self.last['o_recovery_required'] and not self.last['o_submit_ready']
        assert len(self.scoreboard.actions) == before, 'Local reset fabricated a remote release'
        await self.step(i_reconcile_valid=0)
        self.peers.block.clear()
        self.peers.recover_system()
        await self.reconcile()
        await self.quiescent()
        self.coverage.hit('local_reset_never_clears_remote_ownership_without_global_system_recovery')

    async def protection_and_exhaustion(self):
        # Optional protection is exercised on the actual stored control codeword.
        protection = self.p['CONTROL_PROTECTION']
        if protection:
            self.active['expect_fault'] = True
            self.active['inject'] = 1
            item = await self.step()
            if protection == 2:
                assert not item.post['o_integrity_error']
                await self.step()
                assert not self.last['o_recovery_required']
                self.coverage.hit('secded_single_control_bit_corrected_and_scrubbed')
                self.active['inject'] = 3
                await self.step()
            await self.step()
            assert self.last['o_recovery_required'] and not self.last['o_submit_ready']
            await self.reset()
            self.peers.recover_system()
            await self.reconcile()
            self.active['expect_fault'] = False
            self.coverage.hit('uncorrectable_protected_control_state_fails_closed_until_reset')
        # Tag exhaustion is fail-stop. No wrap, blind replay or ownership release.
        await self.reset()
        self.peers.recover_system()
        await self.step(i_reconcile_valid=1, i_reconcile_clean=1,
                        i_reconcile_cluster_busy_mask=0, i_reconcile_service_busy=0,
                        i_reconcile_tag_base=0xfffe, i_reconcile_allocation_base=0,
                        i_reconcile_epoch_base=0)
        await self.step(i_reconcile_valid=0)
        k = await self.submit(self.descriptor())
        await self.wait(lambda: self.last['o_error_code'] == ERR['EXHAUSTED'])
        assert self.last['o_cluster_reserved_mask'] and self.last['o_recovery_required']
        await self.reset()
        self.peers.recover_system()
        await self.reconcile()
        await self.quiescent()
        self.coverage.hit('tag_space_exhaustion_never_wraps_and_requires_clean_recovery')

    async def bounded_queues_and_readiness(self):
        # Fill all retained descriptor slots while an offered command is stalled.
        self.peers.block.add(6)
        kernels = [await self.submit(self.descriptor(mask=1))
                   for _ in range(self.p['MAX_PENDING_KERNELS'])]
        assert not self.last['o_submit_ready']
        await self.step()
        assert self.last['o_pending_count'] == self.p['MAX_PENDING_KERNELS']
        self.peers.block.clear()
        done = set()
        for _ in range(10000):
            for k in kernels:
                r = self.record(k)
                if r and r['state'] == STATE['RUNNING'] and k not in done:
                    await self.event(k, 'COMPUTE_DONE')
                    await self.event(k, 'EXTERNAL_DONE')
                    done.add(k)
            if all(self.notice_for(k, result=True) for k in kernels):
                break
            await self.step()
        assert len(done) == len(kernels)
        await self.quiescent()
        self.coverage.hit('bounded_pending_storage_backpressures_and_drains_without_losing_descriptors')
        # Admission can remain stalled while cancellation returns all resources.
        await self.step(i_admission_ready=0)
        k = await self.submit(self.descriptor())
        await self.wait(lambda: self.last['o_admission_valid'])
        bits = self.last['o_admission_record']
        await self.policy('CANCEL', k)
        await self.wait(lambda: self.last['o_cluster_reserved_mask'] == 0)
        assert not self.notice_for(k) and not self.notice_for(k, result=True)
        for _ in range(5):
            await self.step()
            assert self.last['o_admission_valid'] and self.last['o_admission_record'] == bits
        await self.step(i_admission_ready=1)
        await self.result(k, NOTICE['CANCELED'])
        await self.quiescent()
        self.coverage.hit('held_admission_remains_immutable_through_cancel_and_precedes_terminal_result')
        # Readiness events are needed when initial input/output credits are absent.
        flags = 0x88 | int(bool(self.p['ENABLE_SAFE_SUSPEND']))
        k = await self.submit(self.descriptor(flags=flags))
        await self.wait(lambda: self.record(k)['state'] == STATE['READY'])
        identity = self.record(k)['identity']
        for _ in range(8):
            await self.step()
            assert self.record(k)['state'] == STATE['READY']
        await self.event(k, 'INPUT_READY')
        for _ in range(3):
            await self.step()
            assert self.record(k)['state'] == STATE['READY']
        await self.event(k, 'OUTPUT_SPACE')
        await self.running(k)
        assert self.record(k)['identity'] == identity, 'START changed an already-bound service epoch'
        await self.complete(k)
        await self.quiescent()
        self.coverage.hit('start_requires_matching_input_and_output_readiness_in_prebound_epoch')
        # Both query responses must survive a stopped policy-response consumer.
        k = await self.submit(self.descriptor())
        await self.running(k)
        await self.step(i_policy_response_ready=0)
        tags = [await self.policy('QUERY', k, wait=False)
                for _ in range(self.p['RESPONSE_QUEUE_DEPTH'])]
        assert not self.last['o_policy_ready']
        saved = self.last['o_policy_response_record']
        for _ in range(4):
            await self.step()
            assert self.last['o_policy_response_valid'] and self.last['o_policy_response_record'] == saved
        await self.step(i_policy_response_ready=1)
        await self.wait(lambda: all(any(r['tag'] == tag for r in self.scoreboard.policy_replies)
                                   for tag in tags))
        await self.complete(k)
        await self.quiescent()
        self.coverage.hit('policy_response_capacity_backpressures_requests_and_preserves_ordered_replies')

    async def observability(self):
        # A predeclared multi-cluster package is still one indivisible admission.
        k = await self.submit(self.descriptor(mask=(1 << self.p['NUM_CLUSTERS']) - 1))
        await self.running(k)
        assert self.last['o_active_count'] == 1
        assert self.record(k)['mask'] == (1 << self.p['NUM_CLUSTERS']) - 1
        await self.complete(k)
        await self.quiescent()
        self.coverage.hit('full_array_predeclared_package_is_one_atomic_reservation')
        if self.p['ENABLE_DEADLINE_MONITORING']:
            k = await self.submit(self.descriptor(deadline=self.last['o_time'] + 4))
            await self.running(k)
            r = self.record(k)
            assert self.last['o_record_deadline_warned'] >> r['slot'] & 1
            await self.complete(k)
            await self.quiescent()
            self.coverage.hit('deadline_negative_slack_warns_without_becoming_completion_or_rejection')
        if self.p['ENABLE_COUNTER_FEEDBACK']:
            flags = 0x9e
            k = await self.submit(self.descriptor(flags=flags))
            await self.running(k)
            await self.snapshot(k, 1, 0x1111)
            await self.wait(lambda: self.record(k)['metrics'] == 0x1111)
            await self.event(k, 'COMPUTE_DONE')
            await self.event(k, 'EXTERNAL_DONE')
            for _ in range(80):
                await self.step()
            assert self.notice_for(k, result=True) is None, 'Old snapshot satisfied completion sampling'
            await self.snapshot(k, 2, 0x2222, critical=1)
            await self.result(k)
            await self.quiescent()
            self.coverage.hit('requested_completion_snapshot_must_be_coherent_and_newer_than_compute_done')
        lifecycle = pack('lifecycle', flags=0x8e, kernel_timeout=12)
        k = await self.submit(self.descriptor(lifecycle_record=lifecycle))
        await self.running(k)
        await self.result(k, NOTICE['FAILED'], ERR['TIMEOUT'])
        await self.quiescent()
        self.coverage.hit('kernel_timeout_is_an_abort_and_drain_obligation')
        # Test/scan and clock/power qualification must not consume a held command.
        self.peers.block.add(6)
        k = await self.submit(self.descriptor())
        await self.wait(lambda: self.last['o_array_runtime_valid'])
        action = self.last['o_action_record']
        for signal in ('i_test_mode', 'i_scan_enable', 'i_clock_ready', 'i_power_good'):
            active_value = 1 if signal in ('i_test_mode', 'i_scan_enable') else 0
            for _ in range(3):
                item = await self.step(**{signal: active_value})
                assert not item.post['o_array_runtime_valid'] and not item.post['o_submit_ready']
                assert item.post['o_action_record'] == action
            await self.step(**{signal: 1 - active_value})
        self.peers.block.clear()
        await self.complete(k)
        await self.quiescent()
        self.coverage.hit('test_scan_clock_and_power_qualification_preserve_live_control_obligations')
        await self.step(i_counter_snapshot=1)
        await self.step(i_counter_snapshot=0, i_counter_read_snapshot=1)
        assert self.last['o_counter_snapshot_valid']
        await self.step(i_counter_read=1, i_counter_index=0)
        assert self.last['o_counter_valid'] and self.last['o_counter_data'] > 0
        await self.step(i_counter_read=0, i_counter_read_snapshot=0)
        self.coverage.hit('reused_performance_counters_publish_nonzero_submission_activity')

    async def immediate_and_early_terminals(self):
        self.peers.block.add(6)
        k = await self.submit(self.descriptor())
        await self.wait(lambda: self.last['o_array_runtime_valid'])
        action = unpack('action', self.last['o_array_runtime_record'])
        premature = pack('ack', **{n: action[n] for n in ('identity', 'command', 'cluster_mask', 'tag')},
                         status=ACK['OK'], flags=3)
        self.peers.foreign.append((6, premature))
        for _ in range(4):
            await self.step()
            assert self.last['o_action_active'] and not self.last['o_action_sent']
            assert not self.last['o_record_array_owned']
        self.peers.block.clear()
        await self.complete(k)
        await self.quiescent()
        self.coverage.hit('terminal_before_command_acceptance_is_quarantined')
        self.peers.immediate = True
        k = await self.submit(self.descriptor())
        await self.complete(k)
        await self.quiescent()
        self.peers.immediate = False
        self.coverage.hit('matching_terminal_on_command_acceptance_edge_completes_exactly_once')
        self.peers.delay = lambda ep, action: 24 if action['command'] == CMD['ALLOCATE'] else 1
        k = await self.submit(self.descriptor())
        await self.wait(lambda: self.last['o_action_sent'])
        action = unpack('action', self.last['o_action_record'])
        for field in ('identity', 'command'):
            wrong = {n: action[n] for n in ('identity', 'command', 'cluster_mask', 'tag')}
            wrong[field] ^= 1
            self.peers.foreign.append((6, pack('ack', **wrong, status=ACK['OK'], flags=3)))
            for _ in range(3):
                await self.step()
                assert self.last['o_action_active'] and not self.last['o_record_array_owned']
        self.peers.delay = None
        await self.complete(k)
        await self.quiescent()
        self.coverage.hit('same_tag_wrong_owner_or_command_cannot_retire_inflight_action')

    async def exclusive_resource_conflicts(self):
        if self.p['NUM_CLUSTERS'] < 2 or self.p['MAX_ACTIVE_KERNELS'] < 2:
            return
        for field in ('dma_mask', 'memory_mask', 'scratchpad_mask', 'event_mask', 'counter_mask'):
            first = self.descriptor(mask=1)
            resource = unpack('resource', first['resource_record'])
            resource[field] = 1
            first['resource_record'] = pack('resource', **resource)
            k1 = await self.submit(first)
            await self.running(k1)
            second = self.descriptor(mask=2)
            resource = unpack('resource', second['resource_record'])
            resource[field] = 1
            second['resource_record'] = pack('resource', **resource)
            k2 = await self.submit(second)
            for _ in range(6):
                await self.step()
            assert self.record(k2)['state'] == STATE['WAIT_RESOURCES'], field
            assert self.last['o_cluster_reserved_mask'] == 1
            await self.complete(k1)
            await self.complete(k2)
            await self.quiescent()
        self.coverage.hit('dma_memory_scratchpad_event_and_counter_conflicts_are_atomic')
