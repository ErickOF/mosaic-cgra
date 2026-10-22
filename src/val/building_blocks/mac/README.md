# Scalar integer MAC validation

This suite implements the self-checking PyUVM validation for
[`mosaic-mac`](../../../../../specs/building-blocks/mosaic-mac/README.md).
The RTL is [`mac.sv`](../../../rtl/building_blocks/mac.sv).

## Run

From `mosaic-cgra`:

```sh
make setup
make pyuvm SIM=icarus COCOTB_TOPLEVEL=mac
make mac-regression SIM=icarus
make mac-regression SIM=vcs VCS_BIN_DIR=/path/to/vcs/bin
```

The Makefile discovers the suite, registers the complete RTL dependency list,
adds the shared native HDL checker, and enables `MOSAIC_MAC_ASSERTIONS` during
RTL simulation. Synthesis and gate source lists exclude that checker.

The full campaign defaults to 2,000 randomized cycles per profile, with additional
directed and exhaustive cases. Override `MAC_SEED`, `MAC_RANDOM_CYCLES` (minimum
1,000), or `MAC_REGRESSION_BUILD`. For a selected profile:

```sh
.venv/bin/python src/val/building_blocks/mac/run_mac_regression.py \
    --sim icarus --build-dir build/icarus/mac/selected \
    --case w16_a32_sat1_l2_r1_m4 --random-cycles 2000
```

For a custom direct simulation, pass RTL parameters and matching `MAC_*`
expectations. Icarus uses `-Pmac.PARAMETER=value`; VCS uses
`-pvalue+mac.PARAMETER=value`. For example:

```sh
MAC_OPERAND_WIDTH=16 MAC_ACC_WIDTH=64 MAC_LATENCY=2 MAC_ASYNC_RESET=1 \
make pyuvm SIM=icarus COCOTB_TOPLEVEL=mac \
    SIM_BUILD=build/icarus/mac/custom \
    COMPILE_ARGS='-Pmac.OPERAND_WIDTH=16 -Pmac.ACC_WIDTH=64 -Pmac.LATENCY=2 -Pmac.ASYNC_RESET=1'
```

`MAC_CHECK_INTERNALS=0 MAC_HDL_ASSERTIONS=0` selects the public-port checker alone.
Disabled checks are reported as `NOT_RUN`. This driver uses 1 ps precision and
zero-delay RTL; it does not qualify SDF timing simulation. Gate-level power and
timing require a compatible stimulus timing policy and separate evidence.

## Composition and arithmetic

The implementation specializes the existing `dot_product` to one always-active
term and permanently enabled accumulation. No existing RTL module is modified.
Its reduction tree becomes a wire. Its `dff` and `operand_isolation` instances
provide pipeline storage and activity suppression. A separate persistent
`accumulator` would change the interface and recurrence behavior, so it belongs
in a containing datapath.

The core infers one shared signed multiplier with `OPERAND_WIDTH + 1` inputs.
Each extra bit is the selected sign extension or zero extension. Its low
`2 * OPERAND_WIDTH` bits contain the exact signed or unsigned product: only
redundant extension bits are removed. The product is extended to `ACC_WIDTH`
before the `ACC_WIDTH + 1` adder. Overflow and carry describe the pre-saturation
sum, while zero and negative describe the final result. Signed carry and unsigned
overflow/negative are forced low. Modular mode wraps only the final sum.

Saturation is selected per operation and statically removed when unsupported.
An unsupported saturation request or X/Z signedness/saturation control returns
a valid illegal response with zero result and arithmetic flags. Invalid and
illegal inputs isolate both multiplicands and the accumulator before arithmetic.
Unknown *legal active data* is rejected by integration assertions; it is not
silently converted into a numerical result. Unknown valid, reset, and enable are
also rejected at active observation points. Valid may be ignored during a known
pipeline freeze; zero-latency profiles ignore clock, reset, and enable entirely.

The released architecture is:

| Latency | Implementation |
|---|---|
| 0 | Combinational multiply, add, saturation, status, and output clamp |
| 1 | Combinational arithmetic followed by one response register |
| 2 and above | Product/addend/mode register, then arithmetic and response registers |

All registered stages share `i_clock_enable`. A latency of L produces a response
after L enabled rising edges, counting the sampling edge as the first edge.
Held valid results do not represent new completions. Reset clears valid and
illegal controls regardless of enable; arithmetic data and metadata remain
unreset, hold for bubbles/illegal operations, and cannot become visible without
an aligned legal valid bit. This requires the usual physical RDC and DFT checks.
There is no generated clock or implicit accumulator feedback.

The default maximum latency is four. A custom positive `MAX_LATENCY` is allowed;
the regression also checks a six-stage profile. The implementation rejects
invalid widths, nonbinary Boolean parameters, unknown parameters, latency outside
the declared range, and dimensions that overflow its supported packed-size range
at elaboration. No external contracts package or dependency manifest is required.

Each coverage JSON publishes numerical and timing metadata and conservative
full-range accumulation counts from zero. Representative counts are:

