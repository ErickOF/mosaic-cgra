# Accumulator RTL and PyUVM validation

This suite implements the [integer accumulator-bank specification](../../../../../specs/building-blocks/mosaic-accumulator/README.md).
The RTL is [`accumulator.sv`](../../../rtl/building_blocks/accumulator.sv), with
fixed baseline command enums in [`accumulator_pkg.sv`](../../../rtl/building_blocks/accumulator_pkg.sv).
It reuses the repository's `dff`, `lane_mask`, and `operand_isolation` modules.
No external contract package or dependency manifest is introduced. Integrators
must map these specification-defined encodings into their released contracts.
Exact dependency and verification source hashes are recorded by the runner.

## Run

```sh
make setup
make accumulator-regression
make accumulator-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=accumulator
```

The regression defaults to VCS. Local runs use native Icarus Verilog and the
actual decorated `test_accumulator.AccumulatorTest` PyUVM test. Python 3.10 or newer
is required; local validation uses Python 3.12. Set `ACCUMULATOR_SEED`,
`ACCUMULATOR_RANDOM_CYCLES` (at least 1000), and `ACCUMULATOR_REGRESSION_BUILD` to
configure the campaign. Defaults are seed `20261020` plus profile index, 2000
random clock opportunities per profile, and `build/<simulator>/accumulator/regression`.

A filtered campaign still runs all parameter guards and protocol probes:

```sh
.venv/bin/python src/val/building_blocks/accumulator/run_accumulator_regression.py \
  --sim icarus --build-dir build/accumulator-focused \
  --case w32_n4_sub1_sat1_a0
```

For direct Make invocation, compiler parameters must match the expected
`ACCUMULATOR_ACC_WIDTH`, `_NUM_LANES`, `_SUPPORT_SUBTRACT`, `_SUPPORT_SATURATION`,
and `_ASYNC_RESET` environment variables. `COMMAND_WIDTH` must remain 2.
For example:

```sh
ACCUMULATOR_ACC_WIDTH=8 ACCUMULATOR_NUM_LANES=4 \
make pyuvm SIM=icarus COCOTB_TOPLEVEL=accumulator \
  SIM_BUILD=build/icarus/accumulator/custom \
  COMPILE_ARGS='-Paccumulator.ACC_WIDTH=8 -Paccumulator.NUM_LANES=4'
```

VCS uses `-pvalue+accumulator.PARAMETER=value` instead of Icarus `-P`. Use a new
build directory when changing a direct invocation's geometry. The regression
runner writes parameter dependencies to force the intended elaboration.
The Makefile discovers the new `building_blocks` category and supplies the enum
package and common primitives in order for simulation and synthesis.

## State and numerical behavior

Each lane holds a value, validity, and signedness. Lane zero is the least-significant
word and bit zero of every mask/status bus. Commands are `CLEAR=0`, `LOAD=1`,
`ADD=2`, `SUB=3`. The command, signedness and saturation mode are shared by all
selected lanes; arithmetic and carry/borrow never cross lane boundaries.

CLEAR establishes valid typed zero. LOAD establishes valid state and may change
signedness. ADD/SUB require valid state with matching signedness in every selected
lane. One failing selected lane cancels the complete command; masked invalid or
incompatible lanes do not participate. A zero mask is a no-op only when the global
command, feature, signedness and saturation controls are legal.

The numerical oracle uses arbitrary-precision Python integers, mathematical signed
ranges and modulo arithmetic. It independently predicts carry, borrow, signed
overflow, saturation, zero and negative flags. Saturation reports the mathematical
range error separately from whether the final value changes the modular result.
CLEAR/LOAD and every inapplicable status field remain zero as specified.

There is one command update and one response advancement per enabled rising edge.
Dependent commands see the preceding updated state. `o_data`, `o_state_valid`,
and `o_state_signed` are persistent outputs; the other outputs are registered
command responses. An enabled bubble clears response valid/status without changing
state. A disabled clock holds both persistent state and the entire old response,
including valid. The tile must commit each held response only once and must not
commit an illegal update as successful work.

