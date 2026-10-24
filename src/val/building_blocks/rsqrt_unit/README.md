# Inverse-square-root unit PyUVM validation

The native `rsqrt_unit` top implements the
[inverse-square-root specification](../../../../../specs/building-blocks/mosaic-rsqrt-unit/README.md).
Repository-local enums and four-bit error codes are in `rsqrt_unit_pkg.sv`.
Parameter-dependent token and result structures remain local to the top. No external
contracts package or dependency manifest is required.

## Run

From `mosaic-cgra`:

```sh
make rsqrt-unit-regression SIM=icarus
make rsqrt-unit-regression SIM=vcs
make pyuvm SIM=icarus COCOTB_TOPLEVEL=rsqrt_unit
```

The Makefile discovers this suite and supplies its complete RTL dependencies. Local
validation uses Python 3.12, cocotb 2.1, PyUVM 5.0, gmpy2 2.2.1 and MPFR 4.2.1.
VCS requires its configured executable and license; the local campaign uses Icarus.
The same test and Makefile targets support VCS, whose qualification is separate.

Set `RSQRT_UNIT_SEED`, `RSQRT_UNIT_RANDOM_CYCLES` (minimum 1000), and
`RSQRT_UNIT_REGRESSION_BUILD` to configure the campaign. `RSQRT_UNIT_JOBS` in the
environment sets concurrency, defaulting to four simulations for Icarus and one for
VCS. Every profile has a deterministic distinct seed. Selected-profile runs use:

```sh
.venv/bin/python src/val/building_blocks/rsqrt_unit/run_rsqrt_unit_regression.py \
  --sim icarus --build-dir build/icarus/rsqrt_unit/selected \
  --case default --case default_unrolled
```

Direct parameterized tests require both simulator parameter overrides and matching
`RSQRT_UNIT_<PARAMETER>` environment values. The decorated PyUVM entry checks every
parameter and port width before stimulus.

## Composition and arithmetic

| Function | Reuse |
|---|---|
| Epsilon addition | Widened unsigned `scalar_alu` add |
| Leading-one normalization | MSB-priority `priority_encoder` |
| All three Newton products | Full-width unsigned `multiplier` |
| `3 - n*y_squared` | Extended unsigned `scalar_alu` subtraction |
| All numerical rounding | `polynomial_unit_round` with zero sign extension |
| Half-exponent restoration | `reciprocal_unit_scale` with negative sign disabled |
| Seed storage and protection | Shared `protected_seed_rom`, common mux, parity and ECC |
| Iterative state and phase | `event_barrier_state` and common DFFs |
| Elastic pipeline and results | `event_barrier_queue` and common FIFOs |
| Asynchronous reset release | Common two-stage `reset_synchronizer` |

`protected_seed_rom` was extracted from the reciprocal seed implementation. Both
units now instantiate it with constant numerical images. The reciprocal seed bits,
IDs, checksum algorithm, ports and numerical behavior are preserved, and its Python
regression is rerun to verify the shared implementation.

Input validation rejects known illegal iterations and unsupported epsilon use with
a zero-data error response, iterations/quality zero, and the zero-iteration error
latency. These capability checks precede predication; predication then suppresses
all numerical validation and activity. A negative signed input is an error before
any epsilon addition. Input signedness and output range are independent.

For a legal nonnegative operand, epsilon addition uses `INPUT_WIDTH + 1` bits.
Only a requested, supported, nonzero epsilon enables the adder. Effective zero is
classified after addition, so positive epsilon can rescue a zero input. A disabled
or numerically suppressed epsilon is isolated before capture and its bits may be
unknown; an active unknown epsilon fails closed. Other unknown request modes,
operand or ownership fields fail closed without accepting a token.

Normalization converts the widened effective magnitude into a mantissa in `[1,2)`,
clamping a rounded endpoint below two. It computes exponent `p - INPUT_FRACTION_WIDTH`,
parity and floor half exponent even for negative exponents. The parity-adjusted
normalized value lies in `[1,4)`. A separate signed shift wire preserves floor
semantics before conditional output isolation.

