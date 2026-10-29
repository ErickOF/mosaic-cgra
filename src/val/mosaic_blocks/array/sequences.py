"""Directed lifecycle, true inter-cluster workloads, stalls and containment tests."""
from copy import deepcopy
import json
import random
from pyuvm import uvm_sequence
from cocotb.types import LogicArray
from cluster.config import ClusterConfig
from cluster.sequences import ClusterSequence
from cluster.transaction import ClusterItem
from cluster.model import crc32c, expected_results, descriptor, mst_pack, MST_PARAMETERS
from global_noc_contract import signature, PROTOCOL_ID, flow_words, crc32c as noc_crc
from mosaic_blocks.array.model import AllocationModel, stream_images


class LocalSession(ClusterSequence):
    """Reuse released cluster transactions through public array gateways only."""
    def __init__(self, parent, index):
        a = parent.c.artifacts/f'cluster_{index}'
        c = ClusterConfig(json.loads((a/'manifest.json').read_text()),
            json.loads((a/'ports.json').read_text()), parent.c.seed, parent.c.random_cycles,
            parent.c.coverage_file)
        super().__init__(c, None, parent.coverage)
        self.parent, self.slot = parent, index
        self.completions = []

    def view(self, p):
        result = {}
        for name, (_, width) in self.c.ports.items():
            if name.startswith(('i_cfg_request_', 'o_cfg_response_')) or name in (
                'o_cfg_request_ready', 'i_cfg_response_ready', 'i_clk', 'i_rstb', 'i_test_mode', 'i_scan_enable'):
                result[name] = p.get(name, 0)
            else:
                public = name[:2]+'cluster_'+name[2:]
                value = p.get(public, 0)
                result[name] = (value >> (width*self.slot)) & ((1<<width)-1) if value is not None else None
        return result

    async def cycle(self, label='local', fault=None, **ports):
        self.base.update(ports)
        updates = dict(i_cfg_cluster_slot=self.slot, i_cfg_array_package_id=self.parent.package)
        for name, value in self.base.items():
            if name.startswith('i_cfg_request_') or name == 'i_cfg_response_ready': updates[name] = value
            elif name.startswith(('i_runtime_', 'i_cfg_commit_')) or name in ('i_rstb', 'i_test_mode', 'i_scan_enable', 'i_event_ready'):
                continue
            else:
                public = name[:2]+'cluster_'+name[2:]
                if public in self.parent.ports:
                    width = self.c.ports[name][1]
                    before = updates.get(public, self.parent.ports[public])
                    updates[public] = (before & ~(((1<<width)-1) << (width*self.slot))) | (value << (width*self.slot))
        item = await self.parent.step(label, fault=fault, **updates)
        pre, post = self.view(item.pre), self.view(item.post)
        self.last = post
        if pre['o_cfg_response_valid'] and pre['i_cfg_response_ready']:
            self.cfg_responses.setdefault(pre['o_cfg_response_tag'], []).append(pre)
        return type('LocalObservation', (), dict(pre=pre, post=post))()

    async def submit(self, desc):
        await super().submit(desc)
        await self.cycle('descriptor_retire')


