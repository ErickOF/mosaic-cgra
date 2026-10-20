# Register-slice verification

The specification is
[`specs/basic/mosaic-register-slice/README.md`](../../../../../specs/basic/mosaic-register-slice/README.md).
The implementation is [`register_slice.sv`](../../../rtl/basic/register_slice.sv).
The decorated PyUVM test is `test_register_slice.RegisterSliceTest`.

```sh
make setup
make register-slice-regression              # native VCS
make register-slice-regression SIM=icarus   # local four-state RTL regression
make pyuvm SIM=icarus COCOTB_TOPLEVEL=register_slice
```

Run selected widths/reset styles while retaining all parameter and protocol probes:

```sh
.venv/bin/python src/val/basic/register_slice/run_register_slice_regression.py \
  --sim icarus --build-dir build/register-slice-focused \
  --case w65_a1 --seed 42 --random-cycles 1000
```

`--case` is repeatable. Names encode data width and asynchronous-reset selection.
The effective seed is the base seed plus the profile's index in the full matrix,
so filtering preserves reproducibility. Sources resolve relative to the runner,
which works from another directory. At least 1000 random cycles are required.
The runner also accepts `--rtl`, compiler/runtime flags and a simulator binary
directory.

Make settings are `REGISTER_SLICE_REGRESSION_BUILD`, `REGISTER_SLICE_RANDOM_CYCLES`
and `REGISTER_SLICE_SEED`. Reports default to
`build/<simulator>/register_slice/regression`; `make -n` preserves existing reports.
For direct `make pyuvm`, `REGISTER_SLICE_DATA_WIDTH` and
`REGISTER_SLICE_ASYNC_RESET` describe the expected parameters, defaulting to 32
and zero. Compiler overrides must match these values; the runner supplies both.

`REGISTER_SLICE_CHECK_INTERNALS=0` selects port-only checking. Geometry and raw
storage assertions then report `NOT_RUN`. `REGISTER_SLICE_COVERAGE_FILE` overrides
the coverage path. Use `TEST_SETTLE_NS=0` and 1 ps or finer precision. This suite
checks zero-delay RTL rather than timing-annotated gate models.

## RTL and interface contract

The slice contains one valid bit and exactly `DATA_WIDTH` unreset payload bits.
Common `dff` implements the selected validity-reset style; common
`operand_isolation` clamps invalid output data to zero. Dependency source hashes
are recorded in release evidence, and the Makefile provides their ordered sources
for simulation and synthesis. No dependency lockfile or private encoding package
is introduced.

An empty slice accepts an offered input. A full slice holds when downstream ready
is low. When downstream ready is high, the old item is consumed and an offered
new item replaces it on the same edge. Only accepted valid inputs write payload;
bubbles, stalls and reset preserve the data register. Invalid output data is zero.
Malformed widths or reset flags, including X/Z values, fail elaboration through
the named `register_slice_parameters_must_be_valid` guard.

The forward data and valid paths are registered. A newly accepted input becomes
visible after its capture edge and can first be consumed at the next rising edge.
The consumer observes the old output before a replacement commits. Continuous
replacement sustains one item per cycle without a bubble. The reverse path is
combinational: `o_ready = !o_valid || i_ready`. It does not depend on `i_valid`.

Synchronous reset takes effect on a rising edge. Before that edge, an occupied
slice still exposes its old output. A synchronous reset pulse entirely between
edges leaves stored state intact. Asynchronous reset assertion clears validity
immediately, including between edges. Payload holds in both styles. Reset edges
credit no input acceptance or output consumption, even if interface values would
otherwise resemble a handshake. Ready is not independently gated by reset.
After reset takes effect, valid is low, output data is zero and ready is high.

A producer offering valid data while blocked must hold valid and the complete
payload until acceptance or reset cancellation. Changing invalid input data is
legal, including when the output is stalled. Tests cover these changes separately
from negative tests that alter a pending valid offer. Normal accepted data must
be known. Explicit directed items opt into intentional four-state transport and
check that each X/Z bit is captured and returned without conversion.

Item format and sidebands are opaque; pack coherent metadata into `DATA_WIDTH`.
Reset release synchronization, channel alignment, ready-chain timing, CDC/RDC
and power-off state policy belong to integration. Chaining adds one forward cycle
per stage and propagates ready combinationally; the slice is not a CDC primitive
or a registered-ready boundary. Forward progress requires eventual downstream
ready and is not guaranteed against permanent backpressure.

