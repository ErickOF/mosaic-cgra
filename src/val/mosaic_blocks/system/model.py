"""Independent byte memory, platform fence, descriptor and region reference models."""
from collections import deque
import random


def crc32c(data: bytes) -> int:
    crc = 0xffffffff
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x82f63b78 if crc & 1 else 0)
    return crc ^ 0xffffffff


def record(contract, kind, payload=0, *, bits=None, owner=5, kernel=3, package=101,
           generation=1, epoch=0, slot=0, tag=1, flags=0):
    """Pack the published wire format with a byte-based independent CRC oracle."""
    group = contract['groups'].get(str(kind), contract['groups'].get(kind))
    expected = group['payload_bits'] if group else {7:160,8:160,9:0,10:8,12:1}.get(kind)
    if expected is None:
        raise ValueError('Unsupported record kind')
    bits = expected if bits is None else bits
    if not 0 <= payload < 1 << 1536 or not 0 <= flags < 256:
        raise ValueError('Payload/flags overflow')
    fields = [(0,32,0x5359534d),(32,16,1),(48,8,kind),(56,8,flags),(64,16,owner),
        (80,16,kernel),(96,32,package),(128,16,generation),(144,8,epoch),(152,8,slot),
        (160,16,bits),(192,16,tag),(256,256,int(contract['manifest_sha256'],16)),(512,1536,payload)]
    value = 0
    for offset,width,item in fields:
        if not 0 <= item < 1 << width:
            raise ValueError('Header overflow')
        value |= item << offset
    data = bytearray(value.to_bytes(256,'little'))
    data[28:32] = crc32c(data).to_bytes(4,'little')
    return bytes(data)


def payload(contract, kind, fields):
    group = contract['groups'].get(str(kind), contract['groups'].get(kind))
    expected = {f['name'] for f in group['payload']}
    if fields.keys() - expected:
        raise ValueError(f'Unknown native fields: {fields.keys()-expected}')
    value = 0
    for f in group['payload']:
        item = fields.get(f['name'],0)
        if not 0 <= item < 1 << f['width']:
            raise ValueError(f"Overflow: {f['name']}")
        value |= item << f['offset']
    return value


class RegionModel:
    """Overflow-safe half-open intervals; no RTL state encoding is used."""
    def __init__(self):
        self.regions = {}

    def register(self, slot, base, size, owner, kernel, generation, permissions, *, actor=None, admin=False):
        if base < 0x100000 or base % 256 or size <= 0 or base + size >= 1 << 64:
            raise ValueError('bounds/alignment')
        if not permissions or permissions & ~3 or owner in (0,65535):
            raise ValueError('permission')
        old = self.regions.get(slot)
        actor=owner if actor is None else actor
        if old and old['owner']!=actor and not admin:
            raise ValueError('owner')
        if generation != (old['generation'] if old else 0) + 1 or generation > 65535:
            raise ValueError('generation')
        if old and old['state'] != 'host':
            raise ValueError('ownership')
        if any(k != slot and base < r['base']+r['size'] and r['base'] < base+size
               for k,r in self.regions.items()):
            raise ValueError('overlap')
        self.regions[slot] = dict(base=base,size=size,owner=owner,kernel=kernel,
            generation=generation,permissions=permissions,state='host')

    def authorize(self, slot, address, size, write, owner, kernel, generation):
        r = self.regions[slot]
        return (r['state']=='dma' and r['owner']==owner and r['kernel']==kernel and
            r['generation']==generation and bool(r['permissions'] & (2 if write else 1)) and
            size > 0 and r['base'] <= address < address+size <= r['base']+r['size'])


