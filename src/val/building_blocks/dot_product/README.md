# Integer dot-product RTL and PyUVM validation

This suite implements the [dot-product specification](../../../../../specs/building-blocks/mosaic-dot-product/README.md)
with [`dot_product.sv`](../../../rtl/building_blocks/dot_product.sv). It reuses the
existing `dff` and `operand_isolation` modules and the shared `mosaic_uvm` test
infrastructure. There is no multiplier RTL in this repository, so each term uses
one inferred multiplier. The unit has no persistent accumulator state; composing
the existing `accumulator` externally preserves that distinction.

## Run

```sh
make setup
make dot-product-regression                    # VCS executable and license required
make dot-product-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=dot_product
```

The native regression runs the actual decorated `test_dot_product.DotProductTest`
with a test, environment, agent, sequencer, driver, monitor, independent model,
scoreboard and coverage collector. Python 3.10 or newer is required; local runs
use Python 3.12, cocotb 2.1 and PyUVM 5.0.

`DOT_PRODUCT_SEED`, `DOT_PRODUCT_RANDOM_CYCLES` (at least 1000) and
`DOT_PRODUCT_REGRESSION_BUILD` configure the campaign. Defaults are seed 20261020
plus the profile index, 2000 random opportunities per profile, and
`build/<simulator>/dot_product/regression`.

Select profiles directly:

```sh
.venv/bin/python src/val/building_blocks/dot_product/run_dot_product_regression.py \
  --sim icarus --build-dir build/dot-product-selected \
  --case e8_n4_a32_acc1_sat1_l2_r0_m8
```

For custom direct Make runs, compiler parameters and corresponding
`DOT_PRODUCT_<PARAMETER>` environment variables must agree. Icarus uses
`-Pdot_product.PARAMETER=value`; VCS uses `-pvalue+dot_product.PARAMETER=value`.
Use a fresh build directory when changing direct invocation parameters. The
regression runner writes parameter dependencies to force the requested geometry.

The Makefile supplies the common sources in simulation and synthesis order.
`DOT_PRODUCT_HDL_ASSERTIONS=1` includes the verification-only HDL oracle during
native RTL simulation. Synthesis and gate sources exclude it. For a port-only run:

```sh
DOT_PRODUCT_CHECK_INTERNALS=0 DOT_PRODUCT_HDL_ASSERTIONS=0 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=dot_product
```

Disabled checks report `NOT_RUN`. The driver requires zero-delay RTL,
`TEST_SETTLE_NS=0` and at most 1 ps simulator precision. It does not implement
SDF-aware sampling or qualify timing-annotated gate simulation.

## Numerical and pipeline structure

Term zero occupies the least-significant element. The mask preserves positions.
Signedness is shared by both vectors and the external accumulator. Every product
has exactly `2 * ELEMENT_WIDTH` architectural bits; the reduction uses
`2 * ELEMENT_WIDTH + ceil(log2(NUM_TERMS))` bits at every tree level.

One shared signed multiplier per term receives an extra sign/zero-extension bit
to support both signed and unsigned inputs. Its low `2 * ELEMENT_WIDTH` bits
encode the complete specified product; discarded extension bits are redundant.
Both operands are isolated before multiplication when a term is masked or the
request is invalid, illegal, reset or stalled. Reset and stall qualification
apply only to registered profiles.

The balanced tree pads to the next power of two with constant zero leaves.
Generated levels make the acyclic topology explicit, including one-term and odd
term counts. Active count follows a separate balanced population-count tree.
Only the final accumulator addition can wrap or saturate; it uses `ACC_WIDTH + 1`
bits. Pure mode isolates both adder operands and bypasses the adder. Static
feature branches remove accumulation or saturation hardware when disabled.

| Latency | Pipeline cuts |
| --- | --- |
| `0` | Combinational products, reduction, accumulation and result policy; clock, reset and enable are ignored. |
| `1` | Entire arithmetic cone followed by one response register stage. |
| `2` | Per-term product registers, followed by reduction/accumulation and one response register stage. |
| `3` through `MAX_LATENCY` | The same product and arithmetic cuts as latency two, followed by additional response delay stages. |

Latency counts enabled rising edges, with one request or bubble per enabled
edge. There is no output-ready port. Every register uses `i_clk`; all response
controls freeze together when enable is low. Product banks update only for active
legal terms. Response data banks update only for legal valid inputs to that
stage. Metadata and accumulator operands remain aligned across stalls. Arithmetic
payload is unreset; reset clears valid/illegal controls and prevents stale data
from becoming visible again. Both reset styles override clock enable.

