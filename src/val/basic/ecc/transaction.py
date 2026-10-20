"""Independent encode/decode stimuli and immutable observations."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item


INPUTS = ('i_encode_data', 'i_decode_codeword')
DECODE_OUTPUTS = ('o_decoded_data', 'o_corrected_codeword', 'o_no_error', 'o_corrected', 'o_uncorrectable',
                  'o_scrub_required', 'o_error_position_valid', 'o_error_position', 'o_syndrome', 'o_overall_parity_error')
OUTPUTS = ('o_encoded_codeword', *DECODE_OUTPUTS)


class EccItem(uvm_sequence_item):
    def __init__(self, label, encode, received, *, base=None, faults=(), random=False):
        super().__init__(label)
        self.encode, self.received = encode, received
        self.base, self.faults, self.random = base, tuple(faults), random


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    internals: dict[str, str]
    item: EccItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    quiet: bool
