# Reciprocal unit PyUVM validation

The native `reciprocal_unit` top implements the
[reciprocal specification](../../../../../specs/building-blocks/mosaic-reciprocal-unit/README.md).
Repository-local enums and four-bit error codes live in
`src/rtl/building_blocks/reciprocal_unit_pkg.sv`. The implementation requires no
external contracts package or dependency manifest.

## Run

From `mosaic-cgra`:

```sh
make reciprocal-unit-regression SIM=icarus
make reciprocal-unit-regression SIM=vcs
make pyuvm SIM=icarus COCOTB_TOPLEVEL=reciprocal_unit
```

The Makefile selects all RTL dependencies and discovers this validation package.
The regression uses the repository Python 3.12 environment, cocotb and PyUVM.
`SIM=vcs` requires a configured VCS installation and license. The locally executed
campaign uses Icarus; VCS qualification is separate.

`RECIPROCAL_UNIT_SEED`, `RECIPROCAL_UNIT_RANDOM_CYCLES` (minimum 1000),
`RECIPROCAL_UNIT_REGRESSION_BUILD`, and the environment variable
`RECIPROCAL_UNIT_JOBS` configure the campaign. Icarus defaults to four concurrent
simulations; VCS defaults to one. Each profile receives a deterministic distinct
seed. To run selected profiles:

```sh
.venv/bin/python src/val/building_blocks/reciprocal_unit/run_reciprocal_unit_regression.py \
  --sim icarus --build-dir build/icarus/reciprocal_unit/selected \
  --case default --case default_unrolled
```

For a parameterized direct test, provide matching simulator overrides and
`RECIPROCAL_UNIT_<PARAMETER>` environment variables. The decorated test verifies
hardware parameters and every port width before sending transactions.

## RTL composition and scheduling

| Function | Reused implementation |
|---|---|
| Leading-one location | `priority_encoder` with MSB priority |
| Both Newton products | Unsigned `multiplier`, combinational latency |
| `2 - t` | Unsigned extended-width `scalar_alu` subtraction |
| Magnitude rounding | `polynomial_unit_round`, with an additional zero sign bit |
| Immutable seed ROM selection | Generated constants and common `mux` |
| Seed checking and correction | Common `parity` and striped `ecc` codecs |
| Iterative payload, phase and validity | `event_barrier_state` using DFFs and optional parity |
| Pipeline and result buffering | `event_barrier_queue` using common one-entry FIFOs |
| Asynchronous reset release | Common two-stage `reset_synchronizer` |

The generated image now uses `protected_seed_rom`, shared with the rsqrt unit.
The reciprocal image bits, ID, checksum and numerical behavior are unchanged.

The iterative architecture contains one shared multiplier. A request accepted at
edge `t` becomes result-valid after edge `t + 3 + 2 * iterations`, with the same
unstalled initiation interval. Normalization, seed lookup, both products per
iteration and final scaling each occupy their specified cycle. The evaluator can
accept a replacement on its result-creation edge.

The unrolled architecture contains two multiplier positions per maximum iteration
and `3 + 2 * MAX_ITERATIONS` elastic token positions before the result queue.
Latency is that fixed number of cycles, and unstalled initiation interval is one.
Requests with fewer iterations bypass unused arithmetic positions while retaining
their token latency. Every position can hold its data under backpressure.

Zero and predicated tokens retain their captured iteration latency while all
normalizer, seed and multiply enables remain low. Predication precedes the zero
check. An illegal known iteration count produces a zero-data error response with
iterations and quality ID zero; its iterative latency is three cycles, and its
unrolled latency is unchanged. Unknown request fields fail closed without a
handshake. Response payloads are zero when result-valid is low.

All numerical operations use complete products and explicit rounding boundaries.
The most-negative input is converted in `INPUT_WIDTH + 1` magnitude bits. Both
normalization and output scale shifts have enough vector headroom to avoid wrap.
The original sign is applied after magnitude rounding and saturation, including
the asymmetric negative signed endpoint. The rounded flag collects discarded
nonzero bits across normalization, both Newton products and final scaling.

The parameter guard rejects undefined controls, X/Z or nonpositive required
widths/depths, illegal fraction relationships, oversized seed storage and derived
arithmetic overflow. Maximum iterations may be zero. Derived geometry is expressed
as local parameters and cannot be independently configured.

## Seed image and protection

`images.py` generates exact midpoint reciprocals with integer division and
nearest-even rounding. The checked-in `seed_image.json` contains all 64 default
24-bit Q20 seeds, generator version, image ID and checksum. CI regenerates it and
compares the complete serialized artifact. Every simulated profile also checks the
RTL ID and checksum against independently generated values.

The checksum is FNV-1a-32 over little-endian unsigned 32-bit generator version,
internal width, internal fractional width and address width, followed by each seed
in `ceil(INTERNAL_WIDTH / 8)` little-endian bytes. Image ID is the checksum XOR
`0x52435001`, identifying the reciprocal generator and version. These are
reproducibility identifiers, not cryptographic signatures.

The RTL ROM uses constant rational arithmetic at elaboration. It has no runtime
write port, divider, real-number computation or initialization file. Identity is
hardwired and checked for disagreement. Seed contents do not reset. Parity detects
odd changes; SECDED corrects one bit and rejects two. Wide SECDED words are striped
into at most 256 data bits per codec. Correction occurs on read without scrubbing.

