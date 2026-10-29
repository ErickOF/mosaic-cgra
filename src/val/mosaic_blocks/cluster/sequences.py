"""Specification-directed tests against the actual tiles, fabrics and SRAM banks."""
from copy import deepcopy
import os
import random
from pyuvm import uvm_sequence
from cocotb.types import LogicArray
from cluster.model import (MST_PARAMETERS, crc32c, descriptor, envelope, expected_results,
                           images, ordered_tiles, cycle_order, mst_pack)
from cluster.transaction import ClusterItem

class ClusterSequence(uvm_sequence):
    def __init__(self, config, active, coverage):
        super().__init__('cluster_specification')
        self.c, self.active, self.coverage = config, active, coverage
        self.base = {n: 0 for n, (direction, _) in config.ports.items()
                     if direction == 'input' and n != 'i_clk'}
        self.rng = random.Random(config.seed)
        self.index = self.tag = 0
        self.last = {}
        self.runtime_responses = {}
        self.cfg_responses = {}
        self.completions = []
        self.events = []
        self.boundary = []
        self.owner, self.kernel, self.package, self.context = 5, 3, 11, 0
        self.n = config.manifest['geometry']['n']
        self.all_tiles = (1 << self.n) - 1
        self.ne = self.n + 2
        self.words = [e['words'] for e in config.manifest['config_endpoint_table']]
        self.defaults = dict(i_runtime_response_ready=1, i_cfg_response_ready=1,
            i_event_ready=1, i_package_response_ready=1, i_mst_completion_ready=1, i_mst_rejection_ready=1,
            i_mst_region_response_ready=1, i_mst_buffer_response_ready=1,
            i_mst_dma_out_ready=1, i_memory_rsp_ready=7, i_boundary_ready=255)

    async def cycle(self, label='idle', fault=None, **ports):
        self.base.update(ports)
        item = ClusterItem(f'{label}_{self.index}', self.base, fault)
        self.index += 1
        if os.getenv('CLUSTER_TRACE'):
            print(item.get_name(), flush=True)
        await self.start_item(item)
        await self.finish_item(item)
        self.last = item.post
        p = item.pre
        if p['i_rstb']:
            if p['o_runtime_response_valid'] and p['i_runtime_response_ready']:
                self.runtime_responses[p['o_runtime_response_tag']] = p
            if p['o_cfg_response_valid'] and p['i_cfg_response_ready']:
                self.cfg_responses.setdefault(p['o_cfg_response_tag'], []).append(p)
            if p['o_mst_completion_valid'] and p['i_mst_completion_ready']:
                self.completions.append(p)
            if p['o_event_valid'] and p['i_event_ready']:
                self.events.append(p)
            valid = p['o_boundary_valid'] & p['i_boundary_ready']
            for port in range(self.c.manifest['geometry']['mesh']['B']):
                if valid >> port & 1:
                    self.boundary.append((port, p['o_boundary_data'] >> (port*32) & 0xffffffff,
                                          p['o_boundary_metadata'] >> (port*512) & ((1<<512)-1)))
        return item

    async def idle(self, cycles=5, **ports):
        item = None
        for _ in range(cycles):
            item = await self.cycle(**ports)
        return item

    async def reset(self):
        self.base.update({n: 0 for n in self.base})
        self.runtime_responses.clear()
        self.cfg_responses.clear()
        self.completions.clear()
        self.events.clear()
        self.boundary.clear()
        await self.idle(4, i_rstb=0)
        await self.idle(16, i_rstb=1, **self.defaults)
        assert self.last['o_status_cluster_state'] == 0, self.last
        assert not self.last['o_status_error'], self.last
        assert self.last['o_status_manifest_hash'] == int(self.c.manifest['manifest_sha256'], 16)
        self.coverage.hit('coordinated_reset')

    async def runtime(self, command, *, error=0, state=None, hold=0, **kwargs):
        self.tag += 1
        tag = self.tag
        args = dict(i_runtime_valid=1, i_runtime_command=command,
            i_runtime_owner_id=self.owner, i_runtime_kernel_id=self.kernel,
            i_runtime_package_id=self.package, i_runtime_context_id=self.context,
            i_runtime_resource_mask=self.all_tiles, i_runtime_flags=0, i_runtime_tag=tag,
            i_runtime_response_ready=int(not hold), i_test_mode=0, i_scan_enable=0) | kwargs
        for _ in range(200):
            item = await self.cycle('runtime_accept', **args)
            if item.pre['o_runtime_ready']:
                break
        else: raise AssertionError(('Runtime ingress blocked', command, self.last))
        self.base['i_runtime_valid'] = 0
        for _ in range(300):
            if item.post['o_runtime_response_valid']:
                break
            item = await self.cycle('runtime_response')
        else: raise AssertionError(('Runtime response timeout', command, self.last))
        if hold:
            await self.idle(hold)
            self.base['i_runtime_response_ready'] = 1
        for _ in range(5):
            await self.cycle('runtime_retire')
            if tag in self.runtime_responses: break
        p = self.runtime_responses.pop(tag)
        assert p['o_runtime_response_error_code'] == error, (command, error, p)
        assert p['o_runtime_response_status'] == int(error != 0)
        if state is not None: assert p['o_runtime_response_state'] == state, (command, state, p)
        return p

    async def cfg(self, command, mask, *, version=0, word=0, data=0, crc=0,
                  error=0, hold=0, owner=None, package=None):
        self.tag += 1
        tag = self.tag
        args = dict(i_cfg_request_valid=1, i_cfg_request_command=command,
            i_cfg_request_destination_mask=mask,
            i_cfg_request_owner_id=self.owner if owner is None else owner,
            i_cfg_request_kernel_id=self.kernel,
            i_cfg_request_package_id=self.package if package is None else package,
            i_cfg_request_context_id=self.context, i_cfg_request_expected_version=version,
            i_cfg_request_word_index=word, i_cfg_request_write_data=data,
            i_cfg_request_write_strobe=255, i_cfg_request_expected_crc=crc,
            i_cfg_request_tag=tag, i_cfg_request_epoch=self.last['o_cfg_configuration_epoch'],
            i_cfg_request_flags=0, i_cfg_request_protocol=1, i_cfg_response_ready=int(not hold))
        for _ in range(1000):
            item = await self.cycle(f'cfg_accept_{command}_{mask}_{word}', **args)
            if item.pre['o_cfg_request_ready']: break
        else: raise AssertionError(('Configuration ingress blocked', command, self.last))
        self.base['i_cfg_request_valid'] = 0
        for _ in range(5000):
            if hold and item.post['o_cfg_response_valid']:
                await self.idle(hold)
                self.base['i_cfg_response_ready'] = 1
                hold = 0
            replies = self.cfg_responses.get(tag, [])
            if replies and replies[-1]['o_cfg_response_last']: break
            item = await self.cycle(f'cfg_response_{command}_{mask}_{word}')
        else: raise AssertionError(('Configuration timeout', command, mask, self.last))
        replies = self.cfg_responses.pop(tag)
        assert all(p['o_cfg_response_error_code'] == error for p in replies), (
            command, mask, word, version, error,
            [(p['o_cfg_response_endpoint_id'], p['o_cfg_response_status'],
              p['o_cfg_response_error_code'], p['o_cfg_response_context_version']) for p in replies])
        if not error and mask:
            ids = [self.c.manifest['config_endpoint_table'][e]['id'] for e in range(self.ne)
                   if mask >> e & 1]
            assert [p['o_cfg_response_endpoint_id'] for p in replies] == sorted(ids)
        return replies

    async def management(self, record):
        for _ in range(100):
            item = await self.cycle('mst_region', i_mst_region_valid=1,
                i_mst_region_index=0, i_mst_region_record=mst_pack(MST_PARAMETERS,'region', record))
            if item.pre['o_mst_region_ready']: break
        else: raise AssertionError('MST region management blocked')
        self.base['i_mst_region_valid'] = 0
        for _ in range(100):
            if item.post['o_mst_region_response_valid']: break
            item = await self.cycle('mst_region_response')
        assert item.post['o_mst_region_response_valid']
        assert not item.post['o_mst_region_response_error'], item.post
        await self.idle(2)

    async def manifest(self, crcs, *, error=0, hold=0, **changes):
        self.tag+=1
        args=dict(i_package_valid=1,i_package_owner_id=self.owner,
            i_package_kernel_id=self.kernel,i_package_id=self.package,
            i_package_context_id=self.context,
            i_package_allocation_generation=self.last['o_status_allocation_generation'],
            i_package_architecture_hash=int(self.c.manifest['manifest_sha256'],16),
            i_package_topology_id=self.last['o_status_topology_id'],
            i_package_contract_version=1,i_package_requirements=0,
            i_package_resource_mask=self.all_tiles,i_package_endpoint_mask=(1<<self.ne)-1,
            i_package_context_versions=sum(v<<(16*i) for i,v in enumerate(self.words)),
            i_package_image_crcs=sum(v<<(32*i) for i,v in enumerate(crcs)),
            i_package_epoch=(self.last['o_status_execution_epoch']+1)&15,
            i_package_suspend_safe=1,i_package_tag=self.tag,
            i_package_response_ready=int(not hold))|changes
        for _ in range(100):
            item=await self.cycle('manifest_accept',**args)
            if item.pre['o_package_ready']: break
        else: raise AssertionError('Manifest ingress blocked')
        self.base['i_package_valid']=0
        for _ in range(10):
            if item.post['o_package_response_valid']: break
            item=await self.cycle('manifest_response')
        assert item.post['o_package_response_valid']
        assert item.post['o_package_response_tag']==self.tag
        assert item.post['o_package_response_error_code']==error,(
            error,item.post['o_package_response_error_code'])
        if hold: await self.idle(hold)
        await self.cycle('manifest_retire',i_package_response_ready=1)

    async def setup(self, count, *, boundary=False, fault_commit=False, suspend_safe=True):
        await self.runtime(1, state=1, hold=4)
        allocation = self.last['o_status_allocation_generation']
        await self.runtime(2, state=2)
        await self.management(dict(valid=1,generation=1,space=0,base=0,
            limit=self.c.manifest['geometry']['capacity'],owner=self.owner,kernel=self.kernel,
            allocation=allocation, read_enable=1,write_enable=1,dma_enable=1,
            channel_mask=3,buffer_mask=3))
        raw, info = images(self.c.parameters, owner=self.owner,kernel=self.kernel,
            package=self.package,allocation=allocation,context=self.context,count=count,
            region_generation=self.last['o_status_scratchpad_generation']+1,boundary=boundary)
        self.image_set = raw
        self.route_info = info
        crcs=[crc32c(value,words*8) for value,words in zip(raw,self.words)]
        await self.manifest(crcs,error=6,i_package_architecture_hash=0)
        await self.manifest(crcs,error=16,i_package_requirements=1)
        await self.manifest(crcs,error=3,i_package_owner_id=self.owner+1)
        await self.manifest(crcs,error=18,i_package_epoch=15)
        await self.manifest(crcs,hold=4,i_package_suspend_safe=int(suspend_safe))
        self.coverage.hit('architecture_topology_manifest')
        # An unauthorized request is rejected before reaching any endpoint.
        await self.cfg(1, 1, owner=self.owner+1, error=5)
        bct_mask=sum(1<<e for e,t in enumerate(ordered_tiles(self.c.parameters))
                     if t['class']=='BCT')
        await self.cfg(1,bct_mask,version=0,word=7,data=0,hold=4)
        self.coverage.hit('configuration_multicast_exact_once')
        await self.cfg(0,0,owner=self.owner+1,error=5)
        for ep, (image, words) in enumerate(zip(raw, self.words)):
            # Fresh contexts begin at version zero. QUERY is a real native operation.
            replies = await self.cfg(5, 1 << ep)
            initial = replies[0]['o_cfg_response_context_version']
            is_bct=ep<self.n and ordered_tiles(self.c.parameters)[ep]['class']=='BCT'
            assert initial == int(is_bct), (ep, initial)
            indices=[word for word in range(words) if not (is_bct and word==7)]
            for offset,word in enumerate(indices):
                await self.cfg(1, 1 << ep, version=initial+offset,word=word,
                               data=image >> (64*word) & ((1<<64)-1))
            checksum = crc32c(image,words*8)
            readback=await self.cfg(2,1<<ep,version=words,word=0)
            assert readback[0]['o_cfg_response_read_data']==image&((1<<64)-1)
            if ep==self.ne-1:
                await self.cfg(3,1<<ep,version=words,crc=checksum^1,error=23)
                self.coverage.hit('bad_image_crc_rejected')
            await self.cfg(3, 1 << ep, version=words,crc=checksum)
            if ep==0:
                await self.cfg(6,1<<ep,version=words,crc=checksum,package=self.package+1,error=24)
                self.coverage.hit('package_binding_rejected')
            await self.cfg(6, 1 << ep, version=words,crc=checksum,
                           hold=4 if ep == 0 else 0)
        self.coverage.hit('real_endpoint_images_validated')
        await self.runtime(4, error=4)  # PREPARE cannot start execution.
        if fault_commit:
            await self.cycle('arm_native_commit_failure',
                fault=('u_infra1.i_region_rsp_error',1))
        args = dict(i_cfg_commit_valid=1,i_cfg_commit_destination_mask=(1<<self.ne)-1,
            i_cfg_commit_owner_id=self.owner,i_cfg_commit_kernel_id=self.kernel,
            i_cfg_commit_package_id=self.package,
            i_cfg_commit_context_ids=sum(self.context << (8*i) for i in range(self.ne)),
            i_cfg_commit_context_versions=sum(v << (16*i) for i,v in enumerate(self.words)),
            i_cfg_commit_epoch=(self.last['o_status_execution_epoch']+1)&15)
        for _ in range(100):
            item = await self.cycle('commit_accept', **args)
            if item.pre['o_cfg_commit_ready']: break
        else: raise AssertionError(('Commit not ready',self.last))
        self.base['i_cfg_commit_valid'] = 0
        # Adversarial changes after acceptance must not change the captured tuple.
        self.base['i_cfg_commit_owner_id'] = self.owner+9
        self.base['i_cfg_commit_package_id'] = 0xbad
        if fault_commit:
            for _ in range(2000):
                await self.cycle('partial_commit_failure')
                if self.last['o_cfg_commit_error']: break
            else: raise AssertionError('Missing native commit failure')
            await self.idle(5)
            assert self.last['o_cfg_execution_hold']
            assert self.last['o_status_cluster_state']==13
            assert self.last['o_status_owner_id']==self.owner
            assert self.last['o_cfg_commit_failure_mask'] & (1<<(self.ne-1))
            assert self.last['o_cfg_commit_ack_mask']!=((1<<self.ne)-1)
            assert self.last['o_status_tile_versions']!=0  # Other endpoints activated.
            await self.cycle('release_native_failure',fault=('release',))
            await self.runtime(4,error=4)
            self.coverage.hit('partial_commit_requires_reset')
            return info
        for _ in range(2000):
            item = await self.cycle('commit_ack')
            assert not item.post['o_cfg_commit_error'], item.post
            if item.pre['o_cfg_commit_complete'] or item.post['o_cfg_commit_complete']: break
        else: raise AssertionError(('Commit timeout',self.last))
        await self.idle(5)
        assert self.last['o_cfg_execution_hold']
        assert self.last['o_cfg_commit_ack_mask'] == (1<<self.ne)-1
        await self.runtime(3, state=3)
        self.coverage.hit('coordinated_native_commit')
        return info

    async def memory(self, address, data=None, *, owner=None, error=False):
        self.tag += 1
        tag = self.tag
        args=dict(i_memory_req_valid=1,i_memory_req_opcode=int(data is not None),
            i_memory_req_addr=address,i_memory_req_size=4,i_memory_req_wdata=data or 0,
            i_memory_req_wstrb=(15 << (address%8)) if data is not None else 0,
            i_memory_req_owner_id=self.owner if owner is None else owner,
            i_memory_req_kernel_id=self.kernel,i_memory_req_region_id=0,
            i_memory_req_generation=self.last['o_status_scratchpad_generation'],
            i_memory_req_tag=tag, i_memory_rsp_ready=0)
        for _ in range(300):
            item=await self.cycle('memory_accept',**args)
            if item.pre['o_memory_req_ready'] & 1: break
        else: raise AssertionError(('Host memory blocked',self.last))
        self.base['i_memory_req_valid']=0
        for _ in range(300):
            if item.post['o_memory_rsp_valid'] & 1: break
            item=await self.cycle('memory_response')
        else: raise AssertionError(('Host memory response timeout',self.last))
        p=item.post
        assert p['o_memory_rsp_tag'] & ((1<<76)-1) == tag
        assert bool(p['o_memory_rsp_error'] & 1) == error, (address, p['o_memory_rsp_error_code'] & 255,
            p['o_status_scratchpad_generation'], self.last['o_status_first_error_code'])
        await self.idle(2)
        await self.cycle('memory_retire',i_memory_rsp_ready=7)
        return p['o_memory_rsp_rdata'] & ((1<<64)-1)

    async def submit(self, desc):
        args={f'i_mst_descriptor_{name}':mst_pack(MST_PARAMETERS,
            'endpoint' if name in ('source','destination') else name,value)
              for name,value in desc.items()}
        for _ in range(100):
            item=await self.cycle('descriptor_accept',i_mst_descriptor_valid=1,**args)
            if item.pre['o_mst_descriptor_ready']: break
        else: raise AssertionError(('MST descriptor blocked',self.last))
        self.base['i_mst_descriptor_valid']=0
        for _ in range(20):
            if item.post['o_mst_descriptor_accepted']: return
            assert not item.post['o_mst_descriptor_rejected'],item.post
            item=await self.cycle('descriptor_admitted')
        raise AssertionError('MST admission missing')

    async def pipeline(self):
        count=24
        await self.setup(count)
        values=[0,1,0xffffffff,0x80000000]+[self.rng.getrandbits(32) for _ in range(count-4)]
        for k,value in enumerate(values): await self.memory(k*4,value)
        await self.memory(0, owner=self.owner+1, error=True)
        await self.runtime(4, state=4)
        await self.idle(6)
        native_epoch=self.last['o_mst_execution_epoch']
        mst_slot=next(i for i,t in enumerate(ordered_tiles(self.c.parameters)) if t['class']=='MST')
        identity=dict(command=1,generation=1,owner=self.owner,kernel=self.kernel,
            package_id=self.package,context_id=self.context,version=self.words[mst_slot],
            allocation=self.last['o_status_allocation_generation'],epoch=native_epoch)
        store=descriptor(identity|dict(command=2),store=True,count=count)
        load=descriptor(identity,count=count)
        # Accept the destination binding before admitting its producer.
        await self.submit(store)
        await self.submit(load)
        self.base['i_mst_session_end']=1
        # Both native completions and cluster events are independently held.
        self.base['i_mst_completion_ready']=0
        self.base['i_event_ready']=0
        for _ in range(2000):
            await self.cycle('pipeline_backpressure')
            if self.last['o_mst_completion_valid']: break
            assert not self.last['o_status_error'],self.last
        else: raise AssertionError(('Pipeline failed to complete a command',self.last))
        await self.runtime(9,error=8)
        await self.runtime(8,error=8)
        self.coverage.hit('abort_preserves_accepted_stores')
        await self.idle(7)
        await self.idle(1,i_mst_completion_ready=1,i_event_ready=1)
        for _ in range(3000):
            await self.cycle('pipeline_drain')
            assert not self.last['o_status_error'],self.last
            if any(e['o_event_type']==2 for e in self.events): break
        else: raise AssertionError(('Kernel completion timeout',self.last))
        assert len(self.completions)==2
        expected_ids={mst_pack(MST_PARAMETERS,'identity',d['identity']) for d in (load,store)}
        assert {p['o_mst_completion_identity'] for p in self.completions}==expected_ids
        for p in self.completions:
            assert p['o_mst_completion_status']==0,p
            assert not p['o_mst_completion_partial'] and not p['o_mst_completion_effects_unknown']
        by_id={p['o_mst_completion_identity']:p for p in self.completions}
        assert by_id[mst_pack(MST_PARAMETERS,'identity',load['identity'])]['o_mst_completion_bytes_read']==4*count
        assert by_id[mst_pack(MST_PARAMETERS,'identity',store['identity'])]['o_mst_completion_bytes_written']==4*count
        for k,value in enumerate(expected_results(values)):
            actual=await self.memory(256+k*4)
            assert actual & 0xffffffff == value,('Arithmetic/store mismatch',k,actual,value)
        self.base['i_mst_session_end']=0
        await self.idle(10)
        await self.runtime(4,error=4)  # A new launch needs a fresh coordinated commit.
        await self.runtime(11)
        await self.cycle('snapshot_read',i_counter_read=1,i_counter_owner_id=self.owner,
                         i_counter_index=1)
        assert self.last['o_counter_snapshot_valid']
        assert self.last['o_counter_valid'] and self.last['o_counter_value'] > 0
        await self.cycle(i_counter_read=0)
        await self.runtime(9,state=0)
        await self.idle(10)
        assert not self.last['o_status_owner_id'] and self.last['o_status_quiescent']
        assert self.last['o_cluster_clock_enable']==int(not self.c.parameters['clock_gating'])
        self.coverage.hit('load_compute_store_real_sram')
        self.coverage.hit('exact_committed_bytes')
        self.coverage.hit('release_waits_for_obligations')
        self.coverage.hit('owner_isolation')
        self.coverage.hit('coherent_counter_snapshot')
        self.coverage.hit('idle_clock_gate')
        # Permission descriptors and snapshot authorization do not cross owners.
        previous_owner,previous_kernel=self.owner,self.kernel
        self.owner,self.kernel=7,13
        await self.runtime(1,state=1)
        assert self.last['o_status_allocation_generation']==2
        assert not self.last['o_counter_snapshot_valid']
        await self.cycle('new_owner_snapshot',i_counter_read=1,
                         i_counter_owner_id=self.owner,i_counter_index=1)
        assert not self.last['o_counter_valid'] and not self.last['o_counter_value']
        await self.cycle(i_counter_read=0)
        await self.memory(0,error=True)
        await self.runtime(9,state=0)
        self.owner,self.kernel=previous_owner,previous_kernel
        self.coverage.hit('new_owner_has_no_stale_snapshot_or_region')

    async def boundary_lifecycle(self):
        await self.reset()
        count=6
        info=await self.setup(count,boundary=True)
        await self.runtime(4,state=4)
        await self.idle(6)
        versions=self.last['o_status_tile_versions']
        await self.runtime(5,state=9)
        assert self.last['o_boundary_isolation_enable']
        await self.runtime(6,error=3,i_runtime_owner_id=self.owner+1)
        await self.runtime(6,error=6,i_runtime_package_id=self.package+1)
        await self.runtime(6,state=4)
        assert self.last['o_status_tile_versions']==versions
        await self.runtime(12,error=16)
        await self.runtime(11,error=3,i_runtime_owner_id=self.owner+1)
        ingress,egress=info['ingress'],info['egress']
        self.base['i_mst_session_end']=1
        self.base['i_boundary_ready']=0
        values=[self.rng.getrandbits(32) for _ in range(count)]
        common=[]
        for k,value in enumerate(values):
            blob=(8<<2)|((0x1234+k)<<230)|(1<<250)
            common.append(blob)
            meta=envelope(self.c.parameters,owner=self.owner,kernel=self.kernel,
                package=self.package,context=self.context,version=self.words[-2],
                epoch=self.last['o_status_execution_epoch'],common=blob)
            for _ in range(1000):
                item=await self.cycle('boundary_input',i_boundary_valid=1<<ingress,
                    i_boundary_data=value<<(32*ingress),i_boundary_metadata=meta<<(512*ingress))
                if item.pre['o_boundary_ready']>>ingress&1: break
            else: raise AssertionError(('Boundary input blocked',self.last))
            self.base['i_boundary_valid']=0
            await self.cycle('input_gap')
        for _ in range(1000):
            if self.last['o_boundary_valid']>>egress&1: break
            await self.cycle('boundary_wait')
        else: raise AssertionError('No boundary output')
        await self.runtime(9,error=8)
        await self.idle(9)
        last_slot=cycle_order(self.c.parameters)[-1]
        last_id=ordered_tiles(self.c.parameters)[last_slot]['id']
        for _ in range(1500):
            await self.cycle('boundary_consume',i_boundary_ready=(1<<egress) if
                             self.rng.randrange(4) else 0)
            assert not self.last['o_status_error'],self.last
            if len(self.boundary)==count and any(e['o_event_type']==2 for e in self.events): break
        else: raise AssertionError(('Boundary completion timeout',self.last))
        expected=[]
        for value,blob in zip(expected_results(values),common):
            expected.append((egress,value,envelope(self.c.parameters,owner=self.owner,
                kernel=self.kernel,package=self.package,context=self.context,
                version=self.words[-2],epoch=self.last['o_status_execution_epoch'],
                common=blob,source=last_id)))
        assert self.boundary==expected,('Data/metadata conservation',self.boundary,expected)
        await self.idle(8,i_mst_session_end=0,i_boundary_valid=0,i_boundary_ready=255)
        # Inject a named native status fault only after all accepted work retires.
        before=len([e for e in self.events if e['o_event_type']==3])
        await self.cycle('mesh_fault',i_event_ready=0,fault=('u_mesh.o_error',1))
        await self.idle(4)
        assert self.last['o_status_cluster_state']==13 and self.last['o_status_fatal_error']
        assert self.last['o_status_first_error_source']==240
        await self.cycle('release_fault',fault=('release',))
        await self.idle(6,i_event_ready=1)
        assert len([e for e in self.events if e['o_event_type']==3])==before+1
        await self.runtime(0,state=13)
        await self.runtime(10,error=4)
        self.coverage.hit('native_fault_containment')
        self.coverage.hit('suspend_resume_identity_preserved')
        self.coverage.hit('boundary_metadata_all_bits_preserved')
        self.coverage.hit('optional_power_rejected')

    async def drain_abort(self):
        await self.reset()
        await self.setup(10,boundary=True,suspend_safe=False)
        await self.runtime(4,state=4)
        await self.idle(8)
        await self.runtime(5,error=16)
        command=7 if self.c.parameters['clock_gating'] else 8
        await self.runtime(command,state=3)
        await self.idle(10)
        assert not self.last['o_status_scratchpad_busy']
        assert not self.last['o_status_network_busy']
        await self.runtime(9,state=0)
        self.coverage.hit('orderly_drain' if command==7 else 'compute_abort_at_empty_boundary')

    async def unknown_runtime(self):
        values=dict(i_runtime_command=0,i_runtime_owner_id=self.owner,
            i_runtime_kernel_id=self.kernel,i_runtime_package_id=self.package,
            i_runtime_context_id=0,i_runtime_resource_mask=self.all_tiles,
            i_runtime_flags=0,i_runtime_tag=0xdead)
        for field,value in values.items():
            width=self.c.widths[field]
            await self.cycle('unknown_runtime',i_runtime_valid=1,
                             **(values|{field:LogicArray('X'*width)}))
            assert not self.last['o_runtime_ready']
            assert self.last['o_status_cluster_state']==0 and not self.last['o_status_error']
            await self.cycle('restore_runtime',i_runtime_valid=0,**values)
        await self.cycle('unknown_valid',i_runtime_valid=LogicArray('X'))
        assert self.last['o_status_cluster_state']==0 and not self.last['o_status_error']
        await self.cycle('restore_valid',i_runtime_valid=0)
        await self.runtime(0,state=0)
        self.coverage.hit('unknown_runtime_fail_closed')

    async def protected_control_fault(self):
        await self.reset()
        await self.cycle('controller_fault',i_event_ready=0,
                         fault=('u_control.u_state.stored',1))
        await self.idle(5)
        assert self.last['o_status_fatal_error'] and self.last['o_status_first_error_code']==17
        await self.cycle('controller_fault_release',fault=('release',))
        await self.idle(4)
        assert self.last['o_status_fatal_error']
        await self.idle(8,i_event_ready=1)
        faults=[e for e in self.events if e['o_event_type']==3]
        assert len(faults)==1,('Repeated first-fault event',len(faults))
        await self.reset()
        self.coverage.hit('protected_controller_fail_stop')

    async def protected_event_fault(self):
        await self.reset()
        await self.runtime(1, state=1)
        # Named parity probe only: corruption is injected into actual collector
        # metadata, never substituted for normal functional event production.
        await self.cycle('event_directory_fault', i_event_ready=0,
            fault=('u_events.g_events.u_queue.u_metadata.g_protection.u_parity_bit.o_q', 1))
        await self.idle(5)
        assert self.last['o_status_fatal_error']
        assert self.last['o_status_first_error_code'] == 17
        assert self.last['o_status_first_error_source'] == 245
        assert self.last['o_boundary_isolation_enable'] and not self.last['o_status_quiescent']
        assert self.last['o_status_owner_id'] == self.owner
        await self.cycle('event_directory_release', fault=('release',), i_event_ready=1)
        await self.idle(5)
        assert self.last['o_status_fatal_error'] and self.last['o_interrupt']
        await self.runtime(10, error=4)
        await self.reset()
        self.coverage.hit('protected_event_collector_fail_stop')

    async def body(self):
        await self.reset()
        await self.runtime(0,state=0)
        await self.unknown_runtime()
        await self.runtime(1,error=5,i_runtime_resource_mask=1)
        await self.pipeline()
        await self.boundary_lifecycle()
        await self.drain_abort()
        await self.protected_control_fault()
        await self.protected_event_fault()
        for _ in range(self.c.random_cycles):
            if self.rng.randrange(50)==0:
                await self.runtime(0,state=0,hold=self.rng.randrange(1,4))
            else: await self.cycle('random_idle',i_test_mode=int(self.rng.randrange(20)==0))
        await self.idle(4,i_test_mode=0)
        self.coverage.hit('random_clock_wakeup')

class ClusterSmokeSequence(ClusterSequence):
    async def body(self):
        await self.reset()
        await self.runtime(1,state=1,hold=4)
        await self.runtime(2,state=2)
        await self.runtime(4,error=4)
        await self.runtime(9,state=0)
        await self.idle(12)
        assert self.last['o_status_quiescent']
        self.coverage.hit('generated_four_by_four_control')


class ClusterCommitFaultSequence(ClusterSequence):
    async def body(self):
        await self.reset()
        await self.setup(4,boundary=True,fault_commit=True)
        await self.reset()
