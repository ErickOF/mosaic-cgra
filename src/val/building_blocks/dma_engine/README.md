# DMA engine PyUVM validation

This suite implements self-checking validation of the
[DMA specification](../../../../../specs/building-blocks/mosaic-dma-engine/README.md)
against `src/rtl/building_blocks/dma_engine.sv`. It uses the test, environment,
agent, sequencer, driver, monitor, reference model, scoreboard and coverage
structure shared by the other MOSAIC suites. Python 3.10 or newer is required;
local qualification uses Python 3.12, cocotb 2.1 and PyUVM 5.0.

## Running

```sh
make dma-engine-regression                     # VCS installation/license required
make dma-engine-regression SIM=icarus          # native four-state RTL
make pyuvm SIM=icarus COCOTB_TOPLEVEL=dma_engine # default hardware parameters
```

Configure `DMA_ENGINE_SEED`, `DMA_ENGINE_RANDOM_CYCLES` (at least 1000) and
`DMA_ENGINE_REGRESSION_BUILD`. `DMA_ENGINE_JOBS` sets profile parallelism from
1 to 32, defaulting to 4 for Icarus and 1 for VCS. The regression runs 25 profiles: all 16 event-start,
cancellation, command-parity and reset combinations; four channel/depth/data-width
geometries with both resets; and a non-power-of-two queue profile. Channel counts
are 1, 2, 3, 4 and 8; data widths are 32, 64, 128 and 256 bits; address widths
are 8, 32, 40 and 64 bits. Each profile adds 2000 seeded random clock opportunities
to directed stimulus. The runner also requires 111 invalid parameter configurations
to fail elaboration through the explicit parameter guard.

Select profiles with the runner directly:

```sh
.venv/bin/python src/val/building_blocks/dma_engine/run_dma_engine_regression.py \
  --sim icarus --build-dir build/icarus/dma_engine/selected \
  --case core_e1_c1_p1_a0
```

Reports include `summary.json`, per-profile `coverage.json`, `parameters.json`,
JUnit `results.xml` and simulator logs. A passing campaign requires the exact
`test_dma_engine.DmaEngineTest` once per profile, matching parameters/seed/random
count, all mandatory goals and enabled Python private-byte/directory checks.
The runner forces `DMA_ENGINE_HDL_ASSERTIONS=0`; the test verifies that no optional
HDL checker was instantiated. Source, dependency,
verification, shared-helper and Makefile hashes identify the tested revision.
The runner verifies these hashes again before accepting the final result.
Missing simulators or licenses produce `NOT_RUN`.

## Hardware and integration

DMA RTL uses one declaration or assignment per line, lines of at most 100
characters, and spaces after commas. Operators in right-hand expressions have
spaces around them except unary `!` and operators inside selections. Unary `!`
has no padding; slices, array indices and queue accesses stay compact on either
side of an assignment, as in `data[index*WIDTH+:WIDTH] = source[index+1] + offset;`
and `if (!valid[index])`. Declaration dimensions also stay compact. Combinational
and clocked processes use `always_comb` and `always_ff`. The package owns the enums.
Command, completion and event payload structs stay in `dma_engine.sv` because
their field widths depend on module parameters; queue widths use `$bits` of
those local packed types.

The DMA schedules independent channels with registered command queues, one active
command per channel and an elastic copy FIFO. It supports memory-to-memory,
memory-to-stream and stream-to-memory transfers; linear and signed-stride 1D/2D
address patterns; quiescent protection-region updates; immediate/OR/AND starts;
round-robin completion arbitration; atomic completion/event creation; cancellation,
timeouts, drain, coordinated flush and optional command parity.

Existing RTL provides `fifo` for command/data/completion/event storage,
`round_robin_arbiter` and its `priority_encoder` dependency for retirement,
`counter` for transfer/cancel timing, `dff` for accepted descriptors and ID-directory entries,
`operand_isolation` for inactive data and affine arithmetic, and `parity` for
protected command storage. The command queue shares a common `decoder` across its
ID/context directory banks and uses `write_gate` to suppress payload writes during
reset. Directory payload remains unreset; reset clears the occupancy that qualifies
duplicate and cancellation comparisons. These blocks use the existing clock and
clock enables. `dma_engine_bounds.sv` validates the complete affine
rectangle and element footprint using extended signed arithmetic before any
backend work. Load/store engines generate addresses from the forwarded descriptors;
instantiating an AGU inside the DMA would duplicate that backend responsibility.

The existing `load_engine` and `store_engine` RTL are separate backend modules;
the DMA exposes descriptor, stream and completion interfaces to connect them.
The Python peers used here are independent
protocol models, with randomized descriptor readiness, data latency, independent
store acceptance/commit delays and cancellation acknowledgements. They do not
establish integration with a real memory system.

The following ports extend the specification's tables to carry information needed
by its behavior. Packed channel slices use `channel * field_width +: field_width`.

| Port | Per-channel width | Contract |
| --- | --- | --- |
| `i_store_bytes_committed` | `BYTE_COUNT_WIDTH` | Cumulative committed bytes for the currently armed store descriptor; not merely accepted stream bytes. Start at zero, increase monotonically, and hold the final value through matching store done or cancel done. It cannot exceed bytes handed to the store. |
| `i_load_stream_epoch` | `DESCRIPTOR_EPOCH_WIDTH` | Epoch of each load beat, held with that beat during stalls. Stale/unknown epochs are rejected and reported without updating live progress. |
| `o_load_priority` | `PRIORITY_WIDTH` | Captured command priority with the load descriptor. |
| `o_store_priority` | `PRIORITY_WIDTH` | Captured command priority with the store descriptor. |

