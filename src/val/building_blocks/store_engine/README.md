# Ordered store engine RTL and PyUVM validation

[`store_engine.sv`](../../../rtl/building_blocks/store_engine.sv) implements the
[ordered store-engine specification](../../../../../specs/building-blocks/mosaic-store-engine/README.md).
One descriptor owns the engine. Each accepted legal input beat pairs atomically
with one AGU address and one tagged memory write. Responses may arrive in any
order; only ordered retirement releases completion slots and tags.

## Run

```sh
make setup
make pyuvm SIM=icarus COCOTB_TOPLEVEL=store_engine
make store-engine-regression SIM=icarus
make store-engine-regression                    # Requires VCS and its license
```

The decorated test is `test_store_engine.StoreEngineTest`. Test, environment,
agent, driver, monitor, sequence, transaction, model, scoreboard and coverage are
separate Python files. The existing `mosaic_uvm` library supplies agent/environment
wiring, regression execution, JUnit checks and evidence handling. The store model
also reuses the load-engine reference's descriptor mathematics; its store
handshakes, beat validation and completion ledger are independent of the DUT.

The full campaign has **80 profiles**, **49 invalid-parameter checks** and **eight
expected-failure data assertion probes**:

- 32/64-bit addresses, 32/64/128-bit data, capacities 1/2/3/4/8/16, both resets.
- One-bit addresses, one-byte elements, odd 24-bit data and narrow metadata.
- Exact default parameters with each reset style.
- Zero, negative, unknown, unsupported and derived-width-overflow parameters.
- X and Z in an enabled byte, at byte zero and byte 15, with both resets.

Each profile runs directed traffic and 2000 seeded random clock opportunities.
`STORE_ENGINE_SEED` defaults to 20261022 and advances by profile index.
`STORE_ENGINE_RANDOM_CYCLES` must be at least 1000.
`STORE_ENGINE_REGRESSION_BUILD` selects the evidence directory.
`STORE_ENGINE_JOBS` selects 1–32 concurrent simulations: four by default for Icarus
and one for VCS. Each profile has an isolated build directory. Select a subset:

```sh
.venv/bin/python src/val/building_blocks/store_engine/run_store_engine_regression.py \
  --sim icarus --build-dir build/store-engine-selected \
  --case w32_d128_c16_e16_n8_r0_m0
```

Custom direct runs must pass matching compiler parameters and
`STORE_ENGINE_<PARAMETER>` environment variables. Icarus uses
`-Pstore_engine.PARAMETER=value`; VCS uses `-pvalue+store_engine.PARAMETER=value`.
Use a fresh build directory when changing geometry. The regression runner handles
matching parameter flags, environment values and rebuild dependencies.

Private storage checks and the native simulation checker are enabled by default.
For a simulator without private hierarchy access, a public-port run is available:

```sh
STORE_ENGINE_CHECK_INTERNALS=0 STORE_ENGINE_HDL_ASSERTIONS=0 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=store_engine
```

Omitted checks are recorded as `NOT_RUN`; this option is not full qualification.
The full runner always enables them. Tests use zero-delay RTL, nominal 10 ns clock
opportunities and 1 ps observation ticks. `TEST_SETTLE_NS` must be zero.

## RTL reuse and storage

The engine instantiates the existing `agu` with `i_is_write=1`. The existing
`dma_engine_bounds` checks the entire affine descriptor rectangle, including the
bytes of the final element, before issuing any write. Both helpers retain their
repository-local packages. Common `dff`, `counter`, `decoder`, `write_gate` and
`operand_isolation` modules provide state, occupancy, tag decoding, qualified
updates and inactive-output clamps.

The descriptor write gate separates valid starts from rejected descriptors. A
vector response write gate suppresses updates from unallocated, duplicate,
out-of-range or unknown response controls. A legal response carrying a memory
error still captures its error bit. Existing shared RTL is unchanged.

Completion slots use separately enabled DFFs so arbitrary response tags can update
their entries. Reset clears allocation/presence flags, pointers, occupancy and
command status. Final-entry and response-error payload bits are unreset; valid
ownership qualifies their use, and allocation initializes the next owner's error.
Every slot capture and hold is checked during simulation. No stream data buffer
is needed because addresses and legal stream beats advance together.

