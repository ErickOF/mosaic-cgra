"""Packed port transactions and observations of actual DUT signals."""

from dataclasses import dataclass
from pyuvm import uvm_sequence_item
from mosaic_uvm.logic import bits

INPUTS = ('i_read_enable', 'i_read_address', 'i_write_enable', 'i_write_address', 'i_write_data')


def pack(words, width):
    return ''.join(bits(word, width) for word in reversed(tuple(words)))


def fields(word, width):
    return tuple(word[len(word)-(index+1)*width:len(word)-index*width] for index in range(len(word)//width))


def known(word):
    return set(word) <= {'0', '1'}


class RegisterFileItem(uvm_sequence_item):
    def __init__(self, label, ports, *, edge=True, random=False, four_state_data=False):
        super().__init__(label)
        self.ports = dict(ports)
        self.edge, self.random, self.four_state_data = edge, random, four_state_data
        self.pre = None


@dataclass(frozen=True)
class Observation:
    ports: dict[str, str]
    storage: tuple[str, ...]
    item: RegisterFileItem
    stage: str


@dataclass(frozen=True)
class Activity:
    name: str
    forbidden: bool