class MemoryModel:
    """Canonical split-channel memory and fence BFMs with held, delayed responses.

    Write data is staged at its handshake and becomes visible only on the terminal
    write acknowledgement. A platform fence never acknowledges an uncommitted write.
    """
    def __init__(self, width, seed):
        self.width, self.size = width, width//8
        self.rng = random.Random(seed)
        self.memory = {}
        self.reset()

    def reset(self):
        self.clock = 0
        self.read = self.write = self.fence = None
        self.reads = self.writes = self.fences = 0
        self.mode = 'normal'
        self.held_read = self.held_write = self.held_fence = None
        self.freeze_requests = False

    def put(self, address, data):
        self.memory.update({address+k:byte for k,byte in enumerate(data)})

    def get(self, address, size):
        return bytes(self.memory.get(address+k,0) for k in range(size))

    def drive(self):
        self.clock += 1
        p = dict(i_mem_request_ready=int(not self.freeze_requests and self.rng.randrange(4)!=0),
            i_mem_write_ready=int(self.rng.randrange(3)!=0), i_mem_read_valid=0,
            i_mem_read_data=0,i_mem_read_keep=0,i_mem_read_last=0,i_mem_read_id=0,i_mem_read_status=0,
            i_mem_write_response_valid=0,i_mem_write_response_id=0,i_mem_write_response_status=0,
            i_fence_ready=int(self.rng.randrange(4)!=0),i_fence_response_valid=0,
            i_fence_response_tag=0,i_fence_response_status=0)
        if self.read and self.clock >= self.read['at'] and self.mode != 'timeout':
            r = self.read
            if self.held_read is None:
                error = self.mode == 'read_error'
                self.held_read = dict(i_mem_read_valid=1,
                    i_mem_read_data=int.from_bytes(self.get(r['address']+r['done'],self.size),'little'),
                    i_mem_read_keep=(1<<self.size)-1,
                    i_mem_read_last=int(error or r['done']+self.size==r['length']),
                    i_mem_read_id=r['id'] ^ int(self.mode=='wrong_id'),i_mem_read_status=1 if error else 0)
            p.update(self.held_read)
        if self.write and self.write.get('data') is not None and self.clock >= self.write['at']:
            if self.held_write is None:
                self.held_write = dict(i_mem_write_response_valid=1,
                    i_mem_write_response_id=self.write['id'],
                    i_mem_write_response_status=int(self.mode=='write_error'))
            if self.mode != 'hold_write': p.update(self.held_write)
        if self.fence and self.clock >= self.fence['at']:
            if self.held_fence is None:
                self.held_fence = dict(i_fence_response_valid=1,
                    i_fence_response_tag=self.fence['tag'],i_fence_response_status=0)
            if self.mode != 'hold_fence': p.update(self.held_fence)
        return p

    def observe(self,p):
        if not p['i_rstb']:
            return
        if p['o_mem_request_valid'] and p['i_mem_request_ready']:
            assert self.read is None and self.write is None,'Aliased memory obligation'
            r = dict(address=p['o_mem_request_address'],length=p['o_mem_request_length'],
                id=p['o_mem_request_id'],done=0,at=self.clock+self.rng.randrange(1,6))
            if p['o_mem_request_write']:
                self.write = r | dict(data=None)
            else:
                self.read = r
        if p['o_mem_write_valid'] and p['i_mem_write_ready']:
            assert self.write and self.write['data'] is None
            assert p['o_mem_write_id']==self.write['id'] and p['o_mem_write_last']
            assert p['o_mem_write_strobe']==(1<<self.size)-1
            self.write['data']=p['o_mem_write_data'].to_bytes(self.size,'little')
            self.write['at']=self.clock+self.rng.randrange(3,12)
        if p['i_mem_read_valid'] and p['o_mem_read_ready']:
            assert self.read
            self.reads += 1
            self.read['done'] += self.size
            if p['i_mem_read_last']:
                self.read=None
            else:
                self.read['at']=self.clock+self.rng.randrange(1,4)
            self.held_read=None
        if p['i_mem_write_response_valid'] and p['o_mem_write_response_ready']:
            assert self.write and self.write['data'] is not None
            if p['i_mem_write_response_status']==0:
                self.put(self.write['address'],self.write['data'])
            self.writes += 1
            self.write=self.held_write=None
        if p['o_fence_valid'] and p['i_fence_ready']:
            assert self.fence is None and self.write is None
            self.fence=dict(tag=p['o_fence_tag'],at=self.clock+self.rng.randrange(3,9))
        if p['i_fence_response_valid'] and p['o_fence_response_ready']:
            assert self.fence and self.write is None
            self.fence=self.held_fence=None
            self.fences += 1