Protected profiles also parity-protect the iterative token and phase, every
occupied pipeline token, queue pointers/occupancy/payload and sticky error/fatal
state. The queues check ownership census against occupancy. Parity provides
single-bit metadata detection, rather than multi-bit metadata correction.

Fatal seed, arithmetic, identity or ownership errors block requests, suppress
successful completion of the affected token and discard all remaining evaluator
and queue state at the containment edge. Integration must retire these outstanding
tags through reset recovery. Flush and error-clear preserve fatal status. A forced
ROM fault in validation is released before reset; reset alone cannot repair a
physically damaged immutable ROM.

Flush has priority over normal transfers, removes all evaluation/results, clears
recoverable error and pulses flushed when work existed. Drain blocks admission
while existing work completes. Error-clear is accepted only without work, request,
flush or drain, and cannot clear fatal errors. Asynchronous reset asserts
immediately and waits for two clean clocks before acceptance. Unknown controls
are treated as inactive and reported; unknown reset cannot clock ownership or
release a reset domain.

## Verification and evidence

The UVM structure separates `transaction`, `sequences`, `driver`, `monitor`,
`agent`, `env`, `scoreboard` and `coverage`. It reuses the common active-agent,
environment, coverage and regression infrastructure. Numerical and Hamming Python
helpers are shared with polynomial verification; the reciprocal normalization,
seed generation, Newton and scaling model is independent of RTL signals.

The passive monitor samples actual pre-NBA clock edges, settled values and held
values between edges. The scoreboard tracks independent tokens and output credits,
checks every public result/status/event, exact unstalled and stalled timing,
request/result conservation and ordering, and actual datapath access enables.
It checks that zero, predication and unused iterations cannot access arithmetic.
The source does not embed a second HDL checker.

The campaign covers 40 profiles: the exact defaults and their unrolled counterpart;
a cross of both architectures, all three protection modes, both zero policies and
both reset styles; and seven geometry pairs. Required 8/16/32-bit input/output,
16/24/32/48-bit internal, 3/4/6/8-bit seed address, zero through three iterations,
and non-power-of-two queues are represented. Smaller 4-bit and seed-depth 2/4
profiles supplement those required widths. The campaign runs 2000 random cycles
per profile by default, four pure Python model tests and 68 strict elaboration
parameter rejection checks through its Python runner.

Directed checks cover all leading-one positions, reachable seed addresses crossed
with every iteration count, signed endpoints, both rounding modes, rounding ties,
normalization near one, both Newton correction directions, output shift/range
boundaries, zero and predication, continuous throughput, full queues and stalls,
drain, flush and reset in every physical phase, X/Z controls, and fault recovery.
Every input encoding is exhausted at input widths of eight bits or less for both
signedness choices, both rounding modes and every legal iteration count.

Protection tests fault every stored seed bit, including parity/Hamming/overall
check bits. SECDED tests adjacent double-bit pairs across the full codeword, and
the pure Python codec tests exhaust every bit pair for representative widths.
Unknown seed bits, identity, pipeline/iterative state, result ownership, sticky
state and the arithmetic-failure path are also injected. Fault hooks are cocotb
hierarchical accesses; no injection ports are added to the synthesizable top.

Evidence is under `build/<sim>/reciprocal_unit/regression/`: exact decorated-test
results, coverage, simulation/guard logs, numerical quality reports and a summary.
The runner compares ordered directed arithmetic traces between matched
architectures and rejects missing tests, skipped tests, absent coverage, mismatched
parameters/seeds, stale artifacts and changed RTL or verification sources.
Selected runs identify their smaller scope explicitly.

## Numerical characterization and limits

`default_characterization.json` exhausts every nonzero default input under signed
and unsigned interpretation, both round modes and every iteration count. It
publishes absolute/relative maximum, mean and percentiles; error by leading-one
magnitude; monotonicity findings; overflow/underflow magnitude ranges; and latency
and initiation interval. Saturation error is included and separately distinguished
from the unclamped error. A conservative no-clamp analytical bound includes seed,
normalization, both Newton roundings and output quantization. Every regression
recomputes the default artifact, and characterizes each distinct numerical geometry
exhaustively for reduced inputs or with explicitly identified deterministic samples
for wider inputs.

Regenerate or compare the default characterization:

```sh
PYTHONPATH=src/val/building_blocks:src/val/lib .venv/bin/python \
  -m reciprocal_unit.characterize --output \
  src/val/building_blocks/reciprocal_unit/default_characterization.json --check
```

The application example evaluates positive-sum normalization, representing the
reciprocal step of Softmax, with a separately rounded fixed-point multiply. It
reports probability and sum error; it does not qualify a complete Softmax model or
an application-owned accuracy target. Additional Newton iterations can reach the
output quantization floor, and output saturation can dominate mathematical error.
Monotonicity is stated only for the characterized interval or samples, not assumed
for every legal parameter combination.

Validation is Python-driven simulation and numerical testing only. HDL assertions,
formal, lint, CDC/RDC, low-power checks, synthesis, physical implementation, timing
and power are `NOT_RUN`. Design Compiler synthesis is deferred. Area and energy
remain unmeasured; this functional campaign does not claim physical signoff.