The exact product order is `y*y`, `n*y_squared`, then `y*correction`. Each of the
first two products rounds at the internal fraction boundary. The final product
rounds at fraction width plus one, including division by two. All operands and
products retain their full width. An out-of-range intermediate or nonpositive
correction/estimate is fatal. Final scaling rounds magnitude, then clamps to the
selected positive signed or unsigned endpoint. Overflow and underflow are numerical
status; the rounded flag collects every discarded nonzero bit.

## Scheduling and controls

A request accepted at edge `t` becomes result-valid after edge
`t + 4 + 3 * iterations` in the iterative architecture. Its unstalled initiation
interval is the same. One multiplier is shared among the three products. Validation
and epsilon, normalization, seed lookup, each product, and final scaling occupy
explicit cycles. A replacement request can be accepted on the completion edge.

The unrolled architecture has `4 + 3 * MAX_ITERATIONS` elastic token positions
before the result queue and three multiplier positions per maximum iteration.
Latency is fixed at that value and unstalled initiation interval is one. Lower
requested iteration counts bypass arithmetic while preserving their stage latency.

Predicated, negative and zero tokens preserve captured iteration timing and their
metadata while the seed/multiplier enables stay low. Result fields remain stable
under output stalls. Invalid response fields are zero. Busy includes queued work;
idle requires both pipeline/iterative and result state to be empty.

Drain blocks admission and lets accepted results complete. Flush has priority over
requests and results, discards all work, clears recoverable error and pulses flushed
when state existed. Error-clear requires no work, request, drain or flush and cannot
clear fatal status. Fatal ownership, seed, arithmetic or identity faults block new
requests, suppress the public response on the containment edge and discard remaining
work. Integration retires these tags through reset recovery; a fault cannot create
a successful response. Output ready is considered independently for capacity, avoiding
a reverse-ready loop through fatal masking.

Protected profiles parity-check the complete live token, phase, pointers, occupancy,
occupied payloads and error/fatal state. They also check occupied-lane census against
queue occupancy. This detects single-bit ownership corruption rather than correcting
arbitrary metadata faults. Flush preserves fatal status. Reset clears ownership,
errors and events; the constant seed image does not reset. Asynchronous reset asserts
immediately, with two clean clocks before acceptance resumes.

## Seed image and reproducibility

`images.py` pins gmpy2 2.2.1 and MPFR 4.2.1. It bounds every positive seed using
512-bit directed-rounding division and square root, rounds both bounds to nearest
even and requires identical integers. Wider custom formats increase precision to
`max(512, 4*INTERNAL_WIDTH + 4*SEED_MANTISSA_ADDRESS_WIDTH + 64)` bits. Exact squared
half-ULP comparisons additionally certify each rounding decision.

`seed_image.json` records generator/version, parameters, precision, library versions,
all default seeds, image ID and checksum. The image has `2**(A + 1)` entries, where
`A` is the mantissa address width; exponent parity selects its high address bit.
CI regenerates and byte-compares the artifact. Every simulated profile checks RTL
identity/checksum against its independently regenerated image.

The RTL constructs the same bits with constant integer comparisons at elaboration.
It has no runtime square root, divider, seed write port, initialization file or
real-number datapath. The shared protected ROM encodes these constants. Parity detects
odd seed changes; SECDED corrects one bit on read and rejects two. Correction does
not scrub the ROM. SECDED stripes contain at most 256 payload bits.

Checksum is FNV-1a-32 over little-endian unsigned 32-bit generator version, internal
width, internal fractional width and mantissa address width, then each seed as
`ceil(INTERNAL_WIDTH/8)` little-endian bytes. Image ID is checksum XOR `0x52535101`,
a separate namespace from the reciprocal image. These are reproducibility identifiers,
not cryptographic signatures. Identity is hardwired and checked for disagreement.

## PyUVM checks and evidence

