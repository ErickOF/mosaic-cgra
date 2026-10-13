"""Directed reset/boundary cases and seeded independent-clock traffic."""

import random
from pyuvm import uvm_sequence

from mosaic_uvm.logic import bits
from async_fifo.transaction import AsyncFifoItem, CHAINS


class AsyncFifoSequence(uvm_sequence):
    def __init__(self, config):
        super().__init__("async_fifo_sequence")
        self.config = config
        self.rng = random.Random(config.seed)
        self.inputs = dict(i_w_clk=0, i_r_clk=0, i_w_rstb=0, i_r_rstb=0,
                           i_w_valid=0, i_r_ready=0, i_w_data="0" * config.width)
        self.last = None
        self.pending = False
        self.words = 0

    def word(self):
        width = self.config.width
        index = self.words
        self.words += 1
        if index % 11 == 0:
            return "x" * width
        if index % 11 == 1:
            return "z" * width
        return bits(self.rng.getrandbits(width), width)

    async def send(self, label, *, delay_ps=100, relation="manual", random=False,
                   fault=None, cancellation=False, **changes):
        self.inputs.update(changes)
        item = AsyncFifoItem(label, self.inputs, delay_ps=delay_ps, relation=relation,
                             random=random, fault=fault, cancellation=cancellation)
        await self.start_item(item)
        await self.finish_item(item)
        assert item.observation is not None, "No monitor observation returned"
        self.last = item.observation
        before, after = self.last.before, self.last.after
        push = before.ports["i_w_clk"] == "0" and after.ports["i_w_clk"] == "1" and before.integer("i_w_valid") and before.integer("o_w_ready")
        if push:
            self.pending = False
        return bool(push)

    async def cycles(self, count, *, domains="wr", label="settle", relation="manual"):
        for index in range(count):
            await self.send(f"{label}_{index}_fall", relation=relation, **{f"i_{domain}_clk": 0 for domain in domains})
            await self.send(f"{label}_{index}_rise", relation=relation, **{f"i_{domain}_clk": 1 for domain in domains})

    async def initialize(self, order="w"):
        self.pending = False
        await self.send("coordinated_assert", cancellation=True, i_w_clk=0, i_r_clk=0,
                        i_w_rstb=0, i_r_rstb=0, i_w_valid=0, i_r_ready=0)
        await self.cycles(2)
        await self.send(f"release_{order}", i_w_clk=0, i_r_clk=0, **{f"i_{order}_rstb": 1})
        await self.cycles(self.config.stages + 2, domains=order, label=f"stopped_{'r' if order == 'w' else 'w'}_init")
        assert not self.last.after.integer("o_w_init_done") and not self.last.after.integer("o_r_init_done"), "Stopped/reset peer permitted initialization"
        other = "r" if order == "w" else "w"
        await self.send("release_peer", i_w_clk=0, i_r_clk=0, **{f"i_{other}_rstb": 1})
        await self.cycles(self.config.stages + 3)
        assert self.last.after.integer("o_w_ready") and not self.last.after.integer("o_r_valid"), "Initialization did not reach empty operational state"

    async def traffic(self, events, *, relation="relatively_prime", write=1.0, read=1.0,
                      run_w=True, run_r=True, accept_limit=None, random=False):
        """Schedule clocks independently; endpoints change only on local falls.

        Source records remain pending until an observed write handshake. The
        random campaign therefore preserves the producer's stall obligation.
        """
        halves = {"write_faster": (40, 100), "read_faster": (100, 40),
                  "equal_drift": (100, 100), "relatively_prime": (70, 110),
                  "random_periods": (60, 90)}[relation]
        periods = dict(zip("wr", halves))
        # Withdraw an already accepted word before the first new rising edge;
        # preserve an outstanding word even when the next block stops sourcing.
        await self.send("clock_phase_setup", relation=relation, i_w_clk=0, i_r_clk=0,
                        i_w_valid=int(self.pending))
        next_edge = {domain: periods[domain] + (30 if domain == "r" else 0)
                     for domain, running in zip("wr", (run_w, run_r)) if running}
        assert next_edge
        elapsed, accepted = 0, 0
        for index in range(events):
            event_time = min(next_edge.values())
            changes = {}
            for domain in tuple(next_edge):
                if next_edge[domain] != event_time:
                    continue
                level = 1 - self.inputs[f"i_{domain}_clk"]
                changes[f"i_{domain}_clk"] = level
                if not level:
                    if domain == "w" and not self.pending:
                        valid = (accept_limit is None or accepted < accept_limit) and self.rng.random() < write
                        changes["i_w_valid"] = int(valid)
                        changes["i_w_data"] = self.word()
                        self.pending = bool(valid)
                    elif domain == "r":
                        changes["i_r_ready"] = int(self.rng.random() < read)
                duration = periods[domain]
                if relation == "random_periods":
                    duration = self.rng.randrange(4, 16) * 10
                elif relation == "equal_drift" and not level:
                    duration += self.rng.choice((-10, 0, 10))
                next_edge[domain] += duration
            accepted += await self.send(f"{'random' if random else 'traffic'}_{index}",
                                        delay_ps=event_time - elapsed, relation=relation, random=random, **changes)
            elapsed = event_time

    async def fill(self, relation="relatively_prime"):
        await self.traffic(self.config.latency_budget, relation=relation, write=1, read=0,
                           accept_limit=self.config.depth)
        assert self.last.after.integer("o_w_full"), "Continuous source did not fill FIFO"
        assert not self.pending, "Fill offered more than DEPTH records"

    async def drain(self, relation="relatively_prime", *, stopped_writer=False):
        await self.traffic(self.config.latency_budget, relation=relation, write=0, read=1, run_w=not stopped_writer)
        assert self.last.after.integer("o_r_empty"), "Fair clocks/ready failed to drain FIFO"

    async def write_one(self, word):
        # A preceding pop frees space only after its pointer crosses into the
        # writer. In particular, depth two can require a boundary bubble here.
        for _ in range(self.config.stages + 2):
            if self.last.after.integer("o_w_ready"):
                break
            await self.cycles(1)
        assert self.last.after.integer("o_w_ready"), "Freed space never reached writer with fair clocks"
        await self.send("write_prepare", i_w_clk=0, i_r_clk=0, i_w_valid=1, i_r_ready=0,
                        i_w_data=bits(word, self.config.width))
        self.pending = True
        accepted = await self.send("write_accept", i_w_clk=1)
        assert accepted, "Expected write was blocked"
        await self.send("write_complete", i_w_clk=0, i_w_valid=0)

    async def pop_one(self):
        await self.send("read_prepare", i_w_clk=0, i_r_clk=0, i_w_valid=0, i_r_ready=0)
        await self.cycles(self.config.stages + 2)
        assert self.last.after.integer("o_r_valid"), "Accepted write never became visible with fair clocks"
        await self.send("read_fall", i_w_clk=0, i_r_clk=0, i_r_ready=1)
        await self.send("read_accept", i_r_clk=1)
        await self.send("read_complete", i_r_clk=0, i_r_ready=0)

    async def address_cross(self):
        # Rotate the read address, then fill and drain at every rotation. This
        # explicitly closes the specification's write-address/read-address cross.
        for offset in range(self.config.depth):
            await self.initialize("r" if offset % 2 else "w")
            for index in range(offset):
                await self.write_one(index % (1 << self.config.width))
                await self.pop_one()
            for _ in range(self.config.depth):
                await self.write_one(self.word())
            await self.cycles(self.config.stages + 2)
            for _ in range(self.config.depth):
                await self.pop_one()

    async def skew_and_recovery(self, domain):
        peer = "r" if domain == "w" else "w"
        await self.initialize(domain)
        await self.write_one(self.word())
        await self.cycles(self.config.stages + 3)
        await self.send(f"reset_skew_unexpected_{domain}", cancellation=True, i_w_clk=0, i_r_clk=0,
                        i_w_valid=0, i_r_ready=0, **{f"i_{domain}_rstb": 0})
        await self.cycles(self.config.stages + 3)
        assert not self.last.after.integer(f"o_{peer}_init_done"), "Peer did not observe unilateral reset"
        await self.send(f"reset_skew_release_{domain}", i_w_clk=0, i_r_clk=0, **{f"i_{domain}_rstb": 1})
        await self.cycles(2 * self.config.stages + 4)
        assert not self.last.after.integer("o_w_init_done") and not self.last.after.integer("o_r_init_done"), "One-sided release resurrected a stale epoch"
        await self.send(f"reset_skew_assert_{peer}", i_w_clk=0, i_r_clk=0, **{f"i_{peer}_rstb": 0})
        await self.initialize(peer)
        await self.write_one(self.word())
        await self.pop_one()

    async def coincident_transfers(self):
        # One queued, locally visible record leaves both endpoints available,
        # including at depth two with longer synchronization pipelines.
        await self.initialize()
        await self.write_one(self.word())
        await self.cycles(self.config.stages + 2)
        assert self.last.after.integer("o_w_ready") and self.last.after.integer("o_r_valid")
        await self.send("coincident_prepare", i_w_clk=0, i_r_clk=0, i_w_valid=1,
                        i_w_data=self.word(), i_r_ready=1)
        self.pending = True
        assert await self.send("coincident_transfer", i_w_clk=1, i_r_clk=1)
        await self.send("coincident_complete", i_w_clk=0, i_r_clk=0, i_w_valid=0, i_r_ready=0)
        await self.pop_one()

    async def faults(self):
        await self.initialize()
        if self.config.probe:
            name, value = self.config.probe.rsplit(":", 1)
            if name in CHAINS:
                await self.send("illegal_final_stage", fault=(name, self.config.stages - 1, value))
            else:
                await self.send("illegal_control", **{name: value})
            raise AssertionError("Illegal stimulus did not trigger its live assertion")
        for name in CHAINS:
            for value in "xz":
                await self.send("first_stage_inject", i_w_clk=0, i_r_clk=0, fault=(name, 0, value))
                await self.send("first_stage_restore")

    async def body(self):
        if self.config.probe:
            await self.faults()
            return
        await self.initialize("r")
        if self.config.check_internals:
            await self.faults()
        await self.coincident_transfers()
        for relation in ("write_faster", "read_faster", "equal_drift", "relatively_prime", "random_periods"):
            await self.initialize()
            await self.fill(relation)
            # A full FIFO must hold an independently offered producer record.
            await self.traffic(4 * self.config.stages + 20, relation=relation, write=1, read=0)
            await self.drain(relation)
            await self.traffic(12 * self.config.latency_budget, relation=relation, write=1, read=1)
            await self.drain(relation)
        await self.address_cross()
        for domain in "wr":
            await self.initialize(domain)
            if domain == "w":
                await self.fill()
                await self.traffic(self.config.latency_budget, write=0, read=1, run_w=False)
                assert self.last.after.integer("o_r_empty"), "Stopped writer prevented draining visible data"
            else:
                await self.traffic(self.config.latency_budget, write=1, read=0, run_r=False, accept_limit=self.config.depth)
                assert self.last.after.integer("o_w_full"), "Stopped reader permitted overwrite or blocked filling"
            await self.send(f"stopped_{domain}_hold", delay_ps=10000)
            await self.drain()
            await self.skew_and_recovery(domain)
        for level in (0, max(1, self.config.depth // 2), self.config.depth):
            await self.initialize()
            for _ in range(level):
                await self.write_one(self.word())
            await self.cycles(self.config.stages + 3)
            await self.initialize("r")
        await self.traffic(self.config.random_cycles, relation="random_periods", write=0.8, read=0.6, random=True)
        await self.drain()
        await self.send("final_idle", i_w_valid=0, i_r_ready=0)
