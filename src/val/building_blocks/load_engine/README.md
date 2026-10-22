# Ordered load engine RTL and PyUVM validation

[`load_engine.sv`](../../../rtl/building_blocks/load_engine.sv) implements the
[ordered load-engine specification](../../../../../specs/building-blocks/mosaic-load-engine/README.md).
One descriptor owns the engine. Requests allocate sequential circular tags;
responses can arrive in any order; stream acceptance releases only the oldest tag.

## Run

```sh
make setup
make load-engine-regression                    # Requires VCS and its license
make load-engine-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=load_engine
```

The test is the decorated `test_load_engine.LoadEngineTest`. Its test, environment,
agent, sequencer, driver, monitor, reference model, scoreboard and coverage files
follow the other building-block suites. `mosaic_uvm` supplies common wiring and
regression execution, JUnit identity checks and evidence handling.

The regression has **80 profiles** and **48 strict invalid-parameter checks**:

- 32/64-bit addresses, 32/64/128-bit data, capacities 1/2/3/4/8/16, both resets.
- One-bit addresses, one-byte elements, odd 24-bit data and narrow metadata.
- Exact default geometry with both reset styles.

Every profile runs 2000 seeded random cycles plus directed traffic. Set
`LOAD_ENGINE_SEED`, `LOAD_ENGINE_RANDOM_CYCLES` (minimum 1000) and
`LOAD_ENGINE_REGRESSION_BUILD` to override the campaign. The seed advances by
profile index. The runner checks parameters, actual port widths, mandatory goals,
ownership accounting and the identity of the one test that ran. Select profiles:

```sh
.venv/bin/python src/val/building_blocks/load_engine/run_load_engine_regression.py \
  --sim icarus --build-dir build/load-engine-selected \
  --case w32_d128_c16_e16_n8_r0_m0
```

Custom direct runs must pass matching compiler parameters and
`LOAD_ENGINE_<PARAMETER>` environment variables. Icarus accepts
`-Pload_engine.PARAMETER=value`; VCS accepts `-pvalue+load_engine.PARAMETER=value`.
Use a fresh build directory when changing parameters. Regression builds depend on
the parameter file automatically.

The HDL checker and private storage checks are enabled by default. A public-port
RTL run is available for simulators without private hierarchy access:

```sh
LOAD_ENGINE_CHECK_INTERNALS=0 LOAD_ENGINE_HDL_ASSERTIONS=0 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=load_engine
```

That mode omits private payload checks and AGU runtime-fault injection and reports
them as `NOT_RUN`. The driver uses nominal 10 ns clock opportunities and 1 ps
observation ticks. These tests require zero-delay RTL (`TEST_SETTLE_NS=0`); they do
not qualify SDF-annotated gate simulation.

## Reuse and storage

The engine instantiates the existing `agu`, with `i_is_write=0`, for all issued
addresses. The existing `dma_engine_bounds` helper checks the entire affine
rectangle, including the final element's bytes, before the descriptor reaches the
AGU. Both helpers use existing repository-local packages. Common DFFs, counters,
decoders and operand-isolation blocks provide storage, occupancy, tag decoding and
invalid-output clamps. No existing common RTL is changed.

The reorder table uses separately enabled DFF banks because an ordinary FIFO cannot
accept arbitrary tagged response writes. Metadata writes only on an accepted
request. Response payload writes only on a first legal response for an allocated
tag. Neither payload bank resets; reset clears allocated/response-present flags,
pointers, occupancy and command state. Empty and invalid public payloads are zero.
The PyUVM checker verifies every payload capture and every unqualified hold.

Derived tag width is at least one, including capacity one. Pointers use explicit
modulo-capacity terminal comparisons, so non-power-of-two capacities issue no spare
encoding. Request valid deasserts when a cycle starts full, even if a beat retires
on that edge. At nonfull occupancy, allocation and retirement can coincide.

## Descriptor and stream behavior

All descriptor fields must be known, including unused strides. Mode, counts,
element size, alignment and full sequence range are checked before issuance.
Invalid descriptors are consumed with sticky fatal error and one failed-command
event; they generate neither a start event nor memory traffic. Error clear must be
known low for descriptor readiness.

A request consumes an AGU address on exactly the same edge that memory accepts
the request. Its tag remains allocated until stream acceptance, through arbitrary
response latency, response permutation and stream backpressure. Responses must
arrive no earlier than the cycle after request acceptance. A same-edge response
for a previously unallocated tag is malformed even if that tag is allocated on
the edge. A response received for an already completed entry is a duplicate even
if its stream beat retires on the same edge.

The stream head uses metadata saved with its request. Successful data is masked
to the requested low-order bytes; failed reads emit zero data with the same byte
mask and markers. Memory-read errors are ordered and nonfatal. The accumulated
memory-error flag is held through completion and cleared on the next consumed
descriptor. `completed_with_error` is asserted only with normal completion.

The engine can accept request, response and stream transfers on the same edge.
The table has no response-to-stream combinational bypass: a response first makes
its slot eligible after capture. Completion occurs only when the final ordered
stream beat is accepted. Consecutive transfers can produce consecutive asserted
event cycles; stalled interfaces do not generate repeated transfer events.

## Fatal drain, reset and knownness

Malformed responses are consumed and discarded because response ready is high
whenever reset is known inactive. The first fatal classification is sticky. Future
requests stop, allocated slots remain owned, expected responses continue to fill,
and ordered stream beats continue to retire. Failure pulses after all owned slots
drain. An unsolicited idle response sets fatal error without a failed-command
event. Clearing error while busy has no effect.

