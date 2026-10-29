# Mosaic CGRA

Run PyUVM tests through cocotb with Synopsys VCS:

```sh
make setup
make pyuvm
```

Use Python 3.9 or newer with the `venv` module. VCS must be installed with a
working license and its `vcs` executable on `PATH`; alternatively, pass
`VCS_BIN_DIR=/path/to/vcs/bin`. `make setup` installs cocotb 2.1.0 and PyUVM
5.0.0 into `.venv`. No virtual-environment activation is needed.

`make`, `make sim`, and `make pyuvm` all run the included `CounterTest` against
`src/rtl/common/counter.sv` with its default parameters. The test checks reset,
increment/decrement, disabled hold, clear/load priority, saturating boundaries,
and event pulses. A failing test makes the command fail.

Run the predicate-register and Boolean-logic specification regression:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=predicate_unit
make predicate-unit-regression SIM=icarus
```

The predicate bank supports per-lane validity, atomic masked writeback, invalidation,
pre-edge source reads and one-cycle dependent commands. It reuses common DFFs,
decoders, operand isolation and write gates. See the
[predicate unit validation guide](src/val/building_blocks/predicate_unit/README.md)
for parameter profiles, PyUVM coverage and static/formal checks.

Run the masked integer vector reduction specification regression:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=vector_reduction
make vector-reduction-regression SIM=icarus
```

The unit provides exact widened SUM, MIN/MAX and bitwise AND/OR with explicit
empty-mask identities, active count, signed extension and enabled-edge timing.
See the [vector reduction validation guide](src/val/building_blocks/vector_reduction/README.md)
for reusable components, profiles, coverage and static/formal checks.

