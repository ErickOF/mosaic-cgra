# Event/barrier RTL and PyUVM validation

This suite implements the [event/barrier specification](../../../../../specs/building-blocks/mosaic-event-barrier/README.md)
with [`event_barrier.sv`](../../../rtl/building_blocks/event_barrier.sv).
The implementation reuses `counter`, `priority_encoder`, `round_robin_arbiter`,
`fifo`, `decoder`, `dff`, `parity`, and the FIFO/parity operand-isolation paths.

## Run

```sh
make setup
make pyuvm SIM=icarus COCOTB_TOPLEVEL=event_barrier
make event-barrier-regression                    # Requires VCS and its license
make event-barrier-regression SIM=icarus
```

The runner executes the actual decorated `test_event_barrier.EventBarrierTest`
with separate test, environment, agent, sequencer, driver, passive monitor,
independent reference model, scoreboard, and coverage collector. Shared
`mosaic_uvm` components provide the agent wiring and evidence handling.

Configure `EVENT_BARRIER_SEED` (default 20261021),
`EVENT_BARRIER_RANDOM_CYCLES` (default 2000, minimum 1000), and
`EVENT_BARRIER_REGRESSION_BUILD` (default
`build/<simulator>/event_barrier/regression`). Seeds advance by the profile's
index, including when selecting individual cases:

```sh
.venv/bin/python src/val/building_blocks/event_barrier/run_event_barrier_regression.py \
  --sim icarus --build-dir build/event-barrier-selected \
  --case e16_c4_w4_b4_p16_d4_prot0_r0_features111_g4_ctx8_tag8
```

Direct Make runs use the module's default parameters. For custom geometry,
compiler options and `EVENT_BARRIER_<PARAMETER>` environment variables must agree.
Icarus uses `-Pevent_barrier.PARAMETER=value`; VCS uses
`-pvalue+event_barrier.PARAMETER=value`. Select a fresh build directory for direct
runs after changing parameters. The regression runner creates parameter-file
build dependencies and checks every actual DUT port width and parameter.

`EVENT_BARRIER_HDL_ASSERTIONS=1` enables the native verification-only SystemVerilog
checker. It is excluded from synthesis and gate sources. A port-only run is:

```sh
EVENT_BARRIER_CHECK_INTERNALS=0 EVENT_BARRIER_HDL_ASSERTIONS=0 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=event_barrier
```

Parity injection requires private RTL handles and is omitted in port-only runs.
Disabled checks report `NOT_RUN`. This driver uses a 10 ns clock, pre-NBA samples,
and settled zero-delay RTL observations. It does not qualify SDF-annotated gate
simulation or physical timing/power signoff.

## State and atomic scheduling

Event IDs, wait slots, barriers, participants, and packed status use index zero
in the least-significant position. Counts saturate through backpressure; legal
posts never wrap. An empty acknowledgement is consumed and rejected. CLEAR_ALL
explicitly discards all occurrences of the selected event.

Three common round-robin arbiters schedule:

1. Satisfied wait slots, advancing priority only on completed waits.
2. Satisfied-wait versus matching-cancel result creation.
3. External post, external acknowledge, consuming wait, and barrier event posting,
   in that initial priority order.

Internal schedulers use the common arbiter's optional `HOLD_PENDING=0` mode.
Candidates may disappear as other atomic operations change event state. Priority
advances only when the entire selected transaction commits. Existing stream users
retain `HOLD_PENDING=1`, including stalled ownership and lock behavior.

A same-slot cancellation excludes that slot from satisfaction arbitration, even
when the result queue is full. Cancellation of another slot competes fairly with
wait completions. An unmatched or unsupported cancellation produces not-found
and a recoverable error; no result is created. A newly armed wait first becomes
eligible in the next cycle.

There is one event-bank writer per cycle. A consuming ALL wait subtracts one from
each matched count using a single pre-edge snapshot. An observing wait may complete
concurrently with another mutation. A final arrival that posts an event holds ready
low until both release capacity and the mutation grant are available. Queue space
includes a same-edge outgoing transfer. A saturated event can be decremented on
one edge and accept a waiting post on a later edge.

The result and release queues compose common one-entry FIFOs into a ring. Parallel
lane pops implement a synchronous, single-edge flush at every depth, including
asynchronous-reset profiles. Flush is never wired to an asynchronous reset pin.
Only an enqueued lane writes payload; unused data storage is unreset. This
composition adds per-lane FIFO control overhead; technology area/timing comparisons
remain part of later implementation qualification.

Barrier configuration is backpressured while that barrier has arrivals, or a
release record matching its current generation remains queued. This scan handles
generation wrap with outstanding releases. An accepted barrier configuration
excludes arrivals to the same barrier on that edge. Disabling preserves generation.
A policy transfer requires an otherwise idle unit and no other request valid; it
excludes all other input operations on that edge. `o_quiescent` additionally
requires policy valid input to be inactive. Enabled, empty barrier configurations
alone do not prevent idle or quiescence.

## Timing, reset, and protection

