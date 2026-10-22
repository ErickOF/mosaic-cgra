# Scalar integer multiplier validation

This suite validates the
[`mosaic-multiplier` specification](../../../../../specs/building-blocks/mosaic-multiplier/README.md)
against [`multiplier.sv`](../../../rtl/building_blocks/multiplier.sv).

## Run

From `mosaic-cgra`:

```sh
make setup
make pyuvm SIM=icarus COCOTB_TOPLEVEL=multiplier
make multiplier-regression SIM=icarus
make multiplier-regression SIM=vcs VCS_BIN_DIR=/path/to/vcs/bin
```

The Makefile discovers the suite and registers the ordered `dff`,
`operand_isolation`, and multiplier sources. RTL simulation includes
`multiplier_assertions.sv` and enables `MOSAIC_MULTIPLIER_ASSERTIONS` by default.
Synthesis and gate source lists exclude this delayed verification-only checker.

`MULTIPLIER_REGRESSION_BUILD`, `MULTIPLIER_SEED`, and `MULTIPLIER_RANDOM_CYCLES`
configure the complete campaign. The default is 2,000 randomized cycles per
profile, in addition to directed and exhaustive traffic; the minimum is 1,000.
Select profiles directly with the runner:

```sh
.venv/bin/python src/val/building_blocks/multiplier/run_multiplier_regression.py \
    --sim icarus --build-dir build/icarus/multiplier/selected \
    --case w8_l2_r1_m4 --random-cycles 2000
```

For a custom direct run, pass compiler parameters and matching `MULTIPLIER_*`
expectations. Icarus uses `-Pmultiplier.PARAMETER=value`; VCS uses
`-pvalue+multiplier.PARAMETER=value`. For example:

```sh
MULTIPLIER_OPERAND_WIDTH=16 MULTIPLIER_LATENCY=2 MULTIPLIER_ASYNC_RESET=1 \
make pyuvm SIM=icarus COCOTB_TOPLEVEL=multiplier \
    SIM_BUILD=build/icarus/multiplier/custom \
    COMPILE_ARGS='-Pmultiplier.OPERAND_WIDTH=16 -Pmultiplier.LATENCY=2 -Pmultiplier.ASYNC_RESET=1'
```

`MULTIPLIER_CHECK_INTERNALS=0 MULTIPLIER_HDL_ASSERTIONS=0` enables the public-port
checks alone. Disabled checks report `NOT_RUN`. The driver uses 1 ps precision and
zero-delay RTL; it does not qualify SDF timing simulation or physical power.
Those uses need a compatible stimulus timing policy and separate evidence.

## RTL composition

The implementation reuses common `dff` banks for validity and payload registers,
and `operand_isolation` at both multiplier inputs and the final output. No
existing RTL module is changed. The MAC and dot-product blocks have uniform
operation-level signedness, so neither directly supplies this module's two
independent operand interpretations.

Each operand is extended from W bits to a signed W+1-bit value: its extra bit is
its sign bit in signed mode, or zero in unsigned mode. One inferred signed
multiplier handles all four modes. The complete mathematical product fits in 2W
bits; removing the upper two redundant bits of the wider inferred multiplication
does not remove significant product information.

The independent output interpretation is always the OR of the two aligned
signedness controls. In particular, a zero or positive mixed product still has
`o_product_signed=1`. Negative status follows the mathematical sign, and remains
zero for an unsigned product with its most significant product bit set. Zero
status is valid-qualified; it is zero on bubbles rather than describing the
clamped invalid product as an operation.

The default operand width is 32 and the default latency is one. Width one,
non-power-of-two widths, and custom positive maximum latencies are supported.
The release matrix claims widths up to 32 and checks a six-stage custom maximum
in addition to every default latency from zero to four. Invalid widths, unknown
parameters, nonbinary reset parameters, invalid latency ranges, and overflowing
packed dimensions fail elaboration explicitly. `PRODUCT_WIDTH` is derived.

## Pipeline, reset, and activity

At latency zero, the multiplier is entirely combinational and ignores clock,
reset, and clock enable. At latency L>0, a combinational product and its metadata
are followed by L response-register stages. A response appears after exactly L
enabled rising edges, counting the sampling edge as the first. Every stage uses
the shared `i_clock_enable`; directly connected producers and consumers must use
the same advance condition and count a held valid response only once.

Additional response stages do not partition the multiplier's critical path.
Timing closure of a technology implementation, or retiming into an internally
pipelined multiplier, requires separate timing and sequential-equivalence evidence.
There is no ready signal, local elastic buffering, accumulator, or feedback state.

Only pipeline validity is reset, synchronously or asynchronously according to
`ASYNC_RESET`. Reset wins over clock enable. Product and metadata registers remain
unreset and hold when an incoming stage is invalid; final validity controls the
output clamp, preventing stale data from appearing as a new product. The containing
flow must still qualify scan/test enables, reset release, and RDC behavior.

Both multiplier operands and their signedness decode are isolated while invalid.
For registered profiles, they are also isolated while reset or globally stalled.
Unknown ignored operands or signedness cannot contaminate a future valid result.
Unknown active data, signedness, valid, enable, or reset is not converted into an
ordinary operation: integration assertions reject it before architectural commit.
Valid and data may remain ignored during a known stall; zero-latency profiles
ignore even unknown clock/reset/enable values as required by the specification.
No generated clock, rounding, narrowing, saturation, or approximate mode is added.

## PyUVM structure

