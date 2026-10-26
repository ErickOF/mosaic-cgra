"""Coverage is earned from checked transfers and explicit negative scenarios."""
from collections import Counter
from mosaic_uvm.components import CoverageCollector


class MstCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.bins = Counter()
        self.cycles = 0

    def hit(self, name, count=1):
        self.bins[name] += count

    def report(self):
        required = ['reset', 'context', 'region', 'load', 'store', 'forward',
                    'copy', 'dma', 'bounds', 'duplicate', 'cancel', 'backpressure',
                    'event', 'completion', 'unaligned', 'conversion', 'two_dimensional', 'reliable_event', 'chain', 'buffer_roles',
                    'queue_flush', 'timeout', 'suspend_resume', 'terminate_drain', 'counters',
                    'rejection_matrix', 'malformed_stream', 'memory_backpressure',
                    'automatic_context', 'concurrent_channels', 'control_protection', 'partial_write', 'out_of_order_response', 'retention', 'cancel_containment',
                    'stale_tag_containment', 'unknown_descriptor']
        p = self.config.parameters
        optional = dict(copy='SUPPORT_LOCAL_COPY', unaligned='SUPPORT_UNALIGNED',
                        conversion='SUPPORT_ELEMENT_CONVERSION',
                        two_dimensional='SUPPORT_2D', cancel='SUPPORT_CANCELLATION',
                        event='SUPPORT_EVENT_START')
        enabled = dict(retention=p['SUPPORT_RETENTION'],
            out_of_order_response=p['MAX_OUTSTANDING_READS'] > 1,
            cancel_containment=p['CANCEL_TIMEOUT_CYCLES'] <= 64, chain=p['SUPPORT_COMMAND_CHAINING'] and p['NUM_EVENTS'] >= 4,
            buffer_roles=p['SUPPORT_DOUBLE_BUFFER'],
            queue_flush=p['SUPPORT_CANCELLATION'] and p['SUPPORT_EVENT_START'],
            suspend_resume=p['SUPPORT_EVENT_START'], timeout=p['TRANSFER_TIMEOUT_CYCLES'] >= 24,
            partial_write=p['MAX_ELEMENT_BYTES'] >= 2,
            concurrent_channels=p['NUM_LOAD_CHANNELS'] >= 2 and p['NUM_STREAM_OUTPUTS'] >= 2,
            control_protection=p['CONTROL_PROTECTION'])
        required = [n for n in required if enabled.get(n, True)]
        return dict(status='PASS', parameters=p, random_transactions=self.config.random_cycles,
                    hdl_assertions='NOT_RUN', synthesis='Design Compiler (deferred)', goals={n: bool(self.bins[n]) for n in required if n not in optional or
                         p[optional[n]]}, bins=dict(self.bins), cycles=self.cycles,
                    seed=self.config.seed)
