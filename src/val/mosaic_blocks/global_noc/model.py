"""Independent endpoint beat ledger and configuration image helpers."""
from collections import defaultdict, deque
from global_noc.dependencies import profile
from global_noc_contract import signature, PROTOCOL_ID, flow_words, metadata, crc32c, route

TX_FIELDS=('data','keep','last','context_id','message_type','traffic_class','packet_id',
           'user_metadata','error','destination_node','destination_endpoint')
RX_FIELDS=tuple(n.replace('destination','source') for n in TX_FIELDS)
FIELD_WIDTHS=dict(data='TD',keep='TB',last='1',context_id='CX',message_type='MT',
    traffic_class='TC',packet_id='PI',user_metadata='U',error='ER',destination_node='N',
    destination_endpoint='EP',source_node='N',source_endpoint='EP')

def extract(p,prefix,index,a):
    result={}
    for n in TX_FIELDS if prefix=='i_tile_tx_' else RX_FIELDS:
        w=int(FIELD_WIDTHS[n]) if FIELD_WIDTHS[n].isdigit() else a[FIELD_WIDTHS[n]]
        result[n]=p[prefix+n]>>(index*w)&((1<<w)-1)
    return result


def image(p,flows,faults=None):
    words=[signature(p),PROTOCOL_ID]+list(faults or [0]*p['NUM_ROUTERS'])
    words += [w for flow in flows for w in flow]
    return words+[0]*(4*(p['MAX_ACTIVE_FLOWS']-len(flows)))

class Ledger:
    def __init__(self):
        self.pending=defaultdict(deque)
        self.accepted=0
        self.delivered=0
        self.discarded=0

    def inject(self,beat,source,channel,vc):
        expected=beat.copy()
        dest=expected.pop('destination_node')
        endpoint=expected.pop('destination_endpoint')
        expected.update(source_node=source,source_endpoint=channel)
        flow=beat['user_metadata']&0xffff
        self.pending[dest,endpoint,flow,vc].append(expected)
        self.accepted+=1

    def eject(self,beat,node,channel,vc):
        key=node,channel,beat['user_metadata']&0xffff,vc
        assert self.pending[key],f'Unexpected/duplicate delivery: {key}, {beat}'
        expected=self.pending[key].popleft()
        assert beat==expected,('Corrupt, reordered or misrouted beat',expected,beat)
        self.delivered+=1

    def flush(self):
        count=sum(map(len,self.pending.values()))
        self.discarded+=count
        self.pending.clear()
        return count

    @property
    def outstanding(self):return sum(map(len,self.pending.values()))

class FlitLedger:
    """Predict every fragment at every route hop, independently of router state."""
    def __init__(self,p,a):
        self.p=p;self.a=a;self.packets={};self.owners={}
        self.transfers=0

    def inject(self,beat,source,channel):
        key=(source,channel,beat['packet_id'],beat['user_metadata'])
        assert key not in self.packets,'Reused live packet identity'
        hops=[(s,port) for s,port,_ in route(source,beat['destination_node'],self.p)]
        hops.append((beat['destination_node'],0))
        self.packets[key]=(beat,tuple(hops),set())

    def transfer(self,node,port,f):
        key=(f['source_node'],f['source_endpoint'],f['packet_id'],f['user_metadata'])
        assert key in self.packets,('Flit with no accepted beat',node,port,key)
        beat,hops,seen=self.packets[key]
        a=self.a
        fragments=(a['TD']+a['D']-1)//a['D']
        fragment=f['fragment_index']
        assert 0<=fragment<fragments,('Fragment range',f)
        assert (node,port) in hops,('Illegal hop/turn',node,port,hops)
        visit=(node,port,fragment)
        assert visit not in seen,('Duplicate forwarded flit',visit,key)
        if fragment:
            assert (node,port,fragment-1) in seen,('Reordered fragments',visit)
        hop=hops.index((node,port))
        if hop:
            assert (*hops[hop-1],fragment) in seen,('Flit bypassed a router',visit)
        expected={k:beat[k] for k in ('context_id','message_type','traffic_class','packet_id',
            'user_metadata','error','destination_node','destination_endpoint')}
        expected.update(data=beat['data']>>(fragment*a['D'])&((1<<a['D'])-1),
            keep=beat['keep']>>(fragment*a['K'])&((1<<a['K'])-1),
            head=int(fragment==0),tail=int(fragment==fragments-1),stream_last=beat['last'],
            vc=self.p['TRAFFIC_CLASS_TO_VC']>>(beat['traffic_class']*a['VW'])&((1<<a['VW'])-1))
        for field,value in expected.items():assert f[field]==value,(field,value,f,node,port)
        owner=(node,port)
        if fragment==0:
            assert owner not in self.owners,('Interleaved packet heads',owner,key)
            self.owners[owner]=key
        else:assert self.owners.get(owner)==key,('Reservation alias',owner,key)
        if f['tail']:self.owners.pop(owner)
        seen.add(visit);self.transfers+=1

    def eject(self,beat):
        key=(beat['source_node'],beat['source_endpoint'],beat['packet_id'],beat['user_metadata'])
        original,hops,seen=self.packets.pop(key)
        fragments=(self.a['TD']+self.a['D']-1)//self.a['D']
        assert len(seen)==len(hops)*fragments,('Missing route flits',key,hops,seen)

    def flush(self):self.packets.clear();self.owners.clear()
