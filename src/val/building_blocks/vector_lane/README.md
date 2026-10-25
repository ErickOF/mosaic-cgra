# Vector lane validation

The implementation follows the [integer vector lane specification](../../../../../specs/building-blocks/mosaic-vector-lane/README.md).
It implements one physical lane; vector-wide scheduling, writeback atomicity and
persistent accumulation belong to the tile wrapper.

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=vector_lane
make vector-lane-regression SIM=icarus
make vector-lane-static VECTOR_LANE_YOSYS=/path/to/yosys-with-slang
make vector-lane-formal VECTOR_LANE_YOSYS=/path/to/yosys-with-slang
```

The simulation targets also accept `SIM=vcs` and `VCS_BIN_DIR=/path/to/vcs/bin`.
VCS is the Makefile's default simulator. Static checks require Verilator and
Yosys with the slang frontend. Formal checks use Yosys/slang and its SAT engine.
Missing commercial tools or licenses are recorded as `NOT_RUN`.

## Architecture and reuse

`vector_lane.sv` composes the existing `scalar_alu`, `multiplier`, `mac`,
`operand_isolation`, `write_gate` and `dff` modules. The MAC itself reuses the
one-term `dot_product` implementation. Shared opcode values refer directly to
`scalar_alu_pkg`; `vector_lane_pkg` adds MUL, MAC and result-format enums. This
uses repository encodings, consistent with the other implemented blocks; an
external `mosaic-contracts` integration is not claimed.

| Path | Arithmetic width | Unit latency | Extra alignment |
|---|---|---|---|
| ALU | `ELEMENT_WIDTH` | 0 | `LANE_LATENCY` |
| MUL | `2 * ELEMENT_WIDTH` | `MUL_LATENCY` | `LANE_LATENCY - MUL_LATENCY` |
| MAC | `ACC_WIDTH` | `MAC_LATENCY` | `LANE_LATENCY - MAC_LATENCY` |

`vector_lane_pipeline.sv` aligns validity, result format, signedness, predicates
and flags with the numerical result. Reset clears response controls. Numerical
alignment data has no reset and captures only valid incoming results; its stale
contents cannot escape the output clamp. The entire pipeline advances on the
same clock enable. Disabled MUL/MAC branches omit their unit, input isolation and
alignment. No generated clock or persistent accumulator is introduced.

Every request produces one response, including suppressed and illegal requests.
`o_write_enable` is asserted only for a legal executed result. A masked lane wins
before predicate or arithmetic validation; a known false execution predicate
similarly ignores arithmetic controls and data. SELECT has a separate predicate.
Ignored X/Z inputs are allowed; unknown required controls return an illegal
response. Native protocol assertions reject unknown active arithmetic operands,
active valid, or required clock/reset controls.

Element results extend to `ACC_WIDTH` according to `i_signed`, including logic,
shift and select results. Comparisons produce an unsigned Boolean and predicate.
MUL keeps the exact product; MAC adds the full product to the external accumulator.
Unsigned ADD/MAC alone can assert carry, and unsigned SUB alone can assert borrow.
Overflow describes signed ADD/SUB/MAC before saturation. Suppressed, illegal and
invalid responses clear all numerical results, metadata and flags.

## Running parameter profiles

The default profile is INT8/INT32 with all features enabled and all latencies 1.
For a custom direct simulation, pass both elaboration flags and matching test
expectations. For example, a zero-latency INT16/INT64 lane with Icarus:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=vector_lane \
  VECTOR_LANE_ELEMENT_WIDTH=16 VECTOR_LANE_ACC_WIDTH=64 \
  VECTOR_LANE_LANE_LATENCY=0 VECTOR_LANE_MUL_LATENCY=0 VECTOR_LANE_MAC_LATENCY=0 \
  COMPILE_ARGS='-Pvector_lane.ELEMENT_WIDTH=16 -Pvector_lane.ACC_WIDTH=64 \
  -Pvector_lane.LANE_LATENCY=0 -Pvector_lane.MUL_LATENCY=0 -Pvector_lane.MAC_LATENCY=0'
```