Run the integer vector lane specification regression:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=vector_lane
make vector-lane-regression SIM=icarus
```

The lane composes the scalar ALU, multiplier and MAC with lane masking,
predication, result-format metadata and fixed enabled-edge path alignment.
See the [vector lane validation guide](src/val/building_blocks/vector_lane/README.md)
for the parameter matrix, reusable components and static/formal targets.

Run the combinational scalar integer ALU specification regression:

```sh
make scalar-alu-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=scalar_alu
```

The ALU provides modular/saturating arithmetic, Boolean logic, full-width shifts,
comparisons, select, pass-through and optional min/max with explicit status flags.
See the [scalar ALU validation guide](src/val/building_blocks/scalar_alu/README.md)
for the opcode contract, feature profiles, formal/static targets and coverage.

Run the global NoC router specification and mesh regressions:

```sh
make noc-router-regression SIM=icarus
make noc-router-mesh-regression SIM=icarus
make noc-router-topology
```

The five-port router provides deterministic XY/YX routing, packet reservations,
virtual channels, valid-ready or credit links, bounded QoS and optional parity/ECC.
The tests reuse the shared PyUVM infrastructure and exercise real 2x2/4x4 meshes.
See the [router validation guide](src/val/building_blocks/noc_router/README.md)
for configuration, latency, coverage and integration requirements.

Run the scalar integer multiplier specification regression:

```sh
make multiplier-regression
make multiplier-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=multiplier
```

The multiplier returns the exact full-width product with independent operand
signedness, including both mixed modes. It reuses common DFFs and operand isolation
for combinational or globally stalled registered profiles. The 84-profile PyUVM
matrix checks boundaries, exhaustive small products, metadata, status, reset,
and enabled-edge timing. See the
[multiplier validation guide](src/val/building_blocks/multiplier/README.md)
for parameters, architecture, coverage, and evidence limits.

Run the scalar integer MAC specification regression:

```sh
make mac-regression
make mac-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=mac
```

`src/rtl/building_blocks/mac.sv` implements the scalar integer multiply-add
specification by reusing `dot_product` with one term and permanent accumulation.
It preserves the exact full-width product, supports signed/unsigned modular or
saturating results, and provides zero-cycle or globally stalled registered timing.
Run `make pyuvm SIM=icarus COCOTB_TOPLEVEL=mac` for the default profile or
`make mac-regression SIM=icarus` for the 80-profile PyUVM matrix with parameter
and X/Z assertion guards. VCS uses the same targets with `SIM=vcs`.
See [the MAC validation guide](src/val/building_blocks/mac/README.md) for parameter
settings, architecture, reuse, coverage, and evidence limits.

Run the programmable LUT-unit specification regression:

```sh
make lut-unit-regression
make lut-unit-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=lut_unit
```

The LUT unit provides immutable programmable banks, signed/unsigned interpolation,
rounding, protection, fixed processing latency and independent response queues.
It reuses common DFFs, FIFOs, parity, ECC and protected storage/queue helpers.
See the [LUT-unit verification details](src/val/building_blocks/lut_unit/README.md)
for the 51-profile PyUVM campaign, synthetic image generator and lifecycle rules.

Run the polynomial-unit specification regression:

```sh
make polynomial-unit-regression SIM=icarus
make polynomial-unit-regression
make pyuvm SIM=icarus COCOTB_TOPLEVEL=polynomial_unit
```

The polynomial unit supports iterative and elastic unrolled Horner evaluation,
signed fixed-point rounding and saturation, protected coefficient banks and atomic
programming. It reuses the multiplier, LUT bank storage, common decoders/muxes,
protected state and FIFO queues. The Python-only regression covers 55 profiles,
85 parameter guards and architecture equivalence; synthesis is deferred to Design
Compiler. See the
[polynomial-unit verification details](src/val/building_blocks/polynomial_unit/README.md)
for programming, numerical semantics, protection, image recipes and evidence limits.

Run the reciprocal-unit specification regression:

```sh
make reciprocal-unit-regression SIM=icarus
make reciprocal-unit-regression
make pyuvm SIM=icarus COCOTB_TOPLEVEL=reciprocal_unit
```

The reciprocal unit provides iterative and elastic unrolled Newton-Raphson
refinement, exact fixed-point rounding, signed/unsigned saturation and protected,
reproducible seed ROMs. It reuses the priority encoder, multiplier, scalar ALU,
rounding helper, protected state and common FIFO queues. The Python-only campaign
covers 40 profiles, reduced-width exhaustive inputs, seed faults, timing and
architecture equivalence, and publishes numerical error characterization.
Synthesis remains deferred to Design Compiler. See the
[reciprocal-unit verification details](src/val/building_blocks/reciprocal_unit/README.md).

Run the inverse-square-root specification regression:

```sh
make rsqrt-unit-regression SIM=icarus
make rsqrt-unit-regression
make pyuvm SIM=icarus COCOTB_TOPLEVEL=rsqrt_unit
```

The rsqrt unit supports optional widened epsilon addition, exponent-parity
normalization, iterative or unrolled Newton refinement, independent output range,
rounding and protected reproducible seed images. It reuses the reciprocal scale
helper, shared protected ROM, multiplier, scalar ALU, common rounding, state and
FIFO queues. The Python-only campaign covers 40 profiles, reduced-width exhaustive
inputs, fault containment and numerical error characterization. Design Compiler
synthesis is deferred. See the
[rsqrt verification details](src/val/building_blocks/rsqrt_unit/README.md).

Run the nested-loop-controller specification regression:

```sh
make loop-controller-regression
make loop-controller-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=loop_controller
```

The loop controller generates counted/bounded Cartesian iteration tokens with
signed induction, pacing, runtime safe points and held completion records. It
reuses common DFF/parity storage, a decoder for runtime controls, and a priority
encoder and write gate for per-level advancement. The Python-only suite checks
every token against an independent Cartesian-product model and verifies carry
selection and level-update enables. Configure `LOOP_CONTROLLER_JOBS` for parallel
profiles. Synthesis is deferred to Design Compiler. See the
[loop-controller verification details](src/val/building_blocks/loop_controller/README.md)
for the 53-profile PyUVM campaign, local encodings and integration assumptions.

Run the static local-switch specification regression:

```sh
make local-switch-regression
make local-switch-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=local_switch
```

The local switch composes register slices, shared source decoders and sparse
physical muxes with atomic context routing and independent multicast-copy
acknowledgements. Its 120-profile Python-only PyUVM regression checks every physical
edge, fanout, backpressure, replacement,
flush/reset and error handling. See the [local-switch verification details](src/val/building_blocks/local_switch/README.md)
for connectivity encoding, ownership and integration assumptions. Synthesis is
deferred to Design Compiler.

Run the tile-power-controller specification regression:

```sh
make tile-power-controller-regression
make tile-power-controller-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=tile_power_controller
```

The always-on controller implements activity and idle policy, registered clock
requests, wake capture, drain, retention/OFF entry and wake, power qualification,
reset release, test policy and fatal containment. It reuses common counters, DFFs
and reset synchronizers. Its 80-profile Python-only PyUVM regression checks every
physical request and internal timer. See the
[tile-power-controller verification details](src/val/building_blocks/tile_power_controller/README.md)
for local encodings, command legality and tile wrapper integration. Synthesis is
deferred to Design Compiler.

Run the tile-network-interface specification regression:

```sh
make tile-network-interface-regression
make tile-network-interface-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=tile_network_interface
```

The interface bridges tile beats and fixed-length NoC packets with per-channel
queues, packet arbitration, per-VC reassembly, ordered ejection, valid-ready or
credit flow control, parity, and coordinated drain/flush. It reuses common FIFO,
DFF, counter, parity and round-robin modules through the existing queue helpers.
Its 61-profile Python-only PyUVM campaign checks transport contents, ownership,
recovery, events and credit accounting. See the
[tile-network-interface verification details](src/val/building_blocks/tile_network_interface/README.md)
for configuration, local encodings and latency. Synthesis is deferred to Design Compiler.

Run the ordered load-engine specification regression:

```sh
make load-engine-regression
make load-engine-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=load_engine
```

The load engine reuses the AGU and DMA affine bounds checker to issue tagged reads,
accept out-of-order responses and retire stream beats in request order. Common
write gates qualify descriptor capture and suppress malformed response writes. Its PyUVM
suite checks byte masks, metadata, backpressure, tag lifetime, fatal drain and reset.
See the [load-engine verification details](src/val/building_blocks/load_engine/README.md)
for the 80-profile matrix, optional counters and integration assumptions.

Run the ordered store-engine specification regression:

```sh
make store-engine-regression
make store-engine-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=store_engine
```

The store engine reuses the AGU, DMA bounds checker and common storage, counters,
decoders, isolation and write gates. It pairs stream beats with tagged writes,
validates framing and byte strobes, and retires out-of-order responses in request
order. See the [store-engine verification details](src/val/building_blocks/store_engine/README.md)
for the 80-profile Python campaign, optional counters and fatal-drain contracts.
Synthesis is deferred to Design Compiler.

Run the canonical stream-formatter specification regression:

```sh
make stream-formatter-regression
make stream-formatter-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=stream_formatter
```

The formatter reuses the register slice, lane mask and common state, counters,
write gating and isolation. It generates frame/row metadata, validates incoming
claims and clamps invalid bytes in combinational or buffered profiles. See the
[stream-formatter verification details](src/val/building_blocks/stream_formatter/README.md)
for the 40-profile Python campaign, local encodings and flush/reset contracts.
Synthesis is deferred to Design Compiler.

Run the scratchpad-controller specification regression:

```sh
make scratchpad-controller-regression
make scratchpad-controller-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=scratchpad_controller
```

The controller reuses the round-robin arbiter and common state/counters for
bank mapping, permissions, conflict arbitration and ordered per-client completions.
See the [scratchpad-controller verification details](src/val/building_blocks/scratchpad_controller/README.md)
for the 45 standalone and 12 real-bank integration profiles, local encodings,
optional counters and coordinated recovery. Validation uses Python/PyUVM tests;
synthesis is deferred to Design Compiler.

Run the scratchpad-bank specification regression:

```sh
make scratchpad-bank-regression
make scratchpad-bank-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=scratchpad_bank
```

The bank reuses the SRAM wrapper, parity, ECC and common control/storage blocks
for ordered byte-addressed reads and masked writes. Protected partial writes use
atomic RMW; SECDED correction supports inline scrub. See the
[scratchpad-bank verification details](src/val/building_blocks/scratchpad_bank/README.md)
for the 184-profile Python campaign, backend layout and recovery contracts.
Synthesis is deferred to Design Compiler.

Run the fixed-point exponential specification regression:

```sh
make exp-unit-images
make exp-unit-regression
make exp-unit-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=exp_unit
```

The exponential unit implements base-e/base-2 range reduction, generated endpoint
ROMs, optional interpolation, nearest-even/truncating rounding and saturation in
an elastic pipeline. It reuses the multiplier, scalar ALU and rounding helper,
plus common storage, counters, isolation, parity and ECC. The Python-only campaign
covers 57 profiles, 88 parameter guards and four numerical model tests.
Configure `EXP_UNIT_SEED`, `EXP_UNIT_RANDOM_CYCLES`, `EXP_UNIT_REGRESSION_BUILD`
and `EXP_UNIT_JOBS`;
see the [exp-unit verification details](src/val/building_blocks/exp_unit/README.md)
for generated assets, timing, protection and scalar accuracy limits. Synthesis is
deferred to Design Compiler.

Run the event/barrier specification regression:

```sh
make event-barrier-regression
make event-barrier-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=event_barrier
```

The event/barrier unit reuses common counters, decoding, arbitration, FIFOs, DFFs
and parity for atomic event occurrences, one-shot waits and reusable barriers.
Configure `EVENT_BARRIER_SEED`, `EVENT_BARRIER_RANDOM_CYCLES` and
`EVENT_BARRIER_REGRESSION_BUILD`; see the
[event/barrier verification details](src/val/building_blocks/event_barrier/README.md)
for scheduling, local encodings, protection, coverage and qualification limits.

Run the integer dot-product specification regression:

```sh
make dot-product-regression
make dot-product-regression SIM=icarus
```

The unit computes exact masked signed/unsigned products through a balanced tree,
with optional external accumulation, final saturation and enabled-cycle latency.
It reuses `dff` and `operand_isolation`. The structured PyUVM suite covers 102
geometry/feature/latency/reset profiles; see the
[dot-product verification details](src/val/building_blocks/dot_product/README.md)
for pipeline structure, parameter settings, coverage and evidence limits.

Run the DMA engine's specification-based regression:

```sh
make dma-engine-regression
make dma-engine-regression SIM=icarus
```

The DMA reuses existing queues, arbiters, counters, DFFs, decoders, write gates,
parity and operand isolation for multi-channel transfers, protection, event starts, cancellation and
coordinated flush. Its structured PyUVM suite checks exact data/progress and
completion accounting across 25 profiles using Python checks only. It also checks
every command ID-directory entry's capture/retention and fatal cancel timer holds.
Synthesis is deferred to Design Compiler. Store backends supply cumulative
committed bytes for accurate cancellation results. Configure `DMA_ENGINE_SEED`,
`DMA_ENGINE_RANDOM_CYCLES`, `DMA_ENGINE_JOBS` and `DMA_ENGINE_REGRESSION_BUILD`; see the
[DMA verification details](src/val/building_blocks/dma_engine/README.md) for
backend interface extensions, coverage, and qualification limits.

Run the regular address-generation unit's specification-based regression:

```sh
make agu-regression
make agu-regression SIM=icarus
make agu-lint
```

The AGU reuses common counter, DFF, operand-isolation and write-gate RTL for linear and
signed-stride 1D/2D byte addressing. Its structured PyUVM suite checks descriptor
legality, checked address arithmetic, row-base strides, metadata, completion,
sticky errors and backpressure in 32 profiles, with exhaustive small descriptors.
Configure `AGU_SEED`, `AGU_RANDOM_CYCLES` and `AGU_REGRESSION_BUILD`; see the
[AGU verification details](src/val/building_blocks/agu/README.md) for encodings,
assertion controls, coverage and lint reports. Synthesis is deferred to Design Compiler.

Run the integer accumulator bank's specification-based regression:

```sh
make accumulator-regression
make accumulator-regression SIM=icarus
```

The first `building_blocks` module reuses common DFF, lane-mask and operand-isolation
RTL for persistent typed lanes, atomic masked CLEAR/LOAD/ADD/SUB, modular or
saturating arithmetic, response status and clock-enable holds. Its structured
PyUVM suite and optional HDL transition checker validate 120 width/lane/feature/reset
profiles, including exhaustive scalar transitions at widths 1–4. Configure
`ACCUMULATOR_SEED`, `ACCUMULATOR_RANDOM_CYCLES` and `ACCUMULATOR_REGRESSION_BUILD`;
see the [accumulator verification details](src/val/building_blocks/accumulator/README.md)
for parameters, assertion controls, evidence and integration limits.

Run the streaming width converter's specification-based regression:

```sh
make width-converter-regression
make width-converter-regression SIM=icarus
```

The RTL reuses common DFF and operand-isolation blocks for narrow-to-wide packing,
wide-to-narrow serialization and equal-width elastic forwarding. The PyUVM suite
checks positional sparse keep masks, partial/empty packets, metadata, both slice
orders, registered latency, stalls, simultaneous replacement, reset and flush.
Its 76 profiles cover representative ratios 1–8 and unit widths 1, 3, 8 and 64.
Configure `WIDTH_CONVERTER_SEED`, `WIDTH_CONVERTER_RANDOM_CYCLES` and
`WIDTH_CONVERTER_REGRESSION_BUILD`; see the
[width-converter verification details](src/val/basic/width_converter/README.md)
for parameter overrides, evidence and remaining technology signoff checks.

Run the counter's specification-based functional regression:

```sh
make counter-regression
# Local alternative when VCS is unavailable:
make counter-regression SIM=icarus
```

This runs `CounterSpecTest` in a PyUVM environment with a sequencer, driver,
passive monitor, independent reference model, scoreboard, and functional
coverage checks. It exercises the eight recommended configurations from the
[counter specification](../specs/common/mosaic-counter/README.md), including
wrapping arithmetic, asynchronous reset, nonzero reset values, and widths
from 1 to 64 bits. Each configuration runs directed tests, at least 1000
randomized cycles, and X/Z control tests. `CounterTest` remains the quick
smoke test used by the default simulation and power targets.

`COUNTER_SEED` defaults to `20261010`; `COUNTER_RANDOM_CYCLES` defaults to
`2000` per configuration. Each profile adds its matrix index to the seed.
Set `COUNTER_REGRESSION_BUILD` to relocate the reports; the default is
`build/<simulator>/counter/regression`. A missing coverage bin, scoreboard
mismatch, absent result, or simulator failure makes the target fail. The
aggregate `summary.json` records missing simulator tools as `NOT_RUN`.
See the [verification details and local results](src/val/common/counter/README.md)
for requirement mapping, artifacts, and limits of the simulation campaign.

Run the clock gate's specification-based waveform regression:

```sh
make clock-gate-regression
make clock-gate-regression SIM=icarus
```

The PyUVM suite checks enabled and disabled startup in separate simulations,
every observable output edge, complete pulse widths, control changes in both
half-cycles and near both edges, test override, long active/idle intervals,
seeded random activity, and illegal X/Z controls. Coverage distinguishes
requested transitions from their effect on source pulses. Set `CLOCK_GATE_SEED`,
`CLOCK_GATE_RANDOM_CYCLES`, and `CLOCK_GATE_REGRESSION_BUILD` to configure the
campaign. Reports default to `build/<simulator>/clock_gate/regression`.
See the [clock gate verification details](src/val/common/clock_gate/README.md)
for the specification mapping and limits of the RTL simulation.

Run the decoder's specification-based functional regression:

```sh
make decoder-regression
make decoder-regression SIM=icarus
```

The PyUVM suite tests all eight recommended output counts (`1, 2, 3, 4, 5, 8,
16, 32`), every binary encoding, every legal transition pair, enable behavior,
fail-closed X/Z handling, and disabled output inactivity. Four invalid-parameter
cases must fail elaboration. Set `DECODER_SEED`, `DECODER_RANDOM_CYCLES`, and
`DECODER_REGRESSION_BUILD` to configure the campaign. Reports default to
`build/<simulator>/decoder/regression`. See the
[decoder verification details](src/val/common/decoder/README.md)
for requirement mapping and verification scope.

Run the DFF's specification-based sequential regression:

```sh
make dff-regression
make dff-regression SIM=icarus
```

The PyUVM suite covers all seven recommended configurations and four additional
profiles, including all reset/enable branches, widths from 1 to 128 bits,
nonzero reset patterns, short reset pulses, capture/hold sequences, and X/Z
control assertions. A passive waveform monitor also checks output transitions
between clock edges. Configure the campaign with `DFF_SEED`,
`DFF_RANDOM_CYCLES`, and `DFF_REGRESSION_BUILD`; reports default to
`build/<simulator>/dff/regression`. See the
[DFF verification details](src/val/common/dff/README.md) for coverage mapping
and the existing RTL's parameter-validation limitations.

Run the isolation cell's specification-based four-state regression:

```sh
make isolation-cell-regression
make isolation-cell-regression SIM=icarus
```

The PyUVM suite crosses widths `1, 2, 4, 8, 16, 32, 64`, both control polarities,
and zero, one, and mixed clamps in 40 configurations. It checks transparent X/Z
data, known isolated outputs, conservative unknown-control merging, repeated
assertion/release, and continuous output inactivity while isolated. Small widths
also run exhaustive four-state truth tables. Configure the campaign with
`ISOLATION_CELL_SEED`, `ISOLATION_CELL_RANDOM_CYCLES`, and
`ISOLATION_CELL_REGRESSION_BUILD`; reports default to
`build/<simulator>/isolation_cell/regression`. This suite requires Python 3.10
or newer. See the [isolation cell verification details](src/val/common/isolation_cell/README.md)
for requirement mapping, parameter-validation gaps, and the separate UPF and
technology requirements for power-aware signoff.

Run the lane mask's specification-based four-state regression:

```sh
make lane-mask-regression
make lane-mask-regression SIM=icarus
```

The PyUVM suite checks the required lane counts `1, 2, 4, 8, 16` and an additional
three-lane configuration. It verifies every lane independently, all three output
vectors, source suppression, tail and alternating masks, population transitions,
mask crosses, and X/Z controls. Small configurations also run exhaustive vector
truth tables. Configure the campaign with `LANE_MASK_SEED`,
`LANE_MASK_RANDOM_CYCLES`, and `LANE_MASK_REGRESSION_BUILD`; reports default to
`build/<simulator>/lane_mask/regression`. This suite requires Python 3.10 or newer.
See the [lane mask verification details](src/val/common/lane_mask/README.md)
for coverage mapping, parameter rejection, and the downstream integration checks.

Run the level shifter's specification-based four-state regression:

```sh
make level-shifter-regression
make level-shifter-regression SIM=icarus
```

The PyUVM suite covers widths `1, 2, 4, 8, 16, 32, 64` in both static directions,
checking exact bit ordering and propagation of zero, one, X, and Z. It exercises
independent bit transitions, mixed patterns, seeded random data, and short/long
stable intervals with a continuous output monitor. Both directions receive the
same input history at each width. Configure the campaign with
`LEVEL_SHIFTER_SEED`, `LEVEL_SHIFTER_RANDOM_CYCLES`, and
`LEVEL_SHIFTER_REGRESSION_BUILD`; reports default to
`build/<simulator>/level_shifter/regression`. This suite requires Python 3.10 or
newer. See the [level shifter verification details](src/val/common/level_shifter/README.md)
for parameter guards, coverage mapping, and the separate UPF/technology signoff
requirements for physical voltage translation.

Run the mux's specification-based four-state regression:

```sh
make mux-regression
make mux-regression SIM=icarus
```

The PyUVM suite covers all six recommended input-count/data-width configurations
with zero, all-one, and mixed defaults where representable, for 17 profiles.
It checks every legal selection, unused binary encoding, four-state unknown
selection, legal transition pair, selected/unselected input activity, and exact
data bit ordering. Both outputs are monitored during unselected-input and stable
intervals. Configure the campaign with `MUX_SEED`, `MUX_RANDOM_CYCLES`, and
`MUX_REGRESSION_BUILD`; reports default to `build/<simulator>/mux/regression`.
This suite requires Python 3.10 or newer. See the
[mux verification details](src/val/common/mux/README.md) for coverage mapping,
parameter guards, report locations, and physical/integration verification limits.

Run the architectural operand isolation regression:

```sh
make operand-isolation-regression
make operand-isolation-regression SIM=icarus
```

The PyUVM suite crosses widths 1, 8, 16, 32, 64, 128, and 256 with zero,
all-one, and mixed clamps where representable, for 20 profiles. It checks
four-state pass-through, constant isolation, data/control transitions, output
inactivity while isolated, and short/long holds. X/Z controls must produce an
all-X operand and trigger the active testbench known-control assertion;
two negative probes verify that unacknowledged illegal controls fail the test.
Configure `OPERAND_ISOLATION_SEED`, `OPERAND_ISOLATION_RANDOM_CYCLES`, and
`OPERAND_ISOLATION_REGRESSION_BUILD`. See the
[operand isolation verification details](src/val/common/operand_isolation/README.md)
for coverage, reports, and downstream power/integration requirements.

Run the fixed-priority encoder regression:

```sh
make priority-encoder-regression
make priority-encoder-regression SIM=icarus
```

The PyUVM suite crosses widths 1, 2, 3, 4, 5, 8, 16, and 32 with both priority
directions, for 16 profiles. It checks every single/pair request, all requests,
population and selection crosses, output consistency, four-state ambiguity,
and held-input stability. Widths through eight exhaust all binary vectors;
widths through five exhaust all four-state vectors. Configure
`PRIORITY_ENCODER_SEED`, `PRIORITY_ENCODER_RANDOM_CYCLES`, and
`PRIORITY_ENCODER_REGRESSION_BUILD`. See the
[priority encoder verification details](src/val/common/priority_encoder/README.md)
for coverage mapping, elaboration guards, and integration/signoff requirements.

Run the reset synchronizer regression:

```sh
make reset-synchronizer-regression
make reset-synchronizer-regression SIM=icarus
```

The PyUVM suite checks depths 2, 3, and 4, asynchronous assertion in both clock
phases, exact rising-edge release latency, near-edge transitions, stopped/restarted
clocks, reassertion at every intermediate stage, short modeled pulses, and X/Z
reset detection. It checks the portable stage vector and continuously monitors
output/stage changes. Configure `RESET_SYNCHRONIZER_SEED`,
`RESET_SYNCHRONIZER_RANDOM_CYCLES`, and `RESET_SYNCHRONIZER_REGRESSION_BUILD`.
See the [reset synchronizer verification details](src/val/common/reset_synchronizer/README.md)
for timing controls and the separate metastability, CDC/RDC, and physical checks.

Run the portable retention register regression:

```sh
make retention-register-regression
make retention-register-regression SIM=icarus
```

The PyUVM suite crosses widths 1, 8, 16, 32, 64, and 128 with both reset styles,
both enable settings, and zero/all-one/mixed reset values where representable,
for 68 profiles. It checks pre-edge save, latest-image restore, normal capture
and hold, control priority, clock-stopped intervals, sampled X/Z controls, and
illegal protocol sequences. Configure `RETENTION_REGISTER_SEED`,
`RETENTION_REGISTER_RANDOM_CYCLES`, and `RETENTION_REGISTER_REGRESSION_BUILD`.
See the [retention register verification details](src/val/common/retention_register/README.md)
for active assertions and the separate UPF, supply-loss, and retention-cell signoff
requirements. These tests publish portable functional evidence.

Run the write gate regression with destination-state comparisons:

```sh
make write-gate-regression
make write-gate-regression SIM=icarus
```

The PyUVM suite checks widths `1, 2, 4, 8, 16, 32, 64, 128` in functional and
integration fixtures, for 16 profiles. It covers independent mask bits,
four-state controls, suppression ratios, held-input stability, and real HDL
register/memory writes compared with an ungated reference. Configure
`WRITE_GATE_SEED`, `WRITE_GATE_RANDOM_CYCLES`, and `WRITE_GATE_REGRESSION_BUILD`.
See the [write gate verification details](src/val/common/write_gate/README.md)
for active control and integration assertions, coverage, and the separate
physical timing and destination-energy requirements.

Run the asynchronous FIFO regression:

```sh
make async-fifo-regression
make async-fifo-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=async_fifo
```

The PyUVM suite checks ten representative width/depth/synchronizer/threshold
profiles with independent clocks, a queue scoreboard, conservative boundary
timing, repeated pointer wrapping, four-state payloads, clock stops, and reset
cancellation/recovery. Configure `ASYNC_FIFO_SEED`, `ASYNC_FIFO_RANDOM_CYCLES`,
and `ASYNC_FIFO_REGRESSION_BUILD`. The Makefile includes the counter and DFF RTL
dependencies automatically for this top. See the
[async FIFO verification details](src/val/basic/async_fifo/README.md) for profiles,
mandatory coverage, assertion probes, and the separate CDC and physical checks.

Run the sparse bypass network regression:

```sh
make bypass-network-regression
make bypass-network-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=bypass_network
```

The PyUVM suite checks 31 representative graph/width/count/timing profiles with
independent destination lookup, fanout, capture/hold, reset/flush priority, context
invalidation, and four-state protocol assertions. Configure `BYPASS_NETWORK_SEED`,
`BYPASS_NETWORK_RANDOM_CYCLES`, and `BYPASS_NETWORK_REGRESSION_BUILD`. The Makefile
includes the DFF dependency automatically. See the
[bypass network verification details](src/val/basic/bypass_network/README.md)
for mandatory coverage, parameter guards, negative probes, and tile integration
and physical signoff requirements.

Run the context memory regression:

```sh
make context-memory-regression
make context-memory-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=context_memory
```

The RTL reuses common decoders for command selection and a common DFF bank for
committed validity. It implements masked context loading, atomic write/commit,
invalidation, combinational reads, and optional raw readback. Its
PyUVM suite checks 54 profiles, including every exploration depth from 1 through
32 and representative width/slice/read-port/raw/reset combinations. Configure
`CONTEXT_MEMORY_SEED`, `CONTEXT_MEMORY_RANDOM_CYCLES`, and
`CONTEXT_MEMORY_REGRESSION_BUILD`. See the
[context memory verification details](src/val/basic/context_memory/README.md)
for timing, reset qualification, protocol checks, and external validator scope.

Run the context sequencer regression:

```sh
make context-sequencer-regression
make context-sequencer-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=context_sequencer
```

The RTL reuses common DFFs and the loop counter for committed context selection,
candidate waits, counted loops, safe stop/suspend/resume/switch requests,
completion pulses, and sticky errors. Encodings are defined in repository-local
`context_sequencer_pkg.sv`; no external contracts package is required. PyUVM covers
55 controller profiles, every depth from 1 through 32, all feature/reset
combinations, and three real context-memory fixtures. Configure
`CONTEXT_SEQUENCER_SEED`, `CONTEXT_SEQUENCER_RANDOM_CYCLES`, and
`CONTEXT_SEQUENCER_REGRESSION_BUILD`. See the
[context sequencer verification details](src/val/basic/context_sequencer/README.md)
for encodings, runtime policy, RTL reuse, and coverage scope.

Run the data aligner regression:

```sh
make data-aligner-regression
make data-aligner-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=data_aligner
```

The RTL aligns two adjacent words by byte offset, preserves per-byte strobes,
and reports low-edge or high-edge spill. It reuses common operand isolation and
DFFs for combinational or one-entry elastic ready-valid operation. PyUVM checks
57 width/direction/timing profiles with an independent byte-array model and
transaction ledger. Configure `DATA_ALIGNER_SEED`, `DATA_ALIGNER_RANDOM_CYCLES`,
and `DATA_ALIGNER_REGRESSION_BUILD`. See the
[data aligner verification details](src/val/basic/data_aligner/README.md) for
byte ordering, spill handling, cancellation, coverage, and tool scope.

Run the SECDED ECC regression:

```sh
make ecc-regression
make ecc-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=ecc
```

The combinational codec provides independent encode and decode, single-error
correction, double-error detection, fail-closed outputs, and a repaired codeword
for external scrubbing. It reuses common decoder and operand-isolation modules.
PyUVM checks twenty widths from 1 to 256 bits, every parity-count boundary,
every single bit and unordered double-fault pair, and unknown propagation.
Configure `ECC_SEED`, `ECC_RANDOM_CYCLES`, and `ECC_REGRESSION_BUILD`. See the
[ECC verification details](src/val/basic/ecc/README.md) for layout, guarantees,
implementation limits, coverage, and external tool scope.

Run the synchronous FIFO regression:

```sh
make fifo-regression
make fifo-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=fifo
```

The FIFO supports simultaneous enqueue/dequeue, full replacement, odd depths,
occupancy thresholds, and both reset styles without combinational fall-through.
It reuses common DFF and operand-isolation modules and leaves storage unreset.
PyUVM checks 114 width/depth/reset/threshold profiles against an independent
accepted-item queue, with continuous state-enable and backpressure assertions.
Configure `FIFO_SEED`, `FIFO_RANDOM_CYCLES`, and `FIFO_REGRESSION_BUILD`. See the
[FIFO verification details](src/val/basic/fifo/README.md) for parameters, coverage,
protocol probes, and external tool scope.

Run the element packer/unpacker regression:

```sh
make packer-regression
make packer-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=packer
```

The packer converts parallel elements using sign/zero extension, low-bit
truncation or saturation, with lane validity, status, reversal and opaque metadata.
It reuses operand isolation and DFFs for combinational or one-entry elastic output.
PyUVM checks 330 width/lane/feature/timing profiles using an independent integer
model and accepted-beat queue. Configure `PACKER_SEED`, `PACKER_RANDOM_CYCLES`,
and `PACKER_REGRESSION_BUILD`. See the
[packer verification details](src/val/basic/packer/README.md) for conversion
semantics, feature support, coverage and tool scope.

Run the granular parity regression:

```sh
make parity-regression
make parity-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=parity
```

The combinational codec independently generates and checks even parity per
granule, reports granular and aggregate status, and clamps the whole checked word
on any detected error. It reuses common operand isolation. PyUVM checks 101
data/granule geometries, every single protected-bit fault, expected undetected
even faults, X/Z propagation and independent-cone activity. Configure `PARITY_SEED`,
`PARITY_RANDOM_CYCLES` and `PARITY_REGRESSION_BUILD`. See the
[parity verification details](src/val/basic/parity/README.md) for layout, detection
limits, partial-write responsibilities, coverage and local proof scope.

Run the weighted performance-counter bank regression:

```sh
make performance-counters-regression
make performance-counters-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=performance_counters
```

The bank independently selects weighted events, saturates or wraps with sticky
overflow, reports upward threshold crossings, and provides coherent post-update
snapshots and combinational indexed reads. It reuses common DFF and operand
isolation blocks. PyUVM checks 61 parameter profiles, ownership changes, reset
styles, ignored X/Z, and live protocol assertions against arbitrary-precision
state. Configure `PERFORMANCE_COUNTERS_SEED`, `PERFORMANCE_COUNTERS_RANDOM_CYCLES`
and `PERFORMANCE_COUNTERS_REGRESSION_BUILD`. See the
[performance-counter verification details](src/val/basic/performance_counters/README.md)
for packed layout, coverage limits, integration responsibilities and tool scope.

Run the reconfigurable delay-unit regression:

```sh
make rdu-regression
make rdu-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=rdu
```

The RDU statically partitions one total delay-entry budget among operand channels.
It supports combinational bypass, token/bubble delay in accepted schedule advances,
global stalls, independent channel enables and flushes, and guarded delay selection.
It reuses common validity DFFs and output operand isolation while leaving payload
storage unreset. PyUVM checks 88 width/allocation/reset profiles against independent
per-channel histories and observes raw storage enables. Configure `RDU_SEED`,
`RDU_RANDOM_CYCLES` and `RDU_REGRESSION_BUILD`. See the
[RDU verification details](src/val/basic/rdu/README.md) for allocation literals,
configuration boundaries, coverage and qualification scope.

Run the scalar register-file regression:

```sh
make register-file-regression
make register-file-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=register_file
```

The register file provides independent combinational reads and simultaneous
full-word writes to distinct addresses, with no storage reset or implicit
forwarding. It reuses the common decoder for legal write selection. PyUVM checks
55 width/depth/port configurations against an independent initialized-word model,
including pre-edge, edge-time and post-edge read-during-write observations.
Configure `REGISTER_FILE_SEED`, `REGISTER_FILE_RANDOM_CYCLES` and
`REGISTER_FILE_REGRESSION_BUILD`. See the
[register-file verification details](src/val/basic/register_file/README.md) for
initialization policy, coverage, protocol assertions and qualification scope.

Run the elastic register-slice regression:

```sh
make register-slice-regression
make register-slice-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=register_slice
```

The register slice adds one forward cycle with one-item storage, combinational
reverse ready, stable stalled outputs and same-edge consume-and-replace operation.
It reuses the common validity DFF and operand isolation while keeping payload
unreset. PyUVM checks 36 width/reset profiles against an independent acceptance
queue, including real edge-time consumption, reset cancellation and producer
stability. Configure `REGISTER_SLICE_SEED`, `REGISTER_SLICE_RANDOM_CYCLES` and
`REGISTER_SLICE_REGRESSION_BUILD`. See the
[register-slice verification details](src/val/basic/register_slice/README.md) for
reset timing, coverage, interface obligations and qualification scope.

Run the round-robin arbiter regression:

```sh
make round-robin-arbiter-regression
make round-robin-arbiter-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=round_robin_arbiter
```

The arbiter provides zero-cycle cyclic selection, eligibility masking, stable
pending ownership, optional multi-beat locks and sticky protocol errors. It reuses
the common priority encoder and DFF. PyUVM checks requester counts, initial
priorities, both reset styles and accepted-service fairness; a real mux and
register-slice fixture checks requester/payload alignment through stalls and locks.
Configure `ROUND_ROBIN_ARBITER_SEED`, `ROUND_ROBIN_ARBITER_RANDOM_CYCLES` and
`ROUND_ROBIN_ARBITER_REGRESSION_BUILD`. See the
[arbiter verification details](src/val/basic/round_robin_arbiter/README.md) for
coverage, lock obligations, recovery and qualification scope.

Run the skid-buffer regression:

```sh
make skid-buffer-regression
make skid-buffer-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=skid_buffer
```

The skid buffer bypasses data and valid while empty and captures one accepted item
when downstream stalls. Upstream ready depends only on stored validity, breaking
the reverse ready path. A buffered release blocks same-edge input replacement;
the next input can bypass and transfer on the following edge. It reuses the common
DFF, mux and operand-isolation blocks. Configure `SKID_BUFFER_SEED`,
`SKID_BUFFER_RANDOM_CYCLES` and `SKID_BUFFER_REGRESSION_BUILD`. See the
[skid-buffer verification details](src/val/basic/skid_buffer/README.md) for queue
checking, capture-only writes, coverage, reset behavior and qualification scope.

Run the SRAM-wrapper regression:

```sh
make sram-wrapper-regression
make sram-wrapper-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=sram_wrapper
```

The wrapper provides masked 1RW memory access, fixed read maturity, ordered tagged
responses and credit-based read admission. Writes remain admissible when read
credits are exhausted. Reset and flush cancel reads while preserving committed
memory. The shell reuses the common decoder, DFF, counter and operand isolation.
`SRAM_BACKEND_SOURCE` selects a compatible backend for direct simulation and
synthesis; the default is inferred storage. Configure `SRAM_WRAPPER_SEED`,
`SRAM_WRAPPER_RANDOM_CYCLES` and `SRAM_WRAPPER_REGRESSION_BUILD`. See the
[SRAM verification details](src/val/basic/sram_wrapper/README.md) for the edge
timing, backend contract, initialization policy and qualification scope.

Run the stream-fork regression:

```sh
make stream-fork-regression
make stream-fork-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=stream_fork
```

The fork stores one multicast item and independently tracks delivery to every
selected output. It supports partial consumption and same-edge completion and
replacement, with zero data on invalid lanes. The pending bits reuse common
`dff`; output lanes reuse `operand_isolation`. Configure `STREAM_FORK_SEED`,
`STREAM_FORK_RANDOM_CYCLES` and `STREAM_FORK_REGRESSION_BUILD`. See the
[stream-fork verification details](src/val/basic/stream_fork/README.md) for mask
legality, reset timing, per-output reference queues and qualification scope.

Run the stream-join regression:

```sh
make stream-join-regression
make stream-join-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=stream_join
```

The combinational join consumes every required input atomically with one packed
output transaction. It supports runtime required masks, an all-zero idle mask,
and ready on the final missing input. Invalid and optional output lanes reuse
common `operand_isolation`; the join has no clock, reset or storage. Configure
`STREAM_JOIN_SEED`, `STREAM_JOIN_RANDOM_CYCLES` and `STREAM_JOIN_REGRESSION_BUILD`.
See the [stream-join verification details](src/val/basic/stream_join/README.md)
for producer and mask stability, sampling, coverage and qualification scope.

Run the vector-register-file regression:

```sh
make vector-register-file-regression
make vector-register-file-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=vector_register_file
```

The vector file reuses scalar `register_file` banks and their common `decoder`,
one bank per writable slice. It supports lane-gated reads, masked concurrent
writes, and optional lane-zero broadcast. Storage is unreset; disjoint same-entry
writes merge, and reads expose old data at the write edge and merged data afterward.
Configure `VECTOR_REGISTER_FILE_SEED`, `VECTOR_REGISTER_FILE_RANDOM_CYCLES` and
`VECTOR_REGISTER_FILE_REGRESSION_BUILD`. See the
[vector-register-file verification details](src/val/basic/vector_register_file/README.md)
for banking, initialization, slice masks, assertions and qualification scope.

Choose a different HDL top and Python test module:

```sh
make pyuvm COCOTB_TOPLEVEL=my_top COCOTB_TEST_MODULES=test_my_top \
  VERILOG_SOURCES="$(pwd)/src/rtl/my_top.sv $(pwd)/src/rtl/common/counter.sv"
