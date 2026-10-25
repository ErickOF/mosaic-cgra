# Scalar integer ALU validation

This suite validates the
[scalar ALU specification](../../../../../specs/building-blocks/mosaic-scalar-alu/README.md)
against [`scalar_alu.sv`](../../../rtl/building_blocks/scalar_alu.sv).

## Run

From `mosaic-cgra`:

```sh
make setup
make pyuvm SIM=icarus COCOTB_TOPLEVEL=scalar_alu
make scalar-alu-regression SIM=icarus
make scalar-alu-regression SIM=vcs VCS_BIN_DIR=/path/to/vcs/bin
make scalar-alu-static SCALAR_ALU_YOSYS=/path/to/yosys
make scalar-alu-formal SCALAR_ALU_YOSYS=/path/to/yosys
```

Static and formal targets require Yosys with the slang frontend. Static checks also
require Verilator. `SCALAR_ALU_VERILATOR` overrides its executable. Build locations
are controlled by `SCALAR_ALU_REGRESSION_BUILD`, `SCALAR_ALU_STATIC_BUILD`, and
`SCALAR_ALU_FORMAL_BUILD`. Missing tools are `NOT_RUN` and return a nonzero status.

`SCALAR_ALU_SEED` and `SCALAR_ALU_RANDOM_CYCLES` configure simulation. The default
is 2,000 random evaluations per profile, with a minimum of 1,000 in regression
runners. Directed and exhaustive requests are additional. Each campaign writes a
JSON summary with source and verification hashes and per-profile evidence.
Simulation includes JUnit results, parameters, coverage and diagnostic logs.

To select a profile:

```sh
.venv/bin/python src/val/building_blocks/scalar_alu/run_scalar_alu_regression.py \
    --sim icarus --build-dir build/icarus/scalar_alu/selected \
    --case w5_s1_m0 --random-cycles 1000
```

A custom direct run needs matching compiler overrides and `SCALAR_ALU_*` expected
parameters. Icarus uses `-Pscalar_alu.PARAMETER=value`; VCS uses
`-pvalue+scalar_alu.PARAMETER=value`. For example:

```sh
SCALAR_ALU_DATA_WIDTH=16 SCALAR_ALU_SUPPORT_MINMAX=0 \
make pyuvm SIM=icarus COCOTB_TOPLEVEL=scalar_alu \
    SIM_BUILD=build/icarus/scalar_alu/custom \
    COMPILE_ARGS='-Pscalar_alu.DATA_WIDTH=16 -Pscalar_alu.SUPPORT_MINMAX=0'
```

The default native checker uses `SCALAR_ALU_HDL_ASSERTIONS=1`. Set
`SCALAR_ALU_CHECK_INTERNALS=0 SCALAR_ALU_HDL_ASSERTIONS=0` to use public-port
checks alone. Disabled checks report `NOT_RUN`. `TEST_SETTLE_NS` can extend the
driver observation interval for a separately qualified integration simulation;
zero-delay RTL uses a 2 ps settling interval and a later held observation.
The synthesis and gate source lists exclude the delayed HDL checker.

## RTL and opcode contract

The ALU has no clock, reset, pipeline, validity register or hidden state. Its latency
is zero registered cycles; a surrounding registered interface can evaluate one
operation per cycle. Any buffering or transport belongs outside this module.

The implementation reuses the released `operand_isolation` primitive at the input
and arithmetic cones and `mux` for conditional selection and optional min/max.
No existing RTL module is changed. The repository has no standalone reusable
combinational adder; the arithmetic is implemented directly without introducing
state from the counter or accumulator blocks.

`scalar_alu_pkg.sv` publishes the specification's exact five-bit opcode enum:
ADD/SUB at 0/1; AND/OR/XOR/NOT at 2..5; SLL/SRL/SRA at 6..8; EQ/NE/LT/LE/GT/GE
at 9..14; SELECT at 15; PASS_A/PASS_B at 16/17; MIN/MAX at 18/19. Encodings 20..31
are illegal. These local baseline encodings require no external contract package.
Integration with a versioned external `mosaic-contracts` release remains `NOT_RUN`.

`DATA_WIDTH` defaults to 32; both optional features default to one. `OPCODE_WIDTH`
must be exactly five, and `SHIFT_WIDTH` is a nonoverridable derived local parameter.
Invalid, unknown, nonbinary and overflowing parameters fail elaboration through
`scalar_alu_parameters_must_be_valid`. Widths 1, 2, 3, 4, 5, 8, 16, 32 and 64 are
covered release profiles; 64 is the maximum width claimed by this campaign.

