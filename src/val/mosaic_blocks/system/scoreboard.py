"""Public-interface control, memory, region, held-output and response ledgers."""
from collections import deque
from pyuvm import ConfigDB, uvm_subscriber
from mosaic_blocks.system.model import RegionModel

class SystemScoreboard(uvm_subscriber):
    def build_phase(self):
        self.c=ConfigDB().get(self,'','config')
        self.coverage=ConfigDB().get(self,'','coverage')
        self.pending=deque()
        self.held={}
        self.regions=RegionModel()
        self.shadows={}
        self.live=None
        self.fence_target=None
        self.fence_live=None
        self.native_read=self.native_write=self.native_completions=0
        self.native_seen=set()

    def write(self,obs):
        if obs.phase!='pre': return
        p=obs.ports
        self.coverage.cycles+=1
        if not p['i_rstb']:
            self.pending.clear(); self.held.clear(); self.regions=RegionModel()
            self.shadows.clear(); self.live=None; self.fence_target=None; self.fence_live=None
            self.native_read=self.native_write=self.native_completions=0
            self.native_seen.clear()
            return
        for channel,valid,ready,prefix in (
            ('control','o_ctrl_response_valid','i_ctrl_response_ready','o_ctrl_response_'),
            ('memory','o_mem_request_valid','i_mem_request_ready','o_mem_request_'),
            ('write','o_mem_write_valid','i_mem_write_ready','o_mem_write_'),
            ('fence','o_fence_valid','i_fence_ready','o_fence_')):
            values=tuple((name,p[name]) for name in p if name.startswith(prefix))
            if channel in self.held:
                assert p[valid] and values==self.held[channel],('Unstable',channel)
                self.coverage.hit('control_held' if channel=='control' else 'memory_backpressure')
            if p[valid] and not p[ready]: self.held[channel]=values
            else: self.held.pop(channel,None)
        if self.c.mode=='full':
            for slot in range(self.c.parameters['clusters']):
                if p['o_array_cluster_mst_completion_valid'] >> slot & 1:
                    assert (p['o_array_cluster_mst_completion_status'] >> (2*slot)&3)==0
                    assert not (p['o_array_cluster_mst_completion_partial'] >> slot&1)
                    assert not (p['o_array_cluster_mst_completion_effects_unknown'] >> slot&1)
                    identity=(p['o_array_cluster_mst_completion_identity'] >> (134*slot))&((1<<134)-1)
                    command=identity&65535
                    assert (slot,command) not in self.native_seen,'Duplicate native completion'
                    self.native_seen.add((slot,command))
                    reads=(p['o_array_cluster_mst_completion_bytes_read'] >> (37*slot))&((1<<37)-1)
                    writes=(p['o_array_cluster_mst_completion_bytes_written'] >> (37*slot))&((1<<37)-1)
                    # LOAD's read side and STORE's write side are SRAM obligations.
                    # Other byte counters may describe stream traffic, not SRAM traffic.
                    if command==1:
                        assert slot==0 and reads==96,(slot,command,reads,writes)
                        self.native_read+=reads
                    elif command==2:
                        assert slot==self.c.parameters['clusters']-1 and writes==96
                        self.native_write+=writes
                    else:
                        raise AssertionError(('Unexpected native command',command))
                    assert (identity>>32)&65535==5 and (identity>>48)&65535==3
                    assert (identity>>64)&0xffffffff==11+slot
                    self.native_completions+=1
                    if (self.native_completions,self.native_read,self.native_write)==(2,96,96):
                        self.coverage.hit('actual_mst_bytes')
        if p['o_ctrl_response_valid'] and p['i_ctrl_response_ready']:
            assert self.pending,'Unsolicited control response'
            request=self.pending.popleft()
            assert p['o_ctrl_response_tag']==request['i_ctrl_tag']
            self.coverage.hit('control_exact_once')
            if p['o_ctrl_response_status']==0 and request['i_ctrl_write']:
                address,data,owner=(request[k] for k in ('i_ctrl_address','i_ctrl_write_data','i_ctrl_requester_id'))
                shadow=self.shadows.setdefault(owner,{})
                if 0x3000<=address<=0x3014: shadow[(address-0x3000)//4]=data
                if address==0x3020:
                    self.regions.register(shadow[0],shadow[1]|shadow[2]<<32,shadow[3],
                        shadow[4]&65535,shadow[4]>>16,shadow[5]&65535,shadow[5]>>16,
                        actor=owner,admin=owner==1 and request['i_ctrl_privilege']>=4)
                if address==0x3040: self.fence_target=(data&255,'dma' if data&256 else 'host')
        if p['i_ctrl_valid'] and p['o_ctrl_ready']:
            self.pending.append({k:p[k] for k in p if k.startswith('i_ctrl_')})
        if p['o_mem_request_valid'] and p['i_mem_request_ready']:
            assert self.live is None,'Memory ID alias'
            assert self.regions.authorize(p['o_mem_request_buffer'],p['o_mem_request_address'],
                p['o_mem_request_length'],p['o_mem_request_write'],p['o_mem_request_owner'],
                p['o_mem_request_kernel'],p['o_mem_request_generation']),'Address/owner escape'
            self.live=dict(id=p['o_mem_request_id'],remaining=p['o_mem_request_length'],
                write=p['o_mem_request_write'],data=False)
            self.coverage.hit('memory_bounds')
        if p['o_mem_write_valid'] and p['i_mem_write_ready']:
            assert self.live and self.live['write'] and not self.live['data']
            assert self.live['id']==p['o_mem_write_id']
            self.live['data']=True
        if p['i_mem_read_valid'] and p['o_mem_read_ready']:
            assert self.live and not self.live['write'] and self.live['id']==p['i_mem_read_id']
            self.live['remaining']-=self.c.parameters['memory_data_width']//8
            assert bool(p['i_mem_read_last'])==(self.live['remaining']==0 or p['i_mem_read_status']!=0)
            if p['i_mem_read_last']: self.live=None
        if p['i_mem_write_response_valid'] and p['o_mem_write_response_ready']:
            assert self.live and self.live['data'] and self.live['id']==p['i_mem_write_response_id']
            self.live=None
            self.coverage.hit('write_commit_order')
        if p['o_fence_valid'] and p['i_fence_ready']:
            assert self.fence_live is None and self.live is None
            self.fence_live=(p['o_fence_buffer'],p['o_fence_tag'])
        if p['i_fence_response_valid'] and p['o_fence_response_ready']:
            assert self.fence_live and self.fence_live[1]==p['i_fence_response_tag']
            slot=self.fence_live[0]
            target=self.fence_target[1] if self.fence_target and self.fence_target[0]==slot else 'host'
            if not p['i_fence_response_status']: self.regions.regions[slot]['state']=target
            self.fence_live=None; self.fence_target=None

    def check_phase(self):
        assert not self.pending,'Accepted control request lacks response'
        assert self.live is None,'Memory operation did not retire'
        if self.c.mode=='full':
            assert (self.native_completions,self.native_read,self.native_write)==(2,96,96)