```

Place tests in `src/val/<category>/<top>`; the Makefile discovers the directory
matching `COCOTB_TOPLEVEL`. The counter suite is in `src/val/common/counter`.
Specification suites separate their configuration, transactions, agent, driver,
monitor, model, scoreboard, coverage, environment and sequences. Shared utilities
and regression infrastructure live in `src/val/lib/mosaic_uvm`. See the
[PyUVM structure](src/val/README.md) for component roles, imports and sampling
coordination.
Set `PYUVM_TEST_DIR=/absolute/path/to/tests` to select another location or
choose between multiple suites for the same top. Additional import directories
can be supplied through `PYTHONPATH`. Set
`COCOTB_TEST_MODULES` to importable module names without `.py`; multiple modules
are comma-separated. It defaults to `test_<COCOTB_TOPLEVEL>`. When
`VERILOG_SOURCES` is omitted, the Makefile discovers the selected top under
`src/rtl/<category>/<COCOTB_TOPLEVEL>.sv`. The async FIFO, bypass network, context
memory, context sequencer, data aligner, ECC, synchronous FIFO, packer, parity,
performance counters, RDU, register file, register slice, round-robin arbiter,
skid buffer, SRAM wrapper, stream fork, stream join and vector register file
include their ordered RTL dependencies automatically.
Provide an ordered source list for other designs that instantiate modules or
import packages. Package sources must precede sources that import them.

Pass additional compiler options with `COMPILE_ARGS`, runtime options with
`SIM_ARGS`, and HDL plusargs with `COCOTB_PLUSARGS`. The cocotb VCS backend
supplies SystemVerilog, 64-bit compilation for 64-bit Python, and VPI loading
and signal access. Select a single test with
`COCOTB_TEST_FILTER=CounterTest`. To use an existing Python environment, pass
`PYTHON_BIN=/absolute/path/to/python` with the requirements already installed.

Build products and the JUnit report are stored in
`build/<simulator>/<top>/`, with results in `results.xml`. `make clean` removes
the selected build and report. Clean before changing compiler options or the
source list to force recompilation. `make help` lists the main options.

The shared flow drivers are under `flows/synth`, `flows/power`, and `flows/vcs`;
the reusable timing budget is `src/constraints/timing.sdc`. Machine-specific
synthesis setup files can live at `flows/synth/setup.sh`, which is ignored by
Git. Dry runs of the counter, clock gate, decoder, DFF, isolation cell, lane mask,
level shifter, mux, operand isolation, priority encoder, reset synchronizer,
retention register, write gate, async FIFO, bypass network, context memory,
context sequencer, data aligner, ECC, synchronous FIFO, packer, parity, and
performance-counter, RDU, register-file, register-slice, round-robin-arbiter,
skid-buffer, SRAM-wrapper, stream-fork, stream-join and vector-register-file targets
print their commands without changing reports.

Generate a SAIF activity file from the PyUVM simulation with VCS:

```sh
make saif
```

The target records activity from time zero through the end of the selected
tests and writes `build/vcs/<top>/<top>.saif`. It uses the VCS UCLI `power`
commands in `flows/vcs/saif.tcl` to collect activity directly, including
SystemVerilog signals and memories. It enables `-ucli2Proc`, required by
`config endofsim noexit`, to keep UCLI active after cocotb finishes so the
report is written before exiting. No changes to the RTL or Python tests are
required.

The target also passes `-lca` to `simv` to enable SystemVerilog SAIF monitoring
in VCS releases that gate the SV-SAIF flow as a Limited Customer Availability
feature. This prevents `LCA_FEATURES_NEED_OPTION` at `power -gate_level`.

Configure the output path, captured hierarchy, and report time unit (in
seconds) as needed:

```sh
make saif SAIF_FILE="$(pwd)/build/activity.saif" \
  SAIF_SCOPE=counter SAIF_TIME_UNIT=1e-9
