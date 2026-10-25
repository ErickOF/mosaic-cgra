"""Independent command/order/data/commit ledgers driven by real handshakes."""
from collections import deque
from pyuvm import ConfigDB,uvm_analysis_export,uvm_scoreboard
from dma_engine.model import Error,Status,addresses,legality,known,pattern
from dma_engine.constants import INPUTS,OUTPUTS
from dma_engine.backends import unpack


class DmaScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.c=ConfigDB().get(self,'','config');self.coverage=ConfigDB().get(self,'','coverage')
        self.analysis_export=uvm_analysis_export('analysis_export',self);self.analysis_export.write=self.write
        self.tick=0;self.initialized=False;self.epoch=0;self.regions={};self.reset()
        self.stalled={};self.initialized=False

    def reset(self):
        n=self.c.NUM_CHANNELS
        if hasattr(self,'queues'):
            self.coverage.reset_discarded+=sum(map(len,self.queues))+sum(r is not None for r in self.active)+sum(map(len,self.ready))
        self.queues=[deque() for _ in range(n)];self.active=[None]*n
        self.ready=[deque() for _ in range(n)];self.events={};self.regions={};self.epoch=0
        self.live=set();self.initialized=True;self.flush_seen=False;self.stalled={}

    def channel(self,p,name,ch):
        return unpack(int(p[name],2),ch,self.c.widths[name]//self.c.NUM_CHANNELS)

    def remember_error(self,record,error,status=Status.ERROR):
        if record['error']==Error.NONE:record['error']=error;record['status']=status;record['abort_at']=self.tick;self.coverage.command_errors.add(int(error))

    def data(self,record,side,index):
        d=record['d'];c=self.c;size=1<<d['element_size_log2']
        address=index if d['mode']==2 else record['source'][index]
        space=d['stream_id'] if d['mode']==2 else d['source_space']
        return pattern(address,space,d['context_id'],c.DATA_WIDTH)&((1<<(8*size))-1)

    def payload(self,p,name,ch):
        width=self.c.DATA_WIDTH;end=len(p[name])-ch*width
        return p[name][end-width:end]

    def clean_payload(self,p,prefix,ch,keep):
        word=self.payload(p,prefix+'_data',ch)
        return ''.join(word[b*8:(b+1)*8] if keep&(1<<(self.c.derived['DATA_BYTES']-b-1)) else '00000000'
            for b in range(self.c.derived['DATA_BYTES']))

    def descriptor(self,p,record,ch,side):
        d=record['d'];v=lambda name:self.channel(p,f'o_{side}_{name}',ch)
        assert v('mode')==d['address_mode'] and v('base_address')==d[f'{side if side=="source" else "destination"}_base']

    def check_descriptor(self,p,r,ch,backend):
        d=r['d'];side='source' if backend=='load' else 'destination'
        expected=dict(mode=d['address_mode'],base_address=d[f'{side}_base'],element_size_log2=d['element_size_log2'],
            inner_count=d['inner_count'],outer_count=d['outer_count'],
            inner_stride=d[f'{side}_inner_stride'] if d['address_mode']!=0 else 0,
            outer_stride=d[f'{side}_outer_stride'] if d['address_mode']==2 else 0,
            space_id=d[f'{side}_space'],context_id=d['context_id'],channel_id=d['stream_id'],
            max_burst_beats=d['max_burst_beats'],priority=d['priority'],descriptor_epoch=self.epoch)
        for name,value in expected.items():
            assert self.channel(p,f'o_{backend}_{name}',ch)==value,f'DMA descriptor assertion: {backend}.{name}'
        if backend=='load' and d['mode']==0:assert r['store_armed'],'DMA destination-first assertion'

    def stability(self,p):
        c=self.c
        for prefix,valid,ready,channel in (
                ('completion','o_completion_valid','i_completion_ready',None),('event','o_event_valid','i_event_ready',None),
                *((kind,f'o_{kind}_config_valid',f'i_{kind}_config_ready',ch) for kind in ('load','store') for ch in range(c.NUM_CHANNELS)),
                *(('stream','o_stream_valid','i_stream_ready',ch) for ch in range(c.NUM_CHANNELS)),
                *(('store_stream','o_store_stream_valid','i_store_stream_ready',ch) for ch in range(c.NUM_CHANNELS))):
            if p['i_flush']=='1' or p['i_rstb']=='0':self.stalled.clear();return
            get=lambda name: (self.payload(p,name,channel) if name in ('o_stream_data','o_store_stream_data')
                else int(p[name],2) if channel is None else self.channel(p,name,channel))
            if prefix in ('load','store'):
                names=[name for name in OUTPUTS if name.startswith('o_'+prefix+'_') and not any(
                    term in name for term in ('stream','cancel','config_valid'))]
            elif prefix=='event':names=['o_event_id','o_event_context_id','o_event_command_id','o_event_error']
            else:names=[name for name in OUTPUTS if name.startswith('o_'+prefix+'_') and name!=valid]
            key=(prefix,channel)
            # Cancellation is an explicit revocation boundary for stream/arm output.
            revoked=channel is not None and (self.channel(p,'o_load_cancel',channel) or self.channel(p,'o_store_cancel',channel) or self.channel(p,'o_channel_canceling',channel)
                or (p['i_cancel_valid']=='1' and int(p['i_cancel_channel'],2)==channel))
            if key in self.stalled and not revoked:
                assert get(valid)==1 and tuple(get(name) for name in names)==self.stalled[key],f'DMA stalled payload assertion: {key}'
            if get(valid) and not get(ready):self.stalled[key]=tuple(get(name) for name in names)
            else:self.stalled.pop(key,None)

    def advance(self,p,post,item):
        c=self.c;v=lambda name,ch:self.channel(p,name,ch);self.tick+=1
        for ch in range(c.NUM_CHANNELS):
            command_occupancy=self.channel(post,'o_command_occupancy',ch)
            data_occupancy=self.channel(post,'o_data_fifo_occupancy',ch)
            assert command_occupancy<=c.COMMAND_QUEUE_DEPTH and data_occupancy<=c.DATA_FIFO_DEPTH
            self.coverage.command_occupancy.add((ch,command_occupancy));self.coverage.data_occupancy.add(data_occupancy)
        self.coverage.random_cycles+=item.random
        if p['i_rstb']=='0':
            self.coverage.resets.add(item.get_name());self.reset();return
        if p['i_flush']=='1' and not self.flush_seen:
            self.coverage.flush_discarded+=sum(map(len,self.queues))+sum(r is not None for r in self.active)+sum(map(len,self.ready))
            self.coverage.flushes+=1;self.flush_seen=True;self.epoch=(self.epoch+1)% (1<<c.DESCRIPTOR_EPOCH_WIDTH)
            self.queues=[deque() for _ in range(c.NUM_CHANNELS)];self.active=[None]*c.NUM_CHANNELS
            self.ready=[deque() for _ in range(c.NUM_CHANNELS)];self.events={};self.live.clear();self.stalled.clear()
        elif p['i_flush']=='0':self.flush_seen=False
        if p['i_flush']=='1' or post['o_flushed']=='1':return
        self.stability(p)
        if p['o_error']=='1' and not (p['i_error_clear']=='1' and p['o_quiescent']=='1' and p['o_fatal_error']=='0'):
            assert post['o_error_code']==p['o_error_code'],'DMA sticky first error assertion'
        if p['o_fatal_error']=='1':assert post['o_fatal_error']=='1' and p['o_command_ready']=='0','DMA fatal containment assertion'
        if post['o_fatal_error']=='1':assert post['o_error']=='1','DMA fatal error without diagnostic'
        assert post['o_error']==str(int(int(post['o_error_code'],2)!=0))
        if p['i_error_clear']=='1' and p['o_quiescent']=='1' and p['o_fatal_error']=='0':
            unexpected_done=any(v(f'i_{side}_done',ch) and v(f'i_{side}_done_epoch',ch)==self.epoch
                for side in ('load','store') for ch in range(c.NUM_CHANNELS))
            expected=Error.BACKEND if unexpected_done else Error.NONE
            assert int(post['o_error_code'],2)==expected,'DMA clear lost a new error'
            if unexpected_done:self.coverage.error_clear_collision=True
        if p['o_region_ready']==p['i_region_valid']=='1':
            index=int(p['i_region_index'],2) if known(p['i_region_index']) else -1
            d={name.removeprefix('i_region_'):int(value,2) for name,value in p.items() if name.startswith('i_region_') and known(value)}
            valid=0<=index<c.NUM_PROTECTION_REGIONS and all(known(p['i_region_'+name]) for name in
                ('enable','space_id','base','limit','context_id','read_enable','write_enable')) and (
                not d['enable'] or (d['base']<d['limit']<=1<<c.ADDR_WIDTH and (d['read_enable'] or d['write_enable'])))
            assert post['o_region_updated']==str(int(valid)) and post['o_region_rejected']==str(int(not valid))
            if valid:self.regions[index]=d
            self.coverage.region_results.add(valid)
            if valid:self.coverage.regions.add(index)
        if p['o_completion_valid']=='1' and p['i_completion_ready']=='1':
            ch=int(p['o_completion_channel'],2)
            assert self.ready[ch],'DMA unexpected completion'
            record=self.ready[ch].popleft();d=record['d']
            expected=dict(channel=ch,context_id=d['context_id'],command_id=d['id'],status=int(record['status']),
                bytes_read=record['read'],bytes_written=record['written'],error_code=int(record['error']))
            for name,value in expected.items():
                assert int(p['o_completion_'+name],2)==value,f'DMA completion assertion: {name}: {int(p["o_completion_"+name],2)} != {value}'
            self.coverage.completions+=1;self.coverage.statuses.add(int(record['status']))
            if record['status']==Status.CANCELED:
                described=d['inner_count']*d['outer_count']*(1<<d['element_size_log2'])
                self.coverage.cancel_bytes.add('zero' if record['written']==0 else 'full' if record['written']==described else 'partial')
        if p['o_event_valid']=='1' and p['i_event_ready']=='1':
            key=(int(p['o_event_context_id'],2),int(p['o_event_command_id'],2))
            assert key in self.events,'DMA unexpected event'
            event=(int(p['o_event_id'],2),int(p['o_event_error'],2))
            assert event in self.events[key]
            self.events[key].remove(event)
            if not self.events[key]:del self.events[key]
            self.coverage.events+=1;self.coverage.event_ids.add(event[0])
        if p['i_command_valid']=='1' and p['o_command_ready']=='1':
            error=legality(c,p,self.regions,self.live)
            assert post['o_command_accepted']==str(int(not error)) and post['o_command_rejected']==str(int(bool(error))),f'DMA legality assertion: {error}'
            if error:
                if p['o_error']=='0':
                    assert int(post['o_error_code'],2)==int(error),'DMA rejection error-code assertion'
                self.coverage.rejections.add(int(error))
            else:
                d={name.removeprefix('i_command_'):int(value,2) for name,value in p.items() if name.startswith('i_command_') and known(value)}
                r=dict(d=d,source=addresses(c,d,'source') if d['mode']!=2 else [],
                    destination=addresses(c,d,'destination') if d['mode']!=1 else [],read=0,written=0,
                    source_index=0,destination_index=0,words=[],load_armed=False,store_armed=False,load_done=False,store_done=False,
                    status=Status.SUCCESS,error=Error.NONE,canceled=False,first_present=None)
                self.queues[d['channel']].append(r);self.live.add((d['channel'],d['context_id'],d['id']))
                self.coverage.commands+=1;self.coverage.channel_modes.add((d['channel'],d['mode']));self.coverage.address_modes.add(d['address_mode']);self.coverage.element_sizes.add(d['element_size_log2']);self.coverage.start_modes.add(d['start_mode'])
                self.coverage.contexts.add(d['context_id']);self.coverage.streams.add(d['stream_id'])
                self.coverage.priority_burst.add((d['priority'],d['max_burst_beats']))
                if d['start_mode']!=0:self.coverage.event_masks.add((d['start_mode'],d['start_event_mask'].bit_count()))
        if p['i_cancel_valid']=='1' and p['o_cancel_ready']=='1':
            ch=int(p['i_cancel_channel'],2);key=(int(p['i_cancel_context_id'],2),int(p['i_cancel_command_id'],2));r=self.active[ch]
            candidates=([r] if r and not r['canceled'] else [])+[r for r in self.queues[ch] if not r['canceled']]
            match=next((r for r in candidates if (r['d']['context_id'],r['d']['id'])==key),None)
            assert post['o_cancel_accepted']==str(int(match is not None)) and post['o_cancel_not_found']==str(int(match is None))
            if match:
                match['canceled']=True;self.remember_error(match,Error.CANCELED,Status.CANCELED)
                self.coverage.cancel_phases.add('active' if match is self.active[ch] else 'queued')
        for ch in range(c.NUM_CHANNELS):
            r=self.active[ch]
            if r is None:
                assert not any(v(name,ch) for name in ('o_load_config_valid','o_store_config_valid','o_store_stream_valid','o_stream_valid')),'DMA work without an active command'
            if r:
                d=r['d'];size=1<<d['element_size_log2'];total=d['inner_count']*d['outer_count']
                for side in ('store','load'):
                    if v(f'o_{side}_config_valid',ch):
                        self.check_descriptor(p,r,ch,side)
                        if r['first_present'] is None:r['first_present']=self.tick
                        if v(f'i_{side}_config_ready',ch):r[side+'_armed']=True
                for side in ('load','store'):
                    if v(f'i_{side}_config_rejected',ch):self.remember_error(r,Error.BACKEND);r['canceled']=True
                buffered_words=len(r['words'])
                source_valid=v('i_stream_valid',ch) if d['mode']==2 else v('i_load_stream_valid',ch)
                source_epoch_ok=d['mode']==2 or v('i_load_stream_epoch',ch)==self.epoch
                if source_valid and source_epoch_ok and (r['store_armed'] if d['mode']==2 else r['load_armed']):
                    source='i_stream' if d['mode']==2 else 'i_load_stream'
                    final=r['source_index']==total-1
                    malformed=(r['source_index']>=total or v(source+'_first',ch)!=(r['source_index']==0)
                        or v(source+('_descriptor_last' if d['mode']==2 else '_last'),ch)!=final
                        or v(source+'_keep',ch)!=(1<<size)-1)
                    if d['mode']==2:malformed=malformed or v('i_stream_id',ch)!=d['stream_id'] or v('i_stream_context_id',ch)!=d['context_id'] or v('i_stream_last',ch)!=(final and d['stream_last'])
                    if malformed:self.remember_error(r,Error.FRAMING);r['canceled']=True
                if source_valid and not source_epoch_ok:
                    assert v('o_load_stream_ready',ch)==0,'DMA stale data acceptance assertion'
                    self.coverage.stale_responses+=1
                source_ready=v('o_stream_ready',ch) if d['mode']==2 else v('o_load_stream_ready',ch)
                if source_valid and source_ready:
                    index=r['source_index'];assert index<total and not r['canceled'],'DMA source count assertion'
                    source='i_stream' if d['mode']==2 else 'i_load_stream'
                    source_word=self.clean_payload(p,source,ch,(1<<size)-1)
                    if known(source_word):assert int(source_word,2)==self.data(r,'source',index),'DMA source data assertion'
                    if not known(source_word):self.coverage.payload_states.add((d['mode'],'x' if 'x' in source_word else 'z'))
                    r['words'].append(source_word)
                    r['source_index']+=1;r['read']+=size
                    if v(source+'_error',ch):self.remember_error(r,Error.SOURCE);r['canceled']=True
                sink_valid=v('o_stream_valid',ch) if d['mode']==1 else v('o_store_stream_valid',ch)
                sink_ready=v('i_stream_ready',ch) if d['mode']==1 else v('i_store_stream_ready',ch)
                if sink_valid:
                    index=r['destination_index'];assert index<total,'DMA destination count assertion'
                    sink='o_stream' if d['mode']==1 else 'o_store_stream'
                    if d['mode']==0:
                        assert index<buffered_words,'DMA unbuffered copy assertion'
                        expected_word=r['words'][index]
                    else:
                        source='i_stream' if d['mode']==2 else 'i_load_stream'
                        expected_word=self.clean_payload(p,source,ch,(1<<size)-1)
                    assert self.payload(p,sink+'_data',ch)==expected_word,'DMA destination data assertion'
                    assert v(sink+'_keep',ch)==(1<<size)-1 and v(sink+'_first',ch)==(index==0)
                    lastname='_descriptor_last' if d['mode']==1 else '_last'
                    assert v(sink+lastname,ch)==(index==total-1),'DMA last framing assertion'
                    if d['mode']==1:
                        assert v('o_stream_last',ch)==(index==total-1 and d['stream_last'])
                        assert v('o_stream_id',ch)==d['stream_id'] and v('o_stream_context_id',ch)==d['context_id']
                    if sink_ready:
                        r['destination_index']+=1
                        if d['mode']==1:r['written']+=size
                if r['d']['mode']==0:self.coverage.fifo_activity.add((int(bool(source_valid and source_ready)),int(bool(sink_valid and sink_ready))))
                for side in ('load','store'):
                    if v(f'i_{side}_done',ch) and v(f'i_{side}_done_epoch',ch)==self.epoch:
                        r[side+'_done']=True
                        if v(f'i_{side}_done_error',ch):self.remember_error(r,Error.SOURCE if side=='load' else Error.WRITE);r['canceled']=True
                        if side=='store':r['written']=v('i_store_bytes_committed',ch)
                    if r['canceled'] and v(f'i_{side}_cancel_done',ch):r[side+'_done']=True
                    if side=='store' and v('i_store_cancel_done',ch):r['written']=v('i_store_bytes_committed',ch)
                if (r['canceled'] and self.tick-r['abort_at']>=c.CANCEL_TIMEOUT_CYCLES
                        and v('o_channel_canceling',ch) and v('o_data_fifo_occupancy',ch)>0
                        and all(not r[side+'_armed'] or r[side+'_done'] for side in ('load','store'))):
                    assert not v('o_event_timeout',ch) and not self.channel(post,'o_event_timeout',ch),'DMA acknowledged cancel timeout assertion'
                    self.coverage.cancel_deadline_discard=True
                if unpack(int(post['o_event_timeout'],2),ch,1):
                    if r['canceled']:
                        assert self.tick-r['abort_at']==c.CANCEL_TIMEOUT_CYCLES,'DMA cancel timeout boundary assertion'
                    else:
                        assert r['first_present'] is not None and self.tick-r['first_present']+1==c.TRANSFER_TIMEOUT_CYCLES,'DMA transfer timeout boundary assertion'
                    self.remember_error(r,Error.TIMEOUT);r['canceled']=True;self.coverage.timeouts+=1
            if unpack(int(post['o_event_command_complete'],2),ch,1):
                if r is None:
                    assert self.queues[ch] and self.queues[ch][0]['canceled'],'DMA retirement without command'
                    r=self.queues[ch].popleft()
                if r['error']==Error.NONE:
                    d=r['d'];total=d['inner_count']*d['outer_count']
                    assert r['source_index']==r['destination_index']==total,'DMA early success assertion'
                    assert (d['mode']==2 or r['load_done']) and (d['mode']==1 or r['store_done']),'DMA premature backend completion'
                else:
                    assert all(not r[side+'_armed'] or r[side+'_done'] for side in ('load','store')),'DMA retirement before safe backend teardown'
                self.ready[ch].append(r)
                d=r['d'];self.live.remove((ch,d['context_id'],d['id']))
                if d['completion_event_enable']:self.events.setdefault((d['context_id'],d['id']),[]).append((d['completion_event_id'],int(r['status']!=Status.SUCCESS)))
                self.active[ch]=None
            if unpack(int(post['o_event_command_start'],2),ch,1):
                assert self.active[ch] is None and self.queues[ch],'DMA start/order assertion'
                r=self.queues[ch].popleft();assert not r['canceled']
                d=r['d'];mask=d.get('start_event_mask',0);pending=int(p['i_event_pending'],2)
                assert d['start_mode']==0 or (d['start_mode']==1 and mask&pending) or (d['start_mode']==2 and mask&pending==mask),'DMA early event start'
                self.active[ch]=r;self.coverage.starts+=1
        self.coverage.concurrent=max(self.coverage.concurrent,sum(r is not None for r in self.active))

    def write(self,obs):
        p,item,stage=obs.ports,obs.item,obs.stage
        for name in INPUTS:assert p[name]==item.ports[name],f'DMA stimulus coercion: {name}'
        if stage=='pre' and self.c.ASYNC_RESET and p['i_rstb']=='0':self.reset()
        for name in OUTPUTS:
            if not self.initialized:continue
            if name not in ('o_stream_data','o_store_stream_data'):assert known(p[name]),f'DMA unknown output assertion: {name}'
        if self.initialized:
            for ch in range(self.c.NUM_CHANNELS):
                for prefix in ('o_stream','o_store_stream'):
                    if not self.channel(p,prefix+'_valid',ch):
                        assert set(self.payload(p,prefix+'_data',ch))=={'0'},'DMA invalid payload isolation assertion'
        if stage=='edge':
            assert all(p[name]==item.pre.ports[name] for name in OUTPUTS),'DMA pre-NBA edge observation'
        if stage == 'post' and obs.internals:
            self.check_directory_and_timer(item.pre, obs)
        if stage=='post' and item.edge:self.advance(item.pre.ports,p,item)
        if obs.internals and self.initialized:
            for ch,r in enumerate(self.active):
                if r:
                    for actual,expected in (('bytes_read','read'),('bytes_written','written')):
                        assert int(obs.internals[actual][ch],2)==r[expected],f'DMA private byte-count assertion: {actual}[{ch}]'
        self.coverage.observations[stage]+=1

    def check_directory_and_timer(self, pre, post):
        """Check captures and retention against public acceptance, including reset.

        Untouched entries must retain their four-state payload. Reading the bank
        directly also checks unoccupied entries, which duplicate-ID queries mask.
        """
        c = self.c
        p = pre.ports
        accepted = (
            post.item.edge and p['i_rstb'] == '1'
            and post.ports['o_command_accepted'] == '1'
        )
        channel = int(p['i_command_channel'], 2) if accepted else -1
        for ch in range(c.NUM_CHANNELS):
            write = int(pre.internals['directory_pointer'][ch], 2) if ch == channel else -1
            for slot in range(c.COMMAND_QUEUE_DEPTH):
                index = ch * c.COMMAND_QUEUE_DEPTH + slot
                expected = pre.internals['directory'][index]
                if slot == write:
                    expected = p['i_command_context_id'] + p['i_command_id']
                    self.coverage.directory_captures.add((ch, slot))
                else:
                    self.coverage.directory_holds += 1
                assert post.internals['directory'][index] == expected, (
                    f'DMA command directory capture/hold assertion: channel {ch}, slot {slot}'
                )
            # Phase encodings are independently defined in the local DMA package.
            if p['i_rstb'] == '1' and pre.internals['phase'][ch] == '110':
                assert post.internals['cancel_timer'][ch] == pre.internals['cancel_timer'][ch], (
                    f'DMA fatal cancel timer hold assertion: channel {ch}'
                )
                self.coverage.fatal_timer_holds += 1

    def check_phase(self):
        assert not self.live and not any(self.queues) and not any(self.active) and not any(self.ready) and not self.events,'DMA unfinished command/event ledger'
        assert self.coverage.commands==self.coverage.completions+self.coverage.reset_discarded+self.coverage.flush_discarded,'DMA accepted-command conservation'
