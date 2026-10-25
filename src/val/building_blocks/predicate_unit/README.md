# Predicate unit validation

The RTL implements the [predicate register and logic specification](../../../../../specs/building-blocks/mosaic-predicate-unit/README.md).
One accepted command reads pre-edge predicate state, generates a masked Boolean
result, optionally updates one destination and captures one registered response.

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=predicate_unit
make predicate-unit-regression SIM=icarus
make predicate-unit-static PREDICATE_UNIT_YOSYS=/path/to/yosys-with-slang
make predicate-unit-formal PREDICATE_UNIT_YOSYS=/path/to/yosys-with-slang
```

VCS is the Makefile's default simulator. Use `SIM=vcs` and optionally
`VCS_BIN_DIR=/path/to/vcs/bin` on a licensed server. Local simulation uses Icarus;
Verilator provides lint and Yosys with the slang frontend provides generic
synthesis and formal induction. Results from unavailable tools are `NOT_RUN`.

## RTL and reuse

`predicate_unit_pkg.sv` defines a SystemVerilog opcode enum with the specification's
values: CLEAR=0, SET=1, LOAD=2, PASS_A=3, NOT_A=4, AND=5, OR=6, XOR=7 and INVALIDATE=8.
Values 9–15 are illegal. The encodings are repository-local, consistent with the
other implemented blocks; no external contract package or dependency manifest is
required. External `mosaic-contracts` integration remains `NOT_RUN`.

`predicate_unit.sv` uses these existing common modules:

| Module | Use |
|---|---|
| `dff` | Per-lane data and validity state, plus the complete response |
| `decoder` | Required source selection and optional destination selection |
| `operand_isolation` | Selected-entry/lane read slices and external LOAD input |
| `write_gate` | Suppress every destination update on atomic legality failure |

Each source port reduces independently isolated entry/lane slices. Constants,
LOAD and INVALIDATE bypass stored-source reads; unary commands disable source B.
Invalid cycles, disabled clock enable, reset and empty masks disable all read and
destination decoders. Compute-only commands disable the destination decoder.
Masked source slices clamp to zero before Boolean evaluation. The baseline uses
flip-flops; there is no memory macro, retention cell or generated clock.

Every lane has separate predicate data and validity. Data has no reset and holds
on invalidation. Validity and the entire response reset to zero, with reset taking
priority over clock enable. Stale data cannot become valid without a subsequent
legal write. The chosen reset style applies to validity and response together.
Unreset data requires integration RDC/DFT/power-aware signoff; local checks do not
substitute for those analyses.

The response appears after the accepting rising edge. With clock enable low,
predicate state and response hold; the consumer must account for a held response
only once. Source/destination aliases read old values on the accepting edge, and
a command on the next enabled edge observes the update. There is no ready signal
or output backpressure.

Legal result commands return `result_valid = lane_mask`, masked result bits zero,
and summaries over selected lanes. Empty masks are legal no-ops with both summaries
zero. INVALIDATE requires write enable even for an empty mask; it returns
`invalidated=1`, the selected updated mask and no distributable result. Addresses
are ignored whenever their source/destination is unused or the mask is empty.

Reserved/unknown opcodes, unknown masks/write enable, required unknown/unused
addresses and invalid selected source lanes produce an illegal response and no
state changes. Unknown clock-enable, reset or valid controls are integration failures.
Selected unknown LOAD data triggers native assertions before a legal commit;
masked LOAD data and unused inputs are ignored. The suite preserves four-state
values instead of coercing them to integers.

## Parameters and profile matrix

Defaults are depth four, four lanes, synchronous active-low reset and opcode width
four. `ADDR_WIDTH = max(1, ceil(log2(PRED_DEPTH)))` is derived. Architectural bank
storage is `2 * PRED_DEPTH * NUM_LANES` bits; the response is `3 * NUM_LANES + 5`
bits before synthesis optimization. Data contributes half the bank bits; only
validity and response need reset.

The 40 simulation and static profiles cross depths **1, 2, 3, 4, 8**, lane counts
**1, 2, 4, 8**, and **both reset styles**. Depth three exercises unused addresses;
depth one still has a one-bit address and rejects encoding one when required.
The test checks actual elaborated parameters and all port widths.

For a custom scalar depth-two test, set both the RTL parameter and Python setting:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=predicate_unit \
  PREDICATE_UNIT_PRED_DEPTH=2 PREDICATE_UNIT_NUM_LANES=1 \
  COMPILE_ARGS='-Ppredicate_unit.PRED_DEPTH=2 -Ppredicate_unit.NUM_LANES=1'
```