| Operation | Uncontended behavior |
| --- | --- |
| Policy, arm, barrier configuration, post, acknowledge, nonfinal arrival | State and outcome pulse update after the handshake edge. |
| Satisfied wait | Can enqueue a result on the first edge after arming. |
| Final arrival | Enqueues release and advances generation on the handshake edge. |
| Result/release delivery | Registered queues become visible after enqueue; earliest consumption is the following edge. |
| Flush | Clears transient state and advances enabled generations on each asserted flush edge. |

With persistent eligible requests, the mutation scheduler services each within
four accepted mutation transactions. Wait-slot priority advances after each
completed wait; result creation alternates between persistent completion and
cancel contenders. Backpressure, missing event occurrences, cancellation priority,
and consumer progress can extend latency; there is no unconditional cycle bound.

Reset removes policy, events, waits, barriers, generations, records, errors and
arbitration state. `ASYNC_RESET` selects asynchronous assertion; integration must
synchronize release. Flush preserves policy and barrier configuration, discards
both queues without producing records, clears recoverable errors, and advances
every enabled generation modulo its width. Fatal state errors freeze architectural
updates, including flush, and require reset.

`PROTECT_STATE=1` adds even parity to policy, every wait and barrier entry, event
counts, generations, queue metadata, and occupied queued payloads. A mismatch
blocks all new handshakes immediately and latches fatal state error on the next
edge. Inactive slots are checked as well. Parity detects odd-bit corruption; it
is not an ECC correction guarantee. Protection sidecars are absent when disabled.
Arrived-mask subset checks and unknown count/generation checks remain enabled.

Unknown fields reject the addressed request without changing its architectural
state. Unknown valid, flush, error-clear, reset, or output-ready controls freeze
handshakes; the checker records X/Z injection and verifies known safe outputs.
Unknown reset is kept from entering the reusable DFF banks; enables still require
a known deasserted reset. Invalid result/release payloads and metadata are zero.

## Local encodings

[`event_barrier_pkg.sv`](../../../rtl/building_blocks/event_barrier_pkg.sv) is the
repository-local baseline, following the other building-block packages. No external
`mosaic-contracts` package or dependency manifest is introduced.

| Field | Encoding |
| --- | --- |
| Wait mode, 2 bits | ANY = 0, ALL = 1; 2/3 rejected. |
| Acknowledge mode, 2 bits | ACK_ONE = 0, CLEAR_ALL = 1; 2/3 rejected. |
| Result status, 1 bit | Satisfied = 0, canceled = 1. |
| Error code, 4 bits | None 0; policy 1; post 2; acknowledge 3; wait 4; cancel 5; barrier configuration 6; arrival 7; duplicate 8; stale generation 9; unknown interface control 10; fatal state 11. |

Sticky recoverable status preserves the first error until quiescent error-clear
or flush. Concurrent errors use deterministic priority: unknown interface control,
arrival (stale before duplicate), barrier configuration, cancel, wait, acknowledge,
post, policy. Fatal corruption overrides recoverable status. Invalid request fields
are classified by their request channel; unknown interface controls have code 10.

## Campaign and qualification scope

The 44-profile matrix covers 1/2/3/4/16/32/64 events, count widths 1/2/4/8,
1/2/3/4/8 wait slots and barriers, 1/2/3/4/5/16/32/64 participants, depths 1/2/3/4,
both reset styles, protected/unprotected state, generation widths 2/4, narrow and
default tags/owners, and every combination of consume/cancel/barrier-event features.
Each profile has 2000 random cycles plus directed tests. The runner also checks
68 invalid parameter combinations at elaboration.

Directed checks cover every event ID at every count through saturation, every ANY
winner, every slot/barrier/participant, small ALL arrival permutations, dense forward
and reverse ALL waits, observing/consuming waits, concurrent satisfied slots,
cancellation before and after satisfaction, full queues, stable backpressure,
release-event saturation, generation wrap, disabled and wrong-owner accesses,
invalid modes, coordinated live flush/reset, mutation contention, and X/Z fields.
Protected profiles inject parity faults separately into policy, counts, waits,
barriers, generations and queue metadata, then verify fatal freeze and reset recovery.

All permutations of up to three ALL-wait events are enumerated. Larger wait/barrier
permutation spaces and all possible participant-mask shapes are sampled, not
exhausted. Duplicate arrivals are structurally unreachable with one participant:
its first legal arrival is final and advances generation. That profile omits the
duplicate bin while still checking stale arrivals and generation release.

The model uses Python integer occurrence ledgers, wait masks, barrier sets, ordered
record lists, and circular service-order lists. It predicts every public output
from observed input values and prior reference state. The monitor samples actual
signals before NBA, after the edge, and while held. The separate HDL checker checks
atomic counter arithmetic, matching/consumption, one writer, generation/release
correspondence, queue occupancy, output stability, reset and event pulses.

`summary.json`, actual JUnit results, simulator logs, `parameters.json`, and
`coverage.json` accompany each campaign. Reports include exact RTL, dependency and
verification hashes. Unavailable tools report `NOT_RUN` instead of passing.
Formal safety/liveness proofs, exhaustive release coverage, commercial lint/CDC/RDC,
DFT/low-power checks, technology synthesis and physical timing/power signoff remain
separate release requirements. This functional suite does not claim full physical
or commercial signoff.