Invalid outputs are all zero. Illegal responses retain only valid and illegal
status. Required unknown controls are illegal, including an unknown mask even
when other operands would produce zero. Masked data and an unused accumulator
may contain X/Z. Unknown active data, an enabled unknown accumulator, or unknown
registered reset/enable/accepted-valid controls are integration violations checked
by the testbench and HDL assertions. Zero latency ignores reset/enable even when
they contain X/Z.

Parameters remain untyped until the elaboration guard rejects zero, negative,
unknown or nonbinary settings. Accumulator width must accommodate the full
reduction; latency must fit the selected maximum. Derived widths are local
parameters. Host declaration-size guards also reject dimensions overflowing the
baseline tools' signed integer indexing/storage limits.

The implementation uses the repository's ports and specification encodings.
No external `mosaic-contracts` package or dependency manifest is introduced.
Parameters, exact source/dependency/test hashes and simulator logs accompany each
campaign; external contract and physical integration remain separate release work.

## Checked campaigns and coverage

The 102-profile matrix includes:

- Four INT8 terms into INT32 at every latency from zero through eight, with both resets.
- Eight INT4 terms into INT16/INT32, eight INT8 terms into INT32 and four INT16 terms into INT64.
- One-bit and non-power-of-two element widths, one/two/three/four/eight terms, and minimum legal accumulator widths.
- Every accumulation/saturation feature combination, both reset styles, and combinational, single-cycle and longer pipelines.
- Custom maximum-latency profiles with maxima one and nine.

Each profile checks every term mask, each individual term, every active-count
value, all legal signedness/accumulation/saturation combinations, numerical
boundaries and every applicable carry/overflow/clamp condition. All pairs of
boundary operands are checked in both signedness modes. Directed tests include
signed positive/negative overflow, unsigned carry, exact limits without false
saturation, empty-mask accumulator pass-through and mixed-sign reduction.

Packed operand widths up to four bits exhaustively enumerate both input vectors,
every mask and both signedness modes in pure mode. Larger profiles use boundary
vectors, every mask, deterministic FIR/convolution/matrix/attention-shaped traces,
and seeded random traffic. These are synthetic workload shapes, not measured
application activity or power evidence.

Pipeline tests check full-rate traffic, bubbles, long stalls, every reset fill
position, clockless input changes, short between-edge reset pulses and refill.
Four-state tests corrupt every mask position, each required control, ignored
fields and masked operands. The runner additionally requires 37 bad parameter
configurations to fail elaboration and 40 expected-failure protocol probes to
reject unknown active data or required integration controls.

The monitor observes settled inputs, actual pre-NBA rising edges, settled outputs
and held intervals. The integer oracle independently computes selected products,
mathematical sums, range errors and modulo/clamp results. A separate enabled-edge
history checks timing and request conservation, including reset discards. Private
observations check isolated multiplier/adder inputs, full-width products and
per-bank writes/holds without treating unreset storage as functional state.

`dot_product_assertions.sv` independently computes a serial over-wide mathematical
sum and a stall-aware response history. It checks numerical results, active count,
all status bits, illegal/invalid clamping, fixed enabled latency and reset removal.
Its integration assertions reject unknown active inputs before commit. The
verification-only one-precision-tick delay is excluded from synthesized hardware.

Coverage reports include mandatory goals, mode and status crosses, every mask
population, boundary/product-sign crosses, pipeline occupancy and response
accounting. Unreachable bins have explicit profile waivers; for example, signed
one-bit terms cannot form a negative product. Coverage must accompany a passing
JUnit result for exactly the expected decorated test. Missing simulators or
licenses report `NOT_RUN`.

## Evidence limits

Ignored `build/validation/dot-product-*` artifacts record native simulation,
Verilator lint, direct Slang/Yosys synthesis, deliberate fault-detection checks and
small bounded binary proofs. Generic structure checks cover unresolved cells,
latches, combinational loops, hidden sequential endpoints, generated clocks,
initialized hardware state and disabled-feature removal. They do not establish
technology timing, area or physical power.

Bounded proofs use an independent serial wide sum and enabled-edge history for
small profiles, with arbitrary binary inputs and stalls after an initial reset.
Asynchronous reset uses an edge abstraction. Local proofs completed for 42 of
44 small profiles at bounds of one, eight or twelve steps. The three-term,
three-bit, latency-two accumulated/saturating profiles reached solver time limits
with both reset styles; their unfinished bounds are recorded as `NOT_RUN`. These
checks do not establish unbounded liveness, physical reset release or complete
formal release signoff.

VCS execution, commercial lint/CDC/RDC/DFT/LP, technology synthesis, sequential
equivalence, PrimeTime, PrimePower and external contract compatibility require
their own tools and evidence. Unavailable checks remain `NOT_RUN`; no physical
power, energy or full release-signoff result is claimed by this RTL validation.