class ArraySequence(uvm_sequence):
    def __init__(self, config, coverage):
        super().__init__('array_specification')
        self.c, self.coverage = config, coverage
        self.ports = {n: 0 for n, (direction, _) in config.ports.items() if direction == 'input' and n != 'i_clk'}
        self.n = len(config.parameters['clusters'])
        self.mask = (1<<self.n)-1
        self.target_mask = self.mask
        self.rng = random.Random(config.seed)
        self.serial = self.tag = 0
        self.responses, self.events = {}, []
        self.owner, self.kernel, self.package = 5, 3, 101
        self.generation = self.epoch = 0
        self.last = {}
        self.oracle = AllocationModel(self.n)
        self.local = [LocalSession(self, c) for c in range(self.n)]
        for c, session in enumerate(self.local): session.package = 11+c

    async def step(self, label='idle', fault=None, **changes):
        self.ports.update(changes)
        item = ClusterItem(f'{label}_{self.serial}', self.ports, fault)
        self.serial += 1
        if self.serial % 1000 == 0:
            print(f'Array cycle {self.serial}: {label}', flush=True)
        await self.start_item(item)
        await self.finish_item(item)
        self.last = item.post
        for session in self.local:
            session.last = session.view(item.post)
            pre = session.view(item.pre)
            if pre['o_mst_completion_valid'] and pre['i_mst_completion_ready']:
                session.completions.append(pre)
        if item.pre['i_rstb']:
            if item.pre['o_runtime_response_valid'] and item.pre['i_runtime_response_ready']:
                self.responses[item.pre['o_runtime_response_tag']] = item.pre
            if item.pre['o_event_valid'] and item.pre['i_event_ready']: self.events.append(item.pre)
        return item

    async def idle(self, count=3, **changes):
        for _ in range(count): await self.step(**changes)

    async def reset(self):
        self.ports.update(dict.fromkeys(self.ports, 0))
        self.responses.clear(); self.events.clear()
        self.generation = self.epoch = 0
        self.target_mask = self.mask
        self.oracle = AllocationModel(self.n)
        for s in self.local:
            s.owner, s.kernel = self.owner, self.kernel
            s.base.update(dict.fromkeys(s.base, 0)); s.completions.clear(); s.cfg_responses.clear()
        await self.idle(4)
        await self.idle(16, i_rstb=1, i_runtime_response_ready=1, i_event_ready=1, i_cfg_response_ready=1)
        assert self.last['o_allocated'] == 0 and self.last['o_fatal'] == 0
        assert self.last['o_manifest_hash'] == int(self.c.manifest['manifest_sha256'], 16)
        assert self.last['o_array_id'] == self.c.parameters['array_id']
        self.coverage.hit('reset'); self.coverage.hit('manifest_discovery')

    async def runtime(self, command, *, error=0, hold=0, **changes):
        self.tag += 1
        versions = sum(sum(v << (16*i) for i, v in enumerate(s.words)) << (96*c)
                       for c, s in enumerate(self.local))
        args = dict(i_runtime_valid=1, i_runtime_command=command, i_runtime_owner_id=self.owner,
            i_runtime_kernel_id=self.kernel, i_runtime_array_package_id=self.package,
            i_runtime_manifest_hash=int(self.c.manifest['manifest_sha256'], 16),
            i_runtime_cluster_mask=self.target_mask, i_runtime_allocation_generation=self.generation,
            i_runtime_execution_epoch=self.epoch, i_runtime_context_id=0,
            i_runtime_local_package_ids=sum(s.package << (32*c) for c, s in enumerate(self.local)),
            i_runtime_context_versions=versions, i_runtime_mapping_variant=0, i_runtime_qos_profile=0,
            i_runtime_power_profile=0, i_runtime_flags=0, i_runtime_tag=self.tag,
            i_runtime_response_ready=int(not hold)) | changes
        for _ in range(500):
            item = await self.step('runtime_accept', **args)
            if item.pre['o_runtime_ready']: break
        else: raise AssertionError(('Runtime blocked', command, self.last))
        self.ports['i_runtime_valid'] = 0
        for _ in range(3000):
            if item.post['o_runtime_response_valid']: break
            item = await self.step('runtime_wait')
        else: raise AssertionError(('Runtime missing', command, self.last))
        assert item.post['o_runtime_response_error_code'] == error, (
            'Runtime error', command, error, item.post['o_runtime_response_error_code'], self.last)
        if hold: await self.idle(hold)
        await self.idle(2, i_runtime_response_ready=1)
        response = self.responses.pop(self.tag)
        if not error and command == 1:
            expected_generation = self.oracle.allocate(args['i_runtime_cluster_mask'],
                args['i_runtime_owner_id'], args['i_runtime_kernel_id'], args['i_runtime_array_package_id'])
            for c in range(self.n):
                if args['i_runtime_cluster_mask'] >> c & 1:
                    assert self.last['o_allocation_generations'] >> (16*c) & 65535 == expected_generation
        if not error and command == 12:
            self.oracle.release(args['i_runtime_cluster_mask'], args['i_runtime_owner_id'],
                args['i_runtime_kernel_id'], args['i_runtime_array_package_id'],
                args['i_runtime_allocation_generation'])
        assert self.last['o_allocated'] == sum(self.oracle.records), 'Allocation oracle mismatch'
        if not error and command == 1: self.generation = max(
            self.last['o_allocation_generations'] >> (16*c) & 65535 for c in range(self.n))
        if not error and command == 4: self.epoch += 1
        return response

    async def noc_configuration(self):
        if self.n == 1: return
        p = self.c.manifest['noc_parameters']
        flows = [flow_words(flow_id=c+1, source=c, destination=1-c, owner=self.owner,
            kernel=self.kernel, package=1, generation=1, epoch=0, context=0,
            budget=2, messages=1) for c in range(self.n)]
        words = [signature(p), PROTOCOL_ID] + [0]*self.n + [w for f in flows for w in f]
        version = 0
        async def cfg(command, *, index=0, data=0, checksum=0):
            nonlocal version
            self.tag += 1
            values = dict(i_noc_cfg_valid=1, i_noc_cfg_command=command, i_noc_cfg_owner_id=1,
                i_noc_cfg_kernel_id=1, i_noc_cfg_package_id=1, i_noc_cfg_expected_version=version,
                i_noc_cfg_word_index=index, i_noc_cfg_write_data=data, i_noc_cfg_write_strobe=255,
                i_noc_cfg_expected_crc=checksum, i_noc_cfg_tag=self.tag, i_noc_cfg_response_ready=0)
            for _ in range(100):
                item = await self.step('noc_cfg', **values)
                if item.pre['o_noc_cfg_ready']: break
            else: raise AssertionError('NoC config blocked')
            self.ports['i_noc_cfg_valid'] = 0
            for _ in range(100):
                if item.post['o_noc_cfg_response_valid']: break
                item = await self.step('noc_cfg_wait')
            assert item.post['o_noc_cfg_response_valid']
            assert item.post['o_noc_cfg_response_status'] == 0, (command, item.post)
            version = item.post['o_noc_cfg_response_version']
            await self.idle(2, i_noc_cfg_response_ready=1)
        await cfg(5)
        for i, word in enumerate(words): await cfg(0, index=i, data=word)
        checksum = noc_crc(words)
        for command in (2, 3, 4): await cfg(command, checksum=checksum)
        self.coverage.hit('noc_configuration')

    async def configure(self, count, *, slots=None, role=None, commit=True):
        slots = list(range(self.n)) if slots is None else slots
        await self.runtime(2)
        for c in slots:
            s = self.local[c]
            s.base.update(s.defaults)
            allocation = s.last['o_status_allocation_generation']
            await s.management(dict(valid=1, generation=1, space=0, base=0,
                limit=s.c.manifest['geometry']['capacity'], owner=s.owner, kernel=s.kernel,
                allocation=allocation, read_enable=1, write_enable=1, dma_enable=1,
                channel_mask=3, buffer_mask=3))
            raw, info = stream_images(s.c.parameters, role=role or ('local' if self.n == 1 else
                'source' if c == 0 else 'sink'), owner=s.owner, kernel=s.kernel,
                package=s.package, allocation=allocation, context=0, count=count)
            checksums = [crc32c(image, words*8) for image, words in zip(raw, s.words)]
            await s.manifest(checksums, hold=3)
            for ep, (image, words) in enumerate(zip(raw, s.words)):
                query = await s.cfg(5, 1<<ep)
                initial = query[0]['o_cfg_response_context_version']
                bct = ep < s.n and s.c.parameters['tiles'][ep]['class'] == 'BCT'
                indices = list(range(words))
                for offset, word in enumerate(indices):
                    await s.cfg(1, 1<<ep, version=initial+offset, word=word,
                                data=image >> (64*word) & ((1<<64)-1))
                await s.cfg(3, 1<<ep, version=words, crc=checksums[ep])
                await s.cfg(6, 1<<ep, version=words, crc=checksums[ep], hold=3 if ep == 0 else 0)
        self.coverage.hit('hierarchical_config')
        await self.runtime(5, error=4)
        self.coverage.hit('prepare_before_commit')
        await self.runtime(3)
        if not commit: return
        await self.runtime(4, hold=4)
        assert all(self.local[c].last['o_cfg_execution_hold'] and self.local[c].last['o_cfg_commit_ack_mask'] == 63 for c in slots)
        self.coverage.hit('atomic_commit')

    async def workload(self):
        count = 6 if self.n == 1 else 24
        await self.reset()
        await self.noc_configuration()
        await self.runtime(1, hold=4)
        await self.runtime(1, error=3)
        self.coverage.hit('overlap_rejected')
        await self.runtime(2, error=2, i_runtime_owner_id=99)
        self.coverage.hit('owner_isolation')
        await self.runtime(2, error=5, i_runtime_allocation_generation=99)
        self.coverage.hit('generation_isolation')
        await self.runtime(2, error=6, i_runtime_manifest_hash=0)
        before = self.last['o_allocated']
        for command in (9, 10, 15): await self.runtime(command, error=11)
        assert self.last['o_allocated'] == before
        self.coverage.hit('unsupported_unchanged')
        await self.configure(count)
        values = [self.rng.getrandbits(32) for _ in range(count)]
        for k, value in enumerate(values): await self.local[0].memory(k*4, value)
        await self.runtime(5)
        versions = self.last['o_cluster_status_tile_versions']
        await self.idle(6)
        await self.runtime(6)
        assert not self.last['o_running'] and self.last['o_array_state'] == 6
        await self.runtime(7, error=2, i_runtime_owner_id=self.owner+1)
        await self.runtime(7)
        assert self.last['o_running'] == self.mask
        assert self.last['o_cluster_status_tile_versions'] == versions
        self.coverage.hit('suspend_resume')
        source, sink = self.local[0], self.local[-1]
        def identity(s, command):
            return dict(command=command, generation=1, owner=s.owner, kernel=s.kernel,
                package_id=s.package, context_id=0, version=s.words[3],
                allocation=s.last['o_status_allocation_generation'], epoch=s.last['o_mst_execution_epoch'])
        store = descriptor(identity(sink, 2), store=True, count=count)
        load = descriptor(identity(source, 1), count=count)
        if self.n == 1:
            await sink.submit(store)
            await source.submit(load)
        else:
            await source.submit(load)
            await self.idle(300)
            assert self.last['o_noc_accepted_packets'] > self.last['o_noc_delivered_packets']
            self.coverage.hit('noc_backpressure')
            await sink.submit(store)
        self.ports['i_cluster_mst_session_end'] = self.mask
        await self.idle(12, i_event_ready=0)
        for _ in range(5000):
            await self.step('workload_progress', i_event_ready=int(self.rng.randrange(4) != 0))
            assert self.last['o_fatal'] == 0, ('Array fault', self.last)
            if any(e['o_event_type'] == 2 for e in self.events): break
        else: raise AssertionError(('Workload did not complete', self.last))
        self.coverage.hit('random_stalls')
        await self.idle(10, i_event_ready=1)
        expected = expected_results(values)
        if self.n > 1: expected = expected_results(expected)
        for k, value in enumerate(expected):
            actual = await sink.memory(256+k*4)
            assert actual & 0xffffffff == value, ('SRAM arithmetic', k, actual, value)
        all_completions = [p for s in self.local for p in s.completions]
        assert len(all_completions) == 2
        by_command = {p['o_mst_completion_identity'] & 65535: p for p in all_completions}
        assert by_command[1]['o_mst_completion_bytes_read'] == count*4
        assert by_command[2]['o_mst_completion_bytes_written'] == count*4
        assert all(p['o_mst_completion_status'] == 0 and not p['o_mst_completion_partial'] and
                   not p['o_mst_completion_effects_unknown'] for p in all_completions)
        assert len([e for e in self.events if e['o_event_type'] == 2]) == 1
        self.coverage.hit('load_compute_store'); self.coverage.hit('exact_bytes')
        if self.n > 1:
            assert self.last['o_noc_accepted_packets'] == count == self.last['o_noc_delivered_packets']
            self.coverage.hit('noc_packet_conservation'); self.coverage.hit('package_rebinding')
        self.ports['i_cluster_mst_session_end'] = 0
        await self.idle(10)
        await self.runtime(12)
        assert not self.last['o_allocated'] and not self.last['o_fatal']
        self.coverage.hit('release')

    async def isolation(self):
        await self.reset()
        # Independent owners reserve disjoint complete clusters; no NoC data can
        # pass their adapters even though their physical routers are shared.
        for c in range(self.n):
            await self.runtime(1, i_runtime_cluster_mask=1<<c, i_runtime_owner_id=20+c,
                i_runtime_kernel_id=40+c, i_runtime_array_package_id=200+c)
        assert self.last['o_allocated'] == self.mask
        for c in range(self.n):
            await self.runtime(12, i_runtime_cluster_mask=1<<c, i_runtime_owner_id=20+c,
                i_runtime_kernel_id=40+c, i_runtime_array_package_id=200+c,
                i_runtime_allocation_generation=c+1)
        self.coverage.hit('concurrent_allocations')
        await self.idle(3, i_test_mode=1, i_runtime_valid=1)
        assert not self.last['o_runtime_ready'] and not self.last['o_allocated']
        self.coverage.hit('test_mode')
        await self.idle(2, i_test_mode=0, i_runtime_valid=0)
        unknown = LogicArray('X'*16)
        await self.idle(4, i_runtime_valid=1, i_runtime_owner_id=unknown)
        assert not self.last['o_runtime_ready'] and not self.last['o_allocated']
        await self.idle(2, i_runtime_valid=0, i_runtime_owner_id=0)
        self.coverage.hit('unknown_fail_closed')
        for _ in range(self.c.random_cycles):
            await self.step('random_idle', i_scan_enable=self.rng.randrange(16) == 0)
            assert not self.last['o_allocated'] and not self.last['o_event_valid']
        await self.runtime(1)
        await self.step('native_fault', fault=('u_cluster0.u_mesh.o_error', 1))
        await self.idle(6)
        assert self.last['o_fatal'] == self.mask and self.last['o_allocated'] == self.mask
        await self.step('release_injection', fault=('release',))
        await self.runtime(5, error=4)
        self.coverage.hit('fault_containment')
        await self.reset()

    async def concurrent_kernels(self):
        if self.n == 1: return
        await self.reset()
        await self.noc_configuration()
        identities = [(20+c, 40+c, 200+c) for c in range(self.n)]
        for c, (owner, kernel, package) in enumerate(identities):
            self.owner, self.kernel, self.package = owner, kernel, package
            self.target_mask = 1 << c
            await self.runtime(1)
            self.local[c].owner, self.local[c].kernel = owner, kernel
        for c, identity in enumerate(identities):
            self.owner, self.kernel, self.package = identity
            self.target_mask = 1 << c
            self.generation, self.epoch = c+1, 0
            await self.configure(4, slots=[c], role='local')
            for k in range(4):
                await self.local[c].memory(k*4, (c+1)*100+k)
                await self.local[c].memory(256+k*4, 0)
        for c, identity in enumerate(identities):
            self.owner, self.kernel, self.package = identity
            self.target_mask = 1 << c
            self.generation, self.epoch = c+1, 1
            await self.runtime(5)
        assert self.last['o_running'] == self.mask
        for c, s in enumerate(self.local):
            identity = dict(command=2, generation=1, owner=s.owner, kernel=s.kernel,
                package_id=s.package, context_id=0, version=s.words[3],
                allocation=s.last['o_status_allocation_generation'], epoch=s.last['o_mst_execution_epoch'])
            await s.submit(descriptor(identity, store=True, count=4))
            await s.submit(descriptor(identity | dict(command=1), count=4))
        self.ports['i_cluster_mst_session_end'] = self.mask
        for _ in range(3000):
            await self.step('concurrent_progress', i_event_ready=int(self.rng.randrange(4) != 0))
            if self.last['o_fatal']:
                print('CONCURRENT FAULT', json.dumps({k: v for k, v in self.last.items() if k.startswith(
                    ('o_first_error', 'o_fatal', 'o_cluster_status_first_error', 'o_cluster_mst_error',
                     'o_cluster_status_cluster_state', 'o_cluster_status_owner', 'o_cluster_status_kernel'))}), flush=True)
            assert not self.last['o_fatal'], {k: v for k, v in self.last.items() if k.startswith(
                ('o_first_error', 'o_fatal', 'o_cluster_status_first_error', 'o_cluster_mst_error',
                 'o_cluster_status_cluster_state', 'o_cluster_status_owner', 'o_cluster_status_kernel'))}
            if len([e for e in self.events if e['o_event_type'] == 2]) == self.n: break
        else: raise AssertionError('Concurrent completion missing')
        await self.idle(10, i_event_ready=1, i_cluster_mst_session_end=0)
        for c, identity in enumerate(identities):
            self.owner, self.kernel, self.package = identity
            self.target_mask = 1 << c
            self.generation, self.epoch = c+1, 1
            s = self.local[c]
            for k in range(4):
                assert (await s.memory(256+k*4)) & 0xffffffff == (c+1)*100+k+6
            await s.memory(0, owner=s.owner+100, error=True)
            await self.runtime(13)
            await s.cycle('counter_read', i_counter_read=1, i_counter_owner_id=s.owner, i_counter_index=1)
            assert s.last['o_counter_valid'] and s.last['o_counter_value'] > 0
            await s.cycle('wrong_counter_owner', i_counter_owner_id=s.owner+100)
            assert not s.last['o_counter_valid'] and s.last['o_counter_value'] == 0
            await s.cycle('counter_idle', i_counter_read=0)
            await self.runtime(12)
        assert {e['o_event_cluster_mask'] for e in self.events if e['o_event_type'] == 2} == {1, 2}
        self.coverage.hit('concurrent_kernels')
        self.owner, self.kernel, self.package = 5, 3, 101
        await self.reset()

    async def partial_commit(self):
        await self.reset()
        await self.noc_configuration()
        await self.runtime(1, hold=4)
        await self.configure(3, commit=False)
        await self.step('native_partial_commit', fault=('u_cluster1.u_infra1.i_region_rsp_error', 1))
        await self.runtime(4, error=7, hold=4)
        await self.step('release_partial_fault', fault=('release',))
        await self.idle(8)
        assert self.last['o_fatal'] == self.mask and self.last['o_allocated'] == self.mask
        assert not self.last['o_running']
        assert self.local[0].last['o_status_tile_versions'] != 0
        assert all(s.last['o_cfg_execution_hold'] for s in self.local)
        await self.runtime(5, error=4)
        self.coverage.hit('partial_commit')
        await self.reset()

    async def body(self):
        import os
        if os.getenv('ARRAY_MODE') == 'concurrent':
            await self.concurrent_kernels()
        elif os.getenv('ARRAY_MODE') == 'partial_commit':
            await self.partial_commit()
        else:
            await self.workload()
            await self.isolation()