| Operand width | Accumulator width | Unsigned count | Signed positive count |
|---|---|---|---|
| 8 | 32 | 66,051 | 131,071 |
| 16 | 32 | 1 | 1 |
| 16 | 64 | 4,295,098,371 | 8,589,934,591 |
| 32 | 64 | 1 | 1 |

These are workload-independent bounds from the specification, not a promise that
saturation preserves an exact reduction. Feedback scheduling belongs to a wrapper:
a single dependent accumulator cannot accept updates at II=1 when its recurrence
latency exceeds one enabled edge. No recurrence integration is claimed here.

## Verification structure

- `transaction.py`: four-state requests and passive observations.
- `sequences.py`: directed, exhaustive, workload, pipeline, and seeded traffic.
- `driver.py`: stable input windows, optional real rising edges, and held samples.
- `monitor.py`: actual input/output ports, pre-NBA edges, storage activity, and
  multiplier/adder isolation nodes.
- `agent.py`, `env.py`: normal UVM grouping using shared `mosaic_uvm` wiring.
- `model.py`: independent unbounded Python integers, explicit two's-complement
  interpretation, destination limits, clamp, and modulo. The timing model uses
  enabled-edge deadlines and an ordered pending ledger rather than copying the
  implementation's product and response stages.
- `scoreboard.py`: checks every result and flag, exact deadline/order, reset
  removal, transaction conservation, arithmetic operand clamps, data enables,
  and between-edge pipeline holds.
- `coverage.py`: mandatory goals, observed crosses, explicit mathematical
  waivers, numerical metadata, and reproducible JSON evidence.
- `test_mac.py`: decorated PyUVM test and elaboration/port-width checks.
- `run_mac_regression.py`: profile matrix, strict elaboration guards, expected
  failing X/Z integration probes, JUnit checks, and source hashes.

The shared verification-only
[`dot_product_assertions.sv`](../dot_product/dot_product_assertions.sv) supplies
another wide-integer arithmetic oracle and enabled-edge history. It checks
arithmetic, flag applicability, invalid/illegal clamping, latency, stalls, reset,
and unknown active data/control. It never reads the DUT arithmetic intermediates.
Only its scalar configuration is instantiated; its delayed simulation checks are
excluded from hardware.

## Matrix and coverage

The campaign contains 80 profiles, 29 invalid-parameter guards, and 40 expected
failing integration-assertion probes:

- Required 8×8 into 32 and 16×16 into 32 profiles.
- 16×16 into 64 and 32×32 into 64 profiles.
- Width one, width two, and non-power-of-two widths/accumulators.
- Every default latency from zero through four, both reset styles, saturation
  enabled/disabled, and custom maxima one and six.
- Boundary multiplicands crossed with signedness and representative addends.
  Widths one/two with practical accumulation widths enumerate all multiplicands,
  all accumulator values, and every legal arithmetic mode. Width three enumerates
  all multiplicand pairs with representative accumulator boundaries and modes.
- Positive/negative overflow, carry, every clamp limit, exact limits without false
  flags, product-only and addend-only operations, modular zero, and final negative.
- Full-rate mode changes, bubbles, pipeline fill/drain, every reset occupancy,
  reset with enable low, between-edge reset assertion/release, and stalls of
  1, 3, and 32 cycles at empty, partial, and full occupancy.
- X/Z active modes, ignored invalid operands, illegal-operation operand clamps,
  and rejection probes for X/Z active operands, valid, clock enable, and reset.
- Eight representative traffic distributions plus reproducible randomized inputs,
  controls, bubbles, stalls, and reset interruptions.

Coverage records product/addend/final sign crosses, overflow direction by clamp,
carry by clamp, exact boundary by flags, mathematical/modular zero, final negative
by product/addend signs, valid/enable, occupancy/stall duration, reset occupancy,
and causes of illegal requests. Width-one negative products and negative overflow
are unreachable because signed operands are only zero or minus one; the report
waives those bins explicitly. Unsupported saturation and standalone feedback
integration also have explicit waivers.

A passing campaign requires exactly the expected decorated PyUVM test, all
mandatory coverage goals, the requested randomized count/seed/parameters, and
passing native/internal checks. Missing tools/licenses remain `NOT_RUN`.

## Evidence limits

Ignored `build/validation/mac-*` artifacts contain local simulation, Verilator
lint, Slang/Yosys structural synthesis, bounded binary checks, and deliberately
mutated arithmetic/control checks. Structural checks verify one multiplier and
one full-width adder, feature removal, absence of hidden zero-latency state,
unresolved cells, latches, combinational loops, and generated clocks.

Bounded binary safety checks use a separate wide mathematical sum and enabled
history with arbitrary inputs/stalls after an initial reset. They do not prove
unbounded behavior; asynchronous reset uses an edge abstraction. Four-state
simulation separately checks between-edge reset behavior.

VCS execution, full formal signoff, commercial lint/CDC/RDC/DFT/LP, technology
mapping, retiming equivalence, PrimeTime, PrimePower, physical energy, and external
contract compatibility require separate tools and evidence. They are never
reported as passing by the RTL/PyUVM campaign.