VCS uses `-pvalue+predicate_unit.PARAMETER=value`. The regression supplies matching
settings automatically. `PREDICATE_UNIT_RANDOM_CYCLES` defaults to 2000 (minimum
1000), `PREDICATE_UNIT_SEED` selects a reproducible seed and
`PREDICATE_UNIT_JOBS` controls parallel simulation processes (default 4, range
1–32; use 1 when only one simulator license is available). All three runners
accept repeated `--case` selections.

Nineteen invalid-parameter cases check zero/negative/unknown/oversized dimensions,
invalid reset/opcode-width values and overflow of the supported state geometry.
They must fail at elaboration through the named parameter guard, before runtime.

## PyUVM organization and evidence

Configuration, transactions, sequences, driver, monitor, agent, environment,
reference model, scoreboard and coverage are separate files. The suite reuses
`mosaic_uvm` agent/environment wiring, four-state conversion and regression
execution, generic vector-lane transaction records and the multiplier monitor's
edge/watch coordination. Its prediction does not use DUT internals or RTL helper
functions.

The Python oracle keeps independent lane lists and plans an entire command from a
pre-edge snapshot before mutating state. The scoreboard checks every response,
all validity bits and every initialized physical data bit. A passive monitor also
checks each real DFF's D, Q, enable and reset pins, including clockless windows.
The independent native SystemVerilog oracle uses direct addressed bit updates,
providing an additional check of arithmetic-free logic, state and timing.

Stimulus includes all opcodes, masks/populations, every address encoding, all
source/destination alias combinations, dependent pairs of legal opcodes, partial
validity and atomic failures, compute-only/writeback/invalidation, nested-condition
and loop-tail traces, context preservation/invalidation, long stalls, clockless
commands and reset with empty/partial/full validity. Unknown controls/addresses are
checked as illegal, while ignored X/Z data is tolerated.

Banks with at most two predicate bits in total are exhaustive across all three
architectural states per lane (invalid, valid false, valid true), all 16 opcodes,
all masks, every source/destination address encoding, every external input and
both write-enable values. **The bank is restored before each candidate**, so
writes and invalidations cannot change the intended starting state. Each reset
style exercises 3,072 exhaustive commands at depth1/lanes1, 36,864 at depth1/lanes2
and 9,216 at depth2/lanes1, plus directed and random traffic.

Coverage requires opcode/population/write crosses, address required/ignored
classes, source validity by port, all alias classes, every lane read/write/hold/
invalidate transition, invalidation of valid and invalid state, summary/population
crosses, dependent opcode pairs, each illegal cause with atomic no-update, context
traces and stall/reset classes. Profile-specific waivers identify impossible
partial populations, absent unused addresses and depth-one source-B-first errors.
Coverage is emitted only from checked observations; missing mandatory goals fail
the test.

Twenty-eight negative runs inject X and Z into reset, clock enable, valid and
each of four active LOAD lanes, with both reset styles. A run passes only when
the expected native protocol assertion terminates it. Python checker failures
cannot satisfy this evidence.

## Static and formal checks

The static target lints and generically synthesizes all 40 profiles. It rejects
latches, combinational loops, unresolved modules, unexpected cells and internal
clocks, checks reset topology and confirms that all predicate data bits are
unreset. Reports include architectural storage, optimized resettable bits and
actual cell counts. There is no technology mapping or physical timing claim.

The formal target proves sequential refinement by SAT induction for **26 profiles**:
depths 1–3 with lanes 1–4 and both resets, plus depth4/lanes4 with both resets.
The invariant compares all validity/response bits and all valid predicate data,
leaving uninitialized invalid data unconstrained. After reset initialization,
induction covers arbitrary command sequences, values, masks, aliasing, stalls,
atomic failure and reinitialization. The reset is not constrained after the first
sample. Async reset is modeled at sampled clocks using `async2sync`; clockless
assertion and X/Z behavior are separately exercised by four-state simulation.
Clock-gate/memory replacement equivalence is `NOT_RUN` because no replacement is
implemented.

Simulation reports live under `build/<sim>/predicate_unit/regression/summary.json`;
static and formal reports live under `build/static/predicate_unit/summary.json`
and `build/formal/predicate_unit/summary.json`. They include source/dependency and
verification hashes, exact parameters and tool versions or simulator logs. Each
simulation must execute exactly the decorated `PredicateTest` and produce matching
coverage. Build evidence is ignored by Git.

Commercial lint, CDC, RDC, DFT, VC LP, retention, technology synthesis, PrimeTime,
PrimePower and physical signoff remain external `NOT_RUN` checks. VCS requires a
licensed server and is `NOT_RUN` locally. No local test constitutes product release
or signoff for those flows.
