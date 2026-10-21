"""Independent load/store peers with randomized issue, commit and cancel latency.

These are protocol models of external engines, not replacement synthesizable
backends. Ordered data is generated from received affine descriptors; stores
commit independently of acceptance so cancellation can report partial progress.
"""
import random
from dma_engine.model import pattern,signed


def unpack(value,channel,width): return (value>>(channel*width))&((1<<width)-1)


class Backends:
    def __init__(self,c):
        self.c=c;self.rng=random.Random(c.seed^0xD0A)
        self.cycle=0;self.reset()

    def reset(self):
        self.load=[None]*self.c.NUM_CHANNELS;self.store=[None]*self.c.NUM_CHANNELS
        self.committed=[0]*self.c.NUM_CHANNELS
        self.pending_load_done=[None]*self.c.NUM_CHANNELS
        self.pending_store_done=[None]*self.c.NUM_CHANNELS
        self.cancel_load=[None]*self.c.NUM_CHANNELS;self.cancel_store=[None]*self.c.NUM_CHANNELS
        self.beat=[None]*self.c.NUM_CHANNELS
        self.queued=[[] for _ in range(self.c.NUM_CHANNELS)]
        self.owner=[None]*self.c.NUM_CHANNELS
        self.tile_index=[0]*self.c.NUM_CHANNELS

    def descriptor(self,p,c,side):
        widths=self.c.derived
        d={name:unpack(int(p[f'o_{side}_{name}'],2),c,widths[width]) for name,width in (
            ('mode','MODE_WIDTH'),('base_address','ADDR_WIDTH'),('element_size_log2','SIZE_WIDTH'),
            ('inner_count','COUNT_WIDTH'),('outer_count','COUNT_WIDTH'),('inner_stride','ADDR_WIDTH'),
            ('outer_stride','ADDR_WIDTH'),('space_id','SPACE_ID_WIDTH'),('context_id','CONTEXT_ID_WIDTH'),
            ('channel_id','STREAM_ID_WIDTH'),('priority','PRIORITY_WIDTH'),('max_burst_beats','BURST_WIDTH'),('descriptor_epoch','DESCRIPTOR_EPOCH_WIDTH'))}
        step=(1<<d['element_size_log2']) if d['mode']==0 else signed(d['inner_stride'],self.c.ADDR_WIDTH)
        outer=signed(d['outer_stride'],self.c.ADDR_WIDTH) if d['mode']==2 else 0
        d['addresses']=[d['base_address']+r*outer+k*step for r in range(d['outer_count']) for k in range(d['inner_count'])]
        d.update(index=0,canceling=False,commits=[])
        return d

    def prepare(self,options):
        c=self.c;p={}
        def put(name,ch,value):
            width=c.widths[name]//c.NUM_CHANNELS
            p[name]=(p.get(name,0)&~(((1<<width)-1)<<(ch*width)))|(value<<(ch*width))
        for ch in range(c.NUM_CHANNELS):
            load,store=self.load[ch],self.store[ch]
            put('i_load_config_ready',ch,int(load is None and not options.get('hold_load_arm') and self.rng.random()<(1 if options.get('full_rate') else 0.8)))
            put('i_store_config_ready',ch,int(store is None and not options.get('hold_store_arm') and self.rng.random()<(1 if options.get('full_rate') else 0.8)))
            put('i_store_stream_ready',ch,int(store is not None and not store['canceling'] and
                not options.get('hold_store_data') and self.rng.random()<(1 if options.get('full_rate') else 0.75)))
            put('i_stream_ready',ch,int(not options.get('hold_tile_output') and self.rng.random()<(1 if options.get('full_rate') else 0.75)))
            if load and not load['canceling'] and load['index']<len(load['addresses']):
                if self.beat[ch] is None and not options.get('hold_load_data') and self.rng.random()<(1 if options.get('full_rate') else 0.8):
                    index=load['index'];size=1<<load['element_size_log2']
                    self.beat[ch]=dict(data=pattern(load['addresses'][index],load['space_id'],load['context_id'],c.DATA_WIDTH),
                        keep=(1<<size)-1,first=int(index==0),last=int(index==len(load['addresses'])-1),error=0)
                if self.beat[ch] is not None:
                    put('i_load_stream_valid',ch,1)
                    for name,value in self.beat[ch].items():put('i_load_stream_'+name,ch,value)
                    put('i_load_stream_epoch',ch,load['descriptor_epoch'])
                    fault=options.get('load_fault')
                    if fault and load['index']==fault[1]:put('i_load_stream_'+fault[0],ch,fault[2])
            owner=self.owner[ch]
            if owner and owner['mode']==2 and self.tile_index[ch]<min(owner['inner_count']*owner['outer_count'],options.get('tile_limit',owner['inner_count']*owner['outer_count'])) and not options.get('hold_tile_input'):
                index=self.tile_index[ch];size=1<<owner['element_size_log2']
                put('i_stream_valid',ch,1)
                put('i_stream_data',ch,pattern(index,owner['stream_id'],owner['context_id'],c.DATA_WIDTH))
                put('i_stream_keep',ch,(1<<size)-1);put('i_stream_first',ch,int(index==0))
                final=index==owner['inner_count']*owner['outer_count']-1
                put('i_stream_descriptor_last',ch,int(final));put('i_stream_last',ch,int(final and owner['stream_last']))
                put('i_stream_id',ch,owner['stream_id']);put('i_stream_context_id',ch,owner['context_id'])
                fault=options.get('tile_fault')
                if fault and index==fault[1]:put('i_stream_'+fault[0],ch,fault[2])
            due=self.pending_load_done[ch]
            if due and due[0]<=self.cycle and not options.get('hold_load_done'):
                put('i_load_done',ch,1);put('i_load_done_epoch',ch,due[1]);put('i_load_done_error',ch,int(bool(options.get('load_done_error'))))
            if store and not options.get('hold_commit'):
                while store['commits'] and store['commits'][0][0]<=self.cycle:
                    _,size=store['commits'].pop(0);self.committed[ch]+=size
                if store['index']==len(store['addresses']) and not store['commits'] and not store['canceling'] and self.pending_store_done[ch] is None:
                    self.pending_store_done[ch]=(self.cycle+self.rng.randrange(1,4),store['descriptor_epoch'])
            due=self.pending_store_done[ch]
            if due and due[0]<=self.cycle and not options.get('hold_store_done'):
                put('i_store_done',ch,1);put('i_store_done_epoch',ch,due[1]);put('i_store_done_error',ch,int(bool(options.get('store_done_error'))))
            put('i_store_bytes_committed',ch,self.committed[ch])
            for side,table in (('load',self.cancel_load),('store',self.cancel_store)):
                if table[ch] is not None and table[ch]<=self.cycle and not options.get('hold_cancel_ack'):
                    put(f'i_{side}_cancel_done',ch,1)
        return p

    def advance(self,p,post,options):
        c=self.c
        val=lambda name,ch:unpack(int(p[name],2),ch,c.widths[name]//c.NUM_CHANNELS)
        if p['i_rstb']=='0':self.reset();self.cycle+=1;return
        if post['o_command_accepted']=='1':
            d={name.removeprefix('i_command_'):int(value,2) for name,value in p.items()
                if name.startswith('i_command_') and set(value)<={'0','1'}}
            d['canceled']=False;self.queued[d['channel']].append(d)
        if post['o_cancel_accepted']=='1':
            channel=int(p['i_cancel_channel'],2)
            for d in self.queued[channel]:
                if (d['context_id'],d['id'])==(int(p['i_cancel_context_id'],2),int(p['i_cancel_command_id'],2)):d['canceled']=True
        if p['i_flush']=='1':
            self.queued=[[] for _ in range(c.NUM_CHANNELS)];self.owner=[None]*c.NUM_CHANNELS
        for ch in range(c.NUM_CHANNELS):
            if unpack(int(post['o_event_command_complete'],2),ch,1):
                if self.owner[ch] is not None:self.owner[ch]=None
                elif self.queued[ch] and self.queued[ch][0]['canceled']:self.queued[ch].pop(0)
            if unpack(int(post['o_event_command_start'],2),ch,1):
                assert self.queued[ch] and not self.queued[ch][0]['canceled']
                self.owner[ch]=self.queued[ch].pop(0);self.tile_index[ch]=0
            if val('i_stream_valid',ch) and val('o_stream_ready',ch):self.tile_index[ch]+=1
            for side,table in (('load',self.load),('store',self.store)):
                if val(f'o_{side}_config_valid',ch) and val(f'i_{side}_config_ready',ch):
                    assert table[ch] is None,f'{side} rearmed while busy'
                    table[ch]=self.descriptor(p,ch,side)
                    if side=='store':self.committed[ch]=0
            if val('i_load_stream_valid',ch) and val('o_load_stream_ready',ch):
                load=self.load[ch]
                assert load is not None
                load['index']+=1;self.beat[ch]=None
                if load['index']==len(load['addresses']):
                    self.pending_load_done[ch]=(self.cycle+self.rng.randrange(1,5),load['descriptor_epoch'])
            if val('o_store_stream_valid',ch) and val('i_store_stream_ready',ch):
                store=self.store[ch];assert store is not None
                store['index']+=1
                store['commits'].append((self.cycle+self.rng.randrange(1,8),1<<store['element_size_log2']))
            for side,table,pending,cancel in (
                    ('load',self.load,self.pending_load_done,self.cancel_load),
                    ('store',self.store,self.pending_store_done,self.cancel_store)):
                if val(f'o_{side}_cancel',ch) and table[ch] and not table[ch]['canceling']:
                    table[ch]['canceling']=True;pending[ch]=None
                    cancel[ch]=self.cycle+options.get('cancel_delay',self.rng.randrange(1,5))
                    if side=='load':self.beat[ch]=None
                    else:table[ch]['commits'].clear()  # Uncommitted stores are discarded, never rolled back.
                if val(f'i_{side}_cancel_done',ch):
                    table[ch]=None;pending[ch]=None;cancel[ch]=None
                elif val(f'i_{side}_done',ch) and table[ch] and val(f'i_{side}_done_epoch',ch)==table[ch]['descriptor_epoch']:
                    table[ch]=None;pending[ch]=None;cancel[ch]=None
        self.cycle+=1