```

`SAIF_SCOPE` defaults to `COCOTB_TOPLEVEL`; it can also select a child instance,
such as `my_top.dut`. `SAIF_TIME_UNIT` defaults to `1e-9` (1 ns) and controls
the report units, not the simulation clock. The usual source, test, compiler,
and runtime overrides also apply. This target requires `SIM=vcs`, removes any
previous output before running, and fails if the simulation fails or no
nonempty SAIF file is produced. `make clean` also removes `SAIF_FILE`, including
when its path is outside the selected build directory.

The simulator can be overridden, for example:

```sh
make pyuvm SIM=icarus
```

This uses the same PyUVM test with Icarus Verilog, which must be installed
separately. VCS remains the default.

## Synthesis and gate-level simulation

Synthesize the selected RTL with Synopsys Design Compiler on the licensed server:

```sh
make synth \
  TECH_SETUP_TCL=/server/tech/lib_setup.tcl \
  DC_SETUP_TCL=/server/scripts/dc_setup.tcl
```

`TECH_SETUP_TCL` is required and must configure `target_library` with the
technology `.db` libraries and their search paths. `DC_SETUP_TCL` is an optional
second setup script, sourced after the technology script. Use absolute paths in
these scripts; DC runs from `SYNTH_BUILD`. The PDK and cell models remain on the
server. Override `DC_SHELL` with an absolute executable path when `dc_shell` is
not on `PATH`, and use `DC_ARGS` for shell options. Python is not needed for
`make synth`.

The driver `flows/synth/run.tcl` follows the sections and commands in the
reference screenshots: base paths (`PROJECT_HOME`, `PROJECT_HOME_SYN`), design, RTL,
technology setup, directories, debug output, read/elaborate, checks, constraints,
compile, reports, and outputs. It analyzes `VERILOG_SOURCES` in order,
elaborates `COCOTB_TOPLEVEL`, and sources the shared `src/constraints/timing.sdc`
budget. Script comments and diagnostics are in English. Output paths remain
under `SYNTH_BUILD`:

| Output under `build/synth/<top>/` | Purpose |
| --- | --- |
| `netlist/<top>_syn.v` | Mapped Verilog netlist |
| `netlist/<top>.sdf` | Synthesis delay estimates |
| `netlist/<top>.sdc` | Constraints for downstream tools |
| `db/<top>.ddc`, `db/<top>.svf` | Design database and formal verification guidance |
| `reports/<top>_*.rpt` | Design checks, design summary, QoR, area, timing, constraint violations, power, references, resources |
| `dc.log` | Design Compiler log |

`SYNTH_BUILD` changes the output directory. Each `make synth` reruns synthesis,
removes previous handoff files, and fails on analysis, linking, compilation, or
design-check errors and on missing/empty handoff files. Inspect the timing and
constraint reports to assess whether the chosen budget is met. The power report
uses DC's default activity estimates; simulation activity is generated separately
with the SAIF targets.

The shared SDC retains the reference uncertainty, transition, source/network
latency, I/O delay, and output-load budgets. `SYNTH_CLOCK_PERIOD=4.0` sets
250 MHz for libraries whose time unit is ns; load values use the library
capacitance unit. `SYNTH_CLOCK_PORT=i_clk` selects the counter's actual port;
set it to `clk` for the port in the screenshots. The synthesis driver maps
these Make options to the SDC's `CLOCK_PERIOD` and `CLOCK_PORT` variables.
As in the reference, sequential constraints are skipped when that port is
absent. `SYNTH_CONSTRAINTS` defaults to `src/constraints/timing.sdc`; set it to
`/server/path/design.sdc` to replace this budget, including for combinational
designs.

Other flows can source the same SDC after loading/linking their design and
technology libraries. It uses ordinary Tcl variables and has no dependency
on the synthesis environment or DC compilation commands:

```tcl
set CLOCK_PORT clk
set CLOCK_PERIOD 4.0
set CLOCK_NAME CLK
set OUTPUT_LOAD 0.04
source /absolute/path/mosaic-cgra/src/constraints/timing.sdc
```

Defaults are `CLOCK_PORT=i_clk`, `CLOCK_PERIOD=4.0`, `CLOCK_NAME=CLK`, and
`OUTPUT_LOAD=0.04`. Configure these variables before sourcing the file in a
tool with the corresponding SDC commands. The DC-specific
`set_fix_multiple_port_nets` command stays in the synthesis driver.

Additional synthesis options are configurable:

```sh
make synth TECH_SETUP_TCL=/server/tech/lib_setup.tcl \
  SYNTH_CLOCK_PERIOD=4 SYNTH_CLOCK_PORT=clk \
  SYNTH_PARAMETERS="WIDTH=16" SYNTH_COMPILE_ARGS="-no_autoungroup"
