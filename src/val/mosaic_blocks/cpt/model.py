"""Independent integer, predicate, event and tagged-transport reference models."""
from dataclasses import dataclass, field
from cpt_contract import FIELDS, META, RECORD


def put(fields, values):
    result=0
    for key,value in values.items():
        offset,width=fields[key]
        if not 0 <= value < 1 << width: raise ValueError((key,value,width))
        result |= value << offset
    return result


def unpack(fields,value):
    return {key:value >> offset & ((1 << width)-1) for key,(offset,width) in fields.items()}


def context(p, **overrides):
    levels=overrides.pop('levels',[(0,0,1,1,0,0)]+[(0,0,0,0,0,0)]*(p['MAX_LOOP_DEPTH']-1))
    c=dict(magic=0xc701,command_class=8,lane_mask=(1 << p['PREDICATE_LANES'])-1,
        predicate_route=(1 << p['PREDICATE_OUTPUT_PORTS'])-1,
        event_enable=(1 << p['NUM_EVENTS'])-1,epoch=1,timeout=0,targets=(1<<min(2,p["MAX_PARTICIPANTS"]))-1,
        package_version=1,route_version=1,loop_depth=1,loop_ii=1,loop_export=1,
        loop_event=0,command_limit=0,sequence_enable=0,terminal_context=1,
        next_context=0,allowed_classes=0xff if p['FU_PROFILE'] else 0xbf,register_type=0)
    c.update(overrides)
    c['levels']=levels
    return c


def pack(p,c):
    result=put(FIELDS,{k:v for k,v in c.items() if k!='levels'})
    iw,tw=p['INDEX_WIDTH'],p['TRIP_COUNT_WIDTH']
    width=3*iw+tw+5
    for level,(initial,bound,step,trips,mode,compare) in enumerate(c['levels']):
        values=(initial & ((1<<iw)-1),bound & ((1<<iw)-1),step & ((1<<iw)-1),trips,mode,compare)
        offset=512+level*width
        for value,bits in zip(values,(iw,iw,iw,tw,2,3),strict=True):
            if not 0 <= value < 1 << bits:raise ValueError('Loop field overflow')
            result |= value << offset
            offset += bits
    return result


def command(p, identity, cls, opcode, a=0, b=0, **fields):
    values=dict(command_class=cls,opcode=opcode,source_a=0,source_b=1,destination=0,
        write_enable=0,signed=0,predicate_enable=0,false_token=0,mask=(1<<p['PREDICATE_LANES'])-1,
        object_id=0,sub_id=0,tag=0,generation=0,participant=0,register_type=1,terminal=0)
    values.update(fields)
    return (a & 0xffffffff) | (b & 0xffffffff)<<32, identity | put(META,values)


def event(p,identity,kind=0,**overrides):
    ci=max(1,(p['CONTEXT_DEPTH']-1).bit_length())
    cid=identity & ((1<<ci)-1)
    version=identity>>ci
    d=dict(kind=kind,owner=5,context_version=version,epoch=1,sequence=0,
        source=0,event_id=0,opcode=0,namespace=0,flags=0,tag=0,participants=0,
        package_version=1,route_version=1,payload=0)
    d.update(overrides)
    return (1 if kind in (6,7) else 7) | cid<<3 | 9 << (ci+3) | put(RECORD,d)


def signed(value,width=32):
    return value-(1<<width) if value>>(width-1)&1 else value


def compare(op,a,b,is_signed=False):
    if op>=6:b=0
    if is_signed:a,b=signed(a),signed(b)
    return (a==b,a!=b,a<b,a<=b,a>b,a>=b,a==0,a!=0)[op]


@dataclass
class Architecture:
    p: dict
    predicates: dict = field(default_factory=dict)
    registers: dict = field(default_factory=dict)

    def evaluate(self,data,meta,condition=True,external=0):
        m=unpack(META,meta)
        cls,op=m['command_class'],m['opcode']
        a,b=data&0xffffffff,data>>32
        mask=m['mask'] & ((1<<self.p['PREDICATE_LANES'])-1)
        error=False
        result=0
        lanes=0
        predicate=None
        if not condition:return dict(data=0,error=False,
            predicate=(0,mask) if m['false_token'] and cls in (0,1) else None,
            suppress=not m['false_token'])
        if cls==0 and op==2 and m['predicate_load']:a=external
        if cls in (0,1):
            x,xv=self.predicates.get(m['source_a'],(0,0))
            y,yv=self.predicates.get(m['source_b'],(0,0))
            if cls==1:
                if m['rf_a']:
                    entry=self.registers.get(m['source_a'])
                    if entry is None or entry[1]!=m['register_type']:error=True
                    else:a=entry[0]
                if m['rf_b']:
                    entry=self.registers.get(m['source_b'])
                    if entry is None or entry[1]!=m['register_type']:error=True
                    else:b=entry[0]
                if op>7:error=True
                elif not error:result=mask if compare(op,a,b,m['signed']) else 0
            else:
                error=(op>8 or 3<=op<=7 and xv & mask != mask or
                       5<=op<=7 and yv & mask != mask or op==8 and not m['write_enable'])
                if not error:
                    result=(0,mask,a & mask,x & mask,~x & mask,x & y & mask,
                            (x | y)&mask,(x ^ y)&mask,0)[op]
            if m['destination']>=self.p['PREDICATE_DEPTH']:error=True
            if not error:
                lanes=mask if op!=8 or cls==1 else 0
                predicate=(result,lanes)
                if m['write_enable']:
                    old,valid=self.predicates.get(m['destination'],(0,0))
                    self.predicates[m['destination']]=(old & ~mask | result,
                        valid & ~mask if cls==0 and op==8 else valid | mask)
        elif cls==7:
            addr=m['destination']
            if op==0:
                entry=self.registers.get(m['source_a'])
                if entry is None or entry[1]!=m['register_type']:error=True
                else:result=entry[0]
            elif op==1:
                error=addr>=self.p['CONTROL_REGISTER_DEPTH'] or not 1<=m['register_type']<=6
                if not error:self.registers[addr]=(a,m['register_type'])
            elif op==2:
                error=addr>=self.p['CONTROL_REGISTER_DEPTH']
                if not error:self.registers.pop(addr,None)
            elif op>5:error=True
        return dict(data=result,error=bool(error),predicate=predicate,suppress=False)
