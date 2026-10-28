"""Check accepted-beat conservation, ordering, credit bounds and held records."""
from pyuvm import ConfigDB, uvm_subscriber
from global_noc.model import Ledger, FlitLedger, extract

class NocScoreboard(uvm_subscriber):
    def build_phase(self):
        self.c=ConfigDB().get(self,'','config')
        self.active=ConfigDB().get(self,'','active')
        self.coverage=ConfigDB().get(self,'','coverage')
        self.ledger=Ledger()
        self.flits=FlitLedger(self.c.parameters,self.c.a)
        self.previous_credits=None
        self.holds={}

    def write(self,obs):
        p=obs.ports
        c,a=self.c.parameters,self.c.a
        self.coverage.cycles+=1
        if p['i_noc_rstb']==0:
            self.coverage.counts['reset_discards']+=self.ledger.outstanding
            self.ledger=Ledger();self.flits.flush();self.previous_credits=None
            self.holds.clear();return
        if p['i_noc_rstb'] is None:return
        if p['o_flushing']:
            self.coverage.counts['discarded']+=self.ledger.flush()
            self.holds.clear();self.flits.flush();self.previous_credits=None
            return
        assert not p['o_fatal_error'] or self.active.get('expect_fatal'),p
        if p['o_fatal_error']:
            assert not p['o_tile_rx_valid'],'Fatal transport published a successful beat'
            self.holds.clear();self.previous_credits=None
            return
        for i in range(a['NE']*a['TX']):
            if p['i_tile_tx_valid']>>i & p['o_tile_tx_ready']>>i & 1:
                beat=extract(p,'i_tile_tx_',i,a)
                vc=c['TRAFFIC_CLASS_TO_VC']>>(beat['traffic_class']*a['VW'])&((1<<a['VW'])-1)
                self.ledger.inject(beat,i//a['TX'],i%a['TX'],vc)
                self.flits.inject(beat,i//a['TX'],i%a['TX'])
                self.coverage.counts['accepted']+=1
                self.coverage.classes.add(beat['traffic_class'])
                self.coverage.pairs.add((i//a['TX'],beat['destination_node']))
        # Physical link observations corroborate the independent endpoint ledger.
        # A registered hop prevents same-edge consecutive router transfers; process
        # previous hops before later hops when multiple packets move concurrently.
        pending=list(obs.transfers)
        while pending:
            remaining=[]
            for n,port,f in pending:
                key=(f['source_node'],f['source_endpoint'],f['packet_id'],f['user_metadata'])
                if key in self.flits.packets:
                    _,hops,seen=self.flits.packets[key]
                    hop=hops.index((n,port)) if (n,port) in hops else 0
                    if hop and (*hops[hop-1],f['fragment_index']) not in seen:
                        remaining.append((n,port,f));continue
                self.flits.transfer(n,port,f)
                self.coverage.counts['router_flits']+=1
            assert len(remaining)<len(pending),'Flit bypass/unknown route dependency'
            pending=remaining
        if c['FLOW_CONTROL']==1:
            counts=[p['o_router_output_credit_count']>>(i*a['CW'])&((1<<a['CW'])-1)
                    for i in range(a['NN']*5*a['V'])]
            if self.previous_credits is not None:
                assert counts==self.previous_credits,('Credit conservation',counts,self.previous_credits)
            expected=counts.copy()
            for n,port,f in obs.transfers:expected[(n*5+port)*a['V']+f['vc']]-=1
            for n,port,vc,epoch in obs.credit_events:
                current=p['o_link_epoch']>>((n*5+port)*a['E'])&((1<<a['E'])-1)
                if epoch==current and vc<a['V']:expected[(n*5+port)*a['V']+vc]+=1
            self.previous_credits=expected
        for i in range(a['NE']*a['RX']):
            valid=p['o_tile_rx_valid']>>i&1
            ready=p['i_tile_rx_ready']>>i&1
            if valid:
                beat=extract(p,'o_tile_rx_',i,a)
                if i in self.holds:assert beat==self.holds[i],('Changed stalled RX',i)
                if ready:
                    vc=c['TRAFFIC_CLASS_TO_VC']>>(beat['traffic_class']*a['VW'])&((1<<a['VW'])-1)
                    self.ledger.eject(beat,i//a['RX'],i%a['RX'],vc)
                    self.flits.eject(beat)
                    self.coverage.counts['delivered']+=1
                else:
                    self.coverage.hit('backpressure')
                if not ready:self.holds[i]=beat
                else:self.holds.pop(i,None)
            else:assert i not in self.holds,'Stalled RX lost valid'
        for n,width,limit,count in (
            ('o_router_input_vc_occupancy',a['OCC'],a['DEPTH'],a['NN']*5*a['V']),
            ('o_router_output_credit_count',a['CW'],a['DEPTH'],a['NN']*5*a['V']),
            ('o_endpoint_rx_vc_occupancy',a['VO'],c['ENDPOINT_RX_VC_DEPTH'],a['NE']*a['V'])):
            value=p[n]
            assert value is not None,(n,'unknown')
            for index in range(count):assert value>>(index*width)&((1<<width)-1)<=limit,(n,index)
        actual=sum((p['o_flow_outstanding']>>(i*16))&0xffff for i in range(a['MF']))
        # Public counts describe pre-edge state; ledger has just included this edge.
        if p['o_idle']:assert actual==0,'False idle with pending flow obligations'
        if c['ENABLE_COUNTERS']:
            assert p['o_accepted_packets']-p['o_delivered_packets']-p['o_discarded_packets']==actual
        if p['o_lifecycle_valid'] and p['o_lifecycle_status']==0:
            self.coverage.hit('drain')
        for name,valid,ready,fields in (
            ('cfg','o_cfg_response_valid','i_cfg_response_ready',('status','data','version','crc','tag')),
            ('lifecycle','o_lifecycle_valid','i_lifecycle_ready',('status','tag'))):
            key=name
            if p[valid]:
                record=tuple(p[f'o_{name}_'+('response_' if name=='cfg' else '')+f] for f in fields)
                if key in self.holds:assert record==self.holds[key],f'Changed held {name}'
                if not p[ready]:self.holds[key]=record
                else:self.holds.pop(key,None)
            else:assert key not in self.holds,f'Lost held {name}'

    def check_phase(self):
        assert self.ledger.outstanding==0,('Unresolved packets',self.ledger.pending)
        assert not self.flits.packets and not self.flits.owners,'Unresolved physical packets'
        counts=self.coverage.counts
        assert counts['accepted']==counts['delivered']+counts['discarded']+counts['reset_discards'],counts