```

`SYNTH_PARAMETERS` uses DC's `elaborate -parameters` syntax.
`SYNTH_COMPILE_ARGS` is a Tcl list of additional `compile_ultra` options; the
default is empty. Both passes use `-gate_clock -retime`, and the second adds
`-incremental`. The script enables leakage optimization and configures latch
clock gating with `-control_point before`, as in the screenshots. Use a test
matching the chosen parameters and transformations.

`SYNTH_CPUS` defaults to 4. If the server provides `set_multi_cpu_usage`, the
script uses the command from the photo; otherwise, it uses DC's documented
[`set_host_options -max_cores`](https://studylib.net/doc/27956669/design-compiler%C2%AE-user-guide-version-v-2023.12--december-2023).
It calls `optimize_leakage` between passes when the server provides it. When
that command is absent, the log states that leakage optimization is handled
during the enabled `compile_ultra` passes. Synopsys documents leakage
optimization during compilation in the [Power Compiler user
guide](https://iccircle.com/static/upload/img20240918122431.pdf).
The script retains error propagation, Verilog name normalization, and SDF
output for the gate simulation flow.

Run the same PyUVM test on the mapped netlist, supplying the Verilog models for
all cells and macros instantiated by that netlist:

```sh
make gate-sim CELL_MODELS="/server/tech/cells.v /server/macros/models.v"
make gate-saif CELL_MODELS="/server/tech/cells.v /server/macros/models.v"
```

These targets use `NETLIST_FILE`, defaulting to the synthesized netlist, and
compile it with `CELL_MODELS` instead of the RTL. They use existing netlists
without rerunning synthesis. Functional gate simulation results are stored in
`build/vcs/<top>/gate/functional/`; `gate-saif` also writes `<top>.saif` there.
Override `GATE_SIM_BUILD`, `GATE_RESULTS_FILE`, and `GATE_SAIF_FILE` to change
these paths. The existing test selection, include paths, compiler, runtime,
and SAIF scope/time-unit options apply.

For timing simulation, add an SDF file. VCS receives
`-sdf <corner>:<scope>:<absolute-file>` at compilation, with `SDF_CORNER=max`
and `SDF_SCOPE=COCOTB_TOPLEVEL` by default; `min` and `typ` are also accepted:

```sh
make gate-saif CELL_MODELS=/server/tech/cells.v \
  SDF_FILE="$(pwd)/build/synth/counter/netlist/counter.sdf"

