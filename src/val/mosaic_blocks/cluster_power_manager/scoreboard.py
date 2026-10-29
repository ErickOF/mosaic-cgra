"""Passive protocol, ownership, physical sequencing and actual-clock checks."""
from pyuvm import ConfigDB, uvm_subscriber
from cluster_power_manager.config import WIDTHS, CODES, pack, unpack
from cluster_power_manager.model import (CommandLedger, PhysicalQualification, command_from_ports,
                                        complete_drain, lane, STATE, PHASE, CMD, STATUS)


class PowerScoreboard(uvm_subscriber):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.active = ConfigDB().get(self, '', 'active')
        self.ledger = CommandLedger()
        self.physical = PhysicalQualification(self.c.parameters)
        self.holds = {}
        self.responses = []
        self.events = []
        self.last = None
        self.drain_proven = False
        self.validation_proven = False
        self.next_event = 0
        self.tile_pending = {}
        self.tile_idle = set()
        self.last_edges = {}

    def held(self, name, valid, ready, record):
        if name in self.holds:
            assert valid and record == self.holds[name], ('Stalled payload changed', name)
        if valid and not ready:
            self.holds[name] = record
            self.coverage.counts['stalled_cycles'] += 1
        else:
            self.holds.pop(name, None)

    def write(self, observation):
        p = observation.ports
        c = self.coverage
        params = self.c.parameters
        c.cycles += 1
        c.clock_edges = observation.clock_edges
        if p['i_aon_rstb'] != 1:
            if self.ledger.pending is not None:
                c.counts['reset_command_recovery'] += 1
            self.ledger = CommandLedger()
            self.physical = PhysicalQualification(params)
            self.holds.clear()
            self.last = None
            self.drain_proven = self.validation_proven = False
            self.next_event = 0
            self.tile_pending.clear()
            self.tile_idle.clear()
            return
        if p['o_power_state'] is None:
            return
        c.states.add(p['o_power_state'])
        c.phases.add(p['o_transition_phase'])
        # No physical control can become unknown after the external AON reset.
        for name in ('o_cluster_clock_enable','o_clock_group_enable','o_isolation_enable',
                     'o_cluster_reset_request','o_power_switch_enable','o_boundary_endpoint_enable'):
            assert p[name] is not None, ('Unknown physical control', name)
        assert p['o_power_switch_enable'] == (1 << params['NUM_POWER_SWITCH_GROUPS']) - 1
        assert not p['o_retention_save'] and not p['o_retention_restore'] and not p['o_sram_power_mode']
        self.physical.step(p)
        if p['i_command_valid'] == 1 and p['o_command_ready']:
            self.ledger.accept(command_from_ports(p))
            c.counts['commands'] += 1
        self.held('response', p['o_response_valid'], p['i_response_ready'], p['o_response_record'])
        if p['o_response_valid'] and p['i_response_ready']:
            response = unpack('response', p['o_response_record'])
            self.ledger.respond(response)
            self.responses.append(response)
            c.counts['responses'] += 1
            assert response['command'] == p['o_response_command']
            assert response['status'] == p['o_response_status']
            assert response['state'] == p['o_response_reached_state']
            assert response['tag'] == p['o_response_tag']
        self.held('event', p['o_event_valid'], p['i_event_ready'], p['o_event_record'])
        if p['o_event_valid'] and p['i_event_ready']:
            event = unpack('event', p['o_event_record'])
            assert event['sequence_id'] == self.next_event, ('Event delivery sequence', event)
            self.next_event += 1
            self.events.append(event)
            c.counts['events'] += 1
        if p['o_fatal_error']:
            self.holds.pop('validation', None)
            self.tile_pending.clear()
        else:
            self.held('validation', p['o_revalidate_valid'], p['i_revalidate_ready'], p['o_revalidate_record'])
        if p['o_revalidate_valid'] and p['i_revalidate_ready']:
            self.ledger.validation_request(unpack('validation', p['o_revalidate_record']))
            self.validation_proven = False
            c.counts['validation_requests'] += 1
        if p['i_revalidate_response_valid'] and p['o_revalidate_response_ready']:
            self.validation_proven |= self.ledger.validation_response(
                unpack('validation_response', p['i_revalidate_response_record']))
        if p['o_transition_phase'] == PHASE['DRAIN'] and complete_drain(p, params):
            self.drain_proven = True
        if p['o_cluster_accept_enable']:
            assert p['o_power_state'] in (STATE['ACTIVE'], STATE['STALLED'])
            assert self.validation_proven and not p['o_cluster_execution_hold']
            assert not p['o_isolation_enable'] and not p['o_cluster_reset_request']
            assert p['i_array_transition_authorized'] and p['i_system_transition_authorized']
            assert not p['i_array_execution_hold'] and not p['o_write_disable']
        # The real common isolation cells clamp all handshake directions.
        for e in range(params['NUM_BOUNDARY_ENDPOINTS']):
            width = max(1, (params['NUM_ISOLATION_GROUPS'] - 1).bit_length())
            isolation_group = lane(params['BOUNDARY_ISOLATION_TABLE'], e, width)
            clamp = not (p['o_boundary_endpoint_enable'] >> e & 1) or \
                (p['o_isolation_enable'] >> isolation_group & 1)
            for suffix in ('valid','ready'):
                expected = 0 if clamp else p['i_boundary_source_' + suffix] >> e & 1
                assert p['o_boundary_' + suffix] >> e & 1 == expected
        if p['o_power_state'] == STATE['CLOCK_GATED']:
            assert not p['o_cluster_clock_enable'] and not p['o_clock_group_enable']
            assert not p['o_isolation_enable'] and not p['o_boundary_endpoint_enable']
            assert not p['o_tile_clock_enable']
        if p['o_fatal_error'] and p['o_power_state'] == STATE['ERROR']:
            assert not p['o_cluster_accept_enable'] and not p['o_cluster_clock_enable']
            assert p['o_isolation_enable'] == (1 << params['NUM_ISOLATION_GROUPS']) - 1
            assert not p['o_boundary_endpoint_enable']
        for t in range(params['NUM_TILES']):
            valid = p['o_tile_command_valid'] >> t & 1
            ready = p['o_tile_command_ready'] >> t & 1
            command = lane(p['o_tile_power_command'], t, 3)
            if not p['o_fatal_error']:
                self.held(('tile',t), valid, ready, command)
                if valid and ready:
                    assert t not in self.tile_pending, ('Duplicate tile command', t)
                    self.tile_pending[t] = command
                    c.counts['tile_commands'] += 1
                if p['o_tile_command_done'] >> t & 1:
                    assert t in self.tile_pending, ('Unsolicited tile completion', t)
                    completed = self.tile_pending.pop(t)
                    if completed == 1:
                        self.tile_idle.add(t)
                    else:
                        self.tile_idle.discard(t)
                    c.counts['tile_completions'] += 1
            else:
                self.holds.pop(('tile',t), None)
        if self.last is not None and self.last['o_cluster_clock_enable'] and \
                not p['o_cluster_clock_enable'] and not p['o_fatal_error'] and not p['o_test_active']:
            assert self.drain_proven and len(self.tile_idle) == params['NUM_TILES'], \
                'Clock stopped before complete cluster/tile drain'
            self.drain_proven = False
            c.counts['gates'] += 1
        self.last = p.copy()

    def check_phase(self):
        assert self.ledger.pending is None
        assert not self.holds and not self.tile_pending
