"""Program the actual shell; directed and random vector mappings use public ports."""
from bct.sequences import BctSequence
from vct.transaction import VctItem
from vct.model import pack, sources, unpack, payload
from bct.scoreboard import number

class VctSequence(BctSequence):
    async def cycle(self, label='idle', *, core_edge=True, cfg_edge=None, fault=None, **ports):
        self.index += 1
        import os
        if os.getenv('VCT_DEBUG_CYCLES'):
            print(self.index, label, flush=True)
        auto = dict(i_body_save_done=number(self.last.get('o_body_save', '0')) or 0,
                    i_body_restore_done=number(self.last.get('o_body_restore', '0')) or 0,
                    i_body_isolation_ack=number(self.last.get('o_body_isolate', '0')) or 0)
        if 'o_body_power_enable' in self.last:
            auto['i_body_power_good'] = number(self.last['o_body_power_enable'])
        item = VctItem(f'{label}_{self.index}', self.base | auto | ports,
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

    async def provision(self, context, cid=None, *, activate=True, error=False):
        if cid is None:
            cid = (number(self.last.get('o_status_active_context', 0)) + 1) % self.c.CONTEXT_DEPTH
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

    async def runtime(self, command, context=None, owner=5, kernel=3, *, wait=True):
        if context is None:
            context = number(self.last.get('o_status_active_context', 0)) or 0
        return await super().runtime(command, context, owner, kernel, wait=wait)

    def context(self, **changes):
        s = sources(self.c.parameters)
        return dict(schema=1, fu=0, opcode=0, format_a=0, format_b=0, format_c=2,
            result_format=0, source_a=0, source_b=1, source_c=s['zero'],
            lane_mask=(1 << self.c.NUM_LANES) - 1, runtime_tail=(1 << self.c.NUM_LANES) - 1,
            output_mask=(1 << self.c.DATA_OUTPUT_PORTS) - 1, iterations=4, terminal=1,
            monitor=1) | changes

    async def read_body_counter(self, index):
        for _ in range(20):
            item = await self.cycle('body_counter_request', i_debug_request_valid=1,
                i_debug_request_address=0x80 + index, i_debug_request_owner_id=5,
                i_debug_response_ready=0)
            if number(item.edges['core']['o_debug_request_ready']): break
        else: raise AssertionError('Body counter request starved')
        await self.idle(2, i_debug_response_ready=0)
        assert number(self.last['o_debug_response_valid'])
        assert not number(self.last['o_debug_response_error'])
        value = number(self.last['o_debug_response_read_data'])
        await self.idle(2)
        return value

    async def traffic(self, context, values, *, masks=None, tails=None, predicates=None,
                      expected_error=None, random_cycles=0, completion=True, limit=3000, skew=False):
        from vct.model import operands_used
        c = self.c
        normalized = unpack(c.parameters, pack(c.parameters, context))
        required = sorted(set(context[f'source_{n}'] for n, use in zip('abc', operands_used(normalized))
                              if use and context[f'source_{n}'] < c.DATA_INPUT_PORTS))
        sent = {p: 0 for p in required}
        pred_sent = 0
        count = len(values)
        version = number(self.last['o_status_context_version'])
        cid = number(self.last['o_status_active_context'])
        base = c.aliases['CI'] + c.CONTEXT_VERSION_WIDTH
        full = (1 << c.NUM_LANES) - 1
        for tick in range(random_cycles or limit):
            valid = data = metadata = 0
            for port in required:
                index = sent[port]
                if index < count and (not skew or port != 1 or tick >= 6):
                    valid |= 1 << port
                    value = values[index][port]
                    data |= value << (port * c.DATA_WIDTH)
                    fmt = next(context.get(f'format_{n}', 0) for n, use in zip('abc', operands_used(normalized))
                               if use and context[f'source_{n}'] == port)
                    mask = masks[index] if masks else full
                    tail = tails[index] if tails else full
                    meta = version << c.aliases['CI'] | cid | fmt << base | mask << (base + 3)
                    meta |= context.get('signed_mode', 0) << (base + 3 + c.NUM_LANES)
                    meta |= tail << (base + 4 + c.NUM_LANES)
                    metadata |= meta << (port * c.DATA_METADATA_WIDTH)
            scheduled = c.parameters['INPUT_ELASTIC_MASK'] != (1 << c.DATA_INPUT_PORTS) - 1
            if scheduled and tick % 40 != 8: valid = 0
            pred_valid = int(context.get('predicate_mode', 0) == 1 and pred_sent < count)
            pred = predicates[pred_sent] if predicates and pred_valid else full
            ready = self.rng.getrandbits(c.DATA_OUTPUT_PORTS) if random_cycles else (
                (1 << c.DATA_OUTPUT_PORTS) - 1 if tick % 19 >= 7 else 0)
            if scheduled and random_cycles: ready = (1 << c.DATA_OUTPUT_PORTS) - 1
            item = await self.cycle('vector_traffic', i_data_in_valid=valid,
                i_data_in_payload=data, i_data_in_metadata=metadata,
                i_predicate_in_valid=pred_valid, i_predicate_in_payload=pred,
                i_predicate_in_metadata=cid, i_data_out_ready=ready)
            edge = item.edges.get('core')
            if edge:
                p = {n: number(v) for n, v in edge.items()}
                for port in required:
                    sent[port] += int(bool(valid >> port & p['o_data_in_ready'] >> port & 1))
                pred_sent += int(bool(pred_valid and p['o_predicate_in_ready']))
            if number(self.last['o_status_error']):
                assert expected_error is not None and number(self.last['o_status_error_code']) == expected_error, (
                    'unexpected error', number(self.last['o_status_error_code']), context)
                return
            if completion and number(self.last['o_status_execution_state']) == 11:
                assert all(n == count for n in sent.values()), ('lost inputs', sent, count)
                self.coverage.hit('ordered_completion')
                return
        if random_cycles: return
        if not completion: return
        raise AssertionError(('Vector mapping did not complete', self.last, sent, context))

    async def run_mapping(self, context, count=4, **kwargs):
        await self.setup_case(context)
        width = self.c.ELEMENT_WIDTH
        values = [[payload([self.rng.getrandbits(width) for _ in range(self.c.NUM_LANES)], width)
                   for _ in range(self.c.DATA_INPUT_PORTS)] for _ in range(count)]
        await self.traffic(context, values, **kwargs)

    async def body(self):
        c = self.c
        s = sources(c.parameters)
        full = (1 << c.NUM_LANES) - 1
        # Every integer opcode, all signedness and supported saturation boundaries.
        for op in range(22):
            if op in (18, 19) and not c.SUPPORT_MINMAX or op == 20 and not c.SUPPORT_MUL or op == 21 and not c.SUPPORT_MAC:
                continue
            ctx = self.context(opcode=op, result_format=1 if op == 20 else 2 if op == 21 else 0,
                signed_mode=op % 2, select_mask=full // 3,
                source_c=s['vacc'] if op == 21 else s['zero'],
                clear_vacc=full if op == 21 else 0, write_vacc=int(op == 21),
                write_predicate=int(9 <= op <= 14), predicate_output=int(9 <= op <= 14))
            await self.run_mapping(ctx)
        if c.SUPPORT_SATURATION:
            ctx = self.context(saturate=1, signed_mode=1)
            await self.setup_case(ctx)
            high = payload([(1 << (c.ELEMENT_WIDTH - 1)) - 1] * c.NUM_LANES, c.ELEMENT_WIDTH)
            one = payload([1] * c.NUM_LANES, c.ELEMENT_WIDTH)
            await self.traffic(ctx, [[high, one] + [0] * (c.DATA_INPUT_PORTS - 2)] * 4)
        # Every lane mask, with explicit metadata and runtime tail intersection.
        ctx = self.context(metadata_mask=1, iterations=1 << c.NUM_LANES)
        await self.run_mapping(ctx, 1 << c.NUM_LANES, masks=list(range(1 << c.NUM_LANES)))
        for mode in (1, 3):
            ctx = self.context(predicate_mode=mode)
            await self.run_mapping(ctx, predicates=[full, full // 3, 0, full])
        if c.SUPPORT_PREDICATED_TOKEN:
            await self.run_mapping(self.context(predicate_mode=3, false_token=1))
        # An independently written predicate entry is reused after context activation.
        ctx = self.context(opcode=9, write_predicate=1)
        await self.run_mapping(ctx)
        ctx = self.context(predicate_mode=2)
        await self.provision(ctx)
        await self.runtime(1)
        values = [[1] * c.DATA_INPUT_PORTS] * 4
        await self.traffic(ctx, values)
        # Tail masks preserve lane order and do not compact operands.
        ctx = self.context(tail_mask=1, runtime_tail=full ^ (1 << (c.NUM_LANES - 1)))
        await self.run_mapping(ctx, tails=[full, 1, full // 3, full])
        # Reduction identities, empty masks and exact dot products.
        if c.FU_PROFILE:
            for op in range(5):
                if op in (1, 2) and not c.SUPPORT_MINMAX: continue
                ctx = self.context(fu=1, opcode=op, result_format=4 if op == 0 else 3,
                    source_b=s['zero'], signed_mode=op % 2,
                    metadata_mask=1, write_sacc=int(op == 0))
                await self.run_mapping(ctx, masks=[full, 1, full // 3 or 1, full if op in (1,2) else 0])
            ctx = self.context(fu=1, result_format=4, source_b=s['zero'],
                source_c=s['sacc'], format_c=4, accumulate=1, clear_sacc=1,
                write_sacc=1, signed_mode=1)
            await self.run_mapping(ctx)
        if c.FU_PROFILE == 2:
            ctx = self.context(fu=2, result_format=4, signed_mode=1, metadata_mask=1)
            await self.run_mapping(ctx, masks=[full, 0, 1, full // 3])
            ctx = self.context(fu=2, result_format=4, signed_mode=1, accumulate=1,
                source_c=s['sacc'], format_c=4, clear_sacc=1, write_sacc=1)
            await self.run_mapping(ctx)
        if c.SUPPORT_BROADCAST:
            for fmt in (3,4):
                ctx = self.context(fu=3, source_b=s['zero'], format_a=fmt,
                    result_format=0 if fmt == 3 else 2)
                await self.setup_case(ctx)
                await self.traffic(ctx, [[3] * c.DATA_INPUT_PORTS] * 4)
        if c.SUPPORT_LANE_SELECT:
            for lane in range(c.NUM_LANES):
                await self.run_mapping(self.context(fu=4, source_b=s['zero'],
                    result_format=3, extract_lane=lane))
        # Explicit pass-through covers all five formats and every physical input.
        for fmt in range(5):
            from vct.model import lane_width
            width = lane_width(c.parameters, fmt)
            ctx = self.context(fu=5, source_b=s['zero'], format_a=fmt,
                result_format=fmt, iterations=2)
            await self.setup_case(ctx)
            values = [[payload([self.rng.getrandbits(width) for _ in range(
                1 if fmt >= 3 else c.NUM_LANES)], width)
                for _ in range(c.DATA_INPUT_PORTS)] for _ in range(2)]
            await self.traffic(ctx, values)
        for port in range(2, c.DATA_INPUT_PORTS):
            await self.run_mapping(self.context(fu=5, source_a=port, source_b=s['zero']))
        # An execution mask is independently written by compare predicates.
        writer = self.context(opcode=10, source_b=s['zero'], write_mask=1)
        await self.run_mapping(writer)
        reader = self.context(fu=5, source_b=s['zero'], local_mask=1, iterations=2)
        await self.provision(reader)
        await self.runtime(1)
        await self.traffic(reader, [[3] * c.DATA_INPUT_PORTS] * 2)
        self.coverage.hit('local_mask')
        # Full vector accumulation and masked feedback.
        ctx = self.context(fu=5, source_b=s['zero'], format_a=2, result_format=2,
            source_a=s['immediate'], immediate=payload([2] * c.NUM_LANES, c.ACC_WIDTH),
            write_vacc=1, iterations=1)
        await self.run_mapping(ctx, 1)
        ctx = self.context(fu=5, source_a=s['vacc'], source_b=s['zero'],
            format_a=2, result_format=2, iterations=4)
        await self.provision(ctx)
        await self.runtime(1)
        await self.traffic(ctx, [[0] * c.DATA_INPUT_PORTS] * 4)
        self.coverage.hit('accumulator_feedback')
        # Masked write of an upper slice group, followed by typed VRF readback.
        slice_index = c.ACC_WIDTH // c.WRITE_SLICE_WIDTH - c.ELEMENT_WIDTH // c.WRITE_SLICE_WIDTH
        ctx = self.context(fu=5, source_b=s['zero'], write_rf=1, write_slice=slice_index)
        await self.run_mapping(ctx)
        if c.BYPASS_PROFILE:
            ctx = self.context(fu=5, source_a=s['rf'], source_b=s['zero'],
                read_slice_a=slice_index, lane_mask=full // 3, iterations=2)
            await self.provision(ctx)
            await self.runtime(1)
            await self.traffic(ctx, [[0] * c.DATA_INPUT_PORTS] * 2)
            # Change just one slice in alternating lanes, preserving all others.
            writer = self.context(fu=5, source_b=s['zero'], write_rf=1,
                write_slice=slice_index, lane_mask=full // 3, iterations=2,
                slice_mask=sum(1 << (l * (c.ACC_WIDTH // c.WRITE_SLICE_WIDTH) + slice_index)
                               for l in range(c.NUM_LANES)))
            await self.provision(writer)
            await self.runtime(1)
            await self.traffic(writer, [[payload([5] * c.NUM_LANES, c.ELEMENT_WIDTH)] *
                                       c.DATA_INPUT_PORTS] * 2)
            reader = self.context(fu=5, source_a=s['rf'], source_b=s['zero'],
                read_slice_a=slice_index, iterations=2)
            await self.provision(reader)
            await self.runtime(1)
            await self.traffic(reader, [[0] * c.DATA_INPUT_PORTS] * 2)
            before = await self.read_body_counter(9)
            pair = self.context(source_a=s['rf'], source_b=s['rf'] + 1,
                read_slice_a=slice_index, read_slice_b=slice_index, iterations=2)
            await self.provision(pair)
            await self.runtime(1)
            await self.traffic(pair, [[0] * c.DATA_INPUT_PORTS] * 2)
            after = await self.read_body_counter(9)
            assert after - before == 4 * c.NUM_LANES * c.ELEMENT_WIDTH // c.WRITE_SLICE_WIDTH
            self.coverage.hit('counter_slice_count')
        self.coverage.hit('partial_slices')
        ctx = self.context(fu=5, source_b=s['zero'], write_bypass=1)
        await self.run_mapping(ctx)
        partial = self.context(fu=5, source_b=s['zero'], write_bypass=1,
            lane_mask=full // 3, iterations=2)
        await self.provision(partial)
        await self.runtime(1)
        await self.traffic(partial, [[payload([7] * c.NUM_LANES, c.ELEMENT_WIDTH)] *
                                    c.DATA_INPUT_PORTS] * 2)
        ctx = self.context(fu=5, source_a=s['bypass'], source_b=s['zero'], iterations=2)
        await self.provision(ctx)
        await self.runtime(1)
        await self.traffic(ctx, [[0] * c.DATA_INPUT_PORTS] * 2)
        ctx = self.context(fu=5, source_a=s['previous'], source_b=s['zero'], iterations=2)
        await self.provision(ctx)
        await self.runtime(1)
        await self.traffic(ctx, [[0] * c.DATA_INPUT_PORTS] * 2)
        self.coverage.hit('atomic_destinations')
        # Random full-lane vectors and congestion, without changing an unaccepted token.
        ctx = self.context(iterations=0, terminal=0, metadata_mask=1)
        await self.setup_case(ctx)
        values = [[payload([self.rng.getrandbits(c.ELEMENT_WIDTH) for _ in range(c.NUM_LANES)], c.ELEMENT_WIDTH)
                   for _ in range(c.DATA_INPUT_PORTS)] for _ in range(c.random_cycles)]
        await self.traffic(ctx, values, masks=[self.rng.randrange(full + 1) for _ in values],
                           random_cycles=c.random_cycles, completion=False)
        self.coverage.random_cycles = c.random_cycles
        await self.runtime(5)
        self.coverage.hit('terminate')
        # More negative/lifecycle cases follow; each begins a fresh ownership epoch.
        await self.negative_and_lifecycle()
        await self.reset()
    async def negative_and_lifecycle(self):
        c = self.c
        s = sources(c.parameters)
        full = (1 << c.NUM_LANES) - 1
        for change in (dict(schema=0), dict(fu=7), dict(result_format=4),
                       dict(required_rf=1, invalidate_rf=1), dict(format_a=7)):
            await self.reset()
            await self.runtime(0)
            await self.provision(self.context(**change), activate=False, error=True)
        await self.reset()
        await self.runtime(0)
        response = await self.cfg(5, owner=6)
        assert number(response['o_cfg_response_error'])
        self.coverage.hit('ownership_rejection')
        if c.SYNC_PROFILE == 1:
            delay = c.RDU_TOTAL_DELAY_ENTRIES // c.DATA_INPUT_PORTS
            ctx = self.context(fu=5, source_b=s['zero'], delays=delay)
            await self.run_mapping(ctx)
            # Different per-channel delays and staggered producers preserve order.
            dw = max(1, c.RDU_TOTAL_DELAY_ENTRIES.bit_length())
            ctx = self.context(delays=(1 << dw), iterations=4)
            await self.run_mapping(ctx, skew=True)
            self.coverage.hit('rdu_delay')
        if c.BYPASS_PROFILE:
            ctx = self.context(fu=5, source_a=s['rf'], source_b=s['zero'], iterations=1)
            await self.reset()
            await self.runtime(0)
            await self.provision(ctx)
            await self.runtime(1)
            await self.idle(12)
            if c.SYNC_PROFILE == 2:
                assert not number(self.last['o_status_error']) and not number(self.last['o_data_out_valid'])
            else:
                assert number(self.last['o_status_error_code']) == 0x82, self.last
            self.coverage.hit('invalid_slice')
        else:
            # The minimal graph rejects VRF reads instead of allocating that edge.
            await self.reset()
            await self.runtime(0)
            await self.provision(self.context(source_a=s['rf']), activate=False, error=True)
            self.coverage.hit('invalid_slice')
        if c.REQUIRE_CANONICAL_FORMAT:
            ctx = self.context(fu=5, source_b=s['zero'], iterations=1)
            await self.setup_case(ctx)
            await self.traffic(ctx, [[1 << (c.NUM_LANES * c.ELEMENT_WIDTH)] * c.DATA_INPUT_PORTS],
                               expected_error=0x81)
            assert number(self.last['o_status_error_code']) == 0x81
        else:
            ctx = self.context(fu=5, source_b=s['zero'], iterations=1)
            await self.setup_case(ctx)
            await self.traffic(ctx, [[1 << (c.NUM_LANES * c.ELEMENT_WIDTH)] * c.DATA_INPUT_PORTS])
        self.coverage.hit('format_rejection' if c.REQUIRE_CANONICAL_FORMAT else 'format_padding_allowed')
        # Known inactive X data must never contaminate the sole active lane.
        ctx = self.context(fu=5, source_b=s['zero'], lane_mask=1, iterations=1)
        await self.setup_case(ctx)
        cid = number(self.last['o_status_active_context'])
        meta = number(self.last['o_status_context_version']) << c.aliases['CI'] | cid
        raw = '0' * (c.DATA_INPUT_PORTS * c.DATA_WIDTH - c.NUM_LANES * c.ELEMENT_WIDTH)
        raw += 'x' * ((c.NUM_LANES - 1) * c.ELEMENT_WIDTH) + format(3, f'0{c.ELEMENT_WIDTH}b')
        for _ in range(12):
            item = await self.cycle('inactive_x', i_data_in_valid=1,
                                    i_data_in_payload=raw, i_data_in_metadata=meta)
            if number(item.edges['core']['o_data_in_ready']) & 1: break
        else: raise AssertionError('Inactive-X input not accepted')
        for _ in range(40):
            await self.cycle('inactive_x_result')
            if number(self.last['o_status_execution_state']) == 11: break
        else: raise AssertionError('Inactive X contaminated active work')
        assert not number(self.last['o_status_error'])
        self.coverage.hit('inactive_x')
        # Reset explicitly discards owned output work under backpressure.
        ctx = self.context(fu=5, source_b=s['zero'], iterations=1)
        await self.setup_case(ctx)
        meta = number(self.last['o_status_context_version']) << c.aliases['CI'] | number(self.last['o_status_active_context'])
        for _ in range(12):
            item = await self.cycle('pending_reset_input', i_data_in_valid=1,
                i_data_in_payload=3, i_data_in_metadata=meta, i_data_out_ready=0)
            if number(item.edges['core']['o_data_in_ready']) & 1: break
        await self.idle(4, i_data_out_ready=0)
        await self.reset()
        assert number(self.last['o_status_owner_id']) == 0
        self.coverage.hit('reset_pending')
        ctx = self.context(fu=5, source_b=s['zero'], iterations=0, terminal=0)
        await self.setup_case(ctx)
        # No unaccepted operands remain when suspend is requested.
        response = await self.runtime(2)
        assert not number(response['o_runtime_response_error']), response
        response = await self.runtime(3)
        assert not number(response['o_runtime_response_error'])
        self.coverage.hit('suspend_resume')
        # Drain and a stopped clock do not create transfers or change ownership.
        await self.cycle('stopped_clock', core_edge=False)
        response = await self.runtime(4)
        assert not number(response['o_runtime_response_error']), response
        self.coverage.hit('drain')
        await self.setup_case(ctx)
        await self.cycle('unknown_reset', i_rstb='x')
        assert number(self.last['o_data_in_ready']) == 0 and number(self.last['o_data_out_valid']) == 0
        await self.idle(8)
        assert number(self.last['o_status_owner_id']) == 5
        assert not number(self.last['o_status_fatal_error'])
        self.coverage.hit('unknown_reset')
        await self.idle(4)
        for _ in range(12):
            item = await self.cycle('counter_read', i_debug_request_valid=1,
                i_debug_request_address=0x80, i_debug_request_owner_id=5,
                i_debug_response_ready=0)
            if number(item.edges['core']['o_debug_request_ready']): break
        await self.idle(3, i_debug_response_ready=0)
        assert number(self.last['o_debug_response_valid'])
        assert not number(self.last['o_debug_response_error'])
        saved = self.last['o_debug_response_read_data']
        await self.cycle('counter_unknown_ready', i_debug_response_ready='x')
        assert self.last['o_debug_response_read_data'] == saved
        await self.idle(2)
        self.coverage.hit('counters')
        await self.reset()
        if c.SUPPORT_SPATIAL_TEMPORAL and c.CONTEXT_DEPTH > 1:
            for mode in (1,2,3):
                await self.reset()
                await self.runtime(0)
                first = self.context(source_a=s['immediate'], source_b=s['immediate'],
                    immediate=payload([1] * c.NUM_LANES, c.ELEMENT_WIDTH),
                    opcode=9 if mode == 2 else 0, iterations=2,
                    terminal=0, advance_mode=mode, next_context=1)
                last = self.context(fu=5, source_a=s['immediate'], source_b=s['zero'],
                    immediate=7, iterations=2)
                await self.provision(last, 1, activate=False)
                await self.provision(first, 0)
                await self.runtime(1, 0)
                sent = mode != 3
                for _ in range(180):
                    event = 7 | (3 << (c.aliases['CI'] + 3))
                    item = await self.cycle('temporal', i_event_in_valid=int(not sent),
                                            i_event_in_payload=event)
                    if number(item.edges['core']['o_event_in_ready']): sent = True
                    if number(self.last['o_status_execution_state']) == 11: break
                else: raise AssertionError(('Temporal mapping failed', mode, self.last))
                assert number(self.last['o_status_active_context']) == 1
            self.coverage.hit('temporal')
        if c.SUPPORT_RETENTION:
            ctx = self.context(fu=5, source_b=s['zero'], write_rf=1, iterations=1)
            await self.run_mapping(ctx, 1)
            await self.power(3)
            assert number(self.last['o_status_power_state']) == 3
            await self.power(0)
            if c.BYPASS_PROFILE:
                reader = self.context(fu=5, source_a=s['rf'], source_b=s['zero'], iterations=2)
                await self.provision(reader)
                await self.runtime(1)
                await self.traffic(reader, [[0] * c.DATA_INPUT_PORTS] * 2)
            self.coverage.hit('retention')
            await self.power(4)
            assert number(self.last['o_status_power_state']) == 4
            await self.power(0)
            self.coverage.hit('power_off')
        ctx = self.context(fu=5, source_a=s['immediate'], source_b=s['zero'],
                           immediate=8, iterations=0, terminal=0)
        await self.setup_case(ctx)
        await self.idle(8)
        await self.cycle('corrupt_context', fault=('context',0,1))
        await self.idle(8)
        assert number(self.last['o_status_error_code']) == 0x80
        self.coverage.hit('runtime_context_rejection')
        await self.reset(fault=('release',0,0))
        if c.CONTROL_PROTECTION:
            await self.setup_case(ctx)
            await self.idle(12)
            await self.cycle('corrupt_control', fault=('control',0,3 if c.CONTROL_PROTECTION == 2 else 1))
            await self.idle(12)
            assert number(self.last['o_status_fatal_error'])
            self.coverage.hit('fault_containment')
            await self.reset(fault=('release',0,0))
        elif c.VRF_PROTECTION:
            writer = self.context(fu=5, source_b=s['zero'], write_rf=1, iterations=1)
            await self.run_mapping(writer, 1)
            reader = self.context(fu=5, source_a=s['rf'], source_b=s['zero'], iterations=0, terminal=0)
            if c.BYPASS_PROFILE:
                await self.provision(reader)
                await self.cycle('corrupt_vrf', fault=('rf',0,3 if c.VRF_PROTECTION == 2 else 1))
                await self.runtime(1)
                await self.idle(12)
                assert number(self.last['o_status_fatal_error'])
                await self.reset(fault=('release',0,0))
            else:
                # Predicate and accumulator witnesses use VRF_PROTECTION as well.
                await self.cycle('corrupt_accumulator', fault=('accumulator',0,3 if c.VRF_PROTECTION == 2 else 1))
                await self.idle(12)
                assert number(self.last['o_status_fatal_error'])
                await self.reset(fault=('release',0,0))
            self.coverage.hit('fault_containment')
