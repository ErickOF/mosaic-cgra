"""Independent committed words and timestamped read obligations, never DUT storage."""
from collections import deque
from dataclasses import dataclass
from mosaic_uvm.logic import bits
from sram_wrapper.transaction import BACKEND


def known(word): return set(word) <= {'0','1'}
def address(word, depth): return int(word,2) if known(word) and int(word,2)<depth else None


def merge(old,new,mask,granule):
    return ''.join(new[start:start+granule] if enable=='1' else old[start:start+granule]
        for start,enable in zip(range(0,len(old),granule),mask))


@dataclass
class Read:
    data: str
    tag: str
    accepted: int
    due: int
    canceled: bool=False
    matured: bool=False


class SramModel:
    def __init__(self,c):
        self.config=c
        self.memory=['x'*c.width for _ in range(c.depth)]
        self.reads=deque()
        self.backend_due=deque()
        self.edge=0
        self.initialized=False
        self.backend_data=None
        self.accepted_reads=self.accepted_writes=self.effective_writes=self.zero_writes=0
        self.consumed=self.canceled=self.matured=self.physical_returns=0
        self.tags=['0'*c.tag_width for _ in range(c.latency+1)]
        self.responses=['x'*(c.width+c.tag_width) for _ in range(c.credits)]
        self.read_pointer=self.write_pointer=0

    def clear(self):
        for read in self.reads: read.canceled=True
        self.canceled+=len(self.reads)
        self.reads.clear()
        self.tags=['0'*self.config.tag_width for _ in self.tags]
        self.read_pointer=self.write_pointer=0
        self.initialized=True

    def outputs(self,p):
        c=self.config
        out={name:'0'*c.widths[name] for name in c.widths if name.startswith('o_')}
        if p['i_rstb']!='1' or p['i_flush']!='0': return out
        head=self.reads[0] if self.reads and self.reads[0].due<=self.edge else None
        out.update(o_busy=str(int(bool(self.reads))),o_outstanding_reads=bits(len(self.reads),c.count_width))
        error=p['i_req_valid']=='1' and address(p['i_req_addr'],c.depth) is None
        out['o_req_error']=str(int(error))
        if not error:
            write=p['i_req_valid']=='1' and p['i_req_write']=='1'
            legal_operation=p['i_req_valid']=='0' or p['i_req_write'] in ('0','1')
            out['o_req_ready']=str(int(legal_operation and (write or len(self.reads)<c.credits or head is not None and p['i_rsp_ready']=='1')))
        if head:out.update(o_rsp_valid='1',o_rsp_rdata=head.data,o_rsp_tag=head.tag)
        return out

    def backend(self,p):
        c=self.config
        accepted=p['i_req_valid']=='1' and self.outputs(p)['o_req_ready']=='1' and p['i_rstb']=='1' and p['i_flush']=='0'
        write=accepted and p['i_req_write']=='1'
        enabled=accepted and (not write or known(p['i_req_wmask']) and '1' in p['i_req_wmask'])
        actual_write=enabled and write
        mask=p['i_req_wmask'] if actual_write else '0'*c.mask_width
        data=merge('0'*c.width,p['i_req_wdata'],mask,c.granule)
        return dict(zip(BACKEND[:-1],(str(int(enabled)),str(int(actual_write)),p['i_req_addr'] if enabled else '0'*c.address_width,data,mask)))

    def pipeline(self):
        stages={self.edge-read.accepted:read for read in self.reads if self.edge-read.accepted<=self.config.latency}
        return stages

    def internals(self):
        c=self.config
        stages=self.pipeline()
        queued=sum(read.due<self.edge for read in self.reads)
        result=dict(outstanding=bits(len(self.reads),c.count_width),queued=bits(queued,c.count_width),
            read_pointer=bits(self.read_pointer,max(1,(c.credits-1).bit_length())),
            write_pointer=bits(self.write_pointer,max(1,(c.credits-1).bit_length())),
            read_valid=bits(sum(1<<stage for stage in stages),c.latency+1))
        result.update({f'tag_{stage}':word for stage,word in enumerate(self.tags)})
        result.update({f'mem_{index}':word for index,word in enumerate(self.memory)})
        result.update({f'rsp_{index}':word for index,word in enumerate(self.responses)})
        if self.backend_data is not None:result['backend_rdata']=self.backend_data
        return result

    def transfers(self,p):
        outputs=self.outputs(p)
        accepted=p['i_req_valid']=='1' and outputs['o_req_ready']=='1'
        pop=outputs['o_rsp_valid']=='1' and p['i_rsp_ready']=='1'
        queued=sum(read.due<self.edge for read in self.reads)
        mature=next((read for read in self.reads if read.due==self.edge),None)
        enqueue=mature if mature and (queued or p['i_rsp_ready']=='0') else None
        write=address(p['i_req_addr'],self.config.depth) if accepted and p['i_req_write']=='1' and '1' in p['i_req_wmask'] else None
        return dict(accepted=accepted,pop=pop,enqueue=enqueue,queued=queued,memory_write=write,
            response_write=self.write_pointer if enqueue else None)

    def step(self,p):
        c=self.config
        before=self.transfers(p)
        old_edge=self.edge
        self.edge+=1
        event=dict(before,clear=None,read=None,write=False,matured=[],physical=[],consumed=None,
            before_count=len(self.reads),pipeline=set(self.pipeline()),queued_before=before['queued'])
        if p['i_rstb']=='0' or p['i_flush']=='1':
            event['clear']='reset' if p['i_rstb']=='0' else 'flush'
            event['canceled']=list(self.reads)
            self.clear()
        else:
            stages={old_edge-read.accepted:read for read in self.reads if old_edge-read.accepted<=c.latency}
            for stage in range(c.latency,0,-1):
                if stage-1 in stages:self.tags[stage]=stages[stage-1].tag
            if before['enqueue']:
                read=before['enqueue'];self.responses[self.write_pointer]=read.tag+read.data
                self.write_pointer=(self.write_pointer+1)%c.credits
            if before['pop']:
                event['consumed']=self.reads.popleft()
                self.consumed+=1
                if before['queued']:self.read_pointer=(self.read_pointer+1)%c.credits
            if before['accepted']:
                target=address(p['i_req_addr'],c.depth)
                if p['i_req_write']=='1':
                    self.accepted_writes+=1
                    event['write']=True
                    event['old_word']=self.memory[target]
                    if '1' in p['i_req_wmask']:
                        self.effective_writes+=1
                        self.memory[target]=merge(self.memory[target],p['i_req_wdata'],p['i_req_wmask'],c.granule)
                    else:self.zero_writes+=1
                    event['new_word']=self.memory[target]
                else:
                    read=Read(self.memory[target],p['i_req_tag'],self.edge,self.edge+c.latency)
                    self.reads.append(read);self.backend_due.append(read)
                    self.tags[0]=read.tag
                    self.accepted_reads+=1;event['read']=read
        while self.backend_due and self.backend_due[0].due==self.edge:
            read=self.backend_due.popleft();self.backend_data=read.data
            self.physical_returns+=1;event['physical'].append(read)
            if not read.canceled:
                read.matured=True;self.matured+=1;event['matured'].append(read)
        self.conservation()
        return event

    def conservation(self):
        assert 0<=len(self.reads)<=self.config.credits,'Read-credit bound assertion failed'
        assert self.accepted_reads==self.consumed+self.canceled+len(self.reads),'Read-obligation conservation assertion failed'
        assert all(a.accepted<b.accepted for a,b in zip(self.reads,list(self.reads)[1:])), 'Read ordering assertion failed'
