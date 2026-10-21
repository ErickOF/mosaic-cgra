"""Checked handshake coverage, explicit geometry waivers, and campaign evidence."""

from collections import Counter
from itertools import product
from mosaic_uvm.components import CoverageCollector
from agu.model import Error, Mode, known
from agu.transaction import DESCRIPTOR


def sign(value):
    return -1 if value<0 else 1 if value>0 else 0


class AguCoverage(CoverageCollector):
    def build_phase(self):
        super().build_phase()
        self.events,self.observations = Counter(),Counter()
        self.errors,self.modes,self.sizes,self.signs = set(),set(),set(),set()
        self.metadata,self.eos,self.markers,self.reset_states = set(),set(),set(),set()
        self.unknowns,self.ignored,self.ready_unknown = set(),set(),set()
        self.counts,self.recovery,self.mode_count = set(),set(),set()
        self.recovered_errors = set()
        self.size_alignment = set()
        self.range_positions,self.stall_markers = set(),set()
        self.stall=self.maximum_stall=self.random_transactions=self.exhaustive_descriptors=0
        self.transfers=self.completed=self.starts=0

    def record(self,event,p,item):
        c=self.config
        kind=event['kind']
        self.events[kind]+=1
        self.random_transactions+=item.random
        if kind in ('clear','reset') and event['previous_error']:
            self.recovered_errors.add(event['previous_error'])
        if kind=='reset': self.reset_states.add(item.get_name().removeprefix('reset_'))
        if kind=='stall':
            self.stall+=1
            self.maximum_stall=max(self.maximum_stall,self.stall)
            if event['unknown']: self.ready_unknown.add(p['i_ready'])
            self.stall_markers.add((item.pre.ports['o_first'],item.pre.ports['o_last'],item.pre.ports['o_row_last']))
        else: self.stall=0
        if event['error']: self.errors.add(event['error'])
        if kind in ('start','reject'):
            if known(p['i_element_size_log2']):
                self.size_alignment.add((int(p['i_element_size_log2'],2),event['error']))
            for name in DESCRIPTOR:
                for state in set(p[name]) & {'x','z'}: self.unknowns.add((name,state))
            if kind=='start':
                self.starts+=1
                self.exhaustive_descriptors+=item.get_name()=='exhaustive'
                d=event['descriptor'];mode=d['i_mode']
                self.modes.add(mode);self.sizes.add(d['i_element_size_log2'])
                self.signs.add((mode,sign(d['inner_step']),sign(d['outer_step'])))
                self.eos.add(d['i_emit_end_of_stream'])
                self.metadata.add((d['i_is_write'],d['i_address_space'],d['i_channel_id'],d['i_context_id']))
                self.counts.add((d['i_inner_count'],d['i_outer_count']))
                self.mode_count.add((mode,'one' if d['i_inner_count']==1 else 'many',
                    'one' if d['i_outer_count']==1 else 'many'))
                self.recovery.add(event['before'])
                for name in ('i_inner_stride','i_outer_stride'):
                    if not known(p[name]): self.ignored.update((name,state) for state in set(p[name])&{'x','z'})
        if kind in ('accept','range','complete'):
            self.transfers+=1
            pre=item.pre.ports
            self.markers.add(tuple(pre[name] for name in ('o_first','o_last','o_row_first','o_row_last')))
        if kind=='range': self.range_positions.add((event['error'],event['row'],event['column']))
        if kind=='complete': self.completed+=1

    def report(self):
        c=self.config
        errors=set(range(1,12))
        waivers={}
        if c.count_max==1:
            for error in (Error.OUTER_1D,Error.UNDERFLOW,Error.OVERFLOW):
                errors.remove(error);waivers[error.name]='COUNT_WIDTH=1 permits only one address and one row'
        if c.max_log2==0:
            for error in (Error.BASE_ALIGN,Error.INNER_ALIGN,Error.OUTER_ALIGN):
                errors.remove(error);waivers[error.name]='Only one-byte elements are enabled'
        if c.max_log2==(1<<c.size_width)-1:
            errors.remove(Error.SIZE);waivers['SIZE']='Every element-size bit encoding is supported'
        signs={(0,1,0),(1,0,0),(1,-1,0)}
        if c.width>1: signs.add((1,1,0))
        signs|={(2,a,b) for a,b in product((-1,0,1) if c.width>1 else (-1,0),repeat=2)}
        metadata=set(product((0,1),(0,(1<<c.space)-1),(0,(1<<c.channel)-1),(0,(1<<c.context)-1)))
        count_classes={(mode,'one','one') for mode in Mode}
        if c.count_max>1:
            count_classes|={(mode,'many','one') for mode in Mode}
            count_classes|={(2,a,'many') for a in ('one','many')}
        expected_exhaustive=0
        positions=range(min(6,c.count_max-1))
        expected_range={(int(error),r,col) for error,pos,axis in product(
            (Error.UNDERFLOW,Error.OVERFLOW),positions,(0,1))
            if axis==0 or c.width>1 or error==Error.UNDERFLOW
            for r,col in ((0,pos) if axis==0 else (pos,0),)}
        if c.width==1:
            waivers['POSITIVE_PROGRAMMABLE_STRIDE']='One-bit signed strides encode only zero and minus one; linear overflow remains covered'
        if (c.width,c.count,c.max_element)==(3,2,2):
            # 8-bit-pattern bases/strides, three nonzero counts, two elements,
            # two ready schedules; divide aligned dimensions independently.
            expected_exhaustive=2*sum((8//e)*3 + (8//e)*3*(8//e)
                + (8//e)*9*(8//e)**2 for e in (1,2))
        goals=dict(all_modes=set(Mode)<=self.modes, all_supported_elements=set(range(c.max_log2+1))<=self.sizes,
            all_reachable_errors=errors<=self.errors, all_stride_sign_crosses=signs<=self.signs,
            element_alignment_error_cross=set(product(range(1,c.max_log2+1),(0,6,7,8)))<=self.size_alignment,
            count_class_mode_cross=count_classes<=self.mode_count,
            direction_space_channel_context_cross=metadata<=self.metadata,
            eos_enabled_and_disabled={0,1}<=self.eos,
            first_last_and_row_markers=('1','1','1','1') in self.markers,
            bounded_maximum_count=(c.count_max,1) in self.counts and (c.count_max,c.count_max) in self.counts,
            full_rate_and_backpressure=self.events['accept']>0 if c.count_max>1 else self.completed>0,
            long_backpressure=self.maximum_stall>=32,
            unknown_ready_holds={'x','z'}<=self.ready_unknown,
            all_required_and_ignored_unknown_fields=set(product(DESCRIPTOR,'xz'))<=self.unknowns,
            unknown_ignored_strides=set(product(('i_inner_stride','i_outer_stride'),'xz'))<=self.ignored,
            reset_each_lifetime_state={'idle','active','stalled','error'}<=self.reset_states,
            sticky_error_and_recovery=self.events['clear']>0 and self.events['reject']>0 and self.starts>0,
            runtime_range_recovery=c.count_max==1 or self.events['range']>0,
            classified_error_recovery=errors<=self.recovered_errors,
            inner_and_row_boundary_range_positions=expected_range<=self.range_positions,
            completion_and_restart=self.completed>0 and self.events['start']>self.completed,
            exhaustive_small_descriptors=not expected_exhaustive or self.exhaustive_descriptors==expected_exhaustive,
            configured_random_campaign=self.random_transactions==c.random_cycles,
            actual_edge_observations=self.observations['edge']==sum(self.events.values())>0
                and self.observations['pre']==self.observations['post']==self.observations['held'])
        return dict(status='PASS' if all(goals.values()) else 'FAIL',parameters=c.parameters,seed=c.seed,
            random_transactions=self.random_transactions,goals=goals,events=dict(self.events),
            observations=dict(self.observations),starts=self.starts,transfers=self.transfers,completed=self.completed,
            exhaustive_descriptors=self.exhaustive_descriptors,expected_exhaustive_descriptors=expected_exhaustive,
            error_codes=sorted(self.errors),geometry_waivers=waivers,maximum_stall=self.maximum_stall,
            range_positions=sorted(self.range_positions),mode_stride_sign_cross=sorted(self.signs),
            mode_count_cross=sorted(self.mode_count),metadata_cross=sorted(self.metadata),
            internal_storage_assertions='PASS' if c.check_internals else 'NOT_RUN',
            hdl_handshake_assertions='PASS' if c.hdl_assertions else 'NOT_RUN')
