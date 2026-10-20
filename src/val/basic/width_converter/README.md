# Width-converter PyUVM validation

This suite checks the [streaming width-converter specification](../../../../../specs/basic/mosaic-width-converter/README.md)
against [`width_converter.sv`](../../../rtl/basic/width_converter.sv). It uses the
repository's existing `dff` and `operand_isolation` RTL without modifying them.
The runner records the exact RTL, dependency and verification source hashes.
It uses the positional interface defined in the specification; no external packet
encodings or dependency manifest are introduced.

## Run

```sh
make setup
make width-converter-regression
make width-converter-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=width_converter
```

The regression defaults to VCS. Both simulator backends use native compilation
and the decorated `test_width_converter.WidthConverterTest` PyUVM test. This suite
requires Python 3.10 or newer. Override
`WIDTH_CONVERTER_REGRESSION_BUILD`, `WIDTH_CONVERTER_RANDOM_CYCLES` (at least 1000),
and `WIDTH_CONVERTER_SEED` to select the evidence directory and random campaign.
Defaults are `build/<simulator>/width_converter/regression`, 2000 cycles per
profile, and seed `20261020` plus the profile index.

A focused profile can be selected through the standalone runner, including when
invoked outside the repository:

```sh
.venv/bin/python src/val/basic/width_converter/run_width_converter_regression.py \
  --sim icarus --build-dir build/width-converter-focused \
  --case i32_o128_u8_m1_l1_a0
```

Focused runs still execute parameter guards and protocol probes. Custom RTL
parameters need matching `WIDTH_CONVERTER_IN_WIDTH`, `_OUT_WIDTH`, `_UNIT_WIDTH`,
`_USER_WIDTH`, `_LSB_FIRST` and `_ASYNC_RESET` environment settings. For example:

```sh
WIDTH_CONVERTER_IN_WIDTH=18 WIDTH_CONVERTER_OUT_WIDTH=6 \
WIDTH_CONVERTER_UNIT_WIDTH=3 WIDTH_CONVERTER_USER_WIDTH=3 \
make pyuvm SIM=icarus COCOTB_TOPLEVEL=width_converter \
  SIM_BUILD=build/icarus/width_converter/custom \
  COMPILE_ARGS='-Pwidth_converter.IN_WIDTH=18 -Pwidth_converter.OUT_WIDTH=6 -Pwidth_converter.UNIT_WIDTH=3 -Pwidth_converter.USER_WIDTH=3'
```

For VCS, use `-pvalue+width_converter.PARAMETER=value` instead of Icarus `-P`.
Use a fresh build directory for a changed parameter set. Derived parameters are
localparams and cannot be independently configured.

## Component structure and oracle

The test builds the normal sequencer, driver, monitor, agent, environment,
scoreboard and separate coverage collector. Shared `mosaic_uvm` components handle
wiring, strict four-state reads, simulator execution and evidence validation.

The functional model stores accepted transfer units as ordered records. A cleared
keep bit becomes an explicit hole, rather than a compacted-away unit. Packing
groups narrow records and pads unfilled slices; serialization queues narrow
records in stream order and removes only trailing terminal holes. Equal-width
mode uses a single queued record. This model does not read the DUT assembly word
to predict functional data.

Every consumed record must match the exact data, keep, last and user value.
Separate ledgers conserve valid units and terminal boundaries across delivery,
reset and explicit flush cancellation. Comparing complete expected beats also
checks empty beats and positional holes that do not contribute valid units.

The monitor observes actual ports before the rising edge, on the rising edge
before NBA updates, after propagation, and during a held interval. Clockless
stimulus and finite between-sample pulses check the registered forward boundary
and producer stability. Input ready may depend on consumer ready, as specified.

Optional raw observations check:

- Every data unit updates only on an accepted input with that keep bit set.
- Keep and last update only on accepted input; packing user updates only on the
  first beat of a new group.
- Idle, stalled, reset and flush intervals preserve the unreset datapath and
  metadata, using an initial observation only as a storage-hold baseline.
- Valid, collection/emission index and terminal index agree with retained records.

`WIDTH_CONVERTER_CHECK_INTERNALS=0` disables hierarchy and raw-storage checks.
Those checks are then reported as `NOT_RUN`; the independent port oracle remains
active. This suite requires zero-delay RTL (`TEST_SETTLE_NS=0`, precision at most
1 ps). It does not qualify a delayed gate simulation by disabling internals.

## RTL behavior and integration

There is one wide-word-equivalent unreset data buffer, one wide keep register,
user and last storage, and direction-specific resettable control. Invalid units
hold their data storage; common operand-isolation instances clamp them at the
output. Reset and flush do not reset or overwrite data/keep/last/user registers.

| Profile | Retained control | Acceptance and output behavior |
| --- | --- | --- |
| Narrow to wide | Complete-valid bit and collection index | Each accepted beat fills its physical slice; a full group or early last registers an output. A consumed output may be replaced by a new group's first beat on the same edge. |
| Wide to narrow | Buffer-valid, emission and terminal indices | Capture registers the first output; each consumed slice advances. The final slice may be replaced with a new wide input on the same edge. |
| Equal width | One valid bit | One-entry elastic forwarding with one-cycle latency and one beat per cycle throughput. No index or terminal search remains. |

