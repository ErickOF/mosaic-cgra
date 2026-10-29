"""Focused PyUVM control checks with explicit tagged Python cluster responders.

These responders qualify rollback and timeout logic only. The separate array
integration tests instantiate actual clusters, NoC routers, TNIs and SRAM banks.
"""
import sys
from pathlib import Path
sys.path[:0] = [str(Path(__file__).resolve().parents[2]),
               str(Path(__file__).resolve().parents[3]/'gen/array')]
import cocotb
from cocotb.triggers import Event
from pyuvm import ConfigDB, test, uvm_test, uvm_sequence
from cluster.transaction import ClusterItem
from mosaic_uvm.components import VerificationEnv
from mosaic_blocks.array.agent import ArrayAgent
from mosaic_blocks.array.scoreboard import ArrayScoreboard
from mosaic_blocks.array.coverage import ArrayCoverage
from mosaic_blocks.array.config import ArrayConfig
from generate import cluster


class ControlCoverage(ArrayCoverage):
    def build_phase(self):
        super().build_phase()
        self.goals = dict.fromkeys(('runtime_exact_once', 'runtime_held', 'rollback',
            'all_rejected', 'partial_commit', 'timeout', 'tag_integrity', 'sticky_integrity', 'fault_before_fanout'), False)


class ControlEnv(VerificationEnv):
    agent_type = ArrayAgent
    scoreboard_type = ArrayScoreboard
    coverage_type = ControlCoverage