Reset clears lane validity and response state independently of clock enable.
It does not create valid zero state. Payload and signedness DFF resets are tied
inactive; their stale values are hidden by validity clamping. Reset is sampled
at a clock edge in synchronous mode and asserts immediately in asynchronous mode.
Short between-edge reset pulses therefore preserve synchronous state and invalidate
asynchronous state. Reset release synchronization belongs to integration.

SUB and saturation use static feature branches. Disabled requests remain encoded
and produce illegal-operation responses. Their arithmetic/clamp cones are absent.
The fixed response interface remains present, and disabled-feature status is zero
on every initialized response. Generic structural accounting includes that full
response bank; it does not assume technology optimization of constant status bits.
Before technology optimization, logical storage is
`NUM_LANES * (ACC_WIDTH + 9) + 2` bits: payload, signedness, validity and the
`2 + 7 * NUM_LANES` response bank.

Accepted unknown commands, masks, signedness or saturation controls are illegal,
with no lane update and no arithmetic status. Unknown selected LOAD/ADD/SUB data
is an integration violation, rejected by assertions before commit. CLEAR ignores
data, and masked data may contain X/Z. All command fields are ignored when valid
is known low; clock-enable stalls also ignore valid and command fields. Reset and
clock enable must remain known, and valid must be known when clock enable is high.

## Independent checking and assertions

The normal PyUVM hierarchy separates configuration, transactions, sequences,
driver, monitor, agent, mathematical model, scoreboard, coverage and environment.
It reuses `mosaic_uvm` wiring, four-state utilities, execution and evidence checks.

The functional model keeps its own initialized values and type history per lane.
It compares every persistent output and response before the edge, at the real
rising edge before NBA updates, after propagation, and during a held interval.
Separate counts distinguish legal/illegal accepted commands, bubbles and physical
clock stalls; a held valid response does not create a new accepted command.

Optional raw observations check payload and signedness holds, per-lane writes and
operation-specific isolated operands. Continuous bit-level permissions detect
unselected writes, idle/reset writes, falling-edge updates and finite clockless
forward-path activity. Initial unreset observations are only hold baselines,
never functional initialization values.

[`accumulator_assertions.sv`](accumulator_assertions.sv) supplies verification-only
SystemVerilog immediate assertions through the RTL's
`MOSAIC_ACCUMULATOR_ASSERTIONS` hook. It samples pre-edge architectural state,
computes an independent signed `ACC_WIDTH+2`-bit mathematical result, and checks
state and responses one precision tick after the edge. It checks reset dominance,
clock holds, all command transitions, atomic rejection, typed validity, numerical
status, and unknown reset/clock-enable/valid/active-data integration violations.
Its timing delay and reference arithmetic are excluded from synthesis.

Native RTL Make simulations enable this checker by default through
`ACCUMULATOR_HDL_ASSERTIONS=1`; the full regression requires it. Synthesis and
mapped-netlist compilation do not include the fixture. Temporal SVA, physical
reset-domain checks and inserted clock-gate equivalence remain separate checks.

A direct port-only RTL run can disable hierarchy and HDL-fixture observations:

```sh
ACCUMULATOR_CHECK_INTERNALS=0 ACCUMULATOR_HDL_ASSERTIONS=0 \
make pyuvm SIM=icarus COCOTB_TOPLEVEL=accumulator \
  SIM_BUILD=build/icarus/accumulator/port-only
```

Elaboration, raw-storage and native HDL-assertion results are then `NOT_RUN`;
independent functional port checking remains active. This suite requires zero-delay
RTL, `TEST_SETTLE_NS=0`, and precision at most 1 ps. Disabling hierarchy does not
qualify timing-annotated gate simulation.

## Matrix and mandatory coverage

The 120 profiles cross all subtraction/saturation/reset feature combinations
with these 15 width/lane geometries:

