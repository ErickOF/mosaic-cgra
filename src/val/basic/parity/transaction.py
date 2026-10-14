"""Independent generation/check words, fault provenance and real observations."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item

INPUTS = ('i_generate_data', 'i_check_data', 'i_check_parity')
CHECK_OUTPUTS = ('o_checked_data', 'o_error_vector', 'o_granule_valid', 'o_no_error', 'o_any_error')
OUTPUTS = ('o_generated_parity', *CHECK_OUTPUTS)


class ParityItem(uvm_sequence_item):
    def __init__(self, label, source, data, parity, *, base=None, faults=(), random=False, selection=None, previous_source=None):
        super().__init__(label)
        self.source, self.data, self.parity = source, data, parity
        self.base, self.faults, self.random = base, tuple(faults), random
        self.selection, self.previous_source = selection, previous_source


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    item: ParityItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    quiet: bool