The suite splits transactions, sequences, driver, passive monitor, agent, environment,
independent numerical model, scoreboard and coverage. Agent/environment wiring,
coverage reporting, four-state conversion and regression execution reuse `mosaic_uvm`.
The Python Hamming and rounding primitives are shared with reciprocal/polynomial
validation; the epsilon, normalization, three-product and scaling oracle is specific
to rsqrt and independent of RTL signals.

The monitor observes actual pre-NBA rising edges, settled outputs and held values.
The scoreboard uses independent token/credit ledgers, checks every result/status/event,
exact latency and initiation interval, arithmetic access enables, ordering, result
stability and conservation through reset, flush and fault containment. Native HDL
assertion checkers are not required for this Python-only campaign.

The 40-profile matrix includes defaults in both architectures, a full cross of
architecture/protection/zero-policy/epsilon support, both reset styles, and seven
geometry pairs. It covers required 8/16/32-bit inputs and outputs, 18/28/36/52-bit
internal widths, 3/4/6/8-bit mantissa addresses, zero through three iterations, all
protection modes, and non-power-of-two queues. Supplemental reduced profiles use
four-bit operands and four seed regions per parity. The default campaign runs 2000
random cycles per profile, five pure Python model tests and 72 strict parameter
rejection checks via its Python runner.

Directed traffic covers every reachable seed address crossed with iterations, all
leading-one positions including epsilon carry, both exponent parities and negative
half exponents, output modes, zero policies, sign/epsilon classes, ties, normalization
near two, both Newton correction directions, exponent scaling and range boundaries.
At input widths of eight or less, every input encoding is exhausted for both input
signedness choices, both output modes, both round modes and every legal iteration
count. Epsilon rescue, minimum/maximum epsilon, negative inputs with epsilon, inactive
X/Z epsilon, illegal capability use, and active unknown controls are checked separately.

Backpressure fills pipeline/results, continuous traffic checks throughput, and flush
and reset exercise every physical phase. Both seed parity halves receive every stored
bit fault, including parity/Hamming/overall check bits. SECDED also receives adjacent
double-bit pairs across the codeword; the Python codec tests exhaust representative
bit pairs. Unknown seeds, state, result ownership, error/fatal state, identity and
internal arithmetic faults are injected through cocotb hierarchy without RTL test ports.

Evidence lives in `build/<sim>/rsqrt_unit/regression/`: exact decorated-test results,
coverage, simulation and rejection logs, numerical quality reports and source hashes.
The runner compares ordered arithmetic traces across paired architectures, verifies
seeds/parameters/random counts and rejects missing/skipped tests, absent coverage,
stale artifacts or sources changed during a campaign. Selected runs identify their
limited scope explicitly.

## Numerical quality and limits

`default_characterization.json` exhausts every nonzero default unsigned input encoding
for every iteration, output mode and rounding mode. Those nonnegative magnitudes also
cover signed-positive numerical behavior. It additionally samples minimum/maximum
epsilon. Reports include absolute/relative maxima, mean and percentiles; error by
magnitude and exponent parity; monotonicity findings; overflow/underflow ranges; and
latency/II. Wide custom profiles use explicitly identified deterministic samples;
reduced formats exhaust nonzero no-epsilon inputs. Negative/zero error responses are
verified by protocol tests instead of assigning them mathematical reciprocal-root error.

```sh
PYTHONPATH=src/val/building_blocks:src/val/lib .venv/bin/python \
  -m rsqrt_unit.characterize --output \
  src/val/building_blocks/rsqrt_unit/default_characterization.json --check
```

The RMSNorm example includes a fixed-point sum-of-squares reduction, its separate
rounding, zero or minimum representable epsilon and a separately rounded final
multiply. It reports reduction and output error against a 512-bit MPFR reference.
This example does not qualify a full network or an application-owned accuracy target.
Finite output precision and saturation can dominate error after refinement; no
monotonicity guarantee is assumed outside characterized intervals or samples.

Validation uses Python-driven simulation and numerical tests only. Native HDL
assertions, formal, lint, CDC/RDC, low-power, synthesis, physical implementation,
timing and power are `NOT_RUN`. Synthesis remains deferred to Design Compiler.
Area and energy are unmeasured; this functional campaign does not claim physical signoff.
