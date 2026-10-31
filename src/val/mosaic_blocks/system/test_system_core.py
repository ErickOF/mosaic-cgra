"""Focused PyUVM qualification of actual system_core with explicit Python array peers.

These peers qualify the core's protocol/fault behavior. Full system tests separately
instantiate and execute the real generated array; these are not array evidence.
"""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[2]),str(Path(__file__).resolve().parents[1])]
import cocotb
from cocotb.triggers import Event
from pyuvm import ConfigDB, test, uvm_test
from mosaic_blocks.system.config import SystemConfig, ROOT
from mosaic_blocks.system.env import SystemEnv
from mosaic_blocks.system.sequences import SystemSequence
from mosaic_blocks.system.model import crc32c


class CoreSequence(SystemSequence):
    def __init__(self,*args):
        super().__init__(*args)
        self.peer=None
        self.peer_count=0
        self.peer_fault=False

    async def cycle(self,label='idle',fault=None,**changes):
        peer=dict(i_dispatch_ready=1,i_dispatch_payload_bits=0xffff,
            i_dispatch_response_valid=0,i_dispatch_response_error=0,
            i_dispatch_response_fault=0,i_dispatch_response_data=0)
        kind=self.last.get('o_dispatch_kind',0)
        group=self.c.manifest['groups'].get(str(kind))
        peer['i_dispatch_payload_bits']=group['payload_bits'] if group else {
            7:160,8:160,9:0,10:8,11:125,12:1}.get(kind,0xffff)
        if self.peer and self.serial>=self.peer['at']:
            peer.update(i_dispatch_response_valid=1,i_dispatch_response_data=self.peer['data'],
                i_dispatch_response_fault=int(self.peer_fault))
        item=await super().cycle(label,fault=fault,**peer,**changes)
        p=item.pre
        if not p['i_rstb']:
            self.peer=None
        else:
            if p['i_dispatch_response_valid'] and p['o_dispatch_response_ready']: self.peer=None
            if p['o_dispatch_valid'] and p['i_dispatch_ready']:
                assert self.peer is None
                self.peer_count+=1
                data=0x1234+((p['o_dispatch_payload']>>2)&0xffffffff) if p['o_dispatch_kind']==11 else 0
                self.peer=dict(at=self.serial+2,data=data)
        return item

    async def minimal(self,output=False):
        self.peer_fault=False
        await self.reset()
        await self.register(0,self.script_address,0x40000,1)
        await self.fence(0)
        if output:
            await self.register(2,self.output_address,16,2)
            await self.fence(2)

    async def until_phase(self,phase,limit=1000):
        for _ in range(limit):
            if self.last['o_core_phase']==phase: return
            await self.cycle('wait_phase')
        raise AssertionError(('Phase timeout',phase,self.last))

    async def rejection_checks(self):
        for mutate in ('crc','magic','owner','generation','hash','slot','padding'):
            frame=bytearray(self.runtime_record(0))
            offsets=dict(crc=28,magic=0,owner=8,generation=16,hash=32,slot=19,padding=255)
            frame[offsets[mutate]]^=1 if mutate!='slot' else 128
            if mutate!='crc':
                frame[28:32]=bytes(4)
                frame[28:32]=crc32c(frame).to_bytes(4,'little')
            before=self.peer_count
            await self.submit([bytes(frame)])
            await self.wait_program(error=6)
            assert self.peer_count==before
        self.coverage.hit('descriptor_rejections')
        # Rejected generation never enqueues a request or locks a region.
        await self.host(0x1000,0); await self.host(0x1004,0)
        await self.host(0x1008,1|(self.program_generation<<16))
        await self.host(0x100c,1,error=7); await self.host(0x1018,1)
        self.coverage.hit('stale_generation')
        before=self.peer_count
        bad=1|(0xfffffff0<<32)|(0<<64)|(32<<96)|(1<<128)
        await self.submit([self.special(7,bad)])
        await self.wait_program(error=8)
        assert self.peer_count==before
        self.coverage.hit('dma_bounds_rejection')
        self.memory.mode='timeout'
        await self.submit([self.runtime_record(0)])
        await self.until_phase(2)
        await self.host(0x1020,1)
        self.memory.mode='normal'
        await self.wait_program(error=13)
        self.coverage.hit('cancel_drains_burst')

    async def queue_checks(self):
        await self.minimal()
        for slot in (1,2,3):
            await self.register(slot,(slot+1)*0x100000,4096,1)
            await self.fence(slot)
        self.memory.mode='timeout'
        await self.submit([self.runtime_record(0)])
        first_generation=self.program_generation
        await self.until_phase(2)
        for slot in (1,2,3):
            frame=self.native(0,dict(i_runtime_command=0,i_runtime_cluster_mask=3),generation=1)
            self.memory.put((slot+1)*0x100000,frame)
            await self.host(0x1000,slot); await self.host(0x1004,0)
            await self.host(0x1008,1|(1<<16))
            await self.host(0x100c,1,error=5 if slot==3 else 0)
        assert self.last['o_command_count']==2
        await self.host(0x1018,1)
        self.memory.mode='normal'
        before=len(self.events)
        for _ in range(1000):
            await self.cycle('queue_retirement')
            await self.service_events()
            done=[e for e in self.events[before:] if e['type']==3]
            if len(done)==3: break
        assert {(e['buffer'],e['generation']) for e in done}=={
            (0,first_generation),(1,1),(2,1)}
        assert all(e['error']==0 for e in done)
        self.coverage.hit('command_queue_full_wrap')
        # A rejected full-queue doorbell must not consume generation or ownership.
        await self.host(0x1000,3); await self.host(0x1004,0)
        await self.host(0x1008,1|(1<<16)); await self.host(0x100c,1)
        for _ in range(300):
            await self.cycle('queue_wrap')
            await self.service_events()
            if any(e['type']==3 and e['buffer']==3 for e in self.events): break
        assert any(e['type']==3 and e['buffer']==3 and e['error']==0 for e in self.events)
        await self.host(0x4000,0,owner=1)
        # Fill the event queue, then require the final producer to remain held.
        for index in range(9):
            await self.submit([self.runtime_record(0)])
            for _ in range(200):
                await self.cycle('event_pressure')
                if self.last['o_core_phase']==0 or (index==8 and self.last['o_event_count']==8 and
                    self.last['o_core_phase']==7): break
            if index<8: assert self.last['o_core_phase']==0
        assert self.last['o_event_count']==8 and not self.last['o_interrupt']
        await self.idle(8)
        await self.event()
        await self.idle(3)
        assert self.last['o_event_count']==8
        while self.last['o_event_count']: await self.event()
        self.coverage.hit('event_full_backpressure')
        # A masked head cannot hide a later unmasked event.
        await self.submit([self.runtime_record(0)])
        await self.until_phase(0)
        for _ in range(200):
            await self.cycle()
            if self.last['o_event_count']: break
        for _ in range(10):
            item=await self.cycle('native_event',i_array_event_valid=1,i_array_event_type=0,
                i_array_event_owner=self.owner,i_array_event_kernel=self.kernel,
                i_array_event_package=self.package,i_array_event_sequence=0)
            if item.pre['o_array_event_ready']: break
        await self.idle(2,i_array_event_valid=0)
        await self.host(0x4000,128,owner=1)
        assert self.last['o_interrupt'] and self.last['o_event_count']==2
        await self.event(); await self.event()
        self.coverage.hit('unmasked_event_behind_head')
        await self.host(0x4000,255,owner=1)

    async def completion_order(self):
        await self.minimal(output=True)
        self.memory.put(self.output_address,bytes(16))
        await self.submit([self.runtime_record(5,epoch=1,flags=4)])
        await self.wait_program()
        store=2|(256<<64)|(16<<96)|(1<<128)
        self.memory.mode='hold_write'
        before=self.peer_count
        await self.submit([self.special(8,store),self.special(10,2)])
        await self.until_phase(17)
        await self.idle(8)
        assert self.memory.write is None and self.peer_count==before
        assert not self.last['o_event_count']
        event=dict(i_array_event_valid=1,i_array_event_type=2,i_array_event_owner=self.owner,
            i_array_event_kernel=self.kernel,i_array_event_package=self.package,
            i_array_event_epoch=1,i_array_event_sequence=0)
        for _ in range(20):
            item=await self.cycle('synthetic_array_terminal',**event)
            if item.pre['o_array_event_ready']: break
        else: raise AssertionError('Array completion blocked')
        await self.idle(2,i_array_event_valid=0)
        assert not [e for e in self.events if e['type']==1]
        await self.until_phase(15)
        await self.idle(8)
        assert not self.last['o_interrupt'] and not self.last['o_event_count']
        assert self.memory.get(self.output_address,16)==bytes(16)
        self.memory.mode='hold_fence'
        await self.until_phase(19)
        await self.idle(12)
        assert not self.last['o_event_count']
        assert self.memory.writes==1 and self.memory.fence
        self.memory.mode='normal'
        await self.wait_program()
        for _ in range(30):
            await self.cycle()
            await self.service_events()
            if any(e['type']==1 for e in self.events): break
        terminals=[e for e in self.events if e['type']==1]
        assert len(terminals)==1 and terminals[0]['flags']==7
        self.coverage.hit('completion_waits_write_and_fence')

    async def fault_checks(self):
        await self.minimal()
        self.memory.mode='timeout'
        await self.submit([self.runtime_record(0)])
        await self.until_phase(2)
        await self.idle(145)
        assert self.last['o_fatal'] and self.last['o_interrupt']
        assert await self.host(0x7000,owner=1)==267
        await self.host(0x7004,1,owner=1,error=14)
        self.memory.mode='normal'
        for _ in range(300):
            await self.cycle('late_read_drain')
            if self.memory.read is None and self.last['o_core_phase']==0: break
        assert self.memory.read is None
        self.coverage.hit('memory_timeout_late_drain')
        await self.minimal()
        self.memory.mode='wrong_id'
        await self.submit([self.runtime_record(0)])
        await self.idle(12)
        assert self.last['o_fatal']
        assert self.memory.read is not None
        self.memory.mode='normal'; self.memory.held_read=None
        for _ in range(200):
            await self.cycle('legitimate_read_retirement')
            if self.memory.read is None and self.last['o_core_phase']==0: break
        assert self.memory.read is None
        self.coverage.hit('wrong_memory_identity')
        await self.minimal()
        self.peer_fault=True
        await self.submit([self.runtime_record(0)])
        for _ in range(200):
            await self.cycle('wrong_array_identity')
            if self.last['o_fatal']: break
        assert self.last['o_fatal']
        self.coverage.hit('wrong_array_identity')
        await self.minimal()
        await self.cycle('protected_region_fault',fault=('g_core.g_region[0].u_region.stored',1))
        await self.idle(3)
        assert self.last['o_fatal'] and self.last['o_interrupt']
        await self.cycle('release_fault',fault=('release',0))
        await self.idle(3)
        assert self.last['o_fatal']
        self.coverage.hit('sticky_region_integrity')
        await self.reset()
        self.coverage.hit('reset_recovery')

    async def body(self):
        await self.reset()
        await self.control_checks()
        await self.rejection_checks()
        await self.queue_checks()
        await self.completion_order()
        await self.fault_checks()
        await self.idle(3,i_ctrl_valid=0,i_ctrl_response_ready=1)


@test(timeout_time=100,timeout_unit='ms')
class SystemCoreTest(uvm_test):
    def build_phase(self):
        actual=SystemConfig.from_environment()
        spec=importlib.util.spec_from_file_location('core_test_generator',ROOT/'src/gen/system/generate.py')
        gen=importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)
        ports=gen.array.cluster.ports('system_core',dict(N=2,B=4,D=128))
        manifest=deepcopy(actual.manifest)
        manifest.update(manifest_sha256='0'*64,array_manifest_sha256='0'*64)
        self.c=SystemConfig(actual.artifacts,manifest,ports,actual.seed,actual.random_cycles,
            actual.coverage_file,'core')
        self.c.coverage_file.unlink(missing_ok=True)
        active=dict(pre=Event(),post=Event(),reset_count=0,fault_mode=False)
        ConfigDB().set(self,'env.*','config',self.c)
        ConfigDB().set(self,'env.*','active',active)
        self.env=SystemEnv('env',self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value=0
        await CoreSequence(self.c,self.env.coverage).start(self.env.sequencer)
        self.drop_objection()