Tag width is at least one. Pointers wrap explicitly at `MAX_OUTSTANDING-1`, so
non-power-of-two tables never issue unused encodings. A table that begins a cycle
full blocks new writes even if a completion retires on that edge. At nonfull
occupancy, allocation, response capture and retirement may occur simultaneously.

## Descriptors, stream beats and completion

All descriptor fields must be known, including ignored strides. Mode, counts,
element size, alignment and full address range are validated before AGU start.
An invalid descriptor produces one failed-command event and sticky fatal error,
with no start event or memory request. Descriptor readiness requires known-low
error clear. Only one descriptor can be active.

A legal input beat must match the current AGU's low-contiguous byte mask,
first/last/row markers, channel, context and configured end-of-stream marker. EOS
is asserted exactly on the final beat when requested. Upstream error must be low.
Legal stream acceptance, AGU advancement and memory request acceptance occur on
the same edge. No tag is allocated merely because valid is asserted.

A malformed beat is consumed once even when memory is blocked or the completion
table is full. It issues no write, allocates no slot and does not advance the AGU.
Stream-local fault priority is unknown control, upstream error, context mismatch,
channel mismatch, keep mismatch, then framing mismatch. Bytes disabled by the
strobe are zero at the request output, including when their source contains X/Z.
Enabled unknown data is a verification failure; it is not a new RTL error class.

Each accepted write owns its tag until ordered retirement. A response may first
arrive on the cycle after request acceptance. A response for a newly allocated
tag on the same edge is unallocated; a second response for a present entry is a
duplicate even if that entry retires on the edge. Response capture does not
release ownership and has no combinational retirement bypass.

The oldest present completion retires automatically, at most one per cycle.
Memory-response errors are nonfatal and accumulate on retirement. Normal completion
occurs on final ordered retirement, with `o_completed_with_error` including the
retiring final response's error. Memory-error status remains visible until the
next consumed descriptor or reset. Consecutive event cycles represent consecutive
transfers; stalled interfaces do not create repeated transfer events.

## Fatal drain and integration

Response ready is high whenever reset is known inactive. Malformed responses are
consumed and discarded. Fatal stream, response or runtime AGU errors stop further
stream consumption and writes, while existing slots retain ownership. Expected
responses continue to capture and retire in order. Failure pulses after all owned
writes drain. An unsolicited idle response sets sticky error without a command
failure event.

The first sticky fatal code wins. For concurrent new faults, response errors
precede descriptor errors, stream errors and runtime AGU errors. A fatal fault on
final retirement produces failure and suppresses normal completion. A legal start
concurrent with an unsolicited response can report start and immediate failure.
Request stability is qualified by the absence of a fatal abort.

The registered sticky error resets only the private AGU, abandoning the unissued
address tail without disturbing completion ownership. No combinational protocol
detector drives its reset. Error clear is accepted only when inactive and empty.
The upstream producer must flush or reframe its unconsumed tail before another
descriptor. Previously committed writes cannot be rolled back.

Unknown controls cannot create transfers. Unknown descriptor/stream/response
fields are rejected when presented. Unknown ready and valid values do not
advance interfaces. X/Z reset freezes architectural state and clamps transfers
and events. Asynchronous reset release must be synchronized externally.

Eventual input beats, request acceptance and response return are environment
fairness assumptions. There is no timeout or cancellation. Quiescence requires
inactive command state, zero occupancy, no request and a reframed upstream source;
`o_idle` additionally requires clear fatal status. Active reset requires coordinated
adapter recovery so stale responses cannot collide with a new tag epoch. The
adapter must preserve request order for overlapping addresses and define whether
its response guarantees visibility; system fences and cache coherence are external.

## Local encodings and optional counters

[`store_engine_pkg.sv`](../../../rtl/building_blocks/store_engine_pkg.sv) defines
five-bit error enums. AGU mode encodings remain linear 0, strided 1D 1, strided
2D 2 and reserved 3. No external contracts package or dependency manifest is needed.