## PyUVM structure and checking

The suite separates `config`, `transaction`, `sequences`, `agent`, `driver`,
`monitor`, `model`, `scoreboard`, `coverage` and `env`. It reuses `mosaic_uvm`
active-agent/environment wiring, four-state helpers, pattern classification,
simulator execution and report validation.

The independent reference queue records accepted payloads and their capture edges.
It removes the oldest item before appending a same-edge replacement. Every consumed
output must equal the oldest accepted item, and no item can be consumed at its
capture edge. The model counts reset discards explicitly and checks
`accepted = consumed + discarded + pending` after every observation. The test drains
all surviving items and pending producer offers before finishing.

The monitor reads real DUT ports before the edge, immediately on the rising edge
before NBA updates, after settling, and during a held interval. Clockless items
vary data, valid and ready to check the registered forward boundary and the
combinational reverse path. Optional internal checking compares valid and payload
against independent predictions. Initial unreset payload is sampled only as a
hold-check baseline; functional expectations always come from accepted inputs.

Continuous monitors reject unauthorized storage changes, forward bypass, output
pulses during held intervals, and finite producer changes while a valid offer is
blocked. They check known controls and producer stability on real signal activity
as well as sampled observations. Asynchronous reset responses are checked after
the assertion event settles. No assertion binds architectural state to an
uninitialized payload value.

## Matrix and required coverage

All 18 widths run with both reset styles, for 36 profiles:
`1, 2, 3, 7, 8, 16, 31, 32, 33, 63, 64, 65, 127, 128, 129, 255, 256, 257`.

Every profile requires 17 goals:

- All eight occupancy/input-valid/downstream-ready combinations.
- Every feasible previous-operation/next-operation pair across idle, fill, hold,
  consume and replace.
- Output stalls of zero through eight cycles and 32 cycles, ending in either
  consumption or replacement; matching producer-backpressure lengths.
- At least 64 consecutive replacements and a 32-cycle producer idle interval.
- Reset occupancy/valid/ready crosses and between-edge reset while empty/full.
- First acceptance after reset and every clockless occupancy/valid/ready cross.
- Data-pattern/operation crosses for fill, consume and both sides of replacement.
- Every bit stored and consumed as zero, one, X and Z; intentional unknown
  transport is explicitly distinguished from normal known-data traffic.
- Every invalid payload bit carrying both X and Z.
- Exact token conservation, exact randomized cycle count and all sampling stages.

Eight malformed width/reset configurations must fail elaboration. Thirty negative
probes cover X/Z reset, valid and ready in both reset styles; each active data bit
in a three-bit instance; dropping/changing a blocked offer; and a finite producer
pulse between observations. Each must fail the exact decorated PyUVM test with the
expected live assertion. Compilation errors, unrelated exceptions, missing tests
and the probe's fallback failure are not accepted as successful rejection.

## Evidence and qualification scope

The runner validates exact JUnit identity, geometry, mandatory goals, seed and
random count. Summaries include RTL, dependency and verification hashes, per-case
logs and UTC timestamps. Filtered campaigns are marked `selected_profiles`.
Generated evidence and local qualification helpers remain under ignored `build/`.

The local campaign passed all 36 profiles, 72,000 randomized cycles and 548,456
observations. It accounted for 49,407 accepted items, 47,691 consumed items and
1,716 explicit reset discards, leaving no pending items. All eight parameter
guards and 30 protocol probes passed. The checker detected all 18 injected defects,
including bypass, broken ready/replacement, bubble/stall/reset payload writes,
wrong reset styles, truncated/sanitized data, wrong clock edges and finite pulses.

Verilator lint passed every profile with no warnings or waivers. Yosys structural
checks confirmed exactly one validity bit plus `DATA_WIDTH` data bits, reset only
on validity, the selected reset style, no latch/memory/generated clock, no forward
combinational path, and the required reverse-ready path. All 36 local unbounded
binary proofs passed against an independent accepted-item state/output model.
These proofs match equal arbitrary binary initial state and use `async2sync` for
an edge-domain asynchronous-reset model. They do not prove X/Z, between-edge reset
timing, liveness or equivalence to a technology-mapped implementation.

Native VCS and licensed lint/CDC/RDC, DFT, VC LP, technology mapping, physical
timing/power, reverse-chain timing and power-transition checks require their tools,
libraries and integration artifacts. Simulation summaries record those external
checks as `NOT_RUN`, separately from supplemental local results. These local
checks do not constitute physical release qualification.