`LSB_FIRST` and `ASYNC_RESET` select static generate branches. LSB-first changes
only complete narrow-slice order; it does not reverse units or bits within a
slice. In packing, metadata must match within each wide group. Full nonterminal
groups may change user at the next group boundary, as the specification permits.

Input ready, output valid/data/keep/last/user and busy clamp to zero while reset
or flush is asserted, including between edges. Synchronous reset changes retained
control only at a clock edge; asynchronous assertion clears it immediately. Flush
always changes retained control synchronously. A short synchronous reset/flush
pulse therefore hides, then re-exposes, an item if no sampling edge occurs.

Inputs must obey producer stability and known-control requirements. The PyUVM
checker actively asserts these rules, accepted keep/last/user legality and
packing metadata consistency. No native HDL protocol assertions are claimed.
The RTL's invalid-parameter branch deliberately instantiates a named unresolved
module so malformed profiles fail elaboration before simulation.

The converter is single-clock, single-context and single-owner. Stop input and
drain busy before an ownership transition, or explicitly authorize flush to
cancel retained units. An incomplete packing group needs its completing beat
(or last) to drain. Asynchronous reset release must be synchronized externally.
Empty terminal inputs emit one empty last beat; systems prohibiting that packet
form must assert their own policy. Width/order/unit/metadata interpretation and
latency must be represented consistently in the mapper and performance model.

## Matrix and mandatory checks

The 76 profiles cross both ordering and reset modes with 19 geometries:

| Input → output bits | Unit bits | User bits |
| --- | --- | --- |
| 1 → 1 | 1 | 1 |
| 8 → 8 | 8 | 3 |
| 32 → 32 | 8 | 1 |
| 1 ↔ 2 | 1 | 1 |
| 6 ↔ 18 | 3 | 3 |
| 32 ↔ 128 | 8 | 1 |
| 8 ↔ 40 | 8 | 5 |
| 8 ↔ 48 | 8 | 2 |
| 64 ↔ 256 | 64 | 8 |
| 3 ↔ 21 | 1 | 2 |
| 16 ↔ 128 | 8 | 4 |

These are representative ratios 1–8, not an exhaustive enumeration of all
positive integer widths and ratios accepted by the RTL.

The suite requires every sequence/physical slice, every input/output keep
population crossed with last, every completion/terminal position, both binary
values on every data bit, empty packets, full/partial groups, and nonterminal
outputs. Directed traffic covers sparse positional holes, terminal trimming,
long multi-group packets, legal user changes, continuous peak-rate traffic,
every reachable ready-valid handshake combination, simultaneous
consume/replacement, input gaps and output stalls of lengths 0–4
and 32. Every retained position is reset and flushed with all four input-valid /
output-ready combinations. Clockless reset pulses distinguish reset styles.

Random traffic varies data, keep, last, legal metadata, producer gaps, consumer
backpressure and explicit flush. A blocked producer retains all fields until
acceptance or cancellation. X/Z tests place unknowns in ignored input units.

The runner additionally requires 27 parameter guards and 58 expected protocol
rejections. Guards cover zero, negative and unknown sizes, invalid booleans,
unit divisibility and noninteger ratios. Protocol probes check X/Z controls,
accepted keep/last/user and active data; every producer field and a finite
producer-data pulse; and metadata mismatch within a partial packing group.
Each rejection must come from the expected decorated test and exact assertion,
rather than a compilation failure, unrelated assertion or missing test.

## Local evidence and limits

Local Icarus evidence is recorded under `build/validation/`:

- `width-converter-final/summary.json`: the native PyUVM matrix, 152,000
  random clock opportunities, parameter guards and expected protocol failures.
- `width-converter-static/lint/summary.json`: Verilator lint for all 76 profiles.
- `width-converter-static/structure/summary.json`: Yosys structural synthesis for
  all profiles, checking exact storage capacity, one wide data buffer, unreset
  data/metadata, no initialization/latches/unresolved cells/generated clocks,
  and no combinational forward path from input valid or payload.
- `width-converter-static/formal/summary.json`: 16 representative unbounded
  binary sequential safety proofs, covering equal widths and ratio-three
  conversion in both orders and reset modes. A proof-only reference uses
  transfer-unit arrays and a different occupancy encoding, with internal
  inductive invariants. It assumes matching user metadata and starts from reset.
  `async2sync` provides an edge abstraction; native simulation separately checks
  between-edge reset behavior. This is not an X/Z or CDC/RDC proof.
- `width-converter-mutations/summary.json`: actual PyUVM detection of 20 injected
  ordering, keep, boundary, capture, clamp, replacement and storage-enable faults.
- `width-converter-port-only/coverage.json`: direct Make invocation with raw
  storage observations disabled.
- `width-converter-flow-tests.log`: existing synthesis/power flow tests.
- `width-converter-vcs/summary.json`: VCS availability status.

The campaign summaries are tied to source hashes; build artifacts are ignored
by Git. Missing simulator tools or licenses are `NOT_RUN`, never `PASS`.
Local structural synthesis does not establish technology area, timing, energy
or power. Commercial lint, CDC/RDC, DFT, VC LP, technology synthesis/equivalence,
physical implementation, PrimeTime, PrimePower and integrated mapper/context
policy checks remain `NOT_RUN` and require the corresponding tools, libraries
and system environment. This implementation is not a claim of full release
signoff under the specification's technology-dependent criteria.