A fatal command resets only its private AGU, aborting the unissued tail. The AGU
reset comes from the registered sticky-error state and external reset, never from
a combinational protocol detector. Reorder ownership and payloads are unaffected
by this local abort. Clearing fatal error after drain releases the AGU for a new
descriptor. No address is discarded by advancing the AGU without a memory request.

Upfront range validation makes ordinary runtime AGU range faults unreachable for
accepted descriptors. Private verification-only injection checks the runtime
failure path after zero, one and several issued reads. It does not weaken the
descriptor checks or modify the AGU implementation.

Within a cycle, malformed response takes priority over descriptor and runtime AGU
faults; an already sticky error always wins. A fatal event concurrent with final
retirement produces failure instead of normal completion. A legal configuration
concurrent with an unsolicited response can report start and immediate failure.
Normal request stability is qualified by the absence of a fatal abort; stream
stability is preserved throughout fatal drain.

Unknown ready/valid values cannot create transfers. Unknown descriptor fields are
rejected; unknown response tag/error is fatal. Successful response data must be
known in the normal memory peer; failed-read data may be unknown and still emits
zero. X/Z reset freezes architectural state and clamps ready/valid/event outputs.
Both reset styles recover on known reset. Asynchronous deassertion must be
synchronized externally.

Memory return, request readiness and stream readiness are fair-environment
assumptions for eventual completion. There is no timeout or local cancellation.
Quiescence requires busy low, occupancy zero and no stream beat. Error must also be
clear for `o_idle`. Resetting an active engine requires coordinated adapter reset
so stale responses cannot collide with reused tags; this contract has no epochs.

## Local error and counter encodings

[`load_engine_pkg.sv`](../../../rtl/building_blocks/load_engine_pkg.sv) defines
four-bit error enums. Modes retain `agu_pkg` values: linear 0, strided 1D 1,
strided 2D 2, reserved 3. No external `mosaic-contracts` artifact or dependency
manifest is introduced.

| Error | Code |
| --- | ---: |
| None | 0 |
| Reserved mode | 1 |
| Zero inner count | 2 |
| Zero outer count | 3 |
| 1D outer count other than one | 4 |
| Unsupported element size | 5 |
| Base alignment | 6 |
| Inner stride alignment | 7 |
| Outer stride alignment | 8 |
| Unknown descriptor field | 9 |
| Full descriptor address range | 10 |
| Runtime AGU failure | 11 |
| Tag outside table | 12 |
| Unallocated tag | 13 |
| Duplicate response | 14 |
| Unknown response control | 15 |

[`load_engine_counters.sv`](../../../rtl/building_blocks/load_engine_counters.sv)
is an optional, bindable instrumentation block. It has explicit enable/clear,
saturating counters and a maximum-occupancy register. It adds no functional ports
or state to an uninstrumented engine. Supply a qualified event vector, accepted
stream-byte count (`popcount(keep)`) and current occupancy. Its index enum is in
`load_engine_pkg`; count `n` occupies `o_counts[n*WIDTH+:WIDTH]`:

| Index | Count |
| --- | --- |
| 0–2 | Commands started, completed, failed |
| 3–5 | Read requests, read responses, stream beats accepted |
| 6 | Request valid with known-low ready |
| 7 | Allocated oldest slot waiting for its response |
| 8 | Stream valid with known-low ready |
| 9 | Cycles at maximum occupancy |
| 10 | Legal memory responses with read error |
| 11 | Malformed response events |
| 12 | Accepted stream bytes |

`i_enable=0` suppresses event, clear, byte and peak updates; reset still clears all
counters. The native checker instantiates enabled and disabled copies and checks
their counters against observed events. Byte counts use a full-width saturating
sum. Counter width and collection windows are integration choices; the descriptor
byte-count width is `2*COUNT_WIDTH + log2(MAX_ELEMENT_BYTES)`.

## Verification scope and remaining release checks

The independent Python reference calculates addresses from row/column coordinates,
validates mathematical rectangle corners and tracks an ordered deque with tagged
responses. A separate memory peer owns transactions from observed request through
observed stream retirement. Neither predicts ordering from DUT storage.

Directed tests cover every mode/element size, signed and zero strides, full tables,
reverse responses, head blocking, prolonged stalls, simultaneous transfers, tag
wrap, first/middle/final memory errors, malformed/duplicate/early responses, first
fatal priority, drain/recovery, coordinated reset and X/Z controls. Random request
backpressure, response latency/permutation and stream backpressure are independent;
mandatory random-only goals check stalls, reordering and wrap where reachable.

The passive monitor samples actual pre-NBA edges, settled outputs and held cycles.
The scoreboard checks all public outputs and the conservation equation
`accepted = delivered + reset_discarded + outstanding`. Private checks cover slot
ownership, stored-response flags, metadata/data captures and inactive-bank holds.
The native HDL checker independently checks ownership, allocation, response writes,
AGU advancement, retirement, completion/drain, error data, events and counters.

Campaigns record actual JUnit results, seeds, parameters, goals, simulator logs and
RTL/dependency/verification hashes. Native simulation assertions are not formal
proofs. Formal, licensed commercial lint/CDC/RDC/DFT/LP, technology synthesis,
physical implementation, PrimeTime and PrimePower remain separate release checks
and are reported as `NOT_RUN` when unavailable. No physical or power result is
claimed by this functional RTL validation.
