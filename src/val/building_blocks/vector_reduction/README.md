# Vector reduction validation

The RTL implements the [integer vector reduction specification](../../../../../specs/building-blocks/mosaic-vector-reduction/README.md):
exact widened SUM, signed/unsigned MIN and MAX, and bitwise AND and OR over a
least-significant-element-first packed vector and element mask.

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=vector_reduction
make vector-reduction-regression SIM=icarus
make vector-reduction-static VECTOR_REDUCTION_YOSYS=/path/to/yosys-with-slang
make vector-reduction-formal VECTOR_REDUCTION_YOSYS=/path/to/yosys-with-slang
```

Simulation also supports `SIM=vcs` and `VCS_BIN_DIR=/path/to/vcs/bin`. VCS is the
Makefile's default backend. Verilator supplies local lint, and Yosys with the slang
frontend supplies generic synthesis and formal checking. Missing commercial tools
are recorded as `NOT_RUN`.

## Architecture and reuse

`vector_reduction.sv` instantiates one balanced `vector_reduction_tree` for each
enabled operation. Every SUM leaf extends to `ELEMENT_WIDTH + ceil(log2(N))`
before addition, and every SUM node retains that width. MIN/MAX nodes carry
selection-valid metadata, so masked and padded values cannot win. Padding uses
zero for SUM/OR and all ones for AND. Mask population has its own balanced tree.
No reduction serializes elements or keeps persistent accumulation state.

The implementation reuses `operand_isolation`, `write_gate`, and the generic
`vector_lane_pipeline` helper, which uses common `dff` instances. Each tree has
separate isolated leaf inputs and a gated signedness control. Only the selected
operation receives selected data. Disabled trees are absent after elaboration.

The operation trees are combinational; `LATENCY` adds response pipeline stages.
All fields advance together on the shared clock enable. Response validity and
metadata reset; numerical data remains unreset and holds on bubbles. Invalid and
illegal outputs are clamped. Reset wins over clock enable, and no generated clock
is introduced. This topology does not claim that increasing latency splits the
arithmetic critical path.

`vector_reduction_pkg` defines opcode enums and aliases the existing vector result
format type. It reuses element (`01`) and accumulator (`11`) encodings from
`vector_lane_pkg`. There is no vector-lane or dot-product datapath dependency and
no cyclic source dependency. The flow uses the existing repository encodings;
external `mosaic-contracts` integration is `NOT_RUN`, consistent with the other
implemented blocks.

| Opcode | Operation | Empty-mask result | Result format |
|---|---|---|---|
| 0 | SUM | Zero | Accumulator |
| 1 | MIN | Illegal | Element |
| 2 | MAX | Illegal | Element |
| 3 | AND | Element-width all ones | Element |
| 4 | OR | Zero | Element |
| 5–7 | Reserved | Illegal | Zero |

Legal results extend according to `i_signed`, including AND/OR identities. Illegal
responses retain `o_valid=1` and clear every other field except illegal status.
Bubbles produce all-zero responses after the same enabled-edge latency. Unknown
opcode, mask or signedness is illegal. Selected X/Z data triggers native protocol
assertions; masked X/Z data and all request inputs during bubbles are ignored.

## Parameter profiles

Defaults are four INT8 elements, INT32 result, all features enabled, latency one,
and synchronous active-low reset. The test checks actual elaborated parameters
and every port width. The regression sets matching elaboration flags and Python
expectations automatically, with a separate build directory for every case.

For a custom single-element, one-bit, zero-latency simulation:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=vector_reduction \
  VECTOR_REDUCTION_ELEMENT_WIDTH=1 VECTOR_REDUCTION_NUM_ELEMENTS=1 \
  VECTOR_REDUCTION_ACC_WIDTH=1 VECTOR_REDUCTION_LATENCY=0 \
  COMPILE_ARGS='-Pvector_reduction.ELEMENT_WIDTH=1 -Pvector_reduction.NUM_ELEMENTS=1 \
  -Pvector_reduction.ACC_WIDTH=1 -Pvector_reduction.LATENCY=0'
```

VCS uses `-pvalue+vector_reduction.PARAMETER=value` instead of Icarus `-P` flags.
`VECTOR_REDUCTION_RANDOM_CYCLES` defaults to 2000 and must be at least 1000.
`VECTOR_REDUCTION_SEED` controls reproducibility; `VECTOR_REDUCTION_JOBS` controls
parallel simulation processes (default 4, range 1–32; use 1 for a single license).
The runner's `--case` option selects individual profiles.

