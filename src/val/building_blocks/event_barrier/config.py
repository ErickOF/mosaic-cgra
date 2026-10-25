"""Expected elaboration and reproducible campaign controls."""
from dataclasses import dataclass
import os
from math import prod
from pathlib import Path
from event_barrier.transaction import PORTS

DEFAULTS = dict(NUM_EVENTS=16, EVENT_COUNT_WIDTH=4, NUM_WAIT_SLOTS=4,
                WAIT_RESULT_QUEUE_DEPTH=4, NUM_BARRIERS=4, MAX_PARTICIPANTS=16,
                BARRIER_RELEASE_QUEUE_DEPTH=4, GENERATION_WIDTH=4, CONTEXT_ID_WIDTH=8,
                WAITER_TAG_WIDTH=8, BARRIER_TAG_WIDTH=8, SUPPORT_WAIT_CONSUME=1,
                SUPPORT_WAIT_CANCEL=1, SUPPORT_BARRIER_EVENTS=1, PROTECT_STATE=0, ASYNC_RESET=0)


@dataclass(frozen=True)
class EventBarrierConfig:
    parameters: dict
    seed: int
    random_cycles: int
    coverage_file: Path
    check_internals: bool
    hdl_assertions: bool

    @classmethod
    def from_environment(cls):
        def setting(name, default):
            return int(os.getenv('EVENT_BARRIER_' + name, str(default)), 0)
        parameters = {name: setting(name, value) for name, value in DEFAULTS.items()}
        path = Path(os.getenv('COCOTB_RESULTS_FILE', 'build/event_barrier/results.xml'))
        return cls(parameters, setting('SEED', 20261021), setting('RANDOM_CYCLES', 2000),
                   Path(os.getenv('EVENT_BARRIER_COVERAGE_FILE', str(path.with_name('coverage.json')))),
                   bool(setting('CHECK_INTERNALS', 1)), bool(setting('HDL_ASSERTIONS', 1)))

    def __getattr__(self, name):
        if name in self.parameters:
            return self.parameters[name]
        raise AttributeError(name)

    @property
    def widths(self):
        p = self.parameters
        values = dict(E=p['NUM_EVENTS'], K=p['EVENT_COUNT_WIDTH'], W=p['NUM_WAIT_SLOTS'],
                      B=p['NUM_BARRIERS'], P=p['MAX_PARTICIPANTS'], G=p['GENERATION_WIDTH'],
                      C=p['CONTEXT_ID_WIDTH'], WT=p['WAITER_TAG_WIDTH'], BT=p['BARRIER_TAG_WIDTH'])
        for name, count in (('EI', values['E']), ('WI', values['W']), ('BI', values['B']),
                            ('PI', values['P'])):
            values[name] = max(1, (count - 1).bit_length())
        values['QW'] = p['WAIT_RESULT_QUEUE_DEPTH'].bit_length()
        values['QR'] = p['BARRIER_RELEASE_QUEUE_DEPTH'].bit_length()
        return {name: width if isinstance(width, int) else
                prod(values[term] for term in width.split('*'))
                for name, (_, width) in PORTS.items()}
