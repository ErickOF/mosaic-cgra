"""Independent authoritative resource/obligation checks, not a lifecycle RTL mirror."""
from dataclasses import dataclass, field
from runtime_controller.config import CODES, WIDTHS, pack, unpack

CMD = CODES['command']
EP = CODES['endpoint']
ACK = CODES['ack_status']
STATE = CODES['kernel_state']
NOTICE = CODES['notice_status']


def key(identity: int) -> tuple[int, ...]:
    i = unpack('identity', identity)
    return tuple(i[n] for n in ('owner_id', 'kernel_id', 'descriptor_id', 'descriptor_generation'))


def lane(value: int, index: int, width: int) -> int:
    return value >> (index * width) & ((1 << width) - 1)


@dataclass
class Obligation:
    descriptor: dict
    admitted: bool = False
    admission_seen: bool = False
    admission_proof: bool = False
    result_seen: bool = False
    clusters: int = 0
    allocation: int = 0
    package: int = 0
    mapping: int = 0
    array_owned: bool = False
    services: set[int] = field(default_factory=set)
    loaded: bool = False
    validated: bool = False
    prepared: bool = False
    committed: bool = False
    active_services: set[int] = field(default_factory=set)
    running: bool = False
    drained: bool = False
    epoch: int = 0
    tags: set[int] = field(default_factory=set)
    events: set[tuple[int, int, int]] = field(default_factory=set)