One W+1-bit adder implements ADD and SUB, complementing B and adding one for
subtraction. ADD reports unsigned carry even in signed mode. SUB reports unsigned
borrow and forces carry low. Signed overflow is qualified by `i_signed` and derives
from the modular result. Saturation clamps only ADD/SUB and preserves those raw
arithmetic flags. Its limits work at width one without invalid part selects.

Signed ordering first compares operand sign bits, then unsigned magnitudes.
SRA has a separately typed signed shift expression, preventing result-mux context
from coercing it into a logical shift. The complete B operand is checked against
W before narrowing to the barrel-shifter amount, so large and non-power-of-two
shift amounts cannot wrap. Oversized SRA replicates the original sign bit.

Zero and negative describe the final legal result. A true comparison is a
zero-extended one; at width one its negative flag is therefore also one. Every
inapplicable flag and every noncomparison predicate is zero.

Both feature parameters select static generate branches. Compiling saturation out
removes its clamp selection; compiling min/max out removes its selection mux.
The shared adder and comparison logic remain because other opcodes require them.

## Required and ignored inputs

Known-low enable clamps all outputs, including illegal status, regardless of other
inputs. Enabled illegal requests assert only `o_illegal_operation`. This includes
reserved/unknown opcodes, unsupported features, misplaced saturation and unknown
required mode controls. An unknown enable also fails closed with illegal status.

`i_saturate` is always required for an enabled request. `i_signed` is required for
ADD/SUB, ordered comparisons and min/max; it is ignored for other operations.
`i_predicate` is required only for SELECT. NOT and PASS_A ignore B, PASS_B ignores
A, and SELECT ignores its unselected operand. Ignored controls and operands can
contain X/Z without invalidating an otherwise legal evaluation.

Unknown active operands are integration violations rather than numerical input
values. The native checker reports them even if an AND mask, comparison or mux
happens to produce known outputs. The positive campaign checks ignored X/Z and
illegal-control containment; separate negative probes require active-operand
assertions to fire. Four-state cases are never converted into two-state integers
before checking their legality or relevance.

## Verification and evidence

Transactions, sequences, driver, passive monitor, agent, environment, scoreboard,
reference model and coverage remain separate. Agent wiring, environment wiring,
four-state conversion, result validation and campaign execution reuse `mosaic_uvm`.

The Python oracle uses unlimited-precision signed/unsigned integers, explicit width
masking, range comparisons for overflow, and explicit floor construction for SRA.
It reads actual DUT ports and checks every result/status bit in settled and held
windows. Optional private checks verify ignored operands and inactive arithmetic
inputs are isolated. There is no synthetic clock or sequential transaction latency.

The independent native HDL oracle uses widened mathematical values and constructs
shifted bits individually. It checks the complete result, predicate, flag and
legality record and separately asserts that required active operands are known.
It never reads DUT decode or arithmetic intermediates.

The 36 simulation profiles cover all width/feature combinations. Every profile
exercises all 32 opcodes with every signedness, saturation and predicate mode,
including unsupported requests. Seeded random operands cover every such mode.
Widths one through three additionally exhaust every operand pair and control mode.
Directed tests include arithmetic limits, all raw carry/borrow/overflow crosses,
every reachable saturation direction, both select polarities, comparison truth
values, every shift boundary, high shift-amount bits, walking bit patterns, and
X/Z controls and ignored operands. Required coverage crosses and documented
width-specific exclusions are written to `coverage.json`.

The runner also requires 20 strict invalid-parameter checks and 20 X/Z operand
assertion probes. No skipped, missing or mismatched decorated test counts as a pass.

`scalar-alu-static` runs warning-fatal Verilator lint and Yosys/slang synthesis
elaboration for all 36 profiles. It checks unresolved references, combinational
loops and netlist cell types. Registers, latches, memories, multiplication,
division and modulo cells are forbidden. Generic cell counts support feature-removal
comparisons; they are not technology area or timing results.

`scalar-alu-formal` proves the entire output record for arbitrary two-state inputs,
all opcodes and control combinations in all 36 profiles. It uses the native
mathematical oracle with observation delays removed, flattened Yosys/slang logic,
and SAT. It does not assume enable, opcode legality, signedness, saturation,
predicate polarity or particular operands. X/Z containment remains simulation
coverage. Logs include generated proof scripts, tool versions and source hashes.

Commercial VCS execution, VC Lint/CDC/RDC, DFT, UPF/VC LP, mapped synthesis,
technology equivalence, BCT integration constraints, PrimeTime and PrimePower
remain separate release checks. Missing licenses, libraries or reports must stay
`NOT_RUN`; generic synthesis and combinational formal proofs do not qualify those
physical or commercial signoff requirements.
