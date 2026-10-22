# Static local switch RTL and PyUVM validation

[`local_switch.sv`](../../../rtl/building_blocks/local_switch.sv) implements the
[static local-switch specification](../../../../../specs/building-blocks/mosaic-local-switch/README.md).
An atomic context selects one physical input per enabled output. Each input stores
one item and owns one pending copy per captured destination. Outputs acknowledge
copies independently; the final acknowledgement may accept a replacement item on
the same edge. There is no dynamic arbitration.

## Run

```sh
make setup
make local-switch-regression                    # Requires VCS and its license
make local-switch-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=local_switch
```

The decorated test is `test_local_switch.LocalSwitchTest`. Separate test,
environment, agent, sequencer, driver, passive monitor, reference, scoreboard and
coverage components reuse the shared `mosaic_uvm` infrastructure. JUnit identity,
actual port widths, elaborated parameters, mandatory goals and ownership accounting
are checked before a profile passes.

The **120-profile** matrix covers:

- 1×1, 2×3, 4×4, 4×8 and 8×8 switches with 32/64/128-bit data.
- Full and sparse connectivity, multicast enabled/disabled, and both reset styles.
- One-bit data/metadata/context, odd 13-bit data and 7-bit metadata, three inputs,
  and a sparse profile with physically isolated inputs.

Duplicate 1×1 full/sparse masks are run once. Every profile runs 2000 random cycles
plus directed traffic. There are **36 strict invalid-parameter elaboration checks**.
Set `LOCAL_SWITCH_SEED`, `LOCAL_SWITCH_RANDOM_CYCLES` (minimum 1000), and
`LOCAL_SWITCH_REGRESSION_BUILD` to control the campaign. Seeds advance by profile
index. Select a profile directly when needed:

```sh
.venv/bin/python src/val/building_blocks/local_switch/run_local_switch_regression.py \
  --sim icarus --build-dir build/local-switch-selected \
  --case i3_o5_d13_m7_c3_edges6357_mc1_r1
```

Custom direct runs require matching compiler overrides and
`LOCAL_SWITCH_<PARAMETER>` environment variables. The connectivity parameter is
intentionally untyped: pass **exactly** `NUM_INPUTS*NUM_OUTPUTS` bits, such as
`16'hffff` for a full 4×4 switch. An unsized decimal override can have a different
width and is rejected. The runner supplies explicitly sized mask literals. Use a
fresh direct build directory when changing geometry; the runner tracks parameter
files as compile dependencies automatically.

Private storage checks and the native HDL checker default to enabled. A public-port
RTL run is available:

```sh
LOCAL_SWITCH_CHECK_INTERNALS=0 LOCAL_SWITCH_HDL_ASSERTIONS=0 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=local_switch
```

That mode omits private payload/ownership checks and ownership-fault injection and
reports them as `NOT_RUN`. Simulation uses nominal 10 ns clock opportunities,
1 ps observation ticks and zero-delay RTL (`TEST_SETTLE_NS=0`). It does not qualify
SDF-annotated gate timing.

## Reuse and sparse connectivity

Each input instantiates the existing `register_slice` with concatenated data and
metadata. A common DFF stores its pending mask. Common DFFs also store the active
configuration, errors and events. Output source selection uses the existing `mux`,
followed by `operand_isolation` to clamp invalid payloads. No existing common or
basic RTL is modified.

Output `o` has a mux lane only for each set bit in
`CONNECTIVITY_MASK[o*NUM_INPUTS+i]`. The RTL compacts connected inputs in increasing
input-index order and translates the active source index into that local mux
index. Absent sources have no payload connection to that output mux. Every output
must have a physical source; inputs may be physically isolated and remain unready.

Input/output data and metadata use the least-significant packed slice for logical
index zero. Route selections use the same convention. Pending status instead uses
input-major order: bit `i*NUM_OUTPUTS+o` represents input `i`'s copy for output `o`.
The suite's explicit `PORTS` schema and regression reports publish widths,
parameters and the physical-edge list for each profile.

Input payload banks are unreset and write only on acceptance. Bubbles, partial
multicast progress, stalls, flush and reset retain the physical payload bits.
Validity controls whether an item exists, so flush/reset discard ownership without
erasing the bank. Invalid output data and metadata are zero. A completed output
cannot consume the same copy again while another destination remains pending.

## Configuration, latency and flow control

Reset disables all routes. An unrouted input is never ready. Legal configuration
updates every output enable/selection and the context identifier atomically; an
illegal configuration leaves them unchanged. Context is opaque and is not inserted
into payload metadata.

A pending configuration receives priority as soon as the switch becomes empty.
All data ready/valid outputs are low on that configuration edge, even when an input
offers a new item. While buffers are occupied, a producer can hold the complete
configuration stable and let old traffic drain. When configuration valid is low,
configuration readiness/quiescence deassert on an otherwise accepted input beat.
Error clear requires quiescence and loses priority to configuration acceptance.

Disabled output selections are ignored for range/connectivity legality, but must
still be known because active configuration is exposed and diagnosed. Multicast
disabled means no two enabled outputs may select the same input.