class Ledger:
    """Check exactly-once notices and ownership at successful terminal acknowledgements."""
    def __init__(self, parameters):
        self.p = parameters
        self.records = {}
        self.pending = {}
        self.seen_tags = set()
        self.last_tag = 0
        self.reset_discards = 0
        self.commands = 0

    def submit(self, ports):
        ident = pack('identity', **{n: ports['i_submit_' + n] for n in
                     ('owner_id', 'kernel_id', 'descriptor_id', 'descriptor_generation')})
        ident_key = key(ident)
        # A deliberately duplicated live owner/kernel may have a distinct descriptor ID.
        assert ident_key not in self.records, ('Duplicate exact descriptor in test', ident_key)
        self.records[ident_key] = Obligation({n.removeprefix('i_submit_'): v
                                             for n, v in ports.items() if n.startswith('i_submit_')})

    def command(self, ep, action):
        self.commands += 1
        tag = action['tag']
        assert tag not in self.seen_tags and tag > self.last_tag, ('Tag reuse/wrap', tag)
        self.last_tag = tag
        self.seen_tags.add(tag)
        assert not self.pending, ('More than one serialized action', self.pending)
        self.pending[tag] = (ep, action)
        r = self.records[key(action['identity'])]
        i = unpack('identity', action['identity'])
        assert r.descriptor['owner_id'] == i['owner_id']
        for field in ('resources', 'qos', 'power', 'lifecycle'):
            name = 'resource' if field == 'resources' else field
            assert action[field] == r.descriptor[name + '_record'], ('Action contract metadata', field)
        variants = [unpack('variant', lane(r.descriptor['variant_records'], v, 256))
                    for v in range(r.descriptor['variant_count'])]
        assert any(v['package_id'] == i['package_id'] and v['mapping_id'] == i['mapping_id']
                   and v['cluster_mask'] == action['cluster_mask'] for v in variants)
        if r.allocation:
            assert (i['allocation_generation'], i['package_id'], i['mapping_id']) == (
                r.allocation, r.package, r.mapping)
        else:
            r.allocation, r.package, r.mapping = (
                i['allocation_generation'], i['package_id'], i['mapping_id'])
        if ep == EP['ARRAY'] and action['command'] in (CMD['START'], CMD['RESUME']):
            assert r.array_owned and r.committed
            required = unpack('resource', r.descriptor['resource_record'])['services']
            assert all(s in r.services and s in r.active_services for s in range(6) if required >> s & 1)
            assert i['epoch'] > r.epoch and i['epoch'] != 0

    def response(self, ep, ack):
        tag = ack['tag']
        if tag not in self.pending:
            return False
        expected_ep, action = self.pending[tag]
        if ep != expected_ep or any(ack[n] != action[n] for n in ('identity', 'command', 'tag')):
            return False
        del self.pending[tag]
        r = self.records[key(action['identity'])]
        if ack['status'] == ACK['UNCERTAIN']:
            if action['command'] == CMD['RESERVE']:
                r.services.add(ep)
            if ep == EP['ARRAY'] and action['command'] == CMD['ALLOCATE']:
                r.array_owned = True
                r.clusters = action['cluster_mask']
            return True
        if ack['status'] != ACK['OK'] or ack['cluster_mask'] != action['cluster_mask']:
            return True
        cmd = action['command']
        if ep == EP['ARRAY']:
            if cmd == CMD['ALLOCATE']:
                assert not r.array_owned
                assert all(not other.array_owned or not (other.clusters & action['cluster_mask'])
                           for other in self.records.values())
                r.array_owned = True
                r.clusters = action['cluster_mask']
            elif cmd == CMD['COMMIT']:
                assert r.array_owned and r.prepared
                r.committed = True
            elif cmd in (CMD['START'], CMD['RESUME']):
                r.running = True
                r.drained = False
                r.epoch = unpack('identity', action['identity'])['epoch']
            elif cmd in (CMD['DRAIN'], CMD['ABORT'], CMD['SUSPEND']):
                r.running = False
                r.drained = True
            elif cmd == CMD['RELEASE']:
                assert not r.running and not r.services
                r.array_owned = False
        else:
            if cmd == CMD['RESERVE']:
                assert r.array_owned and ep not in r.services
                resources = unpack('resource', r.descriptor['resource_record'])
                for other in self.records.values():
                    if other is r or ep not in other.services:
                        continue
                    other_resources = unpack('resource', other.descriptor['resource_record'])
                    for resource in {1: ('dma_mask',), 2: ('memory_mask', 'scratchpad_mask'),
                                     4: ('event_mask', 'counter_mask')}.get(ep, ()):
                        assert not (resources[resource] & other_resources[resource]), resource
                r.services.add(ep)
                required = unpack('resource', r.descriptor['resource_record'])['services']
                r.admission_proof |= all(s in r.services for s in range(6) if required >> s & 1)
            elif cmd == CMD['LOAD']:
                assert ep in r.services
                r.loaded = True
            elif cmd == CMD['VALIDATE']:
                assert r.loaded
                r.validated = True
            elif cmd == CMD['PREPARE']:
                assert r.validated
                r.prepared = True
            elif cmd in (CMD['ACTIVATE'], CMD['RESUME']):
                assert ep in r.services
                r.active_services.add(ep)
            elif cmd == CMD['RELEASE']:
                # Service rollback and normal cleanup occur in reverse acquired order.
                assert ep in r.services and ep == max(r.services)
                r.services.remove(ep)
                r.active_services.discard(ep)
        return True

    def admission(self, notice):
        r = self.records[key(notice['identity'])]
        assert not r.admission_seen
        r.admission_seen = True
        r.admitted = notice['status'] == NOTICE['ADMITTED']
        assert notice['tag'] == r.descriptor['tag']
        if r.admitted:
            required = unpack('resource', r.descriptor['resource_record'])['services']
            assert r.admission_proof
        else:
            assert not r.array_owned and not r.services

    def result(self, notice):
        r = self.records[key(notice['identity'])]
        assert r.admission_seen and r.admitted and not r.result_seen
        assert not r.array_owned and not r.services and not r.running
        r.result_seen = True
        assert notice['tag'] == r.descriptor['tag']

    @property
    def outstanding(self):
        return sum(not r.admission_seen or (r.admitted and not r.result_seen)
                   for r in self.records.values())
