"""Directed power sequencing contracts and seeded adversarial physical peers."""
import random
from pyuvm import uvm_sequence
from cluster_power_manager.config import CODES, WIDTHS, pack, unpack
from cluster_power_manager.model import STATE, PHASE, CMD, STATUS, ERROR, lane
from cluster_power_manager.peers import PhysicalPeers
from cluster_power_manager.transaction import INPUTS, PowerItem


class PowerSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__('cluster_power_contracts')
        self.c = config
        self.p = config.parameters
        self.rng = random.Random(config.seed)
        self.peers = PhysicalPeers(self.rng)
        self.ports = dict.fromkeys(INPUTS, 0)
        self.ports |= dict(i_response_ready=1, i_event_ready=1, i_command_authorized=1,
            i_system_privileged=1, i_cluster_allocated=1, i_allocation_owner_id=0x1234,
            i_allocation_kernel_id=0x5678, i_allocation_package_id=0x11223344,
            i_allocation_generation=2, i_execution_epoch=7, i_system_reset_generation=1,
            i_array_transition_authorized=1, i_system_transition_authorized=1,
            i_global_endpoint_drained=1, i_configuration_idle=1, i_cluster_quiescent=1,
            i_cluster_drain_done=1, i_tile_quiescent_mask=(1 << self.p['NUM_TILES']) - 1,
            i_tile_drain_done_mask=(1 << self.p['NUM_TILES']) - 1, i_scratchpad_idle=1,
            i_memory_boundary_idle=1, i_local_network_idle=1, i_event_idle=1,
            i_counter_snapshot_idle=1, i_debug_idle=1, i_power_good=(1 << self.p['NUM_POWER_SWITCH_GROUPS']) - 1,
            i_power_switch_ack=(1 << self.p['NUM_POWER_SWITCH_GROUPS']) - 1,
            i_voltage_ready=1, i_clock_source_ready=1,
            i_sram_power_ack=(1 << self.p['NUM_SRAM_POWER_GROUPS']) - 1,
            i_boundary_drained=(1 << self.p['NUM_BOUNDARY_ENDPOINTS']) - 1,
            i_boundary_source_valid=(1 << self.p['NUM_BOUNDARY_ENDPOINTS']) - 1,
            i_boundary_source_ready=(1 << self.p['NUM_BOUNDARY_ENDPOINTS']) - 1)
        self.last = None
        self.tag = 0

    def identity(self):
        if not self.ports['i_cluster_allocated']:
            return pack('identity', cluster_id=self.p['CLUSTER_ID'])
        return pack('identity', cluster_id=self.p['CLUSTER_ID'],
                    owner_id=self.ports['i_allocation_owner_id'], kernel_id=self.ports['i_allocation_kernel_id'],
                    package_id=self.ports['i_allocation_package_id'],
                    allocation_generation=self.ports['i_allocation_generation'], epoch=self.ports['i_execution_epoch'])

    async def step(self, **changes):
        self.ports.update(changes)
        driven = self.ports.copy()
        self.peers.drive(driven, self.last, self.p)
        item = PowerItem(driven)
        await self.start_item(item)
        await self.finish_item(item)
        self.peers.observe(item.pre)
        self.last = item.post
        return item

    async def wait(self, predicate, limit=3000, description='condition'):
        for _ in range(limit):
            if self.last is not None and predicate():
                return
            await self.step()
        raise AssertionError((f'Timeout waiting for {description}', self.last,
                              self.scoreboard.responses[-2:]))

    async def boot(self, *, until=None):
        self.peers.global_reset()
        self.ports['i_system_reset_generation'] += 1
        await self.step(i_aon_rstb=0, i_command_valid=0, i_config_valid=0, i_cancel_valid=0,
                        i_wakeup_event=0, i_runtime_wakeup_required=0)
        await self.step()
        await self.step(i_aon_rstb=1)
        if until is not None:
            await self.wait(lambda: self.last['o_transition_phase'] == PHASE[until])
            return
        await self.wait(lambda: self.last['o_power_state'] == STATE['IDLE_ON'] and
                        not self.last['o_transition_active'], description='boot reconciliation')
        assert not self.last['o_fatal_error'] and self.last['o_state_valid']

    async def config(self, **changes):
        defaults = dict(i_config_auto_clock_gate=0, i_config_owner_check=1, i_config_break_even=1,
            i_config_idle_entry_cycles=self.p['IDLE_ENTRY_CYCLES'],
            i_config_min_gated_residency=self.p['MIN_GATED_RESIDENCY_CYCLES'],
            i_config_wake_enable=(1 << self.p['NUM_WAKE_SOURCES']) - 1,
            i_config_allowed_states=0x1e, i_config_allowed_points=1)
        await self.wait(lambda: self.last['o_config_ready'])
        item = await self.step(i_config_valid=1, **(defaults | changes))
        assert item.pre['o_config_ready']
        await self.step(i_config_valid=0)
        return item

    async def command(self, name, *, wait=True, **changes):
        self.tag += 1
        identity = unpack('identity', self.identity())
        fields = dict(i_command=CMD[name], i_command_cluster_id=identity['cluster_id'],
            i_command_owner_id=identity['owner_id'], i_command_kernel_id=identity['kernel_id'],
            i_command_package_id=identity['package_id'],
            i_command_allocation_generation=identity['allocation_generation'],
            i_command_execution_epoch=identity['epoch'], i_command_operating_point=0,
            i_command_expected_idle_cycles=10000, i_command_state_policy_id=0,
            i_command_flags=0, i_command_tag=self.tag,
            i_command_target_state=dict(RUN=STATE['ACTIVE'], IDLE_ON=STATE['IDLE_ON'],
                CLOCK_GATE=STATE['CLOCK_GATED'], RECOVER=STATE['IDLE_ON']).get(name,
                    self.last['o_power_state']))
        for _ in range(3000):
            item = await self.step(i_command_valid=1, **(fields | changes))
            if item.pre['o_command_ready']:
                break
        else:
            raise AssertionError('Command never accepted')
        tag = self.tag
        await self.step(i_command_valid=0)
        if not wait:
            return tag
        return await self.response(tag)

    async def response(self, tag, status=STATUS['OK'], error=None):
        await self.wait(lambda: any(r['tag'] == tag for r in self.scoreboard.responses),
                        description=f'command response {tag}')
        response = next(r for r in reversed(self.scoreboard.responses) if r['tag'] == tag)
        if status is not None:
            assert response['status'] == status, response
        if error is not None:
            assert response['error'] == error, response
        return response

    async def quiet_events(self):
        await self.wait(lambda: self.last['o_quiescent'], description='empty event/response obligations')

    async def body(self):
        await self.boot()
        await self.config()
        self.coverage.hit('boot_qualifies_physical_state_resets_tiles_and_revalidates_endpoints')
        await self.command('RUN')
        await self.step(i_cluster_busy=1, i_cluster_quiescent=0, i_tile_busy_mask=1,
                        i_tile_quiescent_mask=((1 << self.p['NUM_TILES']) - 1) ^ 1)
        assert self.last['o_power_state'] == STATE['ACTIVE']
        await self.step(i_stall_reason=1)
        assert self.last['o_power_state'] == STATE['STALLED']
        await self.step(i_cluster_busy=0, i_cluster_quiescent=1, i_tile_busy_mask=0,
                        i_tile_quiescent_mask=(1 << self.p['NUM_TILES']) - 1, i_stall_reason=0)
        await self.command('CLOCK_GATE')
        assert self.last['o_power_state'] == STATE['CLOCK_GATED']
        before = dict(self.coverage.clock_edges)
        for _ in range(self.p['MIN_GATED_RESIDENCY_CYCLES'] + 3):
            await self.step()
        assert self.coverage.clock_edges.get('root',0) == before.get('root',0)
        self.coverage.hit('complete_drain_and_real_tile_idle_precede_glitch_free_root_shutdown')
        await self.step(i_wakeup_event=1, i_wakeup_identity=self.identity())
        await self.step(i_wakeup_event=0)
        await self.wait(lambda: not self.last['o_transition_active'] and self.last['o_cluster_clock_enable'])
        assert not self.last['o_fatal_error']
        await self.command('QUERY')
        await self.quiet_events()
        self.coverage.hit('always_on_event_wakes_stopped_functional_clock_and_revalidates_identity')
        await self.rejections_and_policy()
        await self.drain_blockers_and_stalls()
        await self.automatic_gating()
        await self.wake_sources_and_residency()
        await self.response_and_event_backpressure()
        await self.cancel_and_timeout()
        await self.physical_faults_and_recovery()
        await self.identity_rebind_and_revalidation()
        await self.test_and_unknowns()
        await self.phase_reset_and_qualification()
        await self.random_traffic()
        await self.protection()
        await self.quiet_events()

    async def reject(self, name, error, **changes):
        tag = await self.command(name, wait=False, **changes)
        return await self.response(tag, STATUS['REJECTED'], ERROR[error])

    async def run(self):
        response = await self.command('RUN', i_command_flags=1)
        assert response['state'] == STATE['ACTIVE']

    async def gate(self):
        response = await self.command('CLOCK_GATE')
        assert response['state'] == STATE['CLOCK_GATED']

    async def rejections_and_policy(self):
        for name in ('RETENTION','OFF','SET_POINT'):
            saved = tuple(self.last[n] for n in ('o_cluster_clock_enable','o_isolation_enable',
                          'o_power_switch_enable','o_boundary_endpoint_enable'))
            await self.reject(name, 'UNSUPPORTED')
            assert saved == tuple(self.last[n] for n in ('o_cluster_clock_enable','o_isolation_enable',
                                  'o_power_switch_enable','o_boundary_endpoint_enable'))
        for field in ('cluster_id','owner_id','kernel_id','package_id','allocation_generation','execution_epoch'):
            identity = unpack('identity', self.identity())
            key = 'epoch' if field == 'execution_epoch' else field
            await self.reject('RUN','IDENTITY',**{'i_command_' + field: identity[key] ^ 1})
        for field in ('i_command_operating_point','i_command_state_policy_id','i_command_flags'):
            await self.reject('RUN','UNSUPPORTED',**{field: 0x80 if field.endswith('flags') else 1})
        await self.reject('RUN','AUTHORITY',i_command_authorized=0)
        await self.step(i_command_authorized=1)
        await self.reject('RUN','AUTHORITY',i_array_transition_authorized=0)
        # A private query is permitted while transition authority is withheld.
        await self.command('QUERY')
        await self.step(i_array_transition_authorized=1)
        await self.reject('RUN','COMMAND',i_command_target_state=STATE['CLOCK_GATED'])
        await self.reject('RUN','AUTHORITY',i_command_flags=1,i_system_privileged=0)
        await self.step(i_system_privileged=1)
        for changes in (dict(i_config_owner_check=0),dict(i_config_idle_entry_cycles=0),
                        dict(i_config_min_gated_residency=0),dict(i_config_allowed_points=0),
                        dict(i_config_allowed_states=0xffffffff)):
            item = await self.config(**changes)
            assert item.pre['o_config_rejected'] and not item.pre['o_config_accepted']
        await self.config(i_config_allowed_states=1 << STATE['IDLE_ON'])
        await self.reject('RUN','POLICY')
        await self.config()
        self.coverage.hit('authorized_full_identity_and_atomic_policy_rejection_without_physical_effects')
        self.coverage.hit('uncharacterized_retention_off_dvfs_and_reserved_flags_are_rejected')

    async def drain_blockers_and_stalls(self):
        all_tiles = (1 << self.p['NUM_TILES']) - 1
        await self.run()
        for reason in range(self.p['NUM_STALL_REASONS']):
            stalls = sum((1 << reason) << (t * self.p['NUM_STALL_REASONS'])
                         for t in range(self.p['NUM_TILES']))
            await self.step(i_cluster_busy=1, i_cluster_quiescent=0, i_tile_busy_mask=all_tiles,
                            i_tile_quiescent_mask=0, i_stall_reason=1 << reason,
                            i_tile_stall_reason=stalls, i_clock_group_request=0)
            assert self.last['o_power_state'] == STATE['STALLED']
            assert self.last['o_idle_count'] == 0 and self.last['o_cluster_clock_enable']
        await self.step(i_cluster_busy=0,i_cluster_quiescent=1,i_tile_busy_mask=0,
                        i_tile_quiescent_mask=all_tiles,i_stall_reason=0,i_tile_stall_reason=0)
        blockers = [(name,0,1) for name in ('i_cluster_quiescent','i_cluster_drain_done',
            'i_scratchpad_idle','i_memory_boundary_idle','i_local_network_idle','i_event_idle',
            'i_configuration_idle','i_counter_snapshot_idle','i_debug_idle','i_global_endpoint_drained')]
        blockers += [(name,all_tiles ^ (1 << t),all_tiles) for name in
                     ('i_tile_quiescent_mask','i_tile_drain_done_mask') for t in range(self.p['NUM_TILES'])]
        all_endpoints = (1 << self.p['NUM_BOUNDARY_ENDPOINTS']) - 1
        blockers += [('i_boundary_drained',all_endpoints ^ (1 << e),all_endpoints)
                     for e in range(self.p['NUM_BOUNDARY_ENDPOINTS'])]
        for name,blocked,released in blockers:
            await self.step(**{name:blocked})
            tag = await self.command('CLOCK_GATE',wait=False)
            await self.wait(lambda:self.last['o_transition_phase']==PHASE['DRAIN'])
            for _ in range(3):
                await self.step()
                assert self.last['o_cluster_clock_enable'] and self.last['o_cluster_execution_hold']
                assert not self.last['o_cluster_accept_enable'] and not self.last['o_boundary_injection_enable']
                assert not self.last['o_write_disable'], 'Drain was frozen before retiring accepted work'
            await self.step(**{name:released})
            await self.response(tag)
            await self.run()
        await self.quiet_events()
        self.coverage.hit('every_tile_endpoint_and_cluster_subsystem_blocks_shutdown_until_drained')
        self.coverage.hit('every_stall_reason_preserves_required_group_clocks_without_idle_qualification')

    async def automatic_gating(self):
        if not self.p['AUTO_CLOCK_GATE_ENABLE']:
            item = await self.config(i_config_auto_clock_gate=1)
            assert item.pre['o_config_rejected']
            self.coverage.hit('statically_disabled_automatic_gating_cannot_be_enabled_by_policy')
            return
        threshold = self.p['IDLE_ENTRY_CYCLES']
        await self.config()
        await self.step(i_array_execution_hold=1)
        await self.config(i_config_auto_clock_gate=1)
        assert self.last['o_idle_count'] == 0
        if threshold > 1:
            for expected in range(1,threshold):
                await self.step(i_debug_idle=1, i_array_execution_hold=0)
                assert self.last['o_idle_count'] == expected
                assert not self.last['o_transition_active']
            await self.step(i_debug_idle=0)
            assert self.last['o_idle_count']==0
        for count in range(threshold):
            await self.step(i_debug_idle=1, i_array_execution_hold=0)
            if count+1<threshold:
                assert self.last['o_idle_count']==count+1 and not self.last['o_transition_active']
            else:
                assert self.last['o_transition_phase']==PHASE['DRAIN']
        await self.wait(lambda:self.last['o_power_state']==STATE['CLOCK_GATED'])
        await self.quiet_events()
        await self.config(i_config_auto_clock_gate=0)
        await self.step(i_runtime_wakeup_required=1)
        await self.step(i_runtime_wakeup_required=0)
        await self.wait(lambda:not self.last['o_transition_active'] and self.last['o_cluster_clock_enable'])
        await self.quiet_events()
        self.coverage.hit('automatic_gate_uses_exact_consecutive_threshold_and_clears_on_interruption')

    async def wake_sources_and_residency(self):
        await self.config(i_config_min_gated_residency=16)
        await self.gate()
        start_residency = self.last['o_state_residency']
        assert start_residency < 16
        await self.step(i_wakeup_event=1,i_wakeup_identity=self.identity())
        await self.step(i_wakeup_event=0)
        while self.last['o_state_residency'] < 16 and not self.last['o_transition_active']:
            assert not self.last['o_cluster_clock_enable']
            await self.step()
        await self.wait(lambda:not self.last['o_transition_active'] and self.last['o_cluster_clock_enable'])
        await self.quiet_events()
        await self.gate()
        await self.reject('RUN','RESIDENCY')
        await self.step(i_runtime_wakeup_required=1)
        await self.step(i_runtime_wakeup_required=0)
        await self.wait(lambda:not self.last['o_transition_active'] and self.last['o_cluster_clock_enable'])
        await self.quiet_events()
        await self.config(i_config_min_gated_residency=1,i_config_wake_enable=0)
        await self.gate()
        await self.step(i_wakeup_event=(1 << self.p['NUM_WAKE_SOURCES'])-1,i_wakeup_identity=self.identity())
        await self.step(i_wakeup_event=0)
        for _ in range(4):
            await self.step()
            assert not self.last['o_wakeup_pending'] and not self.last['o_cluster_clock_enable']
        await self.quiet_events()
        await self.config(i_config_min_gated_residency=1)
        for field in ('owner_id','kernel_id','package_id','allocation_generation','epoch'):
            wrong = unpack('identity',self.identity());wrong[field] ^= 1
            await self.step(i_wakeup_event=1,i_wakeup_identity=pack('identity',**wrong))
            await self.step(i_wakeup_event=0)
            for _ in range(2):
                await self.step()
            assert not self.last['o_cluster_clock_enable'] and not self.last['o_wakeup_pending']
        for source in range(self.p['NUM_WAKE_SOURCES']):
            await self.step(i_wakeup_event=1 << source,i_wakeup_identity=self.identity())
            await self.step(i_wakeup_event=0)
            await self.wait(lambda:not self.last['o_transition_active'] and self.last['o_cluster_clock_enable'])
            if self.p['ENABLE_COUNTERS']:
                assert lane(self.last['o_wake_source_count'],source,32)>0
            await self.gate()
        await self.run()
        await self.quiet_events()
        self.coverage.hit('every_enabled_wake_source_survives_clock_stop_and_preserves_attribution')
        self.coverage.hit('disabled_and_stale_wake_identity_cannot_restart_or_deisolate')
        self.coverage.hit('ordinary_residency_is_enforced_and_mandatory_runtime_wake_bypasses_it')


    async def response_and_event_backpressure(self):
        await self.step(i_response_ready=0)
        tag = await self.command('CLOCK_GATE', wait=False)
        await self.wait(lambda: self.last['o_response_valid'])
        saved = self.last['o_response_record']
        await self.step(i_runtime_wakeup_required=1)
        await self.step(i_runtime_wakeup_required=0)
        await self.wait(lambda: not self.last['o_transition_active'] and
                        self.last['o_cluster_clock_enable'])
        assert self.last['o_response_record'] == saved
        assert unpack('response', saved)['state'] == STATE['CLOCK_GATED']
        await self.step(i_response_ready=1)
        await self.response(tag)
        await self.quiet_events()
        # Saturate diagnostic telemetry while a mandatory wake and a fatal
        # containment action retain their independent progress/storage paths.
        await self.command('CLEAR_ERROR')
        await self.gate()
        await self.step(i_event_ready=0)
        wrong = self.identity() ^ (1 << 8)
        for _ in range(self.p['EVENT_QUEUE_DEPTH'] + 6):
            await self.step(i_wakeup_event=1, i_wakeup_identity=wrong)
        assert self.last['o_diagnostic_overflow']
        await self.step(i_wakeup_event=0, i_runtime_wakeup_required=1)
        await self.step(i_runtime_wakeup_required=0)
        await self.wait(lambda: not self.last['o_transition_active'] and
                        self.last['o_cluster_clock_enable'])
        self.peers.overrides['i_thermal_emergency'] = 1
        await self.wait(lambda: self.last['o_power_state'] == STATE['ERROR'])
        first = self.last['o_error_code']
        for _ in range(5):
            await self.step()
        assert self.last['o_error_code'] == first == ERROR['THERMAL']
        await self.step(i_event_ready=1)
        await self.wait(lambda: any(e['kind'] == CODES['event_kind']['FATAL'] and
                        e['error'] == first for e in self.scoreboard.events))
        self.peers.overrides.clear()
        await self.boot()
        await self.config()
        self.coverage.hit('held_terminal_is_immutable_during_mandatory_wake')
        self.coverage.hit('diagnostic_overflow_and_stalled_events_do_not_block_wake_or_first_fatal')

    async def cancel(self, tag, *, wrong=False):
        item = await self.step(i_cancel_valid=1, i_cancel_identity=self.identity() ^ int(wrong),
                               i_cancel_tag=tag)
        assert item.pre['o_cancel_rejected' if wrong else 'o_cancel_accepted']
        await self.step(i_cancel_valid=0)

    async def cancel_and_timeout(self):
        await self.run()
        await self.step(i_memory_boundary_idle=0)
        tag = await self.command('CLOCK_GATE', wait=False)
        await self.cancel(tag, wrong=True)
        await self.cancel(tag)
        await self.response(tag, STATUS['ROLLED_BACK'], ERROR['CANCELED'])
        assert self.last['o_cluster_clock_enable'] and not self.last['o_fatal_error']
        await self.step(i_memory_boundary_idle=1)
        # Once the root request has fallen the original operation completes;
        # cancellation queues a distinct wake rather than claiming rollback.
        tag = await self.command('CLOCK_GATE', wait=False)
        await self.wait(lambda: self.last['o_transition_phase'] == PHASE['CLOCK_STOP'])
        await self.cancel(tag)
        await self.response(tag)
        await self.wait(lambda: not self.last['o_transition_active'] and
                        self.last['o_cluster_clock_enable'])
        await self.quiet_events()
        await self.step(i_scratchpad_idle=0)
        tag = await self.command('CLOCK_GATE', wait=False)
        if self.p['SUPPORT_ROLLBACK']:
            await self.response(tag, STATUS['ROLLED_BACK'], ERROR['DRAIN_TIMEOUT'])
            assert not self.last['o_fatal_error'] and self.last['o_cluster_clock_enable']
        else:
            await self.response(tag, STATUS['TIMEOUT'], ERROR['DRAIN_TIMEOUT'])
            assert self.last['o_fatal_error']
        await self.step(i_scratchpad_idle=1)
        if self.last['o_fatal_error']:
            await self.boot()
            await self.config()
        # Missing endpoint acknowledgements are past the reversible drain row.
        self.peers.overrides['i_boundary_endpoint_ack'] = (1 << self.p['NUM_BOUNDARY_ENDPOINTS']) - 1
        tag = await self.command('CLOCK_GATE', wait=False)
        await self.response(tag, STATUS['TIMEOUT'], ERROR['ENDPOINT_TIMEOUT'])
        assert self.last['o_fatal_error'] and not self.last['o_cluster_clock_enable']
        self.peers.overrides.clear()
        for _ in range(8):
            await self.step()
            assert self.last['o_fatal_error'] and not self.last['o_cluster_accept_enable']
        await self.boot()
        await self.config()
        self.coverage.hit('cancel_before_effects_rolls_back_and_cancel_after_stop_queues_wake')
        self.coverage.hit('drain_timeout_obeys_rollback_policy_and_late_physical_ack_cannot_release_fault')

    async def physical_faults_and_recovery(self):
        for port, value, expected in (('i_power_good', 0, 'POWER_LOSS'),
                ('i_power_switch_ack', 0, 'POWER_LOSS'),
                ('i_clock_source_ready', 0, 'CLOCK_LOSS'),
                ('i_voltage_fault', 1, 'VOLTAGE_FAULT'),
                ('i_thermal_emergency', 1, 'THERMAL')):
            await self.run()
            await self.command('CLEAR_ERROR')
            self.peers.overrides[port] = value
            await self.wait(lambda: self.last['o_power_state'] == STATE['ERROR'], limit=32)
            assert self.last['o_error_code'] == ERROR[expected], (port, self.last)
            assert not self.last['o_state_valid'] and not self.last['o_cluster_accept_enable']
            original = tuple(self.last[n] for n in ('o_error_code', 'o_first_error_timestamp',
                                                    'o_first_error_phase', 'o_first_error_tag'))
            self.peers.overrides.clear()
            for _ in range(8):
                await self.step()
            await self.reject('CLEAR_ERROR', 'COMMAND')
            assert original == tuple(self.last[n] for n in ('o_error_code', 'o_first_error_timestamp',
                                                           'o_first_error_phase', 'o_first_error_tag'))
            await self.reject('RECOVER', 'AUTHORITY')
            await self.step(i_array_execution_hold=1)
            await self.command('RECOVER', i_command_flags=4)
            assert self.last['o_state_valid'] and not self.last['o_fatal_error']
            assert not self.last['o_cluster_accept_enable']
            await self.command('CLEAR_ERROR')
            assert not self.last['o_error_code']
            await self.step(i_array_execution_hold=0)
        await self.quiet_events()
        self.coverage.hit('power_clock_voltage_and_thermal_faults_contain_before_authorized_recovery')
        self.coverage.hit('first_error_is_sticky_and_recovery_requires_reset_reload_and_fresh_validation')

    async def identity_rebind_and_revalidation(self):
        await self.gate()
        old = self.identity()
        await self.quiet_events()
        await self.step(i_array_execution_hold=1,
                        i_allocation_generation=self.ports['i_allocation_generation'] + 1,
                        i_execution_epoch=self.ports['i_execution_epoch'] + 1)
        await self.step()
        assert self.last['o_allocation_identity'] == self.identity() != old
        assert not self.last['o_state_valid'] and not self.last['o_cluster_clock_enable']
        await self.step(i_wakeup_event=1, i_wakeup_identity=old)
        await self.step(i_wakeup_event=0, i_array_execution_hold=0)
        self.peers.block.add('response')
        tag = await self.command('RUN', wait=False, i_command_flags=1)
        await self.wait(lambda: self.last['o_revalidate_valid'])
        request = unpack('validation', self.last['o_revalidate_record'])
        await self.step()
        for field in ('identity', 'boot_generation', 'serial', 'tag'):
            forged = {n: request[n] for n in ('identity', 'boot_generation', 'serial', 'tag')}
            forged[field] ^= 1
            self.peers.foreign.append(pack('validation_response', **forged, status=0, validity=15))
            # Foreign traffic is explicitly enabled while the honest response
            # remains queued, then blocked again before it can be delivered.
            self.peers.block.discard('response')
            await self.step()
            self.peers.block.add('response')
            assert not self.last['o_cluster_accept_enable']
        self.peers.block.discard('response')
        await self.response(tag)
        assert self.last['o_state_valid'] and self.last['o_allocation_identity'] != old
        await self.quiet_events()
        # A matching but incomplete validation reply is a fatal failed proof.
        await self.gate()
        self.peers.validation_flags = 7
        tag = await self.command('RUN', wait=False, i_command_flags=1)
        await self.response(tag, STATUS['ERROR'], ERROR['REVALIDATE_FAILED'])
        assert self.last['o_fatal_error']
        self.peers.validation_flags = 15
        await self.boot()
        await self.config()
        # Transport backpressure must preserve the entire validation request.
        self.peers.block.add('request')
        tag = await self.command('RUN', wait=False, i_command_flags=1)
        await self.wait(lambda: self.last['o_revalidate_valid'])
        saved = self.last['o_revalidate_record']
        for _ in range(6):
            await self.step()
            assert self.last['o_revalidate_record'] == saved
        self.peers.block.clear()
        await self.response(tag)
        await self.quiet_events()
        self.coverage.hit('allocation_rebind_and_stale_boot_serial_identity_tag_replies_require_fresh_proof')
        self.coverage.hit('incomplete_validation_contains_and_stalled_validation_record_is_stable')

    async def test_and_unknowns(self):
        for request in ('i_test_mode', 'i_scan_enable', 'i_mbist_enable'):
            await self.step(i_array_execution_hold=1, i_test_authorized=1,
                            i_test_clock_enable=1, **{request: 1})
            await self.wait(lambda: self.last['o_test_active'])
            assert not self.last['o_cluster_accept_enable'] and not self.last['o_state_valid']
            assert self.last['o_isolation_enable'] == (1 << self.p['NUM_ISOLATION_GROUPS']) - 1
            assert self.last['o_cluster_reset_request'] == (1 << self.p['NUM_RESET_GROUPS']) - 1
            assert not self.last['o_boundary_valid'] and not self.last['o_boundary_ready']
            await self.reject('RUN', 'TEST', i_command_flags=1)
            await self.step(i_test_clock_enable=0)
            await self.step()
            assert not self.last['o_cluster_clock_enable']
            await self.step(i_test_clock_enable=1)
            await self.step()
            assert self.last['o_cluster_clock_enable']
            await self.step(**{request: 0})
            await self.wait(lambda: not self.last['o_transition_active'])
            assert self.last['o_state_valid']
            await self.step(i_array_execution_hold=0, i_test_authorized=0,
                            i_test_clock_enable=0)
            await self.quiet_events()
        # Unknown frontend data is consumed as a sanitized rejection and
        # never stored as an unknown protected command or physical request.
        await self.reject('RUN', 'UNKNOWN', i_command_owner_id='x' * 16)
        item = await self.config(i_config_idle_entry_cycles='z' * 32)
        assert item.pre['o_config_rejected'] and item.pre['o_config_error_code'] == ERROR['UNKNOWN']
        await self.config()
        await self.step(i_wakeup_identity='x' * 96, i_wakeup_event=1)
        await self.step(i_wakeup_event=0)
        assert not self.last['o_wakeup_pending']
        await self.step(i_cluster_busy='x')
        await self.wait(lambda: self.last['o_power_state'] == STATE['ERROR'])
        assert not self.last['o_boundary_valid'] and not self.last['o_boundary_ready']
        await self.step(i_cluster_busy=0)
        await self.boot()
        await self.config()
        await self.step(i_test_mode=1, i_test_authorized=0, i_array_execution_hold=1)
        await self.wait(lambda: self.last['o_power_state'] == STATE['ERROR'])
        assert self.last['o_error_code'] == ERROR['TEST']
        await self.step(i_test_mode=0, i_array_execution_hold=0)
        await self.boot()
        await self.config()
        self.coverage.hit('test_scan_mbist_are_isolated_authorized_rows_and_exit_reloads_before_release')
        self.coverage.hit('unknown_command_policy_wake_and_live_control_never_authorize_physical_effects')

    async def random_traffic(self):
        for _ in range(self.c.random_cycles):
            await self.step(i_event_ready=1, i_wakeup_event=0)
            self.coverage.random_transactions += 1
            choice = self.rng.randrange(10)
            stable = not self.last['o_transition_active'] and not self.last['o_fatal_error']
            if choice == 0 and stable:
                await self.command('QUERY')
            elif choice == 1 and stable:
                if self.last['o_power_state'] == STATE['CLOCK_GATED']:
                    await self.run()
                else:
                    await self.gate()
            elif choice == 2 and stable:
                await self.step(i_runtime_wakeup_required=1)
                await self.step(i_runtime_wakeup_required=0)
            elif choice == 3 and stable and self.last['o_cluster_clock_enable']:
                await self.run()
                await self.step(i_cluster_busy=1, i_cluster_quiescent=0,
                                i_stall_reason=self.rng.randrange(1 << self.p['NUM_STALL_REASONS']))
                await self.step(i_cluster_busy=0, i_cluster_quiescent=1, i_stall_reason=0)
            else:
                await self.step(i_wakeup_event=(1 << self.rng.randrange(self.p['NUM_WAKE_SOURCES']))
                                if choice == 4 else 0, i_wakeup_identity=self.identity(),
                                i_event_ready=int(self.rng.random() > 0.15))
            if self.last['o_fatal_error']:
                raise AssertionError(('Unexpected randomized fatal', self.last))
        await self.step(i_event_ready=1, i_wakeup_event=0, i_runtime_wakeup_required=0)
        await self.wait(lambda: not self.last['o_transition_active'])
        await self.quiet_events()
        if self.p['ENABLE_COUNTERS']:
            await self.step(i_counter_snapshot=1)
            await self.step(i_counter_snapshot=0, i_counter_read=1,
                            i_counter_read_snapshot=1, i_counter_index=23)
            assert self.last['o_counter_valid'] and self.last['o_counter_data'] > 0
            await self.step(i_counter_read=0)
        else:
            assert not self.last['o_counter_valid'] and not self.last['o_wake_source_count']
        self.coverage.hit('seeded_random_commands_activity_wakes_and_backpressure_leave_no_obligations')
        self.coverage.hit('counter_snapshot_and_disabled_counter_contracts')

    async def protection(self):
        if not self.p['CONTROL_PROTECTION']:
            self.coverage.hit('unprotected_profile_has_known_registered_physical_controls')
            return
        await self.boot()
        await self.config()
        if self.p['CONTROL_PROTECTION'] == 2:
            self.active['inject'] = 1
            await self.step()
            assert not self.last['o_fatal_error']
            self.coverage.hit('secded_corrects_single_bit_control_storage_fault')
        self.active['inject'] = 3 if self.p['CONTROL_PROTECTION'] == 2 else 1
        await self.step()
        await self.wait(lambda: self.last['o_power_state'] == STATE['ERROR'])
        assert self.last['o_error_code'] == ERROR['INTEGRITY']
        assert not self.last['o_cluster_clock_enable'] and not self.last['o_cluster_accept_enable']
        await self.boot()
        await self.config()
        self.coverage.hit('protected_control_storage_fault_is_contained_with_known_physical_outputs')


    async def phase_reset_and_qualification(self):
        # Coordinated resets explicitly invalidate all prior peer obligations.
        for phase in ('POWER', 'CLOCK', 'RESET_HOLD', 'RESET_RELEASE',
                      'TILE_CONFIG', 'TILE_RUN', 'VALIDATE', 'ENDPOINT_ENABLE'):
            await self.boot(until=phase)
            await self.boot()
            await self.config()
        for phase in ('DRAIN', 'ENDPOINT_DISABLE', 'TILE_IDLE', 'CLOCK_STOP'):
            await self.run()
            if phase == 'DRAIN':
                await self.step(i_memory_boundary_idle=0)
            await self.command('CLOCK_GATE', wait=False)
            await self.wait(lambda: self.last['o_transition_phase'] == PHASE[phase],
                            description='reset coverage ' + phase)
            self.ports['i_memory_boundary_idle'] = 1
            await self.boot()
            await self.config()
        # A short good-power pulse cannot authorize the functional root. The
        # qualification model observes raw inputs and synchronization history.
        self.peers.overrides['i_power_good'] = 0
        await self.boot(until='POWER')
        for _ in range(4):
            await self.step()
            assert not self.last['o_cluster_clock_enable']
        self.peers.overrides.clear()
        await self.step()
        self.peers.overrides['i_power_good'] = 0
        for _ in range(4):
            await self.step()
            assert not self.last['o_cluster_clock_enable']
        self.peers.overrides.clear()
        await self.wait(lambda: not self.last['o_transition_active'])
        assert not self.last['o_fatal_error'] and self.last['o_state_valid']
        await self.config()
        # Fresh startup status never receives a timeout exemption.
        for port, phase, expected in (('i_power_good', 'POWER', 'POWER_TIMEOUT'),
                                     ('i_clock_source_ready', 'CLOCK', 'CLOCK_TIMEOUT'),
                                     ('i_reset_ack', 'RESET_HOLD', 'RESET_TIMEOUT')):
            self.peers.overrides[port] = 0
            await self.boot(until=phase)
            await self.wait(lambda: self.last['o_power_state'] == STATE['ERROR'])
            assert self.last['o_error_code'] == ERROR[expected]
            self.peers.overrides.clear()
            await self.boot()
            await self.config()
        await self.run()
        self.peers.overrides['i_clock_stopped'] = 0
        tag = await self.command('CLOCK_GATE', wait=False)
        await self.response(tag, STATUS['TIMEOUT'], ERROR['CLOCK_TIMEOUT'])
        self.peers.overrides.clear()
        await self.boot()
        await self.config()
        self.peers.block.add('response')
        tag = await self.command('RUN', wait=False, i_command_flags=1)
        await self.response(tag, STATUS['TIMEOUT'], ERROR['REVALIDATE_TIMEOUT'])
        self.peers.block.clear()
        for _ in range(10):
            await self.step()
            assert self.last['o_fatal_error'] and not self.last['o_cluster_accept_enable']
        await self.boot()
        await self.config()
        self.coverage.hit('coordinated_reset_reconciles_each_startup_and_gate_phase')
        self.coverage.hit('power_glitch_requires_full_requalification_and_startup_ack_timeouts_contain')
        self.coverage.hit('clock_stop_and_validation_timeout_cannot_be_released_by_late_reply')