class ControlSequence(uvm_sequence):
    def __init__(self, c, coverage):
        super().__init__('array_control_cases')
        self.c, self.coverage = c, coverage
        self.p = {n: 0 for n, (direction, _) in c.ports.items() if direction == 'input' and n != 'i_clk'}
        self.pending, self.calls = {}, []
        self.reject = set()
        self.bad_tag = False
        self.commit_fault = False
        self.race = False
        self.tag = self.index = 0

    async def step(self, fault=None, **changes):
        self.p.update(changes)
        self.p.update(i_cluster_response_valid=sum(1<<c for c in self.pending),
            i_cluster_response_command=sum(r[0] << (c*4) for c, r in self.pending.items()),
            i_cluster_response_tag=sum(r[1] << (c*16) for c, r in self.pending.items()),
            i_cluster_response_error=sum(r[2] << (c*8) for c, r in self.pending.items()))
        item = ClusterItem(f'control_{self.index}', self.p, fault)
        self.index += 1
        await self.start_item(item)
        await self.finish_item(item)
        pre = item.pre
        for c in tuple(self.pending):
            if pre['o_cluster_response_ready'] >> c & 1: del self.pending[c]
        if pre['i_rstb']:
            for c in range(2):
                if pre['o_cluster_valid'] >> c & 1 and pre['i_cluster_ready'] >> c & 1:
                    command = pre['o_cluster_command']
                    self.calls.append((c, command))
                    self.pending[c] = (command, pre['o_command_tag']+int(self.bad_tag and c == 1),
                                       int(command == 1 and c in self.reject))
        self.last = item.post
        return item

    async def reset(self):
        self.p.update(dict.fromkeys(self.p, 0)); self.pending.clear(); self.calls.clear()
        self.reject.clear(); self.bad_tag = self.commit_fault = self.race = False
        for _ in range(3): await self.step()
        for _ in range(4): await self.step(i_rstb=1, i_cluster_ready=3,
            i_cluster_commit_ready=3, i_cluster_prepared=3, i_cluster_quiescent=3,
            i_network_idle=1, i_network_configured=1, i_events_empty=1, i_runtime_response_ready=1)

    async def command(self, command, error=0, generation=0):
        self.tag += 1
        item = await self.step(i_runtime_valid=1, i_runtime_command=command,
            i_runtime_owner_id=1, i_runtime_kernel_id=2, i_runtime_array_package_id=3,
            i_runtime_cluster_mask=3, i_runtime_allocation_generation=generation,
            i_runtime_execution_epoch=0, i_runtime_context_id=0,
            i_runtime_local_package_ids=11 | 12<<32, i_runtime_context_versions=(1<<192)-1,
            i_runtime_mapping_variant=0, i_runtime_qos_profile=0, i_runtime_power_profile=0,
            i_runtime_flags=0, i_runtime_tag=self.tag, i_runtime_response_ready=0)
        assert item.pre['o_runtime_ready']
        self.p['i_runtime_valid'] = 0
        if self.race: self.p['i_network_error'] = 1
        for _ in range(100):
            if item.post['o_runtime_response_valid']: break
            if self.commit_fault and item.post['o_cluster_commit_valid']:
                self.p.update(i_cluster_commit_complete=1, i_cluster_commit_error=2)
            item = await self.step()
        else: raise AssertionError('Control response timeout')
        assert item.post['o_runtime_response_error_code'] == error, (command, error, item.post)
        assert item.post['o_runtime_response_cluster_mask'] == 3
        for _ in range(3): await self.step()
        await self.step(i_runtime_response_ready=1)
        await self.step()

    async def body(self):
        await self.reset()
        self.reject = {0, 1}
        await self.command(1, 7)
        assert self.last['o_allocated'] == 0 and self.last['o_fatal'] == 0
        self.coverage.hit('all_rejected')
        await self.reset()
        self.reject = {1}
        await self.command(1, 7)
        assert self.calls == [(0, 1), (1, 1), (0, 9)]
        assert self.last['o_allocated'] == 0 and self.last['o_fatal'] == 0
        self.coverage.hit('rollback')
        await self.reset()
        await self.command(1)
        await self.command(2, generation=1)
        await self.command(3, generation=1)
        self.commit_fault = True
        await self.command(4, 7, 1)
        assert self.last['o_allocated'] == 3 and self.last['o_fatal'] == 3
        assert not self.last['o_running']
        self.coverage.hit('partial_commit')
        await self.reset()
        self.p['i_cluster_ready'] = 0
        await self.command(1, 8)
        assert self.last['o_fatal'] == 3
        self.coverage.hit('timeout')
        await self.reset()
        self.bad_tag = True
        await self.command(1, 12)
        assert self.last['o_fatal'] == 3 and not self.last['o_running']
        self.coverage.hit('tag_integrity')
        await self.reset()
        await self.step(fault=('g_control.u_state.stored', 1))
        await self.step(fault=('release',))
        for _ in range(4): await self.step()
        assert self.last['o_fatal'] == 3 and not self.last['o_runtime_ready']
        self.coverage.hit('sticky_integrity')
        await self.reset()
        self.race = True
        await self.command(1, 7)
        assert not self.calls, 'Fatal target accepted new native work'
        assert self.last['o_fatal'] == 3 and not self.last['o_running']
        self.coverage.hit('fault_before_fanout')
        await self.reset()


@test(timeout_time=100, timeout_unit='ms')
class ArrayControlTest(uvm_test):
    def build_phase(self):
        c = ArrayConfig.from_environment()
        self.c = ArrayConfig(c.artifacts, c.manifest, cluster.ports('array_control', dict(N=2)),
                             c.seed, c.random_cycles, c.coverage_file)
        active = dict(pre=Event(), post=Event(), reset_count=0, fault_mode=False)
        ConfigDB().set(self, 'env.*', 'config', self.c)
        ConfigDB().set(self, 'env.*', 'active', active)
        self.env = ControlEnv('env', self)

    async def run_phase(self):
        self.raise_objection()
        cocotb.top.i_clk.value = 0
        for n, (direction, _) in self.c.ports.items():
            if direction == 'input' and n != 'i_clk': getattr(cocotb.top, n).value = 0
        await ControlSequence(self.c, self.env.coverage).start(self.env.sequencer)
        self.drop_objection()
