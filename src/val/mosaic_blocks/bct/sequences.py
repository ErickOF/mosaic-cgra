"""External shell programming and directed/random scalar tile mappings."""
from bct.model import pack, sources
from bct.transaction import BctItem, INPUTS
from bct.scoreboard import number
from tile_shell.sequences import TileShellSequence


class BctSequence(TileShellSequence):
    def __init__(self, config):
        super().__init__(config)
        self.base = {n: self.base.get(n, 0) for n in INPUTS}
        self.base.update(i_rstb=1, i_cfg_rstb=1, i_body_power_good=1)
        self.active = None

    async def cycle(self, label='idle', *, core_edge=True, cfg_edge=None, fault=None, **ports):
        self.index += 1
        import os
        if os.getenv('BCT_DEBUG_CYCLES'):
            print(self.index, label, flush=True)
        auto = dict(i_body_save_done=number(self.last.get('o_body_save', '0')) or 0,
                    i_body_restore_done=number(self.last.get('o_body_restore', '0')) or 0,
                    i_body_isolation_ack=number(self.last.get('o_body_isolate', '0')) or 0)
        if 'o_body_power_enable' in self.last:
            auto['i_body_power_good'] = number(self.last['o_body_power_enable'])
        item = BctItem(f'{label}_{self.index}', self.base | auto | ports,
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
            if domain == 'core' and p['o_runtime_response_valid'] and p['i_runtime_response_ready']:
                self.runtime_responses[p['o_runtime_response_tag']] = p
        return item

    async def reset(self, cfg_only=False, fault=None):
        self.base['i_data_in_valid'] = 0
        self.base['i_predicate_in_valid'] = 0
        await super().reset(cfg_only, fault)
        if self.active:
            self.active['contexts'].clear()

    def context(self, **changes):
        s = sources(self.c.parameters)
        if 'immediates' in changes:
            bits = self.c.DATA_WIDTH * self.c.IMMEDIATE_COUNT
            changes['immediates'] &= (1 << bits) - 1
        return dict(schema=1, source_a=0, source_b=s['one'], source_c=s['zero'],
            output_mask=1, iterations=4, terminal=1, monitor=1) | changes

    async def provision(self, context, cid=0, *, activate=True, error=False):
        image = pack(self.c.parameters, context)
        self.active['contexts'][cid] = image
        for word in range(self.c.CONFIG_WORD_COUNT):
            response = await self.cfg(0, cid, word, (image >> (word * self.c.CONFIG_DATA_WIDTH)) &
                                      ((1 << self.c.CONFIG_DATA_WIDTH) - 1))
            assert not number(response['o_cfg_response_error'])
        from tile_shell.model import crc32c
        crc = crc32c(image.to_bytes(self.c.CONFIG_DATA_WIDTH * self.c.CONFIG_WORD_COUNT // 8, 'little'))
        response = await self.cfg(2, cid, crc=crc)
        assert bool(number(response['o_cfg_response_error'])) == error, response
        if error:
            self.coverage.hit('validation_rejection')
            return response
        if activate:
            response = await self.cfg(3, cid)
            assert not number(response['o_cfg_response_error']), response
            await self.idle(4)
        return response

    async def setup_case(self, context):
        await self.reset()
        response = await self.runtime(0)
        assert not number(response['o_runtime_response_error'])
        await self.provision(context)
        response = await self.runtime(1)
        assert not number(response['o_runtime_response_error']), response

    async def traffic(self, context, values, *, predicates=None, completion=True, limit=500, expected_error=None):
        c = self.c
        use_a = context.get('fu', 0) != 0 or context.get('opcode', 0) != 17 and (context.get('opcode', 0) != 15 or context.get('select_condition', 0))
        use_b = context.get('fu', 0) != 0 or context.get('opcode', 0) not in (5, 16) and (context.get('opcode', 0) != 15 or not context.get('select_condition', 0))
        indices = [context['source_a']] if use_a else []
        if use_b: indices.append(context['source_b'])
        if context.get('fu', 0) == 2: indices.append(context['source_c'])
        ports = sorted(set(n for n in indices if n < c.DATA_INPUT_PORTS))
        sent = {n: 0 for n in ports}
        pred_sent = 0
        count = len(values)
        version = number(self.last['o_status_context_version'])
        cid = number(self.last['o_status_active_context'])
        metadata = (version << c.aliases['CI']) | cid
        for tick in range(limit):
            valid = payload = metas = 0
            for port in ports:
                if sent[port] < count:
                    valid |= 1 << port
                    payload |= (values[sent[port]][port] & ((1 << c.DATA_WIDTH) - 1)) \
                        << (port * c.DATA_WIDTH)
                    metas |= metadata << (port * c.DATA_METADATA_WIDTH)
            if self.c.parameters['INPUT_ELASTIC_MASK'] != (1 << c.DATA_INPUT_PORTS) - 1 and tick % 40 != 8:
                valid = 0
            pred_valid = int(context.get('predicate_mode', 0) == 1 and pred_sent < count)
            pred = predicates[pred_sent] if pred_valid and predicates else 1
            ready = (1 << c.DATA_OUTPUT_PORTS) - 1 if tick % 13 >= 4 else 0
            item = await self.cycle('mapped_traffic', i_data_in_valid=valid,
                i_data_in_payload=payload, i_data_in_metadata=metas,
                i_predicate_in_valid=pred_valid, i_predicate_in_payload=pred,
                i_predicate_in_metadata=cid, i_data_out_ready=ready)
            edge = item.edges.get('core')
            if edge:
                p = {n: number(v) for n, v in edge.items()}
                for port in ports:
                    sent[port] += int(bool(valid >> port & p['o_data_in_ready'] >> port & 1))
                pred_sent += int(bool(pred_valid and p['o_predicate_in_ready']))
            if number(self.last['o_status_error']):
                assert expected_error is not None and number(self.last['o_status_error_code']) == expected_error, ('unexpected error', number(self.last['o_status_error_code']), number(self.last['o_status_execution_state']))
                return
            if completion and number(self.last['o_status_execution_state']) == 11:
                assert all(n == count for n in sent.values())
                self.coverage.hit('ordered_completion')
                return
            if not completion and all(n == count for n in sent.values()):
                await self.idle(30)
                return
        raise AssertionError(f'Traffic failed to finish: {context}, sent={sent}, status={self.last}')

    async def debug(self, address, *, owner=5, expected=None, error=False):
        for _ in range(100):
            item = await self.cycle('debug', i_debug_request_valid=1,
                i_debug_request_owner_id=owner, i_debug_request_address=address,
                i_debug_response_ready=0)
            if number(item.edges['core']['o_debug_request_ready']):
                break
        else:
            raise AssertionError('Debug request timed out')
        for _ in range(50):
            await self.cycle('debug_wait', i_debug_response_ready=0)
            if number(self.last['o_debug_response_valid']):
                break
        else:
            raise AssertionError('Debug response timed out')
        value = number(self.last['o_debug_response_read_data'])
        assert bool(number(self.last['o_debug_response_error'])) == error
        if expected is not None:
            assert value == expected, ('counter', address, value, expected)
        await self.idle(3, i_debug_response_ready=0)
        await self.cycle('unknown_debug_ready', i_debug_response_ready='x')
        assert number(self.last['o_debug_response_valid']) == 1
        assert number(self.last['o_debug_response_read_data']) == value
        await self.cycle('debug_accept')
        return value

    async def power(self, state):
        for _ in range(100):
            item = await self.cycle('power_request', i_power_request_valid=1,
                                    i_power_request_state=state)
            if number(item.edges['core']['o_power_request_ready']):
                break
        else:
            raise AssertionError('Power request timed out')
        for _ in range(160):
            item = await self.cycle('power_wait')
            response = item.edges['core']
            if number(response['o_power_response_valid']):
                assert not number(response['o_power_response_error']), (state, response)
                break
        else:
            raise AssertionError(f'Power transition {state} timed out')
        await self.idle(6)

    async def body(self):
        c, s = self.c, sources(self.c.parameters)
        mask = (1 << c.DATA_WIDTH) - 1
        # An uncongested constant mapping makes the exact latency observable
        # even in single-context and feature-disabled profiles.
        constant = self.context(source_a=s['immediate'], source_b=s['one'],
                                immediates=37, iterations=1)
        await self.setup_case(constant)
        await self.idle(20)
        await self.traffic(constant, [[0] * c.DATA_INPUT_PORTS])
        # Every ALU operation, every external input and output, and fanout.
        for opcode in range(20 if c.SUPPORT_MINMAX else 18):
            port = opcode % c.DATA_INPUT_PORTS
            second = (port + 1) % c.DATA_INPUT_PORTS
            context = self.context(opcode=opcode, source_a=port, source_b=second,
                signed_a=opcode % 2, output_mask=1 << (opcode % c.DATA_OUTPUT_PORTS),
                write_rf=1, rf_write=opcode % c.RF_DEPTH, write_predicate=1,
                predicate_write=opcode % c.PREDICATE_DEPTH,
                predicate_output=int(9 <= opcode <= 14),
                write_bypass=int(c.BYPASS_PROFILE != 0 or c.FU_PROFILE == 2))
            await self.setup_case(context)
            values = [[(mask, 1, mask // 2, 0)[k] if p == port else (1, 0, c.DATA_WIDTH, mask)[k]
                       for p in range(c.DATA_INPUT_PORTS)] for k in range(4)]
            await self.traffic(context, values)
        context = self.context(opcode=0, source_a=0, source_b=s['one'],
            output_mask=(1 << c.DATA_OUTPUT_PORTS) - 1, write_rf=1,
            write_bypass=int(c.BYPASS_PROFILE != 0 or c.FU_PROFILE == 2))
        await self.setup_case(context)
        await self.traffic(context, [[n] * c.DATA_INPUT_PORTS for n in (1, 2, 3, 4)])
        self.coverage.hit('atomic_destinations')
        await self.debug(0x80, expected=4)
        await self.debug(0x81, expected=4)
        await self.debug(0x80, owner=6, error=True, expected=0)
        self.coverage.hit('counters')
        for condition in (0, 1):
            ctx = self.context(opcode=15, source_a=0, source_b=s['immediate'],
                               immediates=97, select_condition=condition)
            await self.setup_case(ctx)
            await self.traffic(ctx, [[n] * c.DATA_INPUT_PORTS for n in (2, 3, 5, 7)])
        if c.SUPPORT_SATURATION:
            for opcode in (0, 1):
                for signed_mode in (0, 1):
                    ctx = self.context(opcode=opcode, source_a=0, source_b=s['immediate'],
                        immediates=1, signed_a=signed_mode, saturate=1,
                        write_predicate=1, predicate_output=1, flag_select=6)
                    await self.setup_case(ctx)
                    await self.traffic(ctx, [[n] * c.DATA_INPUT_PORTS for n in
                        (0, mask, (1 << (c.DATA_WIDTH - 1)) - 1, 1 << (c.DATA_WIDTH - 1))])
            self.coverage.hit('saturation')
        # Explicit false modes consume tokens while suppressing local state.
        for mode, token in ((3, 0), (1, c.SUPPORT_PREDICATED_TOKEN)):
            context = self.context(predicate_mode=mode, false_token=token, write_rf=1,
                output_mask=(1 << c.DATA_OUTPUT_PORTS) - 1)
            await self.setup_case(context)
            await self.traffic(context, [[n] * c.DATA_INPUT_PORTS for n in range(4)],
                               predicates=[0, 1, 0, 1])
        # Reuse preserved architectural state across a safe context activation.
        if c.CONTEXT_DEPTH > 1:
            context = self.context(opcode=9, source_b=s['zero'], write_rf=1, rf_write=0,
                write_predicate=1, predicate_write=0, iterations=1,
                write_accumulator=int(c.FU_PROFILE == 2),
                write_bypass=int(c.BYPASS_PROFILE != 0 or c.FU_PROFILE == 2))
            await self.setup_case(context)
            await self.traffic(context, [[0] * c.DATA_INPUT_PORTS])
            candidates = [s['rf'], *range(s['immediate'], s['zero']), s['zero'], s['one']]
            if c.BYPASS_PROFILE != 0 or c.FU_PROFILE == 2: candidates.extend((s['bypass'], s['previous']))
            if c.FU_PROFILE == 2: candidates.append(s['accumulator'])
            if c.BYPASS_PROFILE == 2: candidates.append(s['predicate'])
            for index, source in enumerate(candidates):
                ctx = self.context(opcode=0, source_a=source, source_b=s['one'],
                    predicate_mode=2, predicate_read=0, immediates=19, iterations=2)
                cid = 1 if index % 2 == 0 else 0
                await self.provision(ctx, cid)
                response = await self.runtime(1, cid)
                assert not number(response['o_runtime_response_error'])
                await self.traffic(ctx, [[0] * c.DATA_INPUT_PORTS] * 2)
            self.coverage.hit('source_classes')
        else:
            self.coverage.hit('source_classes')
            # The single-context profile has no preserved predicate bootstrap;
            # invalid local predicates correctly stall, and termination cancels it.
            ctx = self.context(predicate_mode=2)
            await self.setup_case(ctx)
            await self.idle(10)
            assert number(self.last['o_status_execution_state']) != 11
            self.coverage.hit('predicate_2')
        if c.FU_PROFILE:
            for fu in range(1, c.FU_PROFILE + 1):
                for sa, sb in ((0, 0), (1, 1), (1, 0), (0, 1)):
                    ctx = self.context(fu=fu, source_a=0,
                        source_b=1 if c.DATA_INPUT_PORTS > 1 else s['immediate'],
                        source_c=s['one'] if fu == 2 else s['zero'],
                        signed_a=sa, signed_b=sb, immediates=3,
                        write_accumulator=int(fu == 2),
                        saturate=int(fu == 2 and c.SUPPORT_SATURATION))
                    await self.setup_case(ctx)
                    narrow = c.MULTIPLY_OPERAND_WIDTH
                    av = mask if sa else (1 << narrow) - 1
                    bv = mask if sb else min(3, (1 << narrow) - 1)
                    vals = [[av if p == 0 else bv for p in range(c.DATA_INPUT_PORTS)]] * 4
                    await self.traffic(ctx, vals)
                    assert not number(self.last['o_status_error']), self.last
            self.coverage.hit('signed_multiply')
            if c.REQUIRE_CANONICAL_NARROW:
                ctx = self.context(fu=1, source_b=s['one'], iterations=1)
                await self.setup_case(ctx)
                await self.traffic(ctx, [[1 << c.MULTIPLY_OPERAND_WIDTH] * c.DATA_INPUT_PORTS], expected_error=66)
                assert number(self.last['o_status_error_code']) == 66, self.last
                self.coverage.hit('canonical_rejection')
            else:
                self.coverage.hit('canonical_rejection')
        if c.FU_PROFILE == 2:
            ctx = self.context(fu=2, source_a=0, source_b=s['one'],
                source_c=s['accumulator'], clear_accumulator=1, write_accumulator=1)
            await self.setup_case(ctx)
            await self.traffic(ctx, [[n] * c.DATA_INPUT_PORTS for n in (1, 2, 3, 4)])
            self.coverage.hit('accumulator_feedback')
            if c.CONTEXT_DEPTH > 1:
                incompatible = self.context(fu=2, source_a=0, source_b=s['one'],
                    source_c=s['accumulator'], signed_a=1, required_accumulator=1)
                await self.provision(incompatible, 1, activate=False, error=True)
                self.coverage.hit('accumulator_type_rejection')
        if c.DATA_WIDTH > 256 and c.CONTEXT_DEPTH > 1:
            writer = self.context(opcode=16, write_rf=1, iterations=1)
            await self.setup_case(writer)
            await self.traffic(writer, [[1 << (c.DATA_WIDTH - 1)] * c.DATA_INPUT_PORTS])
            reader = self.context(opcode=0, source_a=s['rf'], source_b=s['zero'], iterations=1)
            await self.provision(reader, 1)
            await self.runtime(1, 1)
            await self.traffic(reader, [[0] * c.DATA_INPUT_PORTS])
            self.coverage.hit('striped_rf')
        # Body validation rejects disabled FUs, bad resources and reserved fields.
        for changes in (dict(schema=2), dict(fu=3), dict(required_rf=1, invalidate_rf=1), dict(rf_read_a=c.RF_DEPTH)
                        if c.RF_DEPTH & (c.RF_DEPTH - 1) else dict(flag_select=7, schema=0)):
            await self.reset()
            await self.runtime(0)
            await self.provision(self.context(**changes), activate=False, error=True)
        await self.reset()
        await self.runtime(0)
        response = await self.cfg(5, owner=6)
        assert number(response['o_cfg_response_error'])
        self.coverage.hit('ownership_rejection')
        # RDU priming at the largest generated capacity, with one required input.
        if c.SYNC_PROFILE == 1:
            delay = c.RDU_TOTAL_DELAY_ENTRIES // c.DATA_INPUT_PORTS + int(c.RDU_TOTAL_DELAY_ENTRIES % c.DATA_INPUT_PORTS != 0)
            ctx = self.context(opcode=16, delays=delay)
            await self.setup_case(ctx)
            await self.traffic(ctx, [[n] * c.DATA_INPUT_PORTS for n in range(4)])
            self.coverage.hit('rdu_delay')
        # Repeated spatial mapping with stable producer and independent output stalls.
        ctx = self.context(opcode=0, source_b=s['one'], iterations=0, terminal=0,
                           output_mask=(1 << c.DATA_OUTPUT_PORTS) - 1)
        await self.setup_case(ctx)
        metadata = number(self.last['o_status_context_version']) << c.aliases['CI']
        pending = None
        for random_tick in range(c.random_cycles):
            if pending is None and self.rng.random() < .8:
                pending = self.rng.getrandbits(c.DATA_WIDTH)
            scheduled = self.c.parameters['INPUT_ELASTIC_MASK'] != (1 << c.DATA_INPUT_PORTS) - 1
            offered = pending is not None and (not scheduled or random_tick % 40 == 8)
            item = await self.cycle('random', i_data_in_valid=int(offered),
                i_data_in_payload=pending or 0, i_data_in_metadata=metadata,
                i_data_out_ready=self.rng.getrandbits(c.DATA_OUTPUT_PORTS))
            if offered and number(item.edges['core']['o_data_in_ready']) & 1:
                pending = None
        self.coverage.random_cycles = c.random_cycles
        await self.idle(2)
        response = await self.runtime(2)
        assert not number(response['o_runtime_response_error']), response
        response = await self.runtime(3)
        assert not number(response['o_runtime_response_error']), response
        self.coverage.hit('suspend_resume')
        response = await self.runtime(5)
        assert not number(response['o_runtime_response_error'])
        self.coverage.hit('terminate')
        # Unknown reset pauses a live operation without impersonating reset.
        await self.setup_case(ctx)
        metadata = number(self.last['o_status_context_version']) << c.aliases['CI']
        await self.cycle('before_unknown_reset', i_data_in_valid=1, i_data_in_payload=13 & mask,
            i_data_in_metadata=metadata, i_data_out_ready=0)
        await self.idle(2, i_data_out_ready=0)
        await self.cycle('unknown_reset', i_rstb='x', i_data_out_ready=0)
        assert number(self.last['o_data_in_ready']) == 0
        assert number(self.last['o_data_out_valid']) == 0
        await self.idle(25)
        assert number(self.last['o_status_owner_id']) == 5
        assert not number(self.last['o_status_fatal_error'])
        self.coverage.hit('unknown_reset')
        await self.reset()
        # Pending owned transport is explicitly discarded by reset.
        await self.setup_case(ctx)
        metadata = number(self.last['o_status_context_version']) << c.aliases['CI']
        for pending_tick in range(6):
            await self.cycle('pending_reset', i_data_in_valid=int(pending_tick == 0),
                i_data_in_payload=11 & mask,
                i_data_in_metadata=metadata, i_data_out_ready=0)
        await self.cycle('clock_stopped', core_edge=False, i_data_out_ready=0)
        await self.reset()
        self.coverage.hit('reset_pending')
        if c.SUPPORT_SPATIAL_TEMPORAL and c.CONTEXT_DEPTH > 1:
            ctx0 = self.context(source_a=s['immediate'], source_b=s['one'],
                immediates=5, iterations=3, advance_mode=1, next_context=1, terminal=0)
            ctx1 = self.context(source_a=s['immediate'], source_b=s['one'],
                immediates=7, iterations=2)
            await self.runtime(0)
            await self.provision(ctx1, 1, activate=False)
            await self.provision(ctx0)
            response = await self.runtime(1)
            assert not number(response['o_runtime_response_error'])
            for _ in range(200):
                await self.cycle('temporal')
                if number(self.last['o_status_execution_state']) == 11: break
            else: raise AssertionError('Temporal contexts did not complete')
            assert number(self.last['o_status_active_context']) == 1
            self.coverage.hit('temporal')
        if c.SUPPORT_SPATIAL_TEMPORAL and c.CONTEXT_DEPTH > 1:
            for mode in (2, 3):
                await self.reset()
                await self.runtime(0)
                first = self.context(opcode=9, source_a=s['one'], source_b=s['one'],
                    iterations=1, terminal=0, advance_mode=mode, next_context=1)
                last = self.context(source_a=s['immediate'], immediates=31, iterations=1)
                await self.provision(last, 1, activate=False)
                await self.provision(first)
                response = await self.runtime(1)
                assert not number(response['o_runtime_response_error'])
                event_sent = mode != 3
                for _ in range(160):
                    event = 7 | (3 << (c.aliases['CI'] + 3))
                    item = await self.cycle('context_condition', i_event_in_valid=int(not event_sent),
                        i_event_in_payload=event)
                    if number(item.edges['core']['o_event_in_ready']) & 1:
                        event_sent = True
                    if number(self.last['o_status_execution_state']) == 11: break
                else: raise AssertionError(f'Context advance mode {mode} did not complete')
                assert number(self.last['o_status_active_context']) == 1
            self.coverage.hit('conditional_temporal')
        if c.SUPPORT_RETENTION:
            ctx = self.context(opcode=0, source_b=s['one'], write_rf=1, iterations=1)
            await self.setup_case(ctx)
            await self.traffic(ctx, [[7] * c.DATA_INPUT_PORTS])
            await self.power(3)
            assert number(self.last['o_status_power_state']) == 3
            await self.power(0)
            reader = self.context(source_a=s['rf'], source_b=s['one'], iterations=2)
            await self.provision(reader, 1)
            response = await self.runtime(1, 1)
            assert not number(response['o_runtime_response_error'])
            await self.traffic(reader, [[0] * c.DATA_INPUT_PORTS] * 2)
            self.coverage.hit('retention')
            await self.power(4)
            assert number(self.last['o_status_power_state']) == 4
            await self.power(0)
            self.coverage.hit('power_off')
        # A corrupted active image must fail closed even after validation.
        active = self.context(source_a=s['immediate'], immediates=8, iterations=0, terminal=0)
        await self.setup_case(active)
        await self.idle(12)
        await self.cycle('runtime_context_fault', fault=('context', 0, 1))
        await self.idle(8)
        assert number(self.last['o_status_error_code']) == 64
        self.coverage.hit('runtime_context_rejection')
        await self.reset(fault=('release', 0, 0))
        # Invalid RF state is a static source error or an elastic wait.
        ctx = self.context(source_a=s['rf'], source_b=s['one'])
        await self.setup_case(ctx)
        await self.idle(12)
        if c.SYNC_PROFILE == 2:
            assert not number(self.last['o_status_error'])
            assert not number(self.last['o_data_out_valid'])
        else:
            assert number(self.last['o_status_error_code']) == 65
        self.coverage.hit('invalid_local_source')
        if c.CONTROL_PROTECTION or c.RF_PROTECTION:
            ctx = self.context(source_a=s['immediate'], immediates=8, iterations=0, terminal=0)
            await self.setup_case(ctx)
            await self.idle(15)
            protection = c.CONTROL_PROTECTION or c.RF_PROTECTION
            if c.CONTROL_PROTECTION:
                await self.cycle('fault', fault=('control', 0, 3 if protection == 2 else 1))
            else:
                # Populate RF then use its protected word under a second context.
                ctx = self.context(source_a=s['immediate'], immediates=3, write_rf=1, iterations=1)
                await self.setup_case(ctx)
                await self.traffic(ctx, [[0] * c.DATA_INPUT_PORTS])
                if c.CONTEXT_DEPTH > 1:
                    reader = self.context(source_a=s['rf'], iterations=0, terminal=0)
                    await self.provision(reader, 1)
                    await self.cycle('rf_fault', fault=('rf', 0, 3 if protection == 2 else 1))
                    await self.runtime(1, 1)
            await self.idle(12)
            assert number(self.last['o_status_fatal_error']), self.last
            self.coverage.hit('fault_containment')
            await self.reset(fault=('release', 0, 0))
        await self.reset()