# Use matching post-route outputs from your physical implementation tool.
make gate-saif CELL_MODELS=/server/tech/cells.v \
  NETLIST_FILE=/server/route/counter.v SDF_FILE=/server/route/counter.sdf \
  SDF_CORNER=max GATE_SETTLE_NS=2 TEST_CLOCK_PERIOD_NS=10
```

Timing simulation outputs go in `build/vcs/<top>/gate/timing/`. DC synthesis
produces a mapped netlist and estimated delays. Simulation of the placed and
routed design uses its exported netlist and matching SDF; this Makefile does
not perform place and route. Check VCS's SDF annotation messages to confirm the
cell models and instance names match. See the vendor's [SDF annotation
documentation](https://device.report/m/21147a58a2161729f264107c63437223e00ed7e3bf0dc09504e86cb06b5da352)
for the compilation option.

The starter `CounterTest` drives inputs at the falling edge and samples after
the rising edge. `gate-sim` and `gate-saif` set its settling delay with
`GATE_SETTLE_NS` (default 1 ns); RTL uses `TEST_SETTLE_NS=0`. Set the delay long
enough for the selected netlist/SDF, and keep it below half
`TEST_CLOCK_PERIOD_NS`. The test clock defaults to `SYNTH_CLOCK_PERIOD` interpreted
in ns; override it explicitly if the technology has different time units. The
test has a 1 us timeout. Other PyUVM tests must implement their own timing-aware
sampling.

Use `make clean-gate` before changing the netlist/model list or SDF path, scope,
corner, or compiler flags to force a fresh compilation. Pass the same
`SDF_FILE`/`GATE_SIM_BUILD` overrides when cleaning the timing build.
`make clean-synth` removes the selected synthesis output directory.

## Test-driven power and energy

Run a selected PyUVM test on the gate netlist, capture its activity with VCS,
and analyze average power with PrimeTime PX/PrimePower in one command:

```sh
make power \
  COCOTB_TOPLEVEL=counter COCOTB_TEST_MODULES=test_counter \
  COCOTB_TEST_FILTER=CounterTest \
  POWER_TECH_SETUP_TCL=/server/tech/pt_lib_setup.tcl \
  CELL_MODELS=/server/tech/cells.v \
  NETLIST_FILE=/server/route/counter.v \
  POWER_SDC_FILE=/server/route/counter.sdc \
  SDF_FILE=/server/route/counter.sdf \
  SPEF_FILE=/server/route/counter.spef \
  TEST_CLOCK_PERIOD_NS=4 GATE_SETTLE_NS=1