```text
(1,1), (2,1), (3,1), (4,1), (8,1), (16,1), (32,1), (64,1),
(1,2), (3,2), (8,2), (16,4), (32,4), (32,8), (64,8)
```

These include scalar and four-lane 32-bit baselines, width one, odd width three,
1/2/4/8 lanes, and a maximum locally qualified geometry of eight 64-bit lanes.
Other positive parameter values may elaborate but are not claimed qualified here.

Every scalar profile at widths 1–4 exhausts each stored value, input value, command,
signedness and requested saturation mode, including disabled-feature rejections.
Each request is preceded by a typed LOAD. Larger geometries sweep a boundary
catalog and random full-width data. Directed vectors isolate single-lane invalidity
and type mismatches to prove atomic no-update with otherwise legal peers.

The 33 mandatory goals cover command/mode and mask-population crosses, legal full/zero/alternating mask shapes, every lane's
update/hold behavior, validity/type transitions, all illegal causes, reachable
status values, overflow directions, all supported clamps, exact limits without
false saturation, arithmetic sign crosses, loaded data bits, reset population by
clock-enable/valid, clockless reset timing, stalls of length 0–4 and 32, full-rate
64-command recurrences, ignored X/Z fields, and accepted unknown global controls
crossed with every command and empty/nonempty mask. Unreachable feature/width bins
have explicit per-profile reasons in coverage reports.

The runner also requires 26 malformed-parameter elaboration guards and 28 expected
protocol failures for X/Z reset, clock enable, enabled valid and selected data.
All results must identify the expected decorated test; unrelated failures cannot
satisfy a negative probe. Coverage/JUnit results are invalidated before each run.

## Local evidence and qualification limits

Generated evidence is ignored under `build/validation/`:

- `accumulator-final/summary.json`: native Icarus/PyUVM matrix with the HDL
  checker active, 240,000 random clock opportunities, parameter guards, protocol
  probes and exact current-source hashes.
- `accumulator-static/lint/summary.json`: native-package Verilator lint for all
  120 profiles, without waivers.
- `accumulator-static/structure/summary.json`: Yosys generic checks for every
  profile: exact logical storage, unreset payload/signedness, no initialization,
  latches, generated clocks, unresolved cells or input-to-output bypass, and
  disabled arithmetic-feature removal.
- `accumulator-static/formal/summary.json`: 64 unbounded binary sequential proofs
  for widths 1–4, lanes 1–2 and all feature/reset combinations. They compare raw
  state, typed validity, every persistent output and the complete response against
  a separate mathematical reference from equal arbitrary binary initial state.
  The Yosys view inlines the exact package enum because its frontend does not
  support imports; native lint/simulation use the actual package. `async2sync`
  provides an edge abstraction, not a reset-release or four-state proof.
- `accumulator-mutations/summary.json`: 30 deliberately faulty RTL variants
  rejected by PyUVM with the HDL checker disabled, testing checker independence.
- `accumulator-hdl-assertions/summary.json`: 16 native SV protocol-guard checks and
  independent HDL state/response checker detection of two injected defects.
- `accumulator-port-only/coverage.json`: direct Make run using only the public ports.
- `accumulator-flow-tests.log`: the 31 existing synthesis/power tests using tool stubs.
- `accumulator-vcs/summary.json`: native VCS availability status.

These results are local RTL/generic-analysis evidence. Native VCS, commercial lint,
CDC/RDC, DFT, VC LP, technology synthesis/equivalence, physical implementation,
PrimeTime and PrimePower require the corresponding server tools, libraries,
constraints and activity. Missing checks are `NOT_RUN`, never `PASS`.

The baseline has ordinary, nonretained registers. Context ownership, scale, lane
meaning, save/reload/retention policy, machine-readable contracts and power-domain
sequencing must be supplied by the tile integration. Signedness compatibility alone
does not make state compatible with a new context. These integration and physical
release criteria are not established by the standalone regression.
