"""Shell-only programming, primitive mappings and mapper-owned replay sequences."""
from sft.model import context, pack, required
from sft.transaction import SftItem, INPUTS
from tile_shell.model import number, crc32c
from tile_shell.sequences import TileShellSequence

class SftSequence(TileShellSequence):
    def __init__(self, config):
        super().__init__(config)
        self.base = {n:self.base.get(n,0) for n in INPUTS}
        self.base.update(i_rstb=1,i_cfg_rstb=1,i_body_power_good=1)
        self.active=None

    async def cycle(self, label='idle', *, core_edge=True, cfg_edge=None, fault=None, **ports):
        self.index += 1
        import os
        if os.getenv('SFT_DEBUG_CYCLES'):
            print(self.index, label, flush=True)
        auto = dict(i_body_save_done=number(self.last.get('o_body_save', '0')) or 0,
                    i_body_restore_done=number(self.last.get('o_body_restore', '0')) or 0,
                    i_body_isolation_ack=number(self.last.get('o_body_isolate', '0')) or 0)
        if 'o_body_power_enable' in self.last:
            auto['i_body_power_good'] = number(self.last['o_body_power_enable'])
        item = SftItem(f'{label}_{self.index}', self.base | auto | ports,
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

    async def cfg_response(self, tag):
        for _ in range(20000):
            if tag in self.responses:
                return self.responses.pop(tag)
            await self.cycle()
        raise AssertionError(f'Configuration response timeout, tag {tag}')

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

    def context(self, **changes):
        return context(self.c.parameters, **changes)

    async def provision(self, ctx, cid=0, *, activate=True, error=False):
        image=pack(self.c.parameters,ctx)
        self.active['contexts'][cid]=ctx.copy()
        for word in range(self.c.CONFIG_WORD_COUNT):
            response=await self.cfg(0,cid,word,image >> (64*word) & ((1 << 64)-1))
            assert not number(response['o_cfg_response_error']),response
        crc=crc32c(image.to_bytes(self.c.CONFIG_WORD_COUNT*8,'little'))
        response=await self.cfg(2,cid,crc=crc)
        assert bool(number(response['o_cfg_response_error']))==error,response
        if error:
            self.coverage.hit('validation_rejection')
        elif activate:
            response=await self.cfg(3,cid)
            assert not number(response['o_cfg_response_error']),response
            await self.idle(4)
        return response

    async def setup_case(self,ctx):
        await self.reset()
        assert not number((await self.runtime(0))['o_runtime_response_error'])
        await self.provision(ctx)
        assert number(self.last['o_status_tile_class'])==2
        assert not number((await self.runtime(1))['o_runtime_response_error'])

    async def traffic(self,ctx,values,*,predicates=None,phases=None,complete=True,
                      blocked=0,limit=None,allow_recoverable=False,expected_fatal=None):
        c=self.c
        ports=required(ctx)
        sent={p:0 for p in ports}
        pred_sent=0
        count=len(values)
        version=number(self.last['o_status_context_version'])
        cid=number(self.last['o_status_active_context'])
        identity=cid | version << c.aliases['CI']
        self.active['observed']=[]
        for tick in range(limit or 200+count*80):
            valid=payload=metas=0
            for port in ports:
                index=sent[port]
                if index<count:
                    # Preserve valid/data until acceptance, including independent stalls.
                    valid |= 1 << port
                    payload |= (values[index][port] & ((1 << c.SHELL_DATA_WIDTH)-1)) << (port*c.SHELL_DATA_WIDTH)
                    meta=identity | (phases[index] if phases else 0) << 32 | index << 40
                    metas |= meta << (port*c.DATA_METADATA_WIDTH)
            pred_valid=int(ctx['predicate_mode']==1 and pred_sent<count)
            pred=predicates[pred_sent] if predicates and pred_valid else 1
            ready=0 if tick<blocked else self.rng.randrange(1 << c.DATA_OUTPUT_PORTS) if tick%7<3 else (1 << c.DATA_OUTPUT_PORTS)-1
            item=await self.cycle('traffic',i_data_in_valid=valid,i_data_in_payload=payload,
                i_data_in_metadata=metas,i_data_out_ready=ready,
                i_predicate_in_valid=pred_valid,i_predicate_in_payload=pred,
                i_predicate_in_metadata=cid)
            edge={n:number(v) for n,v in item.edges['core'].items()}
            for port in ports:sent[port]+=int(bool(valid >> port & edge['o_data_in_ready'] >> port & 1))
            pred_sent+=int(bool(pred_valid and edge['o_predicate_in_ready']))
            if number(self.last['o_status_fatal_error']):
                assert expected_fatal is not None and number(self.last['o_status_error_code'])==expected_fatal
                assert all(n==count for n in sent.values())
                self.coverage.hit('count_limit')
                await self.idle(4)
                return []
            assert allow_recoverable or not number(self.last['o_status_error']),('status',self.index,ctx,self.last)
            if complete and number(self.last['o_status_execution_state'])==11:
                assert all(n==count for n in sent.values()),sent
                await self.idle(12)
                return self.active['observed'].copy()
            if not complete and tick>=blocked and all(n==count for n in sent.values()):
                return self.active['observed'].copy()
        import cocotb
        body=cocotb.top.g_sft.u_body
        print('BODY DEBUG', {n:str(getattr(body,n).value) for n in
            ('enabled','executing','context_change','allow_admission','input_valid','input_ready',
             'input_counts','operands_present','operands_known','issue','request_count','engine_phase',
             'request_pop','dispatch','commit','q','n')},flush=True)
        raise AssertionError(('Traffic timeout',ctx,sent,self.last))

    async def case(self,ctx,values,**kwargs):
        ctx=ctx | {'steps':len(values)}
        await self.setup_case(ctx)
        return await self.traffic(ctx,values,**kwargs)

    async def body(self):
        c=self.c
        dmask=(1 << c.SHELL_DATA_WIDTH)-1
        # All scalar operations and both operands, with independently blocked copies.
        for opcode in range(21):
            ctx=self.context(opcode=opcode,source_b=1,signed_data=1,
                saturate=int(bool(c.SUPPORT_SATURATION) and opcode in (0,1,20)),output_mask=(1 << c.DATA_OUTPUT_PORTS)-1)
            values=[(4,2),(-3 & dmask,2),(0,1)]
            if opcode in (6,7,8):values += [(5,c.SHELL_DATA_WIDTH),(-3 & dmask,c.SHELL_DATA_WIDTH+1)]
            if opcode==20:values += [(1 << (c.SHELL_DATA_WIDTH-1),0)]
            await self.case(ctx,values,blocked=18)
        await self.case(self.context(opcode=15,source_b=1,select_condition=1),[(4,7),(0,3)])
        for reduction in range(4):
            packed=sum((n & ((1 << c.REDUCTION_ELEMENT_WIDTH)-1)) << (i*c.REDUCTION_ELEMENT_WIDTH)
                       for i,n in enumerate((-3,2,5,-1)[:c.REDUCTION_LANES]))
            ctx=self.context(operation=7,reduction=reduction,signed_data=1)
            await self.case(ctx,[(packed,0),(packed,0)])
            for empty_policy in range(3):
                await self.case(ctx | {'mask':0,'empty_policy':empty_policy},[(0,0)])
        # One context consumes explicitly phased beats, preserving the same identity.
        ctx=self.context(operation=7,reduction=1,dynamic_phase=1,signed_data=1)
        packed=sum((i+1) << (i*c.REDUCTION_ELEMENT_WIDTH) for i in range(c.REDUCTION_LANES))
        await self.case(ctx,[(packed,0)]*6,phases=[1,2,3,4,5,1])
        if c.FU_PROFILE==2:
            beats=c.MAX_REDUCTION_ELEMENTS//c.REDUCTION_LANES
            one=sum(1 << (i*c.REDUCTION_ELEMENT_WIDTH) for i in range(c.REDUCTION_LANES))
            await self.case(self.context(operation=7,reduction=1,dynamic_phase=1),
                [(one,0)]*(beats+1),phases=[2]+[3]*(beats-1)+[4],expected_fatal=87)
        for bank in range(c.LUT_BANKS):
            ctx=self.context(operation=2,bank=bank,interpolate=int(bool(c.SUPPORT_INTERPOLATION)),rounding=1)
            fraction=1 << (c.LUT_INDEX_FRACTION_WIDTH-1)
            await self.case(ctx,[(0,0),(fraction,0),
                ((1 << (1+c.LUT_ADDRESS_WIDTH+c.LUT_INDEX_FRACTION_WIDTH))-1,0)])
        await self.case(self.context(operation=2,range_error=1),
            [((1 << (1+c.LUT_ADDRESS_WIDTH+c.LUT_INDEX_FRACTION_WIDTH))-1,0)])
        if c.FU_PROFILE:
            await self.case(self.context(operation=1,source_b=1,signed_data=1),[(2,3),(-3 & dmask,4),(0,min(17,(1 << (c.INPUT_WIDTH-1))-1))])
            for degree in range(c.POLY_MAX_DEGREE+1):
                await self.case(self.context(operation=3,degree=degree,bank=degree%c.POLY_BANKS,
                    signed_data=1,rounding=1),[(0,0),(1 << c.INPUT_FRAC_BITS,0),(-min(17,1 << (c.INPUT_WIDTH-1)) & dmask,0)])
        if c.FU_PROFILE>=2:
            for op in (4,5):
                for quality in range(3):
                    await self.case(self.context(operation=op,quality=quality,iterations=quality,
                        rounding=1),[(0,0),(1,0),(1 << c.INPUT_FRAC_BITS,0),(min(17 << c.INPUT_FRAC_BITS,(1 << c.INPUT_WIDTH)-1),0)])
            await self.case(self.context(operation=5,signed_data=1,quality=2,iterations=2,
                epsilon=1),[(-1 & dmask,0),(0,0)])
        if c.FU_PROFILE==3:
            for base in (0,1):
                await self.case(self.context(operation=6,base=base,interpolate=1,rounding=1),
                    [(-256 & dmask,0),(0,0),(256,0),(-4096 & dmask,0),(4096,0)])
        for mode in (0,1):
            await self.case(self.context(operation=8,shift=1,rounding=mode,signed_data=1,
                saturate=int(bool(c.SUPPORT_SATURATION))),[(5,0),(-5 & dmask,0),(1 << (c.OUTPUT_WIDTH+2),0)])
        for false_token in range(1+c.SUPPORT_PREDICATED_TOKEN):
            await self.case(self.context(predicate_mode=1,false_token=false_token,write_rf=int(bool(c.SUPPORT_LOCAL_CHAINING)),
                write_acc=int(bool(c.SUPPORT_LOCAL_CHAINING))),[(1,0),(2,0),(3,0)],predicates=[0,1,0])
        await self.case(self.context(operation=9,opcode=0),[(0,0)])
        if c.SUPPORT_LOCAL_CHAINING:
            # Retire each local update before the next queued dependent read.
            ctx=self.context(operation=9,opcode=1,write_acc=1)
            await self.setup_case(ctx | {'terminal':0,'steps':1})
            await self.traffic(ctx,[(7,0)],complete=False)
            await self.idle(40)
            # A fresh context preserves state only with explicit source format/version.
            self.coverage.hit('write_accumulator')
        await self.validation_and_lifecycle()
        await self.temporal_and_replay()
        values=[(self.rng.getrandbits(c.SHELL_DATA_WIDTH),self.rng.getrandbits(c.SHELL_DATA_WIDTH))
                for _ in range(c.random_cycles)]
        await self.case(self.context(opcode=4,source_b=1),values)
        self.coverage.random_cycles=len(values)
        await self.reset()

    async def validation_and_lifecycle(self):
        c=self.c
        await self.reset()
        assert not number((await self.runtime(0))['o_runtime_response_error'])
        await self.provision(self.context(operation=255),error=True)
        rejected=await self.cfg(0,owner=4)
        assert number(rejected['o_cfg_response_error'])
        self.coverage.hit('ownership_rejection')
        # Cancel validation while the native image loader still owns a request.
        pending=self.context(operation=2)
        image=pack(c.parameters,pending)
        self.active['contexts'][0]=pending.copy()
        for word in range(c.CONFIG_WORD_COUNT):
            response=await self.cfg(0,0,word,image >> (64*word) & ((1 << 64)-1))
            assert not number(response['o_cfg_response_error'])
        await self.cfg(2,crc=crc32c(image.to_bytes(c.CONFIG_WORD_COUNT*8,'little')),wait=False)
        await self.idle(1)
        assert not number((await self.runtime(5))['o_runtime_response_error'])
        await self.idle(8)
        await self.provision(self.context())
        self.coverage.hit('validation_cancel')
        rejected=await self.cfg(0)
        assert number(rejected['o_cfg_response_error'])
        self.coverage.hit('package_isolation')
        # A read of uninitialized owner-private state may produce no successful result.
        await self.setup_case(self.context(operation=9,opcode=3))
        await self.idle(30)
        assert number(self.last['o_status_fatal_error'])==1,self.last
        self.coverage.hit('source_rejection')
        ctx=self.context(steps=4,terminal=0)
        await self.setup_case(ctx)
        await self.traffic(ctx,[(7,0)],complete=False)
        await self.idle(40)
        assert not number((await self.runtime(2))['o_runtime_response_error'])
        assert number(self.last['o_status_execution_state'])==9
        await self.idle(10)
        assert not number((await self.runtime(3))['o_runtime_response_error'])
        self.coverage.hit('suspend_resume')
        await self.traffic(ctx,[(8,0),(9,0),(10,0)],complete=False)
        await self.idle(90)
        value=await self.debug(0x80)
        assert value>=4,value
        self.coverage.hit('counters')
        assert not number((await self.runtime(4))['o_runtime_response_error'])
        await self.idle(20)
        assert number(self.last['o_status_quiescent'])==1
        self.coverage.hit('drain')
        assert not number((await self.runtime(5))['o_runtime_response_error'])
        self.coverage.hit('terminate')
        # Drain a prefix with reservations in both shell and body queues.
        await self.setup_case(self.context(steps=32,terminal=0))
        identity=number(self.last['o_status_context_version']) << c.aliases['CI']
        self.base['i_data_out_ready']=0
        accepted=0
        for tick in range(12):
            item=await self.cycle(i_data_in_valid=1,i_data_in_payload=11,
                i_data_in_metadata=identity)
            accepted+=int(bool(number(item.edges['core']['o_data_in_ready']) & 1))
        assert accepted>0
        tag=await self.runtime(4,wait=False)
        await self.idle(5)
        self.base['i_data_out_ready']=(1 << c.DATA_OUTPUT_PORTS)-1
        for _ in range(250):
            await self.cycle()
            if tag in self.runtime_responses:break
        else:raise AssertionError('Busy drain failed to retire accepted shell operands')
        assert not number(self.runtime_responses.pop(tag)['o_runtime_response_error'])
        await self.idle(16)
        assert number(self.last['o_status_quiescent'])==1
        self.coverage.hit('busy_drain')
        await self.setup_case(self.context(steps=8))
        identity=number(self.last['o_status_context_version']) << c.aliases['CI']
        for _ in range(12):
            await self.cycle(i_data_in_valid=1,i_data_in_payload=2,
                i_data_in_metadata=identity,i_data_out_ready=0)
        assert number(self.last['o_status_busy'])
        await self.reset()
        assert number(self.last['o_data_out_valid'])==0
        self.coverage.hit('reset_pending')
        # Unknown reset and ready pause ownership; neither is an implicit flush.
        ctx=self.context(steps=4)
        await self.setup_case(ctx)
        identity=number(self.last['o_status_context_version']) << c.aliases['CI']
        sent=False
        while not sent:
            item=await self.cycle(i_data_in_valid=1,i_data_in_payload=7,
                i_data_in_metadata=identity,i_data_out_ready=0)
            sent=bool(number(item.edges['core']['o_data_in_ready']) & 1)
        await self.idle(8,i_data_out_ready=0)
        await self.idle(3,i_rstb='x',i_data_out_ready=0)
        await self.idle(3,i_data_out_ready='x'*c.DATA_OUTPUT_PORTS)
        await self.idle(12)
        assert number(self.last['o_status_owner_id'])==5
        assert not number(self.last['o_status_fatal_error'])
        await self.traffic(ctx,[(8,0),(9,0),(10,0)],allow_recoverable=True)
        await self.clear()
        self.coverage.hit('unknown_reset')
        self.coverage.hit('unknown_ready')
        # The public shell checks context identity; the body also matches the
        # opaque operation tag across required data operands.
        await self.setup_case(self.context(source_b=1))
        identity=number(self.last['o_status_context_version']) << c.aliases['CI']
        for _ in range(8):
            await self.cycle(i_data_in_valid=3,i_data_in_payload=3,
                i_data_in_metadata=identity | ((identity | (1 << 40)) << c.DATA_METADATA_WIDTH))
        await self.idle(12)
        assert number(self.last['o_status_fatal_error'])==1
        assert number(self.last['o_data_out_valid'])==0
        self.coverage.hit('metadata_rejection')
        await self.reset()
        if c.CONTROL_PROTECTION:
            await self.setup_case(self.context(steps=8))
            await self.cycle(fault=('control',0,3 if c.CONTROL_PROTECTION==2 else 1))
            await self.idle(2)
            await self.cycle(fault=('release',0,0))
            await self.idle(20)
            assert number(self.last['o_status_fatal_error'])==1
            self.coverage.hit('fault_containment')
            await self.reset()

    async def temporal_and_replay(self):
        c=self.c
        if c.SUPPORT_SPATIAL_TEMPORAL and c.CONTEXT_DEPTH>1:
            await self.reset()
            assert not number((await self.runtime(0))['o_runtime_response_error'])
            rf=bool(c.SUPPORT_LOCAL_CHAINING and c.BYPASS_PROFILE>=1)
            first=self.context(steps=1,terminal=0,advance_context=1,next_context=1,
                immediate=3,write_rf=int(rf),rf_write=0)
            second=self.context(steps=1,source_a=2 if rf else 6,source_b=6,
                immediate=2,output_mask=(1 << c.DATA_OUTPUT_PORTS)-1)
            await self.provision(first,0,activate=True)
            await self.provision(second,1,activate=False)
            await self.idle(5)
            assert not number((await self.runtime(1))['o_runtime_response_error'])
            await self.traffic(first,[(5,0)])
            assert number(self.last['o_status_active_context'])==1
            self.coverage.hit('temporal')
        if c.CONTEXT_DEPTH>=2:
            await self.reset()
            assert not number((await self.runtime(0))['o_runtime_response_error'])
            read=self.context(operation=9,opcode=3)
            write=self.context(operation=9,opcode=1)
            await self.provision(read,0,activate=False)
            write_id=2 if c.CONTEXT_DEPTH>=3 else 1
            await self.provision(write,write_id,activate=False)
            if c.CONTEXT_DEPTH>=3:
                add=self.context(operation=9,opcode=2,steps=2)
                await self.provision(add,1,activate=False)
            for cid,ctx,values in [(write_id,write,[(7,0)]),
                *([(1,add,[(1,0),(3,0)])] if c.CONTEXT_DEPTH>=3 else []),
                (0,read,[(0,0)])]:
                assert not number((await self.cfg(3,cid))['o_cfg_response_error'])
                await self.idle(4)
                assert not number((await self.runtime(1,context=cid))['o_runtime_response_error'])
                await self.traffic(ctx,values)
        # Mapper-owned replay stores each public result in a Python list. Exact
        # SUMSQ is followed by explicit format conversion and optional rsqrt.
        row=[1,2,3,4][:c.REDUCTION_LANES]
        packed=sum(x << (lane*c.REDUCTION_ELEMENT_WIDTH) for lane,x in enumerate(row))
        results=await self.case(self.context(operation=7,reduction=1),[(packed,0)])
        observed=[data for port,data,_ in results if port==0]
        assert observed==[sum(x*x for x in row)],observed
        replay=observed[0]
        await self.case(self.context(operation=8),[(replay,0)])
        if c.FU_PROFILE>=2:
            norm=await self.case(self.context(operation=5,quality=2,iterations=2,rounding=1),
                [(replay << c.INPUT_FRAC_BITS,0)])
            scale=next(data for port,data,_ in norm if port==0)
            products=await self.case(self.context(operation=1,source_b=1),
                [(x << c.INPUT_FRAC_BITS,scale) for x in row])
            values=[(data,0) for port,data,_ in products if port==0]
            await self.case(self.context(operation=8,shift=c.INPUT_FRAC_BITS,rounding=1),values)
        self.coverage.hit('external_replay')