```

Use matching netlist, SDF, SPEF, and constraints exported by the physical
implementation flow. SDF supplies the simulation delays; SPEF supplies the
extracted capacitances for power analysis. The technology libraries need
internal and leakage power models, and should match the selected process,
voltage, temperature, and parasitic corner. This target consumes physical
implementation outputs; it does not run placement and routing.
Synopsys describes this combination in its [post-route power analysis
overview](https://qacf-www.synopsys.com/blogs/chip-design/software-enabled-full-chip-power-signoff-soc-verification.html).

`POWER_SHELL` defaults to `pt_shell` and requires a PrimeTime PX/PrimePower
license in addition to the VCS simulation license. Set it to an absolute
executable path when needed; `POWER_ARGS` adds shell options.
`POWER_TECH_SETUP_TCL` defaults to `TECH_SETUP_TCL`. It must be compatible with
PrimeTime and configure `link_library` with power-characterized `.db`
libraries and their search paths. If only `target_library` is supplied, the
driver builds `link_library` from it. An optional `POWER_TOOL_SETUP_TCL` is
sourced after the technology script and configures PrimeTime PX/PrimePower
independently of the synthesis setup. The DC-only `DC_SETUP_TCL` is not used
by this analysis. Python 3.12+ is needed to generate the energy summary, using
`PYTHON` (for example, `PYTHON=python3.12`); this script has no third-party
dependencies.

For a synthesis-stage estimate, first run `make synth` and then use its
default netlist and SDC:

```sh
make power TECH_SETUP_TCL=/server/tech/pt_compatible_lib_setup.tcl \
  CELL_MODELS=/server/tech/cells.v \
  SDF_FILE="$(pwd)/build/synth/counter/netlist/counter.sdf" \
  COCOTB_TEST_FILTER=CounterTest
```

`POWER_SDC_FILE` defaults to `build/synth/<top>/netlist/<top>.sdc`. When no
`SPEF_FILE` is supplied, the log and JSON identify the result as a
`mapped_netlist_estimate`. Supply post-route inputs for an analysis including
the physical interconnect. `SDF_FILE` is optional for functional simulation,
but timing simulation captures additional transitions caused by gate delays.

`make power` always runs a fresh gate simulation, rebuilding the simulator
to pick up the selected netlist, models, SDF, and options. It uses the usual
`COCOTB_TEST_MODULES`, `COCOTB_TEST_FILTER`, and plusarg selection. Without a
filter, power and energy cover the whole selected test campaign. The SAIF
capture starts at time zero and includes reset, initialization, and idle time
through the end of the test. To characterize a workload, select a test whose
simulation interval represents that workload.

The analyzer reads the same netlist used by the simulator and annotates the
gate SAIF with `read_saif -strip_path`. `POWER_SAIF_STRIP_PATH` defaults to
`SAIF_SCOPE`, with dots replaced by slashes. Override it to match the hierarchy
inside the SAIF, for example `tb/dut`, corresponding to the analysis top.
The summary requires at least one net annotated from the file. Inspect
`activity.rpt` and `activity_unannotated.rpt` to assess coverage; remaining
activity can be propagated or estimated by the tool. The flow uses the
[vendor's averaged SAIF analysis](https://pdfcoffee.com/primetimepxptpxuserguidepdf-pdf-free.html)
and keeps clock scaling disabled to retain the test's measured activity.

Results go under `build/power/<top>/timing/` when `SDF_FILE` is set, or
`build/power/<top>/functional/` otherwise. Set `POWER_BUILD` to keep separate
results for different tests or corners.

| Output under `POWER_BUILD` | Contents |
| --- | --- |
| `summary.json` | Capture duration in seconds, average power in watts, energy in joules, activity coverage, and input/test selection |
| `reports/power.rpt` | Average power and its units |
| `reports/power_hierarchy.rpt` | Power by hierarchy |
| `reports/activity.rpt`, `reports/activity_unannotated.rpt` | SAIF annotation coverage and unannotated objects |
| `reports/check_timing.rpt` | Timing checks |
| `reports/parasitics.rpt` | Parasitic annotation report when SPEF is supplied |
| `power.log` | Power tool log |

The console prints total, dynamic, and leakage power in mW and energy in pJ.
The JSON also includes separate internal and net-switching components.
Energy is computed over the complete captured interval:

```text
duration_s = SAIF DURATION * SAIF TIMESCALE in seconds
dynamic_power_w = internal_power_w + switching_power_w
total_power_w = dynamic_power_w + leakage_power_w
energy_j = average_power_w * duration_s
```

Power units come from the verbose report, including separate dynamic and
leakage units; the summary does not assume that bare numbers are watts.
SAIF provides average activity, so these results describe average power and
interval energy. Peak power and a power waveform require an event-based
analysis with VCD/FSDB.

To analyze an existing gate SAIF without rerunning its test:

```sh
make power-report \
  POWER_TECH_SETUP_TCL=/server/tech/pt_lib_setup.tcl \
  NETLIST_FILE=/server/route/counter.v \
  POWER_SDC_FILE=/server/route/counter.sdc \
  SPEF_FILE=/server/route/counter.spef \
  POWER_SAIF_FILE=/server/activity/CounterTest.saif
