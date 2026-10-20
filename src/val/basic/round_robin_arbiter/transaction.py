"""One arbitration opportunity and real port/control-state observations."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

INPUTS = ('i_rstb', 'i_request', 'i_eligible', 'i_lock', 'i_accept', 'i_flush')
OUTPUTS = ('o_grant_valid', 'o_grant_onehot', 'o_grant_index', 'o_grant_lock', 'o_grant_accepted',
    'o_contended', 'o_pending', 'o_locked', 'o_lock_owner', 'o_protocol_error')
STATE = ('pointer', 'pending_valid', 'pending_index', 'pending_lock', 'locked', 'lock_owner', 'protocol_error')


class ArbiterItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False, pulse=False):
        super().__init__(label)
        self.ports = dict(ports)
        self.edge, self.random, self.pulse = edge, random, pulse
        self.pre = self.observation = None
        self.start_class = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    internals: dict[str, str]
    item: ArbiterItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    forbidden: bool
