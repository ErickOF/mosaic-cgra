"""Check committed memory, exact read maturity, credits, cancellations and pin issue."""
import cocotb
from pyuvm import ConfigDB,uvm_analysis_export,uvm_scoreboard
from mosaic_uvm.logic import logic
from sram_wrapper.model import SramModel,known,address
from sram_wrapper.transaction import Activity,INPUTS,OUTPUTS,FIELDS,BACKEND


class SramScoreboard(uvm_scoreboard):
    def build_phase(self):
        self.config=ConfigDB().get(self,'','config');self.coverage=ConfigDB().get(self,'','coverage')
        self.active=ConfigDB().get(self,'','active')
        self.analysis_export=uvm_analysis_export('analysis_export',self);self.analysis_export.write=self.write
        self.model=SramModel(self.config);self.pending=None
        self.response_baseline=False

    def protocol(self,p,item):
        c=self.config
        for name in ('i_rstb','i_flush','i_req_valid','i_rsp_ready'):
            assert known(p[name]),f'Protocol assertion failed: {name}'
        if p['i_rstb']=='0' or p['i_flush']=='1':self.pending=None;return
        if self.pending is not None:
            assert p['i_req_valid']=='1' and tuple(p[name] for name in FIELDS)==self.pending,'Protocol assertion failed: requester_stability'
        if p['i_req_valid']=='1':
            assert known(p['i_req_write']),'Protocol assertion failed: i_req_write'
            assert known(p['i_req_addr']),'Protocol assertion failed: i_req_addr'
            if address(p['i_req_addr'],c.depth) is None:return
            if p['i_req_write']=='1':
                assert known(p['i_req_wmask']),'Protocol assertion failed: i_req_wmask'
                if not item.fault_data:
                    for start,enabled in zip(range(0,c.width,c.granule),p['i_req_wmask']):
                        assert enabled=='0' or known(p['i_req_wdata'][start:start+c.granule]),'Protocol assertion failed: enabled_write_data'
            elif self.model.outputs(p)['o_req_ready']=='1':
                assert item.fault_tag or known(p['i_req_tag']),'Protocol assertion failed: read_tag'

    def outputs(self,p):
        for name,expected in self.model.outputs(p).items():
            assert p[name]==expected,f'SRAM output assertion failed: {name}: {p[name]} != {expected}'

    def write(self,obs):
        c,m=self.config,self.model
        if isinstance(obs,Activity):
            p={name:logic(getattr(cocotb.top,name)) for name in (*INPUTS,*OUTPUTS)}
            # Check address error/clamps before rejecting its unknown control.
            if m.initialized and all(known(p[name]) for name in ('i_rstb','i_flush','i_req_valid','i_rsp_ready')):
                if p['i_req_valid']=='1' and not known(p['i_req_addr']):self.outputs(p)
            self.protocol(p,self.active['item'])
            assert not obs.forbidden,f'Quiet-waveform assertion failed: {obs.name}'
            self.coverage.transitions[obs.name]+=1;return
        p,item,stage=obs.ports,obs.item,obs.stage
        for name in INPUTS:assert p[name]==item.ports[name],f'Stimulus was coerced: {name}'
        self.protocol(p,item)
        if c.check_internals and not self.response_baseline:
            # Unreset response payload has no meaning until qualified by valid.
            m.responses=[obs.internals[f'rsp_{i}'] for i in range(c.credits)]
            self.response_baseline=True
        if stage=='pre':
            item.start=dict(count=len(m.reads),pipeline=set(m.pipeline()),queued=sum(r.due<m.edge for r in m.reads))
            if c.asynchronous and p['i_rstb']=='0':m.clear()
            before=m.transfers(p)
            self.active.update(memory_write=before['memory_write'],response_write=before['response_write'])
            if p['i_rstb']=='1' and p['i_flush']=='0' and p['i_req_valid']=='1' and m.outputs(p)['o_req_ready']=='0' and m.outputs(p)['o_req_error']=='0':
                self.pending=tuple(p[name] for name in FIELDS)
            if not item.edge and (p['i_rstb']=='0' or p['i_flush']=='1'):
                self.coverage.pulses.add(('reset' if p['i_rstb']=='0' else 'flush',bool(item.start['count'])))
        if stage=='edge':
            for name in OUTPUTS:assert p[name]==item.pre.ports[name],f'Real-edge ordering assertion failed: {name}'
            if c.check_internals:
                for name in BACKEND[:-1]:assert obs.internals[name]==item.pre.internals[name],f'Backend sampled-edge assertion failed: {name}'
        if stage=='post' and item.edge:
            self.coverage.random_transactions+=int(item.random)
            event=m.step(p)
            if event['clear'] is None:
                assert m.initialized,'Reset is required before traffic'
                if event['accepted']:self.pending=None
                if event['consumed']:
                    read=event['consumed']
                    assert item.pre.ports['o_rsp_valid']=='1' and item.pre.ports['o_rsp_rdata']==read.data and item.pre.ports['o_rsp_tag']==read.tag,'Consumed-response ordering assertion failed'
                    assert m.edge>read.due,'Response consumed before maturity assertion failed'
            self.coverage.record(event,p,item,m)
        if m.initialized:
            self.outputs(p)
            if c.check_internals:
                for name,expected in (m.internals()|m.backend(p)).items():
                    assert obs.internals[name]==expected,f'SRAM storage/backend assertion failed: {name}: {obs.internals[name]} != {expected}'
            m.conservation()
        self.coverage.observe(obs,m)

    def check_phase(self):
        self.model.conservation()
        assert not self.model.reads and self.pending is None,'Campaign left a read or request pending'
