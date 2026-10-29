"""Host-driven programs; all configuration and DMA cross the canonical memory port."""
import json
import random
from cocotb.types import LogicArray
from pyuvm import uvm_sequence
from cluster.transaction import ClusterItem
from mosaic_blocks.system.model import MemoryModel, payload, record


class SystemSequence(uvm_sequence):
    def __init__(self,config,coverage):
        super().__init__('system_specification')
        self.c,self.coverage=config,coverage
        self.ports={n:0 for n,(direction,_) in config.ports.items() if direction=='input' and n!='i_clk'}
        self.rng=random.Random(config.seed)
        self.memory=MemoryModel(config.parameters['memory_data_width'],config.seed+1)
        self.tag=self.serial=0
        self.last={}
        self.events=[]
        self.next_event_sequence=0
        self.owner,self.kernel,self.package=5,3,101
        self.program_generation=0
        self.script_address=0x100000
        high=(1<<32) if config.parameters['memory_data_width']==64 else 0
        self.input_address=high+0x200000
        self.output_address=high+0x300000
        self.record_tag=0

    async def cycle(self,label='idle',fault=None,**changes):
        self.ports.update(changes)
        self.ports.update(self.memory.drive())
        item=ClusterItem(f'{label}_{self.serial}',self.ports,fault)
        self.serial+=1
        if self.serial%2000==0: print(f'System cycle {self.serial}: {label}',flush=True)
        await self.start_item(item)
        await self.finish_item(item)
        self.last=item.post
        self.memory.observe(item.pre)
        return item

    async def idle(self,count=2,**changes):
        for _ in range(count): await self.cycle(**changes)

    async def reset(self):
        self.memory.reset()
        self.ports.update(dict.fromkeys(self.ports,0))
        self.events.clear(); self.next_event_sequence=0; self.program_generation=0
        await self.idle(4)
        await self.idle(8,i_rstb=1,i_ctrl_response_ready=1)
        assert not self.last['o_boot_ready']
        await self.idle(4,i_memory_reset_done=1)
        assert self.last['o_boot_ready'] and not self.last['o_fatal'], (
            self.last, await self.host(0x7000, owner=1))
        assert await self.host(0)==0x4d535953
        for base,key in [(0x40,'manifest_sha256'),(0x60,'array_manifest_sha256')]:
            actual=sum([(await self.host(base+4*k)) << (32*k) for k in range(8)])
            assert actual==int(self.c.manifest[key],16)
        await self.host(LogicArray('X'*32),error=14)
        assert await self.host(0x7010,owner=1)==0
        assert await self.host(0x7014,owner=1)==0
        await self.host(0x7004,1,owner=1)
        await self.host(0,owner=LogicArray('X'*16),error=14)
        assert await self.host(0x7018,owner=1)==0
        await self.host(0x7004,1,owner=1)
        self.coverage.hit('reset_discovery')

    async def host(self,address,data=None,*,owner=None,privilege=4,strobe=15,error=0,hold=0):
        self.tag=(self.tag+1)&255
        tag=self.tag
        request=dict(i_ctrl_valid=1,i_ctrl_write=int(data is not None),i_ctrl_address=address,
            i_ctrl_write_data=0 if data is None else data,i_ctrl_write_strobe=strobe,
            i_ctrl_requester_id=self.owner if owner is None else owner,i_ctrl_privilege=privilege,
            i_ctrl_tag=tag,i_ctrl_response_ready=0)
        for _ in range(500):
            item=await self.cycle('host_request',**request)
            if item.pre['o_ctrl_ready']: break
        else: raise AssertionError('Host request timeout')
        self.ports['i_ctrl_valid']=0
        for _ in range(100):
            if item.post['o_ctrl_response_valid']: break
            item=await self.cycle('host_response')
        else: raise AssertionError('Host response timeout')
        assert item.post['o_ctrl_response_tag']==tag
        assert item.post['o_ctrl_response_status']==error,(
            'Control status',address,data,error,item.post['o_ctrl_response_status'],self.last)
        value=item.post['o_ctrl_response_data']
        if hold: await self.idle(hold)
        await self.idle(1,i_ctrl_response_ready=1)
        return value

    async def register(self,slot,address,size,permissions=3,*,owner=None,kernel=None,generation=1,error=0,requester=None):
        owner=self.owner if owner is None else owner
        kernel=self.kernel if kernel is None else kernel
        words=[slot,address&0xffffffff,address>>32,size,owner|(kernel<<16),generation|(permissions<<16)]
        for k,value in enumerate(words): await self.host(0x3000+4*k,value,owner=requester)
        await self.host(0x3020,1,error=error,owner=requester)

    async def event(self,*,owner=None,ack=True):
        words=[await self.host(0x4040+4*k,owner=owner) for k in range(16)]
        value=sum(word << (32*k) for k,word in enumerate(words))
        sequence=(value>>128)&0xffffffff
        assert sequence==self.next_event_sequence,('Event loss/duplication',sequence,self.next_event_sequence)
        # A second read of the head must not pop, clear or tear a record.
        assert await self.host(0x4040,owner=owner)==words[0]
        self.coverage.hit('event_head_atomic')
        if ack:
            await self.host(0x4020,sequence,owner=owner)
            self.next_event_sequence+=1
            self.coverage.hit('event_ack')
        event=dict(type=value&255,owner=(value>>32)&65535,kernel=(value>>48)&65535,
            package=(value>>64)&0xffffffff,epoch=(value>>96)&255,sequence=sequence,
            flags=(value>>10)&63,payload=(value>>160)&((1<<256)-1),
            generation=(value>>112)&65535,error=(value>>464)&65535,buffer=(value>>176)&255)
        if ack: self.events.append(event)
        return event

    async def service_events(self):
        while self.last.get('o_interrupt') and self.last.get('o_event_count'):
            await self.event()

    async def fence(self,slot,to_dma=True):
        await self.host(0x3040,slot|(int(to_dma)<<8))
        for _ in range(300):
            if self.last['o_core_phase']==0: break
            await self.cycle('platform_fence')
        else: raise AssertionError('Fence did not retire')
        await self.service_events()
        self.coverage.hit('buffer_fence')

    def native(self,kind,fields,*,slot=0,epoch=0,flags=0,generation=None):
        self.record_tag+=1
        return record(self.c.manifest,kind,payload(self.c.manifest,kind,fields),owner=self.owner,
            kernel=self.kernel,package=self.package,generation=generation or self.program_generation+1,
            epoch=epoch,slot=slot,tag=self.record_tag,flags=flags)

    def special(self,kind,value=0,*,slot=0,epoch=1,generation=None):
        self.record_tag+=1
        return record(self.c.manifest,kind,value,owner=self.owner,kernel=self.kernel,
            package=self.package,generation=generation or self.program_generation+1,
            epoch=epoch,slot=slot,tag=self.record_tag)

    async def submit(self,records,*,generation=None,mutate=False):
        self.program_generation=self.program_generation+1 if generation is None else generation
        self.memory.put(self.script_address,b''.join(records))
        self.c.coverage_file.parent.mkdir(parents=True, exist_ok=True)
        (self.c.coverage_file.parent/f'program_{self.program_generation}.bin').write_bytes(b''.join(records))
        await self.host(0x1000,0)
        await self.host(0x1004,0)
        await self.host(0x1008,len(records)|(self.program_generation<<16))
        await self.host(0x100c,1,hold=3)
        if mutate:
            await self.host(0x1000,255)
            await self.host(0x1004,0xffffffff)
            await self.host(0x1018,1)
        self.coverage.hit('descriptor_snapshot')

    async def wait_program(self,error=0,limit=200000):
        before=len(self.events)
        for _ in range(limit):
            await self.cycle('program_progress')
            if self.last['o_interrupt']: await self.service_events()
            found=[e for e in self.events[before:] if e['type']==3 and e['generation']==self.program_generation]
            if found:
                if found[0]['error'] != error:
                    print('Program diagnostic', [await self.host(0x7100+4*k) for k in range(4)],
                        {k:v for k,v in self.last.items() if k.startswith('o_array_')}, flush=True)
                assert len(found)==1 and found[0]['error']==error,('Program result',found,error,
                    await self.host(0x101c),self.last)
                assert not self.last['o_fatal'],('Unexpected system fault',self.last)
                self.coverage.hit('program_completion')
                return
        raise AssertionError(('Program timeout',self.last,await self.host(0x101c)))

    def runtime_record(self,command,*,epoch=0,flags=0,allocation=1):
        n=self.c.parameters['clusters']
        native=self.c.manifest['array']
        words=[m['config_endpoint_table'] for m in [json.loads((self.c.artifacts/f'array/cluster_{k}/manifest.json').read_text()) for k in range(n)]]
        versions=sum(sum(e['words'] << (16*j) for j,e in enumerate(entries)) << (96*k)
            for k,entries in enumerate(words))
        return self.native(0,dict(i_runtime_command=command,i_runtime_cluster_mask=(1<<n)-1,
            i_runtime_allocation_generation=0 if command==1 else allocation,
            i_runtime_execution_epoch=epoch,i_runtime_local_package_ids=sum((11+k) << (32*k) for k in range(n)),
            i_runtime_context_versions=versions),epoch=epoch,flags=flags)

    async def control_checks(self):
        await self.host(0,hold=4)
        for address,data,error in [(1,None,3),(0xffff0000,None,1),(0,1,2),(0x9000,None,1),
            (0x7008,2,15),(0x100c,1,6)]:
            await self.host(address,data,error=error,owner=1 if address==0x7008 else None)
        await self.host(0x1000,0,strobe=1,error=4)
        await self.host(0x4000,0,owner=9,privilege=0,error=2)
        await self.host(LogicArray('X'*32),error=14)
        self.coverage.hit('unknown_control')
        for field in self.c.manifest['register_map'].values():
            if field['access']=='RO':
                for index in range(field['words']):
                    await self.host(field['offset']+4*index,0,owner=1,error=2)
        await self.host(0x4000,0x100,owner=1,error=6)
        self.coverage.hit('illegal_registers')
        await self.register(0,self.script_address,0x40000,1)
        await self.register(0,self.script_address,0x40000,1,owner=9,requester=9,
            generation=2,error=2)
        await self.host(0x3024,1,owner=9)
        if self.c.parameters['buffers']>=3:
            await self.register(1,self.input_address,96,1)
            await self.register(2,self.output_address,96,2)
        if self.c.parameters['buffers']>3:
            await self.register(3,self.input_address+0x100,64,1,owner=9,error=2)
            await self.host(0x3024,1)
        # A shadow lease cannot be torn by another requester.
        await self.host(0x1000,0)
        await self.host(0x1004,0,owner=9,error=2)
        await self.host(0x1018,1)
        self.coverage.hit('owner_isolation')
        for slot in range(min(3,self.c.parameters['buffers'])): await self.fence(slot)
        self.memory.freeze_requests=True
        await self.submit([self.runtime_record(0)],mutate=True)
        await self.idle(4)
        self.memory.freeze_requests=False
        await self.wait_program()
        # Masking preserves queued data; a wrong ACK cannot remove the head.
        await self.host(0x4000,0,owner=1)
        await self.submit([self.runtime_record(0)])
        for _ in range(1000):
            await self.cycle('masked_event_wait')
            if self.last['o_event_count']: break
        assert self.last['o_event_count'] and not self.last['o_interrupt']
        await self.host(0x4020,0xffffffff,error=7)
        await self.host(0x4040,owner=9,error=2)
        await self.host(0x4000,255,owner=1,strobe=1)
        await self.service_events()
        self.coverage.hit('irq_mask')
        await self.host(0x5000,1,owner=1)
        before=[await self.host(0x5010+4*k,owner=1) for k in range(8)]
        await self.idle(5)
        after=[await self.host(0x5010+4*k,owner=1) for k in range(8)]
        assert before==after and before[0]>0 and before[2]>0
        self.coverage.hit('counter_snapshot')
        for _ in range(self.c.random_cycles//2):
            address=self.rng.choice([0,4,8,12,16,20,0x9000,3])
            await self.host(address,error=1 if address==0x9000 else 3 if address==3 else 0,
                hold=self.rng.randrange(2))
        self.coverage.hit('random_controls')

    async def body(self):
        await self.reset()
        await self.control_checks()
        if self.c.mode=='full': await self.workload()
        await self.service_events()
        await self.idle(3,i_ctrl_valid=0,i_ctrl_response_ready=1)

    async def workload(self):
        from cluster.model import crc32c, descriptor, mst_pack, MST_PARAMETERS
        from mosaic_blocks.array.model import stream_images
        from cluster.model import mesh_parameters
        from static_mesh.topology import topology_id
        from global_noc_contract import signature, PROTOCOL_ID, flow_words, crc32c as noc_crc
        n=self.c.parameters['clusters']
        count=24
        values=[0,1,0xffffffff,0x80000000]+[self.rng.getrandbits(32) for _ in range(count-4)]
        self.memory.put(self.input_address,b''.join(v.to_bytes(4,'little') for v in values))
        self.memory.put(self.output_address,bytes([0xa5])*96)
        records=[]
        if n>1:
            np=self.c.manifest['array']['noc_parameters']
            flows=[flow_words(flow_id=c+1,source=c,destination=1-c,owner=self.owner,
                kernel=self.kernel,package=1,generation=1,epoch=0,context=0,budget=2,messages=1)
                for c in range(n)]
            words=[signature(np),PROTOCOL_ID]+[0]*n+[w for f in flows for w in f]
            def noc(command,version=0,index=0,data=0,crc=0):
                return self.native(6,dict(i_noc_cfg_command=command,i_noc_cfg_package_id=1,
                    i_noc_cfg_expected_version=version,i_noc_cfg_word_index=index,
                    i_noc_cfg_write_data=data,i_noc_cfg_write_strobe=255,i_noc_cfg_expected_crc=crc))
            records.append(noc(5))
            records += [noc(0,0,k,word) for k,word in enumerate(words)]
            records += [noc(cmd,0,crc=noc_crc(words)) for cmd in (2,3,4)]
        records += [self.runtime_record(1),self.runtime_record(2)]
        native_manifests=[]
        for slot in range(n):
            manifest=json.loads((self.c.artifacts/f'array/cluster_{slot}/manifest.json').read_text())
            native_manifests.append(manifest)
            sizes=[e['words'] for e in manifest['config_endpoint_table']]
            images,_=stream_images(manifest['descriptor'],role='local' if n==1 else
                'source' if slot==0 else 'sink',owner=self.owner,kernel=self.kernel,
                package=11+slot,allocation=1,context=0,count=count)
            checksums=[crc32c(image,size*8) for image,size in zip(images,sizes)]
            region=dict(valid=1,generation=1,space=0,base=0,limit=manifest['geometry']['capacity'],
                owner=self.owner,kernel=self.kernel,allocation=1,read_enable=1,write_enable=1,
                dma_enable=1,channel_mask=3,buffer_mask=3)
            records.append(self.native(3,dict(i_cluster_mst_region_index=0,
                i_cluster_mst_region_record=mst_pack(MST_PARAMETERS,'region',region)),slot=slot))
            records.append(self.native(2,dict(i_cluster_package_id=11+slot,
                i_cluster_package_allocation_generation=1,
                i_cluster_package_architecture_hash=int(manifest['manifest_sha256'],16),
                i_cluster_package_topology_id=topology_id(mesh_parameters(manifest['descriptor'])),
                i_cluster_package_contract_version=1,
                i_cluster_package_resource_mask=15,i_cluster_package_endpoint_mask=63,
                i_cluster_package_context_versions=sum(v << (16*k) for k,v in enumerate(sizes)),
                i_cluster_package_image_crcs=sum(v << (32*k) for k,v in enumerate(checksums)),
                i_cluster_package_epoch=1,i_cluster_package_suspend_safe=1),slot=slot))
            for endpoint,(image,size,checksum) in enumerate(zip(images,sizes,checksums)):
                def cfg(command,version=0,index=0,data=0,crc=0):
                    return self.native(1,dict(i_cfg_request_command=command,
                        i_cfg_request_destination_mask=1<<endpoint,i_cfg_request_package_id=11+slot,
                        i_cfg_request_expected_version=version,i_cfg_request_word_index=index,
                        i_cfg_request_write_data=data,i_cfg_request_write_strobe=255,
                        i_cfg_request_expected_crc=crc,i_cfg_request_protocol=1),slot=slot)
                records += [cfg(1,k,k,(image>>(64*k))&((1<<64)-1)) for k in range(size)]
                records += [cfg(cmd,size,crc=checksum) for cmd in (3,6)]
        records += [self.runtime_record(3),self.runtime_record(4)]
        # The released scratchpad region is provisioned at generation one by commit.
        load=1 | (0 << 32) | (0 << 64) | (96 << 96) | (1 << 128)
        records.append(self.special(7,load,slot=0,epoch=1))
        records.append(self.runtime_record(5,epoch=1,flags=1<<2))
        print('System configuration records:',len(records),flush=True)
        await self.submit(records,mutate=True)
        await self.wait_program()
        native_epochs=await self.host(0x2000)
        native_allocations=await self.host(0x2004)
        assert await self.host(0x2008)==sum(1 << (16*k) for k in range(n))
        records=[]
        def mst(slot,command,store):
            identity=dict(command=command,generation=1,owner=self.owner,kernel=self.kernel,
                package_id=11+slot,context_id=0,version=16,
                allocation=(native_allocations >> (16*slot))&65535,
                epoch=(native_epochs >> (4*slot))&15)
            desc=descriptor(identity,store=store,count=count)
            fields={f'i_cluster_mst_descriptor_{key}':mst_pack(MST_PARAMETERS,
                'endpoint' if key in ('source','destination') else key,value) for key,value in desc.items()}
            return self.native(5,fields,slot=slot,epoch=1)
        records += [mst(n-1,2,True),mst(0,1,False)]
        records += [self.special(12,1,slot=slot) for slot in range(n)]
        records.append(self.special(9))
        store=2 | (0 << 32) | (256 << 64) | (96 << 96) | (1 << 128)
        records += [self.special(8,store,slot=n-1),self.special(10,1),self.special(10,2)]
        print('System workload records:',len(records),flush=True)
        await self.submit(records,mutate=True)
        await self.wait_program()
        for _ in range(1000):
            await self.cycle('host_completion')
            await self.service_events()
            terminals=[e for e in self.events if e['type']==1]
            if terminals: break
        else: raise AssertionError(('Missing host completion',self.last))
        assert len(terminals)==1
        terminal=terminals[0]
        assert (terminal['owner'],terminal['kernel'],terminal['package'],terminal['epoch'])==(
            self.owner,self.kernel,self.package,1)
        assert terminal['flags']==7 and terminal['error']==0
        expected=[(v+(6 if n==1 else 12))&0xffffffff for v in values]
        actual=[int.from_bytes(self.memory.get(self.output_address+4*k,4),'little') for k in range(count)]
        assert actual==expected,('System-memory arithmetic',actual,expected)
        assert self.memory.writes==96//self.memory.size
        assert self.memory.fences>=5
        for name in ('configuration_dma','coordinated_commit','input_dma','actual_compute',
                     'output_dma','fenced_host_completion'):
            self.coverage.hit(name)
        if n>1:
            assert self.last['o_array_noc_accepted_packets']==count
            assert self.last['o_array_noc_delivered_packets']==count
            self.coverage.hit('real_noc')
        await self.submit([self.runtime_record(12,epoch=1)])
        await self.wait_program()
        assert not self.last['o_array_allocated'] and not self.last['o_array_fatal']
        await self.fence(0,False)
        self.coverage.hit('release')
