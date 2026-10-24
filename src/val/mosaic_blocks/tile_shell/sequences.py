"""Directed lifecycle, Python body stub and reproducible multi-port traffic."""
import random
from pyuvm import ConfigDB, uvm_sequence
from tile_shell.transaction import INPUTS, TileShellItem
from tile_shell.model import crc32c, number

class TileShellSequence(uvm_sequence):
    def __init__(self, c):
        super().__init__('specification')
        self.c = c
        self.rng = random.Random(c.seed)
        self.index = self.tag = 0
        self.last = {}
        self.responses = {}
        self.runtime_responses = {}
        self.pending_validation = None
        self.validation_delay = 2
        self.validation_legal = 1
        self.coverage = None
        self.base = dict.fromkeys(INPUTS, 0)
        self.base.update(i_rstb=1, i_cfg_rstb=1, i_body_power_good=1,
            i_body_idle=1, i_body_safe_point=1, i_body_drain_done=1,
            i_body_validate_ready=1, i_cfg_response_ready=1, i_runtime_response_ready=1,
            i_power_response_ready=1, i_debug_response_ready=1, i_trace_ready=1)
        for group, ports in (('data', c.DATA_INPUT_PORTS), ('predicate', c.PREDICATE_INPUT_PORTS),
                             ('event', c.EVENT_INPUT_PORTS)):
            self.base[f'i_body_{group}_in_ready'] = (1 << ports) - 1
        for group, ports in (('data', c.DATA_OUTPUT_PORTS), ('predicate', c.PREDICATE_OUTPUT_PORTS),
                             ('event', c.EVENT_OUTPUT_PORTS)):
            self.base[f'i_{group}_out_ready'] = (1 << ports) - 1

    async def cycle(self, label='idle', *, core_edge=True, cfg_edge=None, fault=None, **ports):
        self.index += 1
        import os
        if os.getenv('TILE_SHELL_DEBUG_CYCLES'):
            print(self.index, label, flush=True)
        auto = dict(i_body_save_done=number(self.last.get('o_body_save', '0')) or 0,
                    i_body_restore_done=number(self.last.get('o_body_restore', '0')) or 0,
                    i_body_isolation_ack=number(self.last.get('o_body_isolate', '0')) or 0)
        if 'o_body_power_enable' in self.last:
            auto['i_body_power_good'] = number(self.last['o_body_power_enable'])
        if self.pending_validation:
            v = self.pending_validation
            v['delay'] -= int(core_edge)
            if v['delay'] <= 0:
                auto.update(i_body_validate_result_valid=1, i_body_validate_context_id=v['context'],
                    i_body_validate_context_version=v['version'], i_body_validate_legal=v['legal'],
                    i_body_validate_error_code=0 if v['legal'] else 9)
        item = TileShellItem(f'{label}_{self.index}', self.base | auto | ports,
            cfg_edge=(self.index % 3 != 0) if cfg_edge is None else cfg_edge,
            core_edge=core_edge, phase=self.index % 2, fault=fault)
        await self.start_item(item)
        await self.finish_item(item)
        self.last = item.post
        for domain, raw in item.edges.items():
            p = {n: number(v) for n, v in raw.items()}
            if domain == 'cfg' or domain == 'core' and not self.c.CONFIG_ASYNC:
                if p['o_cfg_response_valid'] and p['i_cfg_response_ready']:
                    self.responses[p['o_cfg_response_tag']] = p
            if domain == 'core':
                if p['o_runtime_response_valid'] and p['i_runtime_response_ready']:
                    self.runtime_responses[p['o_runtime_response_tag']] = p
                if p['i_body_validate_result_valid'] and p['o_body_validate_result_ready']:
                    self.pending_validation = None
                if p['o_body_validate_valid'] and p['i_body_validate_ready']:
                    assert self.pending_validation is None
                    self.pending_validation = dict(context=p['o_body_validate_context_id'],
                        version=p['o_body_validate_context_version'], legal=self.validation_legal,
                        delay=self.validation_delay)
        return item

    async def idle(self, count=1, **ports):
        for _ in range(count):
            await self.cycle(**ports)

    async def reset(self, cfg_only=False, fault=None):
        self.pending_validation = None
        await self.idle(4, i_rstb=int(cfg_only), i_cfg_rstb=0)
        if fault:
            await self.cycle(fault=fault, i_rstb=0, i_cfg_rstb=0)
        await self.idle(24)
        self.responses.clear()
        self.runtime_responses.clear()
        assert number(self.last['o_status_owner_id']) == 0
        assert number(self.last['o_status_context_valid']) == 0
        assert number(self.last['o_body_clock_enable']) == 0

    def next_tag(self):
        self.tag = (self.tag + 1) % (1 << self.c.RUNTIME_TAG_WIDTH)
        return self.tag

    async def cfg_response(self, tag):
        for _ in range(250):
            if tag in self.responses:
                return self.responses.pop(tag)
            await self.cycle()
        raise AssertionError(f'Configuration response timeout, tag {tag}')

    async def cfg(self, command, context=0, word=0, data=0, strobe=None, crc=0, *, owner=5,
                  tile=None, wait=True):
        tag = self.next_tag()
        p = dict(i_cfg_request_valid=1, i_cfg_request_command=command,
            i_cfg_request_tile_id=self.c.TILE_ID if tile is None else tile,
            i_cfg_request_owner_id=owner, i_cfg_request_context_id=context,
            i_cfg_request_word_index=word, i_cfg_request_write_data=data,
            i_cfg_request_write_strobe=(1 << (self.c.CONFIG_DATA_WIDTH // 8)) - 1 if strobe is None else strobe,
            i_cfg_request_expected_crc=crc, i_cfg_request_tag=tag)
        for _ in range(250):
            item = await self.cycle('config', **p)
            edge = item.edges.get('cfg' if self.c.CONFIG_ASYNC else 'core')
            if edge and number(edge['o_cfg_request_ready']):
                break
        else:
            raise AssertionError('Persistent configuration request starved')
        return await self.cfg_response(tag) if wait else tag

    async def runtime(self, command, context=0, owner=5, kernel=3, *, wait=True):
        tag = self.next_tag()
        for _ in range(250):
            item = await self.cycle('runtime', i_runtime_request_valid=1,
                i_runtime_request_command=command, i_runtime_request_owner_id=owner,
                i_runtime_request_kernel_id=kernel, i_runtime_request_context_id=context,
                i_runtime_request_tag=tag)
            if 'core' in item.edges and number(item.edges['core']['o_runtime_request_ready']):
                break
        else:
            raise AssertionError('Persistent runtime request starved')
        if not wait:
            return tag
        for _ in range(250):
            if tag in self.runtime_responses:
                return self.runtime_responses.pop(tag)
            await self.cycle()
        raise AssertionError('Runtime response timeout')

    async def clear(self):
        await self.idle(8)
        result = await self.runtime(7)
        assert number(result['o_runtime_response_error']) == 0
        await self.idle(2)
        assert number(self.last['o_status_error']) == 0

    async def query_crc(self, context=0):
        result = await self.cfg(5, context)
        return number(result['o_cfg_response_crc'])

    async def provision(self):
        assert number((await self.runtime(0))['o_runtime_response_error']) == 0
        await self.cfg(1, tile=self.c.TILE_ID ^ 1)
        await self.cfg(1, owner=4)
        await self.cfg(6)
        if self.c.CONTEXT_DEPTH < 1 << self.c.aliases['CI']:
            await self.cfg(1, self.c.CONTEXT_DEPTH)
        if self.c.CONFIG_WORD_COUNT < 1 << self.c.aliases['WI']:
            await self.cfg(1, word=self.c.CONFIG_WORD_COUNT)
        await self.cfg(2)
        for word in range(self.c.CONFIG_WORD_COUNT):
            await self.cfg(0, word=word, data=self.rng.getrandbits(self.c.CONFIG_DATA_WIDTH))
            await self.cfg(1, word=word)
        await self.cfg(0, data=0x5a & ((1 << self.c.CONFIG_DATA_WIDTH) - 1), strobe=1)
        await self.cfg(1)
        crc = await self.query_crc()
        if self.c.SUPPORT_CONTEXT_CHECKSUM:
            await self.cfg(2, crc=crc ^ 1)
        self.coverage.scenarios.add('crc')
        self.validation_legal = 0
        await self.cfg(2, crc=crc)
        self.validation_legal = 1
        self.validation_delay = 100
        tag = await self.cfg(2, crc=crc, wait=False)
        for _ in range(100):
            if self.pending_validation:
                break
            await self.cycle()
        assert self.pending_validation
        await self.cfg(0, data=0x96 & ((1 << self.c.CONFIG_DATA_WIDTH) - 1), strobe=1)
        self.pending_validation['delay'] = 0
        stale = await self.cfg_response(tag)
        assert number(stale['o_cfg_response_error_code']) == 10
        self.coverage.scenarios.add('stale_validation')
        self.validation_delay = 2
        await self.cfg(4)
        crc = await self.query_crc()
        result = await self.cfg(2, crc=crc)
        assert number(result['o_cfg_response_error']) == 0
        for context in range(1, self.c.CONTEXT_DEPTH):
            for word in range(self.c.CONFIG_WORD_COUNT):
                await self.cfg(0, context, word, self.rng.getrandbits(self.c.CONFIG_DATA_WIDTH))
                await self.cfg(1, context, word)
            crc = await self.query_crc(context)
            assert number((await self.cfg(2, context, crc=crc))['o_cfg_response_error']) == 0
        for context in range(self.c.CONTEXT_DEPTH):
            result = await self.cfg(3, context)
            assert number(result['o_cfg_response_error']) == 0
        result = await self.cfg(3, 0)
        assert number(result['o_cfg_response_error']) == 0
        await self.clear()
        result = await self.runtime(1, owner=4)
        assert number(result['o_runtime_response_error_code']) == 3
        await self.clear()
        self.coverage.scenarios.add('ownership')

    def traffic(self, value, *, all_ports=True):
        c = self.c
        ci = c.aliases['CI']
        context = number(self.last['o_status_active_context'])
        version = number(self.last['o_status_context_version'])
        p = {}
        for group, width, meta, ports, incoming in (
            ('data_in', c.DATA_WIDTH, c.DATA_METADATA_WIDTH, c.DATA_INPUT_PORTS, True),
            ('data_out', c.DATA_WIDTH, c.DATA_METADATA_WIDTH, c.DATA_OUTPUT_PORTS, False),
            ('predicate_in', c.PREDICATE_WIDTH, c.PREDICATE_METADATA_WIDTH, c.PREDICATE_INPUT_PORTS, True),
            ('predicate_out', c.PREDICATE_WIDTH, c.PREDICATE_METADATA_WIDTH, c.PREDICATE_OUTPUT_PORTS, False),
            ('event_in', c.EVENT_WIDTH, 0, c.EVENT_INPUT_PORTS, True),
            ('event_out', c.EVENT_WIDTH, 0, c.EVENT_OUTPUT_PORTS, False)):
            prefix = 'i_' + ('' if incoming else 'body_') + group
            p[prefix + '_valid'] = (1 << ports) - 1 if all_ports else 1
            payloads = [(value + port) & ((1 << width) - 1) for port in range(ports)]
            if group.startswith('event'):
                payloads = [7 | context << 3 | 3 << (ci + 3) for _ in range(ports)]
            p[prefix + '_payload'] = sum(x << (port * width) for port, x in enumerate(payloads))
            if meta:
                metadata = context | (version << ci if group.startswith('data') else 0)
                p[prefix + '_metadata'] = sum(metadata << (port * meta) for port in range(ports))
        return p

    async def execute(self):
        await self.idle(2, i_body_wakeup_required=1)
        result = await self.runtime(1)
        assert number(result['o_runtime_response_error']) == 0
        await self.idle(8)
        for reasons, state in ((1, 4), (2, 5), (4, 6), (8, 7), (15, 5)):
            await self.cycle('stall_reason', i_body_stall_reasons=reasons)
            assert number(self.last['o_status_stall_reasons']) & reasons == reasons
            # Mixed scheduled profiles can additionally expose an output stall.
            observed = number(self.last['o_status_execution_state'])
            assert observed == state or observed == 5
        await self.idle(3)
        self.coverage.scenarios.add('stall_reasons')
        # Every port moves independently and simultaneously, including predicates
        # with a zero value. No datapath operation is inferred by the shell.
        for i in range(12):
            await self.cycle('simultaneous', **self.traffic(i))
        await self.idle(8)
        bad = self.traffic(1, all_ports=False)
        bad['i_data_in_metadata'] ^= 1 << self.c.aliases['CI']
        await self.cycle('bad_metadata', **bad)
        await self.idle(8)
        self.coverage.scenarios.add('metadata')
        await self.cycle('safe_delay', i_body_safe_point=0)
        self.base['i_body_safe_point'] = 0
        tag = await self.runtime(2, wait=False)
        await self.idle(4)
        assert number(self.last['o_body_suspend_request']) == 1
        self.base['i_body_safe_point'] = 1
        for _ in range(30):
            if tag in self.runtime_responses:
                self.runtime_responses.pop(tag)
                break
            await self.cycle()
        assert number(self.last['o_status_execution_state']) == 9
        await self.idle(3)
        assert number((await self.runtime(3))['o_runtime_response_error']) == 0
        await self.idle(6)
        # Scheduled ports deliberately expose their reserved-cycle violations;
        # recoverable reporting cannot silently admit malformed records.
        for _ in range(4):
            await self.cycle('output_stall', i_data_out_ready=0, **self.traffic(9))
        await self.idle(10)
        # End-of-kernel indication cannot overtake a held external output.
        self.base['i_data_out_ready'] = 0
        sent = False
        for _ in range(12):
            item = await self.cycle('completion_fill', **self.traffic(0x55))
            if number(item.edges['core']['o_body_data_out_ready']):
                sent = True
                break
        if self.c.OUTPUT_BUFFER_DEPTH == 0:
            sent = False
        await self.cycle('completion', i_body_completed=1)
        for _ in range(4):
            await self.cycle('completion_wait')
            assert number(self.last['o_status_execution_state']) != 11 or not sent
        self.base['i_data_out_ready'] = (1 << self.c.DATA_OUTPUT_PORTS) - 1
        for _ in range(50):
            await self.cycle()
            if number(self.last['o_status_execution_state']) == 11:
                break
        assert number(self.last['o_status_execution_state']) == 11
        self.coverage.scenarios.add('completion_ordering')
        await self.clear()
        await self.idle(3, i_body_wakeup_required=1)
        assert number((await self.runtime(1))['o_runtime_response_error']) == 0
        await self.idle(6)
        self.base['i_body_drain_done'] = 0
        tag = await self.runtime(4, wait=False)
        await self.cycle('drained_completion', i_body_completed=1)
        await self.idle(3)
        self.base['i_body_drain_done'] = 1
        for _ in range(50):
            if tag in self.runtime_responses:
                response = self.runtime_responses.pop(tag)
                assert number(response['o_runtime_response_state']) == 11
                break
            await self.cycle()
        else:
            raise AssertionError('Drain did not commit completed execution')
        await self.clear()
        await self.runtime(1)
        await self.idle(6)
        await self.runtime(4)
        await self.clear()
        await self.idle(2, i_body_wakeup_required=1)
        await self.runtime(1)
        await self.idle(6)
        pending = self.traffic(0)
        for i in range(self.c.random_cycles):
            fresh = self.traffic(i)
            for key in tuple(pending):
                if key.endswith('_valid') and pending[key] == 0:
                    prefix = key.removesuffix('_valid')
                    for field in fresh:
                        if field.startswith(prefix + '_'):
                            pending[field] = fresh[field]
            ready = self.rng.getrandbits(self.c.DATA_OUTPUT_PORTS)
            item = await self.cycle('random', i_data_out_ready=ready, i_trace_ready=int(i % 19 >= 5), **pending)
            p = {n: number(v) for n, v in item.edges['core'].items()}
            for key in tuple(pending):
                if key.endswith('_valid'):
                    ready_name = 'o_' + key[2:].removesuffix('_valid') + '_ready'
                    pending[key] &= ~p[ready_name]
        await self.runtime(5)
        await self.idle(10)
        self.coverage.scenarios.add('terminate')

    async def debug_and_power(self):
        for address in (0, 1, 2, 4, 0x40, 0xff):
            for _ in range(20):
                item = await self.cycle('debug', i_debug_request_valid=1,
                    i_debug_request_address=address, i_debug_request_owner_id=5)
                if number(item.edges['core']['o_debug_request_ready']):
                    break
            await self.idle(2)
        # Exercise response hold independently of function execution.
        self.base['i_debug_response_ready'] = 0
        await self.cycle('debug_hold', i_debug_request_valid=1, i_debug_request_address=1)
        await self.idle(4)
        self.base['i_debug_response_ready'] = 1
        await self.idle(3)
        await self.clear()
        states = [2, 0]
        if self.c.SUPPORT_RETENTION:
            states += [3, 0]
        if self.c.SUPPORT_POWER_OFF:
            states += [4, 0]
        for state in states:
            for _ in range(100):
                item = await self.cycle('power_request', i_power_request_valid=1,
                                        i_power_request_state=state)
                if number(item.edges['core']['o_power_request_ready']):
                    break
            for _ in range(150):
                item = await self.cycle('power_wait')
                p = item.edges['core']
                if number(p['o_power_response_valid']):
                    assert number(p['o_power_response_error']) == 0, (state, p)
                    break
            else:
                raise AssertionError('Power response timeout')
            await self.idle(5)
            if state in (2, 3, 4):
                payload = 1 | (3 << (self.c.aliases['CI'] + 3))
                for _ in range(100):
                    item = await self.cycle('gated_wakeup', i_event_in_valid=1,
                                            i_event_in_payload=payload)
                    if number(item.edges['core']['o_event_in_ready']) & 1:
                        break
                for _ in range(100):
                    item = await self.cycle('wakeup_delivery')
                    if number(item.edges['core']['o_body_event_in_valid']) & 1:
                        break
                else:
                    raise AssertionError('Gated wakeup event was lost')
                self.coverage.scenarios.add('gated_wakeup')
        self.coverage.scenarios.add('power_sequence')

    async def unknowns_and_faults(self):
        c = self.c
        for state in 'xz':
            for name, values in (
                ('i_runtime_request_owner_id', dict(i_runtime_request_valid=1)),
                ('i_debug_request_address', dict(i_debug_request_valid=1)),
                ('i_power_request_state', dict(i_power_request_valid=1)),
                ('i_cfg_request_owner_id', dict(i_cfg_request_valid=1)),
                ('i_rstb', {}), ('i_body_safe_point', {}), ('i_data_in_valid', {})):
                await self.cycle('unknown', **values, **{name: state * c.widths[name]})
                if name == 'i_rstb':
                    assert number(self.last['o_status_owner_id']) == 5
        self.coverage.scenarios.add('unknowns')
        await self.clear()
        await self.runtime(1)
        await self.idle(6)
        self.base['i_event_out_ready'] = 0
        await self.cycle('first_complete', i_body_completed=1)
        await self.cycle('complete_low')
        await self.cycle('duplicate_complete', i_body_completed=1)
        await self.idle(2)
        assert number(self.last['o_status_fatal_error']) == 1
        self.base['i_event_out_ready'] = (1 << c.EVENT_OUTPUT_PORTS) - 1
        await self.reset()
        self.coverage.scenarios.add('duplicate_completion')
        for kind, protection in (('control', c.CONTROL_PROTECTION),
                                 ('state_validity', c.CONTROL_PROTECTION),
                                 ('context', c.CONTEXT_PROTECTION)):
            if not protection:
                continue
            for mask in ((4, 3) if protection == 2 else ((1,) if kind == 'state_validity' else (4,))):
                if kind == 'context':
                    await self.cfg(0, data=0x5a)
                await self.cycle('protection_fault', fault=(kind, 0, mask))
                await self.idle(3)
                fatal = protection == 1 or mask.bit_count() == 2
                assert number(self.last['o_status_fatal_error']) == int(fatal)
                await self.reset(fault=('release',))
            self.coverage.scenarios.add('protection')

    async def reset_phases(self):
        for word in range(self.c.CONFIG_WORD_COUNT):
            await self.cfg(0, word=word, data=word + 1)
        crc = await self.query_crc()
        self.base['i_body_validate_ready'] = 0
        validation_tag = await self.cfg(2, crc=crc, wait=False)
        for _ in range(100):
            await self.cycle('validation_hold')
            if number(self.last['o_body_validate_valid']):
                break
        snapshot = {k: v for k, v in self.last.items() if k.startswith('o_body_validate_')}
        for _ in range(4):
            await self.cycle('validation_hold')
            assert all(self.last[k] == v for k, v in snapshot.items())
        await self.cycle('cancel_validation', i_body_fatal_error=1)
        cancelled = await self.cfg_response(validation_tag)
        assert number(cancelled['o_cfg_response_error_code']) == 17
        self.coverage.scenarios.add('validation_cancel')
        await self.reset(cfg_only=bool(self.c.CONFIG_ASYNC))
        self.base['i_body_validate_ready'] = 1
        for word in range(self.c.CONFIG_WORD_COUNT):
            await self.cfg(0, word=word, data=word + 3)
        await self.runtime(0)
        crc = await self.query_crc()
        await self.cfg(2, crc=crc)
        await self.cfg(3)
        await self.runtime(1)
        await self.idle(8)
        snapshot = self.last.copy()
        for _ in range(3):
            await self.cycle('clockless', core_edge=False, cfg_edge=False)
            assert all(self.last[k] == snapshot[k] for k in self.last if k.startswith('o_'))
        self.base['i_body_safe_point'] = 0
        await self.runtime(2, wait=False)
        for _ in range(4):
            await self.cycle('pending_reset', i_data_out_ready=0, **self.traffic(7))
        await self.reset()
        self.base['i_body_safe_point'] = 1
        self.coverage.scenarios.add('reset_phases')
        await self.idle(12)
        for word in range(self.c.CONFIG_WORD_COUNT):
            await self.cfg(0, word=word, data=word + 5)
        await self.runtime(0)
        crc = await self.query_crc()
        await self.cfg(2, crc=crc)
        await self.cfg(3)
        await self.cycle('commit_fault', fault=('validity', 0, 1))
        assert number(self.last['o_status_fatal_error']) == 1
        assert number(self.last['o_body_context_active']) == 0
        await self.reset(fault=('release',))
        self.coverage.scenarios.add('committed_validity')

    async def body(self):
        await self.reset()
        await self.provision()
        await self.execute()
        for address in range(0x40, 0x46):
            await self.cycle('counter_read', i_debug_request_valid=1,
                i_debug_request_address=address, i_debug_request_owner_id=5)
            await self.idle(2)
        await self.runtime(6)
        await self.idle(3)
        assert number(self.last['o_status_context_valid']) == 0
        await self.runtime(0)
        crc = await self.query_crc()
        await self.cfg(2, crc=crc)
        await self.cfg(3)
        await self.debug_and_power()
        await self.unknowns_and_faults()
        if number(self.last['o_status_owner_id']):
            await self.runtime(6)
        await self.cycle('power_loss', i_body_power_good=0, i_body_isolation_ack=0)
        await self.idle(3)
        assert number(self.last['o_status_fatal_error']) == 1
        await self.reset()
        if self.c.CONTEXT_VERSION_WIDTH <= 4:
            for value in range(1 << self.c.CONTEXT_VERSION_WIDTH):
                result = await self.cfg(0, data=value)
            assert number(result['o_cfg_response_error_code']) == 18
            self.coverage.scenarios.add('version_wrap')
            await self.reset()
        # An accepted asynchronous request before either reset cannot reappear.
        await self.cfg(5, wait=False)
        await self.reset(cfg_only=bool(self.c.CONFIG_ASYNC))
        await self.idle(15)
        assert number(self.last['o_cfg_response_valid']) == 0
        self.coverage.scenarios.add('reset_epoch')
        await self.reset_phases()
