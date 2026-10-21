"""Mandatory checked DMA progress, ownership and recovery evidence."""
from collections import Counter
import os
from itertools import product
from mosaic_uvm.components import CoverageCollector


class DmaCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.commands=self.starts=self.completions=self.events=self.random_cycles=0
        self.concurrent=self.flushes=self.timeouts=self.stale_responses=0
        self.reset_discarded=self.flush_discarded=0
        self.cancel_deadline_discard=False
        self.error_clear_collision=False
        self.command_errors=set();self.command_occupancy=set();self.data_occupancy=set();self.fifo_activity=set()
        self.payload_states=set();self.element_sizes=set();self.start_modes=set();self.regions=set()
        self.contexts=set();self.streams=set();self.priority_burst=set();self.event_masks=set();self.event_ids=set();self.cancel_bytes=set()
        self.channel_modes=set();self.address_modes=set();self.rejections=set();self.region_results=set()
        self.statuses=set();self.cancel_phases=set();self.resets=set();self.observations=Counter()

    def report(self):
        c=self.config
        # The FIFO drains one beat per cancel edge. If it is smaller than the
        # acknowledgement deadline, buffered data cannot remain at that edge.
        deadline_discard_reachable=(c.SUPPORT_CANCELLATION and 2<=c.CANCEL_TIMEOUT_CYCLES<=c.DATA_FIFO_DEPTH
            and c.DATA_FIFO_DEPTH<(1<<c.COUNT_WIDTH))
        goals=dict(new_error_wins_over_clear=self.error_clear_collision,
            buffered_discard_after_ack_deadline=not deadline_discard_reachable or self.cancel_deadline_discard,
            legal_four_state_payloads=set(product(range(3),'xz'))<=self.payload_states,
            context_bit_classes={0,1<<(c.CONTEXT_ID_WIDTH-1),(1<<c.CONTEXT_ID_WIDTH)-1}<=self.contexts,
            stream_identifier_bit_classes={0,1<<(c.STREAM_ID_WIDTH-1),(1<<c.STREAM_ID_WIDTH)-1}<=self.streams,
            backend_priority_burst_cross=set(product({0,1<<(c.PRIORITY_WIDTH-1),(1<<c.PRIORITY_WIDTH)-1},{1,c.MAX_BURST_BEATS}))<=self.priority_burst,
            every_completion_event=set(range(c.NUM_EVENTS))<=self.event_ids,
            event_mode_mask_population=not c.SUPPORT_EVENT_START or set(product((1,2),range(1,c.NUM_EVENTS+1)))<=self.event_masks,
            zero_partial_full_canceled_bytes=not c.SUPPORT_CANCELLATION or {'zero','partial','full'}<=self.cancel_bytes,
            all_element_sizes=set(range(c.derived['MAX_ELEMENT_BYTES_LOG2']+1))<=self.element_sizes,
            every_region=set(range(c.NUM_PROTECTION_REGIONS))<=self.regions,
            all_command_fifo_occupancies=set(product(range(c.NUM_CHANNELS),range(c.COMMAND_QUEUE_DEPTH+1)))<=self.command_occupancy,
            all_data_fifo_occupancies=set(range(c.DATA_FIFO_DEPTH+1))<=self.data_occupancy,
            simultaneous_fifo_push_pop=(1,1) in self.fifo_activity,
            all_channels_concurrent=self.concurrent==c.NUM_CHANNELS,
            framing_and_backend_errors={12,13,14,15}<=self.command_errors,
            stale_epochs_observed=self.stale_responses>0,
            invalid_region_update=False in self.region_results,
            all_start_modes=({0,1,2} if c.SUPPORT_EVENT_START else {0})<=self.start_modes,
            all_channels_and_transfer_modes=set(product(range(c.NUM_CHANNELS),range(3)))<=self.channel_modes,
            all_address_modes={0,1,2}<=self.address_modes,legal_region_configuration=True in self.region_results,
            command_errors_rejected={1,4,5,6,7,8,9,10,22}<=self.rejections,
            successful_completion=0 in self.statuses,error_completion=c.TRANSFER_TIMEOUT_CYCLES>256 or 1 in self.statuses,
            canceled_completion=not c.SUPPORT_CANCELLATION or 2 in self.statuses,
            queued_and_active_cancellation=not c.SUPPORT_CANCELLATION or (not c.SUPPORT_EVENT_START or 'queued' in self.cancel_phases) and 'active' in self.cancel_phases,
            coordinated_flush=self.flushes>=3,reset_from_idle_arm_data={'reset_idle','reset_arm','reset_data'}<=self.resets,
            completion_events=self.events>0,configured_random_campaign=self.random_cycles==c.random_cycles,
            edge_and_settled_observations=self.observations['edge']>0 and self.observations['pre']==self.observations['post']==self.observations['held'])
        return dict(hdl_handshake_assertions='PASS' if os.getenv('DMA_ENGINE_HDL_ASSERTIONS','1')=='1' else 'NOT_RUN',
            private_byte_assertions='PASS' if c.check_internals else 'NOT_RUN',status='PASS' if all(goals.values()) else 'FAIL',goals=goals,parameters=c.parameters,seed=c.seed,
            random_transactions=self.random_cycles,commands=self.commands,starts=self.starts,completions=self.completions,events=self.events,
            maximum_concurrent=self.concurrent,rejected_codes=sorted(self.rejections),statuses=sorted(self.statuses),
            cancel_phases=sorted(self.cancel_phases),command_errors=sorted(self.command_errors),cancel_byte_classes=sorted(self.cancel_bytes),fifo_activity=sorted(self.fifo_activity),
            command_occupancy=sorted(self.command_occupancy),data_occupancy=sorted(self.data_occupancy),reset_discarded=self.reset_discarded,flush_discarded=self.flush_discarded,flushes=self.flushes,timeouts=self.timeouts,observations=dict(self.observations))