For VCS, use `-pvalue+vector_lane.PARAMETER=value` in `COMPILE_ARGS`. The regression
runner supplies parameters and expectations together, checks the elaborated
values, and uses a separate build directory for each profile. It supports `--case`
for a selected profile. `VECTOR_LANE_RANDOM_CYCLES` defaults to 2000, with a minimum
of 1000; `VECTOR_LANE_SEED` controls reproducibility. `VECTOR_LANE_JOBS` controls
parallel simulation processes (default 4, range 1 through 32; set 1 for a single
simulator license).

## PyUVM structure and checks

Transactions, configuration, sequences, driver, monitor, agent, environment,
reference model, scoreboard and coverage are separate components. The environment
and agent reuse `mosaic_uvm`; the monitor reuses the multiplier suite's sampling
and between-edge watch machinery. The arithmetic oracle reuses the independent
Python scalar-ALU model, then applies lane extension and status rules. MUL/MAC
predictions use unbounded Python integers. A deadline ledger checks enabled-edge
latency and conservation without reproducing the RTL's register arrays.

A second, independent, wide-integer SystemVerilog reference checks arithmetic,
metadata, path selection, reset and latency through native assertions. The passive
monitor samples before, at and after actual rising edges, checks operand isolation,
and recursively observes every reused DFF's data, enable, reset and output. It
checks capture/hold behavior and detects changes between clock edges.

The 151-profile regression covers:

- Every legal `(LANE_LATENCY, MUL_LATENCY, MAC_LATENCY)` combination from zero
  through four with both reset styles (110 profiles).
- All 16 MUL/MAC/saturation/MINMAX feature combinations.
- Width one, non-power-of-two widths, minimum and wider accumulator widths,
  INT4/INT16 and INT4/INT32, INT8/INT16/INT32/INT64, and INT16/INT32/INT64.
- Custom maximum latency six and ignored disabled-unit latency parameters.
- Boundary arithmetic, signed and unsigned saturation, full products, MAC
  accumulator boundaries, comparisons, SELECT, and shift overshifts.
- Exhaustive small operand pairs for element widths one and two, crossed with
  all 22 operation encodings and both signedness/saturation modes.
- All 32 opcode encodings by signedness/saturation and by mask/predication,
  every applicable result format/status, and all 1024 predecessor/successor pairs.
- X/Z suppression priority, ignored operands, illegal controls, bubbles,
  seeded random traffic, pipeline fill/drain, stalls of 1/3/32 opportunities,
  reset at every occupancy, clockless reset, and refill without stale responses.
- 56 strict elaboration failures and 30 expected native X/Z protocol failures.

Coverage goals fail the test when missing. Width/feature exclusions and external
checks are recorded in each report. Each case contains JUnit results, coverage,
parameters and simulator logs. The campaign summary records source/dependency and
verification SHA-256 hashes, seed, profile results and external-tool status.

## Static and formal scope

Static checks lint and generically synthesize all 151 profiles. They reject
latches, combinational loops, unresolved modules and unexpected arithmetic cells,
check that all sequential cells use `i_clk`, that zero-latency profiles have no
state, and that disabled units disappear. Generic synthesis does not qualify
mapped area, timing, scan or power.

Formal checks compare all output bits with the independent SystemVerilog oracle.
There are 64 combinational proofs (element widths 1 through 4, minimum legal
accumulator, every feature combination) and 110 bounded sequential checks (all
registered latency combinations at width one, both reset styles, plus latency six).
Sequential checks cover `2 * LANE_LATENCY + 6` sampled edges after initial reset,
with arbitrary requests, clock enables and subsequent resets. These are bounded
checks, not unbounded induction. Latencies above four use incremental base-case
checks through the same depth, without an induction step. Asynchronous reset uses a sampled-clock
abstraction; clockless assertion and release are checked in simulation.

The formal runner accepts `--jobs` (default 4), `--timeout` (default 600 seconds
per case), and `--resume`. Resume retains
successful cases only when the RTL/reference source hashes, tool version and
profile parameters match, with successful assertion-proof markers in their logs.

VCS, commercial lint, CDC/RDC, DFT, VC LP, technology mapping, post-route timing and
power, vector-wrapper alignment/atomicity, and external contract integration need
the corresponding server tools or integration context. They remain `NOT_RUN`
until that evidence is produced. Logical isolation checks alone do not establish
physical power savings.
