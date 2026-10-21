"""Independent integer legality, rectangle expansion and deterministic byte data."""
from enum import IntEnum


class Transfer(IntEnum): MEMORY_TO_MEMORY=0; MEMORY_TO_STREAM=1; STREAM_TO_MEMORY=2
class Status(IntEnum): SUCCESS=0; ERROR=1; CANCELED=2; FLUSHED=3
class Error(IntEnum):
    NONE=0; COMMAND=1; REGION=2; PROTOCOL=3; DUPLICATE=4; ALIGNMENT=5; BOUNDS=6
    PERMISSION=7; EVENT=8; BURST=9; OVERLAP=10; PARITY=11; FRAMING=12; SOURCE=13
    WRITE=14; BACKEND=15; EPOCH=16; TIMEOUT=17; CANCELED=18; CANCEL_TIMEOUT=19
    FLUSH=20; OVERFLOW=21; UNKNOWN=22


def known(word): return set(word)<={'0','1'}


def integer(word):
    return int(word,2)


def signed(value,width):
    return value-(1<<width) if value&(1<<(width-1)) else value


def pattern(address,space,context,width):
    # A byte-addressed pattern makes source/destination permutation observable.
    return sum(((address+b)*29+space*47+context*71+(address>>(b%7)))%256 << (8*b)
        for b in range(width//8))


class AddressSequence:
    """Index a potentially huge descriptor without allocating its elements."""
    def __init__(self,base,inner,outer,columns,rows):
        self.base,self.inner,self.outer,self.columns,self.rows=base,inner,outer,columns,rows

    def __len__(self):return self.columns*self.rows

    def __getitem__(self,index):
        if not 0<=index<len(self):raise IndexError(index)
        row,column=divmod(index,self.columns)
        return self.base+row*self.outer+column*self.inner


def addresses(c,d,side):
    size=1<<d['element_size_log2']
    inner=size if d['address_mode']==0 else signed(d[f'{side}_inner_stride'],c.ADDR_WIDTH)
    outer=signed(d[f'{side}_outer_stride'],c.ADDR_WIDTH) if d['address_mode']==2 else 0
    return AddressSequence(d[f'{side}_base'],inner,outer,d['inner_count'],d['outer_count'])


def bounds(c,d,side):
    # Four corners rather than the implementation's signed min/max products.
    size=1<<d['element_size_log2'];n=d['inner_count'];rows=d['outer_count']
    inner=size if d['address_mode']==0 else signed(d[f'{side}_inner_stride'],c.ADDR_WIDTH)
    outer=signed(d[f'{side}_outer_stride'],c.ADDR_WIDTH) if d['address_mode']==2 else 0
    corners=[d[f'{side}_base']+r*outer+k*inner for r in (0,rows-1) for k in (0,n-1)]
    return min(corners),max(corners)+size


def legality(c,ports,regions,live):
    p={name.removeprefix('i_command_'):value for name,value in ports.items() if name.startswith('i_command_')}
    required=('mode','address_mode','inner_count','outer_count','element_size_log2','stream_id','context_id',
        'id','priority','start_mode','completion_event_enable','max_burst_beats')
    if not all(known(p[name]) for name in required):return Error.UNKNOWN
    d={name:integer(value) for name,value in p.items() if known(value)}
    if d['mode']==3 or d['address_mode']==3 or not d['inner_count'] or not d['outer_count'] or (
        d['address_mode']!=2 and d['outer_count']!=1) or d['element_size_log2']>c.derived['MAX_ELEMENT_BYTES_LOG2']:return Error.COMMAND
    if d['mode']!=0 and not known(p['stream_last']):return Error.UNKNOWN
    if d['start_mode']==3 or (not c.SUPPORT_EVENT_START and d['start_mode']!=0) or (
        d['start_mode']!=0 and (not known(p['start_event_mask']) or d['start_event_mask']==0)) or (
        d['completion_event_enable'] and (not known(p['completion_event_id']) or d['completion_event_id']>=c.NUM_EVENTS)):return Error.EVENT
    if not 1<=d['max_burst_beats']<=c.MAX_BURST_BEATS:return Error.BURST
    for side in ('source','destination'):
        if (side=='source' and d['mode']==2) or (side=='destination' and d['mode']==1):continue
        names=[f'{side}_base']
        if d['address_mode']!=0:names.append(f'{side}_inner_stride')
        if d['address_mode']==2:names.append(f'{side}_outer_stride')
        if not all(known(p[name]) for name in names):return Error.UNKNOWN
        size=1<<d['element_size_log2']
        if any(d[name]%size for name in names):return Error.ALIGNMENT
        lo,limit=bounds(c,d,side)
        if lo<0 or limit>(1<<c.ADDR_WIDTH):return Error.BOUNDS
        region=d.get(f'{side}_region',c.NUM_PROTECTION_REGIONS)
        entry=regions.get(region)
        if (not entry or not entry['enable'] or not entry['read_enable' if side=='source' else 'write_enable']
                or d.get(f'{side}_space')!=entry['space_id'] or d['context_id']!=entry['context_id']
                or lo<entry['base'] or limit>entry['limit']):return Error.PERMISSION
    if (d['channel'],d['context_id'],d['id']) in live:return Error.DUPLICATE
    if d['mode']==0 and d['source_space']==d['destination_space']:
        slo,shi=bounds(c,d,'source');dlo,dhi=bounds(c,d,'destination')
        if slo<dhi and dlo<shi:return Error.OVERLAP
    return Error.NONE