There is one registered forward stage. Captured data becomes output-valid after
the acceptance edge and can be consumed on the next edge. There is no input-data
bypass. With all pending consumers ready, every routed input and enabled output
can transfer once per cycle. Output ready may affect input ready; it does not
affect forward valid or payload combinationally.

Each pending consumer can advance without waiting for another consumer. The input
remains blocked until all remaining copies can advance. Final consumption and
replacement use the old item for output transfers and the new item for subsequent
cycles. Unrelated sources progress despite a stalled multicast destination.

## Flush, errors and unknown values

Flush takes priority over configuration and data handshakes. It synchronously
clears buffered validity and pending masks, preserves routes/context and sticky
error, and pulses `o_flushed` only when buffered or pending state existed. It never
gates asynchronous reset. Producers and consumers must coordinate cancellation of
their external ownership.

The first error remains sticky until reset or a quiescent error-clear operation.
A rejected configuration or external protocol error does not disable otherwise
healthy installed routes. Inconsistent internal ownership immediately suppresses
data/configuration handshakes; flush or reset clears that inconsistent state.
Error clear alone cannot repair an occupied corrupt buffer.

[`local_switch_pkg.sv`](../../../rtl/building_blocks/local_switch_pkg.sv) supplies
repository-local three-bit error enums:

| Code | Error |
| ---: | --- |
| 0 | None |
| 1 | Enabled source index outside the input range |
| 2 | Enabled route absent from the physical connectivity |
| 3 | Duplicate source with multicast disabled |
| 4 | Unknown external control or configuration field |
| 5 | Buffered input with an empty pending mask |
| 6 | Pending copy for a disabled or differently selected route |
| 7 | Unknown internal ownership, or pending state without a buffered item |

Within a new cycle, the lowest-index inconsistent input has priority over unknown
external controls and rejected configuration. Configuration checks visit enabled
outputs in index order, testing range, connectivity and duplicate ownership. An
already sticky error always wins. No external `mosaic-contracts` package or
dependency manifest is introduced.

X/Z input valid and output ready bits are never treated as transfers. Unknown
handshake controls are diagnosed, while unrelated known lanes can still progress.
Unknown global flush/config-valid/error-clear controls block data and configuration
handshakes. X/Z reset freezes state and clamps transfer/event outputs; known reset
recovers it. Control/status outputs remain known even during injected ownership
faults. Unknown data/metadata is preserved only with associated output valid; the
suite explicitly checks valid X/Z payloads and invalid zero clamps.

Producer payload/configuration persistence is an environment contract, checked
separately by the scoreboard. Normal stalled-output stability assumes legal global
controls and no coordinated reset/flush or internal ownership fault. Asynchronous
reset release must be synchronized externally. Consumers must eventually accept
pending copies for drain to complete. Global route-graph deadlock freedom belongs
to the mapper and integrating network.

## Validation and qualification boundaries

The primary reference uses one ordered copy queue per output. Every accepted input
records its payload, serial number and destination mask. Queue retirement checks
exactly one copy, unchanged payload/metadata, per-input order and registered
latency. Separate ledgers enforce:

```text
accepted_items = completed_items + discarded_items + buffered_items
accepted_copies = delivered_copies + discarded_copies + pending_copies
```

The passive monitor samples actual pre-NBA edges, settled outputs and held cycles.
The scoreboard checks every public output, every payload capture, every inactive
payload hold and private occupancy/pending storage. Verification-only deposits
exercise empty-pending, wrong-route, orphaned-pending and unknown ownership faults,
followed by flush/recovery. The native HDL checker independently checks copy
conservation, occupancy/pending consistency, route updates, configuration exclusion,
flush containment, invalid clamps and event correspondence.

Directed traffic covers every physical edge and legal fanout, all reachable input
occupancies, independent stalls, maximum rate, replacement, held configuration,
rejected configuration classes, sticky error/clear, and both reset styles. For
multicast, every subset of destinations is consumed before flushing the rest; each
destination also acts as a unique first and last multicast consumer. Reset and
flush occur from every reachable occupancy class. Seeded random traffic varies
routes, source activity, fanout, context duration, payloads and independent consumer
stalls, with natural drain and coordinated flush between contexts.

Required coverage is checked per profile. Source-range errors are unreachable for
power-of-two input counts greater than one; absent-edge errors are unreachable
with full connectivity; duplicate-source errors are unreachable with multicast
enabled or no shared physical source. Fanout is bounded by physical connectivity
and multicast support. Maximum occupancy is the topology's maximum matching, so
isolated inputs do not create impossible goals. These parameter-derived bounds
are recorded with the actual coverage evidence.

Regression artifacts include actual JUnit results, coverage/accounting, simulator
logs, parameters, seeds and exact RTL/dependency/verification hashes. Native HDL
assertions are simulation checks. Formal proofs, licensed commercial lint/CDC/RDC/
DFT/LP, technology timing/area, physical implementation, PrimeTime and PrimePower
are separate release requirements and remain `NOT_RUN` when unavailable. Generic
structural synthesis does not establish physical timing or power signoff.
