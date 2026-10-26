"""Passive public-interface checks; the sequence supplies independent expected data."""
from pyuvm import ConfigDB, uvm_subscriber
from tile_shell.model import number
from mst.model import unpack


class MstScoreboard(uvm_subscriber):
    def build_phase(self):
        self.c = ConfigDB().get(self, '', 'config')
        self.coverage = ConfigDB().get(self, '', 'coverage')
        self.active = ConfigDB().get(self, '', 'active')
        self.held = {}
        self.completed = set()

    def write(self, obs):
        p = {n: number(v) for n, v in obs.ports.items()}
        if obs.domain != 'core':
            return
        self.coverage.cycles += 1
        if p['i_rstb'] != 1:
            self.held.clear()
            self.completed.clear()
            return
        assert self.active.get('allow_fatal') or not p['o_mst_fatal_error'], ('Unexpected MST containment', obs.item.get_name(), p)
        for group, valid, ready, data in (
            ('completion', 'o_completion_valid', 'i_completion_ready',
                ('o_completion_identity', 'o_completion_status', 'o_completion_error_code',
                 'o_completion_bytes_read', 'o_completion_bytes_written', 'o_completion_elements')),
            ('rejection', 'o_rejection_valid', 'i_rejection_ready',
                ('o_rejection_identity', 'o_rejection_code'))):
            if group in self.held:
                assert p[valid] == 1 and tuple(p[n] for n in data) == self.held[group], group
            if p[valid] and not p[ready]:
                self.held[group] = tuple(p[n] for n in data)
                self.coverage.hit('backpressure')
            else:
                self.held.pop(group, None)
            if group == 'completion' and p[valid] and p[ready]:
                identity = p['o_completion_identity']
                assert identity not in self.completed, ('Duplicate completion', identity)
                self.completed.add(identity)
                self.coverage.hit('completion')

        a = self.c.aliases
        for kind in ('read', 'write'):
            widths = dict(address=a['A'], size_log2=a['MSZ'], tag=a['MT'],
                          identity=a['IDW'], region_id=a['RI'], generation=a['DG'], priority=a['PR'])
            if kind == 'write':
                widths.update(data=a['MD'], strobe=a['MY'])
            for client in range(a['NM']):
                key = kind, client
                valid = (p[f'o_scratchpad_{kind}_valid'] >> client) & 1
                ready = (p[f'i_scratchpad_{kind}_ready'] >> client) & 1
                values = tuple((p[f'o_scratchpad_{kind}_{n}'] >> (client*w)) & ((1 << w) - 1)
                               for n, w in widths.items())
                if key in self.held and not self.active.get('allow_fatal'):
                    assert valid and values == self.held[key], ('Unstable request', key)
                if valid and not ready:
                    self.held[key] = values
                    self.coverage.hit('memory_backpressure')
                else:
                    self.held.pop(key, None)

        # Real elastic egress must retain payload and metadata until acceptance.
        flushing = p['i_flush'] or (p['i_runtime_request_valid'] and
            p['o_runtime_request_ready'] and p['i_runtime_request_command'] == 5)
        for group, count, data in (('data', a['NO'], 'payload'), ('dma', a['NDO'], 'data'),
                                   ('event', a['EO'], 'payload')):
            for port in range(count):
                key = group, port
                valid = (p[f'o_{group}_out_valid'] >> port) & 1
                ready = (p[f'i_{group}_out_ready'] >> port) & 1
                width = a['E'] if group == 'event' else a['D']
                values = ((p[f'o_{group}_out_{data}'] >> (port*width)) & ((1 << width) - 1),)
                if group != 'event':
                    values += ((p[f'o_{group}_out_metadata'] >> (port*a['M'])) &
                               ((1 << a['M']) - 1),)
                if key in self.held and not flushing and not self.active.get('allow_fatal'):
                    assert valid and values == self.held[key], ('Unstable egress', key)
                if valid and not ready and not flushing:
                    self.held[key] = values
                else:
                    self.held.pop(key, None)
