"""Require address/mask/hazard, credit, latency, cancellation and storage coverage."""
from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector
from mosaic_uvm.patterns import pattern_classes
from sram_wrapper.config import LONG_STALL,STREAM_LENGTH
from sram_wrapper.model import known,address

PATTERNS={'zero','one','alternating','walking_one','walking_zero'}


class SramCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.observations,self.transitions=Counter(),Counter()
        self.addresses,self.hazards,self.mask_bits,self.mask_transitions=set(),set(),set(),set()
        self.counts,self.queues,self.stage_counts,self.request_credit=set(),set(),set(),set()
        self.simultaneous,self.stall_lengths,self.stall_counts,self.tag_cross=set(),set(),set(),set()
        self.clear_stages,self.clear_queues,self.pulses,self.invalid=set(),set(),set(),set()
        self.data_bits,self.tag_bits,self.ignored_bits=set(),set(),set()
        self.random_transactions=self.backend_operations=self.uninitialized=self.zero_writes=0
        self.canceled_returns=self.full_writes=self.full_read_pop=self.max_write_stream=self.max_read_stream=0
        self.write_stream=self.read_stream=self.stalling=self.longest_stall=0
        self.previous_by_address={}
        self.ledger={}

    def record(self,e,p,item,m):
        c=self.config
        self.backend_operations+=int(e['read'] is not None or e['write'] and '1' in p['i_req_wmask'])
        self.canceled_returns+=sum(read.canceled for read in e['physical'])
        if e['clear']:
            self.clear_stages.update((e['clear'],stage) for stage in item.start['pipeline'])
            self.clear_queues.add((e['clear'],item.start['queued']))
            self.write_stream=self.read_stream=self.stalling=0
        else:
            read=e['read'];pop=e['consumed'] is not None
            self.simultaneous.add((bool(read),e['write'],pop))
            self.write_stream=self.write_stream+1 if e['write'] else 0
            self.read_stream=self.read_stream+1 if read else 0
            self.max_write_stream=max(self.max_write_stream,self.write_stream)
            self.max_read_stream=max(self.max_read_stream,self.read_stream)
            if item.pre.ports['o_rsp_valid']=='1' and p['i_rsp_ready']=='0':
                self.stalling+=1;self.stall_counts.add(e['before_count'])
                self.longest_stall=max(self.longest_stall,self.stalling)
            elif pop:self.stall_lengths.add(self.stalling);self.stalling=0
            if e['accepted']:
                target=int(p['i_req_addr'],2);kind='write' if e['write'] else 'read'
                self.addresses.add((kind,target))
                if target in self.previous_by_address:self.hazards.add((self.previous_by_address[target],kind))
                self.previous_by_address[target]=kind
                if e['write']:
                    self.mask_bits.update(enumerate(reversed(p['i_req_wmask'])))
                    transition='changed' if e['old_word']!=e['new_word'] else 'unchanged'
                    self.mask_transitions.update((name,transition) for name in pattern_classes(p['i_req_wmask']))
                    self.full_writes+=int(e['before_count']==c.credits)
                    self.zero_writes+=int('1' not in p['i_req_wmask'])
                    for bit,enable in enumerate(reversed(p['i_req_wmask'])):
                        if enable=='0':
                            word=p['i_req_wdata'][c.width-(bit+1)*c.granule:c.width-bit*c.granule]
                            self.ignored_bits.update((bit*c.granule+j,state) for j,state in enumerate(reversed(word)) if state in 'xz')
                else:
                    self.full_read_pop+=int(e['before_count']==c.credits and pop)
                    self.uninitialized+=int(not known(read.data))
                    self.tag_cross.update((name,e['before_count']) for name in pattern_classes(read.tag))
                    self.tag_bits.update(('accepted',i,s) for i,s in enumerate(reversed(read.tag)))
            if pop:
                token=e['consumed']
                self.data_bits.update((i,s) for i,s in enumerate(reversed(token.data)))
                self.tag_bits.update(('consumed',i,s) for i,s in enumerate(reversed(token.tag)))
        self.ledger=dict(accepted_reads=m.accepted_reads,accepted_writes=m.accepted_writes,effective_writes=m.effective_writes,
            zero_writes=m.zero_writes,matured=m.matured,physical_returns=m.physical_returns,
            consumed=m.consumed,canceled=m.canceled,pending=len(m.reads))

    def observe(self,obs,m):
        p,c=obs.ports,self.config
        self.observations[obs.stage]+=1
        if not m.initialized or p['i_rstb']!='1' or p['i_flush']!='0':return
        count=len(m.reads);queued=sum(r.due<m.edge for r in m.reads)
        self.counts.add(count);self.queues.add(queued)
        self.stage_counts.update((stage,count) for stage in m.pipeline())
        if obs.stage=='pre' and p['i_req_valid']=='1' and known(p['i_req_addr']):
            target=address(p['i_req_addr'],c.depth)
            if target is None:self.invalid.add(int(p['i_req_addr'],2))
            elif p['i_req_write'] in ('0','1'):
                self.request_credit.add(('write' if p['i_req_write']=='1' else 'read','empty' if count==0 else 'full' if count==c.credits else 'partial'))

    def report(self):
        c=self.config
        credit_states={'empty','full'}|({'partial'} if c.credits>1 else set())
        mask_expected={(name,state) for name in PATTERNS for state in ('unchanged','changed') if state=='unchanged' or name!='zero' and not (c.mask_width==1 and name=='walking_zero')}
        goals=dict(
            every_read_write_address=set(product(('read','write'),range(c.depth)))<=self.addresses,
            every_same_address_operation_pair=set(product(('read','write'),repeat=2))<=self.hazards,
            every_write_mask_bit=set(product(range(c.mask_width),'01'))<=self.mask_bits,
            mask_pattern_transition_cross=mask_expected<=self.mask_transitions,
            every_outstanding_count=set(range(c.credits+1))<=self.counts,
            every_completed_queue_level=set(range(c.credits+1))<=self.queues,
            latency_stage_outstanding_cross=set(product(range(c.latency+1),range(1,c.credits+1)))<=self.stage_counts,
            request_type_credit_cross=set(product(('read','write'),credit_states))<=self.request_credit,
            acceptance_response_consumption_cross={(False,False,False),(True,False,False),(False,True,False),(False,False,True),(True,False,True),(False,True,True)}<=self.simultaneous,
            writes_at_exhausted_read_credits=self.full_writes>0,
            full_read_admission_with_consumption=self.full_read_pop>0,
            response_stall_lengths=(set(range(9))|{LONG_STALL})<=self.stall_lengths,
            stalled_response_outstanding_counts=set(range(1,c.credits+1))<=self.stall_counts,
            tag_class_ordering_distance_cross=set(product(PATTERNS,range(c.credits)))<=self.tag_cross,
            reset_flush_every_latency_stage=set(product(('reset','flush'),range(c.latency+1)))<=self.clear_stages,
            reset_flush_every_response_queue_level=set(product(('reset','flush'),range(c.credits+1)))<=self.clear_queues,
            between_edge_reset_flush_empty_busy=set(product(('reset','flush'),(False,True)))<=self.pulses,
            every_unused_address_encoding=set(range(c.depth,1<<c.address_width))<=self.invalid,
            uninitialized_and_canceled_returns=self.uninitialized>0 and self.canceled_returns>0,
            zero_mask_noops=self.zero_writes>0,
            every_masked_off_unknown_bit=set(product(range(c.width),'xz'))<=self.ignored_bits,
            every_response_data_bit=set(product(range(c.width),'01xz'))<=self.data_bits,
            every_tag_bit=set(product(('accepted','consumed'),range(c.tag_width),'01xz'))<=self.tag_bits,
            continuous_write_stream=self.max_write_stream>=STREAM_LENGTH,
            continuous_read_stream=(self.max_read_stream>=STREAM_LENGTH if c.credits>=c.latency+1 else True),
            read_obligation_conservation=bool(self.ledger) and self.ledger['pending']==0 and self.ledger['accepted_reads']==self.ledger['consumed']+self.ledger['canceled'],
            randomized_campaign=self.random_transactions==c.random_cycles,
            all_sampling_stages=self.observations['pre']==self.observations['post']==self.observations['held'] and self.observations['edge']>0)
        return dict(status='PASS' if all(goals.values()) else 'FAIL',parameters=c.parameters,backend=c.backend,seed=c.seed,
            random_transactions=self.random_transactions,goals=goals,observations=dict(self.observations),token_ledger=self.ledger,
            elaboration_assertions='PASS' if c.check_internals else 'NOT_RUN',internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
            backend_pin_assertions='PASS' if c.check_internals else 'NOT_RUN',backend_operations=self.backend_operations,
            canceled_backend_returns=self.canceled_returns,full_credit_writes=self.full_writes,full_credit_read_pop=self.full_read_pop,
            maximum_read_stream=self.max_read_stream,maximum_write_stream=self.max_write_stream,longest_response_stall=self.longest_stall,
            credit_levels=sorted(self.counts),queue_levels=sorted(self.queues),stage_count_bins=sorted(self.stage_counts),request_credit_bins=sorted(self.request_credit),
            same_address_pairs=sorted(self.hazards),mask_transition_bins=sorted(self.mask_transitions),tag_distance_bins=sorted(self.tag_cross),
            stall_lengths=sorted(self.stall_lengths),stall_count_bins=sorted(self.stall_counts),clear_stage_bins=sorted(self.clear_stages),
            clear_queue_bins=sorted(self.clear_queues),pulse_bins=sorted(self.pulses),invalid_addresses=sorted(self.invalid),waveform_transitions=dict(self.transitions),
            coverage_limits=dict(read_stream='Needs latency+1 credits for the explicit t+latency edge timing' if c.credits==c.latency else 'applicable',
                mask_transition='A one-bit walking-zero mask has no enabled granule' if c.mask_width==1 else 'applicable',
                invalid_addresses='No unused encodings' if c.depth==1<<c.address_width else 'applicable'),
            external_checks=dict.fromkeys(('native_sva','formal','commercial_lint','cdc','rdc','dft','vc_lp','technology_mapping','vendor_macro_equivalence','physical_timing','physical_power','canonical_memory_contract'),'NOT_RUN'))