| Error | Code |
| --- | ---: |
| None | 0 |
| Reserved mode | 1 |
| Zero inner / outer count | 2 / 3 |
| 1D outer count other than one | 4 |
| Unsupported element size | 5 |
| Base / inner-stride / outer-stride alignment | 6 / 7 / 8 |
| Unknown descriptor | 9 |
| Descriptor address range | 10 |
| Runtime AGU fault | 11 |
| Out-of-range / unallocated / duplicate tag | 12 / 13 / 14 |
| Unknown response control | 15 |
| Unknown stream control | 16 |
| Upstream stream error | 17 |
| Context / channel mismatch | 18 / 19 |
| Keep / framing mismatch | 20 / 21 |

[`store_engine_counters.sv`](../../../rtl/building_blocks/store_engine_counters.sv)
is optional instrumentation with explicit enable/clear, saturating counters and a
maximum-occupancy register. Default counter width is 48. Bind or connect the core's
qualified `g_engine.counter_events`, the consumed-keep population count and current
occupancy. Count `n` occupies `o_counts[n*WIDTH+:WIDTH]`:

| Index | Count |
| --- | --- |
| 0–2 | Commands started, completed, failed |
| 3–4 | Stream beats and bytes consumed, including the rejected beat |
| 5–7 | Requests accepted, responses consumed, responses retired |
| 8 | Active address waiting for a known-low stream valid |
| 9 | Request valid with known-low ready |
| 10 | Oldest allocated slot waiting for its response |
| 11 | Cycles at maximum occupancy |
| 12 | Legal memory responses with write error |
| 13–18 | Malformed stream classes in error-code order 16–21 |
| 19 | Response protocol errors |

Byte counts are weighted by supplied keep population, rather than descriptor
size, so malformed beats remain diagnostic. For unknown keep, the verification
binding uses `$countones`, counting only known ones. Choose a counter width large
enough to represent the maximum byte weight. Disabling collection suppresses
clear, event, byte and peak updates; reset still clears all counters. Verification
uses eight-bit enabled/disabled copies to check every count, byte-sum saturation,
peak occupancy and disabled holds. Descriptor byte-count width is independently
`2*COUNT_WIDTH + log2(MAX_ELEMENT_BYTES)`.

## Verification evidence and scope

The reference model computes addresses from descriptor coordinates, validates
mathematical rectangle bounds and maintains an ordered deque of owned writes.
The stream source and memory peer schedule offers, ready, latency and response
order independently. The scoreboard compares every public output at pre-edge,
pre-NBA, settled and held observations. It checks
`accepted = retired + reset_discarded + outstanding` and
`accepted = legal_stream_beats`, including after coordinated resets.

Directed scenarios cover every mode/size/stride sign, occupancy, tag, reverse and
random responses, starvation, request stalls, simultaneous transfers, first/middle/
final memory errors, every stream fault before and after issued writes, malformed
beats at full occupancy with blocked memory, response protocol errors, concurrent
fault priority, final-retirement errors, fatal drain, clear and reset recovery.
Private injection tests the otherwise unreachable runtime AGU failure path.
Mandatory goals check random-only starvation, backpressure, wrap and reachable
response reordering. Coverage records the specification's functional crosses and
checks mode/stride, occupancy transitions, stream class/issued-write state and
idle/active/draining reset states.

Private checks inspect actual DFF captures/holds, allocation/presence and both
reused write gates. The native simulation checker independently checks atomic
pairing, ownership, tags, response writes, ordered retirement, drain, completion
and selected-byte knownness. Negative probes disable the Python scoreboard so
only the native data assertion can satisfy their expected rejection.

The runner checks the actual decorated test identity, JUnit result, seed, geometry,
all mandatory goals and final accounting. Evidence includes per-profile coverage,
logs and RTL/dependency/verification hashes under the selected build directory.

Only Python/PyUVM simulation is run for this change. Native assertions are
simulation checks, not formal proofs. Lint, formal, CDC/RDC/DFT/low-power analysis,
technology synthesis and physical timing/power are `NOT_RUN`. Synthesis is deferred
to **Design Compiler** using the repository flow when technology setup and
libraries are available. No physical or power qualification is claimed.