```

`POWER_SAIF_FILE` defaults to `GATE_SAIF_FILE`; `make power` also writes its
fresh capture to this path. For `power-report`, input/test selection recorded
in JSON comes from the supplied Make options; use values matching the
original simulation. A failed test, tool error, invalid duration, ambiguous
power units, or zero SAIF annotation makes the target fail. Previous power
reports and summaries are removed before each attempt. `make clean-power`
removes the selected `POWER_BUILD`; the simulation and SAIF are cleaned with
`make clean-gate`. If `POWER_SAIF_FILE` uses a custom path, also pass that
path as `GATE_SAIF_FILE` when cleaning.

Run the flow checks without DC/VCS licenses with
`python3 -m unittest discover -s tests -v` (requires `make` and `tclsh`). They
exercise the real synthesis Tcl with stubbed DC commands and check error
propagation, stale-output removal, and gate simulation prerequisites. The VCS
command check uses the Python dependencies from `make setup` or `PYTHON_BIN`.
Power checks also exercise the real Make/Tcl flow with stubbed licensed
commands, unit conversions, SAIF duration, coverage, and simulation failures.
Local checks do not validate the technology models or native licensed power
analysis; run the command above on the server to obtain design power values.

Run the common tile-shell integration regression:

```sh
make tile-shell-regression
make tile-shell-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=tile_shell
```

The shell reuses context memory/sequencing, boundary and asynchronous FIFOs,
protected storage, counters and the tile power controller. Its Python-only suite
checks configuration, ownership, metadata, runtime control, completion ordering,
reset epochs and power handshakes across 27 parameter profiles. See the
[tile-shell validation details](src/val/mosaic_blocks/tile_shell/README.md) for the
repository-local boundary, body contract, debug map, protection and evidence.
Synthesis is deferred to Design Compiler.

Run the scalar BCT integration regression:

```sh
make bct-regression
make bct-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=bct
```

The BCT composes the common tile shell with released scalar arithmetic, register
storage, predication, bypass, RDU/elastic synchronization and protected result
queues. Its Python-only campaign checks BCT-A/M/MAC mappings, atomic destinations,
local-state lifetime, temporal contexts, protection, runtime and power behavior.
See the [BCT validation and context ABI](src/val/mosaic_blocks/bct/README.md) for
configuration, timing, debug counters and evidence. Design Compiler synthesis is
deferred.

Run the vector VCT integration regression:

```sh
make vct-regression
make vct-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=vct
```

The VCT composes the common tile shell with vector lanes, slice-banked VRF,
predicates and masks, vector/scalar accumulators, reduction, optional dot product,
bypass, RDU or elastic synchronization, explicit packing and protected result
storage. The Python-only campaign checks numerical results, lane masks, partial
writes, state lifetime, atomic output, runtime, protection and power behavior.
See the [VCT validation and context ABI](src/val/mosaic_blocks/vct/README.md) for
configuration, conservative timing, debug counters and reproducible evidence.
Design Compiler synthesis is deferred.

Run the configuration-network specification regression:

```sh
make configuration-network-regression SIM=icarus PYTHON_BIN=.venv/bin/python
```

The fabric reuses multicast forks, packet-locking arbiters, FIFOs, skid buffers
and protected storage. Its PyUVM campaign checks packet delivery, ordered endpoint
results, image preparation, coordinated commit, execution hold, cancellation and
fault recovery. A separate conformance test checks the tile-shell configuration
adapter. See the [configuration-network validation guide](src/val/mosaic_blocks/configuration_network/README.md)
for packet and endpoint contracts, supported synchronous profiles and reproducible
evidence. Validation is Python-only; Design Compiler synthesis is deferred.

Run the region-managed banked-scratchpad specification regression:

```sh
make banked-scratchpad-regression
make banked-scratchpad-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=banked_scratchpad
```

The DUT reuses the released scratchpad controller, real SRAM-backed banks and
protection codecs. PyUVM checks region ownership, generation fencing, atomic buffer
swaps, ordered completions, masked accesses, faults, drain/flush and power hooks.
See the [banked-scratchpad ABI and validation details](src/val/mosaic_blocks/banked_scratchpad/README.md)
for parameter profiles, descriptor packing, counters and evidence. Validation is
Python-only; Design Compiler synthesis remains deferred.


The [MST PyUVM suite](src/val/mosaic_blocks/mst/README.md) validates the memory
and stream tile using the existing shell, load/store engines, AGU, conversion,
and protected buffering blocks. Run `make mst-regression SIM=icarus` locally or
select `SIM=vcs` on the licensed server. This is a Python-only campaign;
Design Compiler synthesis is deferred.

Run the generated Cluster-MVP specification campaign:

```sh
make cluster-generate
make cluster-regression SIM=icarus
make cluster-regression
```

The selected 2×2 cluster composes three real BCTs, one MST, the static mesh,
configuration network and banked scratchpad. It adds exclusive allocation,
manifest-checked coordinated commit, lifecycle fanout, explicit metadata/memory
bridges, reliable events and coherent counters. See the
[cluster validation details](src/val/mosaic_blocks/cluster/README.md) for the generated
architecture, public ABI, supported profiles and Python-only evidence. Synthesis
remains deferred to Design Compiler.

Run the Specialized Function Tile specification campaign:

```sh
make sft-generate
make pyuvm SIM=icarus COCOTB_TOPLEVEL=sft
make sft-regression SIM=icarus
```

The SFT composes the actual tile shell and reusable LUT, polynomial, reciprocal,
rsqrt, exponential, exact reduction, scalar arithmetic, storage and formatting
blocks. It provides four guarded fixed-point profiles with ordered retirement,
immutable context/function-bank programming and explicit mapper-owned replay.
See the [SFT validation details](src/val/mosaic_blocks/sft/README.md) for the local
ABI, supported configurations and Python-only evidence. Design Compiler synthesis
is deferred.

Run the Control and Predicate Tile specification campaign:

```sh
make cpt-generate
make pyuvm SIM=icarus COCOTB_TOPLEVEL=cpt
make cpt-regression SIM=icarus
```

The CPT composes the released shell, predicate, comparison, nested-loop,
event/barrier, typed control-register, queue, arbitration and counter modules.
Local and Cluster profiles support reliable event records and explicit tagged
coordination. See the [CPT validation contract](src/val/mosaic_blocks/cpt/README.md)
for the public ABI, supported limits and Python-only evidence. Synthesis remains
deferred to Design Compiler.

Run the global NoC specification campaign:

```sh
make global-noc-generate
make pyuvm SIM=icarus COCOTB_TOPLEVEL=global_noc
make global-noc-regression SIM=icarus
```

The global NoC composes real routers and tile network interfaces into a rectangular
mesh, with flow bindings, dedicated configuration, packet credit reservations,
epochs, coordinated drain/flush and public accounting. See the
[global NoC validation contract](src/val/mosaic_blocks/global_noc/README.md) for the
ABI, supported profiles, endpoint integration obligations and Python-only test
coverage. Synthesis remains deferred to Design Compiler.

Run the runtime-controller specification campaign:

```sh
make runtime-controller-generate
make pyuvm SIM=icarus COCOTB_TOPLEVEL=runtime_controller
make runtime-controller-regression SIM=icarus
```

The runtime controller reuses the existing queues, arbitration, counters and
protected-state blocks for Static and Partitioned admission, complete-cluster
reservations, authoritative lifecycle handshakes, rollback, safe suspend/resume
and monitoring. See the
[runtime-controller validation contract](src/val/mosaic_blocks/runtime_controller/README.md)
for the normalized peer ABI, resource ownership and recovery requirements,
supported limits and Python-only evidence. Synthesis remains deferred to
Design Compiler.

Run the cluster power manager specification campaign:

```sh
make cluster-power-manager-generate
make pyuvm SIM=icarus COCOTB_TOPLEVEL=cluster_power_manager
make cluster-power-manager-regression SIM=icarus
```

The manager composes released tile power controllers, actual root/group clock
gates, reset synchronizers, isolation cells, counters, queues and protected
storage for Clocked and Protected Clocked operation. See the
[cluster power manager validation contract](src/val/mosaic_blocks/cluster_power_manager/README.md)
for the AON ABI, authorization and recovery requirements, Python peer integration
boundary and guarded advanced physical profiles. Synthesis remains deferred to
Design Compiler.