`BYTE_COUNT_WIDTH = 2 * COUNT_WIDTH + log2(DATA_WIDTH / 8) + 1`.
Store counts are sampled only on matching store completion or cancel completion.
Cancellation may discard accepted but uncommitted stores; already committed writes
are never rolled back. Backend cancel acknowledgements must follow actual safe
teardown. Normal completion simultaneous with flush acceptance also proves that
peer idle before the descriptor epoch changes. Old-epoch completion after that
boundary cannot release a current peer. Coordinate backend reset with DMA reset;
an epoch alone cannot protect arbitrary stale traffic after wraparound.

Queued cancellation marks an ordered tombstone. The entry retains its occupancy
slot until reaching the head, then produces a zero-byte canceled completion without
starting a backend. This preserves per-channel completion order; cancellation does
not immediately free a queue slot. Active cancellation gates new transfers, discards
buffered copy data, latches each peer's acknowledgement independently and reports
true partial progress. Cancellation timeout is fatal and requires reset.

The transfer timer counts from the first descriptor presentation, including a
stalled presentation. Success wins on its terminal edge; otherwise the configured
boundary begins cancellation. The cancel timer starts on entry to cancellation.
Its deadline applies to backend acknowledgement; safely discarding an internal
FIFO can continue afterward. The timer holds in fatal state. A quiescent error
clear acknowledges the previous error while retaining a new error on that edge.
Flush advances the epoch once per assertion, suppresses ordinary completions and
empties queues through normal pops while safely canceling armed peers. Protection
configuration survives flush and is disabled by reset.

Control, pointers, counts, errors and pulses reset; payload and descriptor storage
remain unreset and are isolated while invalid. Both synchronous and asynchronous
reset styles are supported. Keep handshake/reset controls known. Unknown required
command, region and backend fields fail closed; unknown ignored command fields are
normalized before parity capture. Legal active payload bytes may contain X/Z.

`dma_engine_pkg.sv` supplies repository-local transfer, start, status, error and phase
enums, following the preceding MOSAIC modules. No external contracts package or
dependency manifest is required. Transfer modes are 0/1/2 in the order above;
start modes are 0 immediate, 1 OR, 2 AND; statuses are 0 success, 1 error,
2 canceled, 3 flushed. Coordinated flush suppresses ordinary completion creation,
so it emits no per-command flushed status. Error codes are defined in the package;
the first command and engine error are retained. Optional software counter banks
and aggregate flush-count reporting are outside this implementation's interface.

## Verification mapping

The reference model uses Python integers and all four rectangle corners for legality.
Independent backend descriptor expansion and address-derived payload patterns detect
address/stride/space mistakes. The scoreboard tracks accepted commands, active
ownership, every source and sink beat, accepted bytes, committed bytes, completion
and event queues. Acceptance must be conserved across completions and explicit
reset/flush discards. Stale responses cannot alter private byte counts. Completion
records are matched by channel and submission order, including canceled entries.

Directed tests cover every channel/direction/address mode/element size, signed and
zero strides, complete affine bounds, protection failures, overlapping copies,
region/context/stream/priority extremes, burst limits, event-mask populations,
queue pressure, simultaneous copy push/pop, all-channel concurrency, malformed
framing at every position of a three-element command, source/write/backend errors,
zero/partial/full committed cancellation, stale data/done epochs, timeout recovery,
flush at arm/data/held-output boundaries, reset during idle/arm/data, clockless reset,
ignored/required X/Z fields, active X/Z payloads and protected command faults.
Large maximum count products run a bounded descriptor prefix followed by flush;
the suite does not claim to complete billions of transfers.

Regression cases also acknowledge cancellation on its final allowed edge while
copy data remains buffered, and collide error clear with an unexpected backend
completion. The buffered-deadline goal applies when the FIFO can retain data at
that edge; smaller FIFOs necessarily empty first. All profiles check the new-error
priority. Python assertions check that the fatal cancel timer stops advancing.

The monitor samples actual pre-NBA rising-edge ports, settled pre/post-edge ports
and held intervals. Private counter observations assert correspondence to the
independent handshake ledger and detect between-edge updates. Python also checks
descriptor/data stability, destination-first arming, legal transfers, FIFO capacity
and successful completion. Every directory slot in every channel must capture a
command ID/context, and all other slots must retain their previous four-state
payload, including during reset and clockless observations. These comparisons use
public command acceptance and observed storage rather than the directory write
enable as the reference.

All checks in the default run and campaign are Python checks against zero-delay
RTL with `TEST_SETTLE_NS=0` and at least 1 ps precision. The existing optional
`dma_engine_assertions.sv` checker is disabled by default and is outside this
campaign's evidence; it remains available through `DMA_ENGINE_HDL_ASSERTIONS=1`
for a separate direct RTL run.

For an explicit port-only RTL run:

```sh
DMA_ENGINE_CHECK_INTERNALS=0 DMA_ENGINE_HDL_ASSERTIONS=0 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=dma_engine
```

Disabled checks report `NOT_RUN`; private command-memory fault injection is skipped.
These switches do not make the driver timing-aware for SDF simulation.

## Evidence limits

This revision is validated with Python/PyUVM tests and Python-driven parameter
guard probes. The complete default campaign adds 50,000 random clock opportunities
to its directed cases. No lint, formal or synthesis flow is part of this campaign.
Synthesis is deferred to Design Compiler.

VCS execution, CDC/RDC/LP, DFT, sequential equivalence, real load/store integration,
post-route timing and physical power/energy require separate evidence. Their status
remains `NOT_RUN`; this RTL validation is not full physical release signoff.