- `transaction.py`: four-state stimulus items and passive observations.
- `sequences.py`: boundaries, powers and adjacent values, exhaustive products,
  mixed-mode transitions, pipeline activity, workload distributions, and random traffic.
- `driver.py`: stable input windows and real optional rising edges.
- `monitor.py`: actual ports, pre-NBA edges, product/metadata banks, and isolated inputs.
- `agent.py`, `env.py`: normal UVM grouping using shared `mosaic_uvm` components.
- `model.py`: independent unbounded Python multiplication, explicit operand
  interpretation, width masking, product metadata, and final flags. Registered
  responses use an ordered deadline ledger keyed by enabled-edge count, rather
  than copying the RTL's register arrays.
- `scoreboard.py`: every visible output at pre/edge/post/held windows, exact
  latency/order, transaction conservation, reset removal, operand isolation,
  every data enable, and between-edge register holds.
- `coverage.py`: mandatory numerical/timing crosses, pipeline-stage observations,
  mathematical waivers, and machine-readable profile metadata.
- `test_multiplier.py`: decorated PyUVM test, port widths, actual parameters, and
  checker/generate-presence checks.
- `run_multiplier_regression.py`: simulator execution, complete profile matrix,
  strict parameter guards, expected failing assertion probes, and source hashes.

`multiplier_assertions.sv` is an additional native oracle. It interprets each
operand by subtracting 2^W from an unsigned magnitude when appropriate, then
multiplies in a wider signed domain. It reads no DUT arithmetic intermediates.
Its enabled-edge history checks arithmetic, aligned signedness and flags, invalid
clamping, bubbles, stalls, and reset. It rejects X/Z active operands and controls.
The one-precision-tick checking delay is excluded from synthesized hardware.

## Matrix and coverage

The full campaign contains 84 profiles, 19 invalid-parameter cases, and 48 expected
failing X/Z integration-assertion probes:

- Widths 1, 2, 3, 4, 5, 8, 16, and 32, crossed with latencies 0 through 4 and both
  reset styles, plus custom maximum latencies one and six.
- Every multiplicand pair and all four signedness modes for widths one through
  four; directed boundaries and 2,000 seeded random cycles for every profile.
- Zero, one, negative-one, signed minimum/maximum, unsigned maximum, and interior
  bit patterns; every pair of powers of two and their adjacent operand values.
- Full product encodings in low, middle, and high result bits; unsigned top-bit
  products with negative clear; zero and negative mixed-signedness products.
- All signedness transitions during consecutive valid operations, alternating
  bubbles, and eight signed/unsigned/mixed/small/zero-heavy/high-toggle distributions.
- Empty/partial/full pipelines, stalls of 1, 3, and 32 cycles, every reset occupancy,
  reset with enable low, between-edge reset assertion/release, immediate traffic
  after reset release, and reset interruption of randomized traffic.
- Unknown ignored operands and modes, changing invalid inputs, stalled unknown
  inputs, and rejection probes for X/Z active data, modes, valid, enable, and reset.

Coverage crosses both signedness bits with operand boundary encodings and operand
classes, product signedness with zero and the product sign bit, mixed direction
with numerical result sign, consecutive-run length with signedness transitions,
validity with enable, and occupancy with stall duration. The private checks also
require every stage to hold valid data, a bubble, and frozen valid/bubble state.
Boundary labels describe raw encodings; for example, all ones is negative one
when signed and the unsigned maximum otherwise. A consecutive-run bin of four
means four or more accepted valid operations.

Width-one mixed products cannot be positive, and unsigned one-bit products cannot
set the high bit of their two-bit result. Widths one and two have no interior
encoding outside boundary/power classes. These bins have explicit profile waivers.
Zero-latency profiles waive registered-state coverage; larger widths waive complete
operand enumeration in favor of the required boundary and seeded campaigns.

Each coverage JSON includes numerical/timing metadata for the implemented profile;
no external contracts package or dependency manifest is introduced. Passing the
regression requires exactly the decorated test, all mandatory goals, matching
parameters/seed/randomized count, and active native/internal checks. A missing
simulator or license reports `NOT_RUN`.

## Evidence limits

Ignored `build/validation/multiplier-*` artifacts record local Icarus simulation,
Verilator lint, Slang/Yosys structural synthesis, bounded binary safety checks,
and deliberate fault-detection checks. Structural checks verify one multiplier,
no adder or hidden accumulator, expected pipeline capacity, no registers at
latency zero, and no latches, unresolved cells, loops, initialized hardware state,
or generated clocks.

Bounded binary checks use a separate subtractive interpretation and enabled-edge
history with arbitrary operands, signedness, valid, stalls, and reset after an
initial reset. Local proofs completed 39 of the original 44 bounds; five bounds
reached the solver time limit. Those five profiles subsequently passed temporal
induction with additional valid-qualified invariants for each pipeline stage.
The original timeout results remain recorded as `NOT_RUN` in the bounded report.
Asynchronous reset uses an edge abstraction. Four-state simulation separately
checks between-edge reset behavior. These local binary checks do not establish
complete formal release signoff, physical reset release, or retiming equivalence.

Commercial lint/CDC/RDC/DFT/LP, technology mapping, macro equivalence, physical
timing, power/energy, and external contract compatibility require their own tools
and evidence. Missing checks are `NOT_RUN`; operand isolation activity checks do
not establish a total-energy benefit. VCS uses the same flow, but execution on a
licensed server remains required when unavailable locally.