The 78-profile matrix covers:

- Latencies zero through eight with both reset styles.
- Element widths 1, 2, 3, 4, 5, 8, 16 and 32.
- Counts 1, 2, 3, 4, 5, 7 and 8, including non-power-of-two padding.
- Minimum legal result widths and wider accumulation buses.
- Four INT8/INT16 elements into INT32, eight INT8 elements into INT32, and
  four INT32 elements into 34 or 64 bits.
- All eight feature combinations with both reset styles.
- A configurable maximum latency of ten with both reset styles.

## PyUVM organization and checks

Configuration, transactions, sequences, driver, monitor, agent, environment,
model, scoreboard and coverage are separate components. The suite reuses shared
`mosaic_uvm` components and four-state conversions, generic vector-lane transaction
records, the existing edge-observation machinery, and register/conservation checks.
It adds reduction-specific stimulus and tree-leaf isolation checks.

The Python oracle walks selected packed elements sequentially and uses unbounded
integers, independently of the balanced RTL tree. A deadline ledger checks latency,
bubbles, reset cancellation and response conservation without copying RTL register
arrays. An independent SystemVerilog oracle uses a flat mathematical loop and a
whole-response history for native arithmetic, protocol, status and latency checks.
The passive monitor checks the actual data/enable/reset/output pins of every DFF,
including between-edge changes and clockless reset behavior.

Stimulus includes boundary values, signed extrema, positive/negative sum growth,
mixed-sign cancellation, repeated and monotonic vectors, duplicate extrema, every
mask population, one-hot and complementary masks, mixed opcodes, bubbles, X/Z,
long stalls, pipeline fill/drain, reset at every occupancy and seeded random data.
Every packed input, mask, opcode and signedness is exhausted when `E*N <= 6` and
`N <= 3`; larger profiles use boundaries and randomized vectors.

Coverage goals require opcode/signedness/population crosses, selected/masked use
of every index, empty-mask legality, formats and extension, extrema boundaries
and ties, signed SUM classes, every opcode predecessor/successor pair, every valid
stage state, stalls of 1/3/32 opportunities, reset by operation/occupancy and exact
response conservation. Profile-specific impossible bins have explicit waivers.
Missing required coverage fails the test.

The runner also checks 48 strict parameter elaboration failures and 20 expected
native X/Z failures, including selected elements at every index of a five-element
profile. The extra zero-latency probes change selected data to X/Z while AND-zero
or OR-ones keeps the numerical output unchanged. Parameter errors must name the intended guard; unrelated compiler errors
cannot pass. A simulation must run exactly one expected decorated PyUVM test and
produce passing JUnit and coverage evidence. Reports include seeds, parameters,
RTL/dependency hashes and verification-source hashes.

## Static and formal scope

Static checks lint and generically synthesize all 78 profiles. They check for
latches, combinational loops, unresolved modules, unexpected arithmetic cells,
generated clocks, hidden state at zero latency and retained disabled trees.
Generic synthesis does not qualify technology timing, area or physical power.

Formal checking contains 130 combinational equivalence proofs: element widths
one through four, element counts one through four, all eight feature combinations,
and the INT8/INT32 and INT16/INT32 release profiles. Thirty-two bounded sequential
profiles cover every registered baseline latency and both reset styles, plus every
feature combination with both resets. The reference is independent of tree shape.

Sequential checks cover `2*LATENCY + 6` sampled edges after an initial reset, with
arbitrary subsequent requests, masks, modes, clock enables and resets. Longer
profiles use incremental base cases through the same depth. These are bounded
checks, not unbounded induction. Clockless asynchronous behavior is additionally
checked in simulation. The formal runner supports `--jobs`, `--timeout` and
`--resume`; cached proofs require matching source hashes, parameters, tool version
and successful assertion-proof markers.

VCS, commercial lint, CDC/RDC, DFT, VC LP, technology mapping, post-route timing,
physical power, hierarchical/VCT integration and external contracts remain
`NOT_RUN` until the corresponding tools and integration evidence are available.
Logical operand isolation alone does not establish physical energy savings.
