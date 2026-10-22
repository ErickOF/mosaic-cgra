# PyUVM validation structure

Each module under `<category>/<module>` is a Python package with these roles:

| File | Responsibility |
| --- | --- |
| `config.py` | Expected RTL parameters and suite-specific timing/campaign settings |
| `transaction.py` | Sequence items and immutable observations/state records |
| `driver.py` | Drive the module interface using its existing sampling schedule |
| `monitor.py` | Read real DUT ports and observe continuous waveform activity |
| `agent.py` | Group the sequencer, driver and monitor |
| `model.py` | Independent module-specific prediction and control rules |
| `scoreboard.py` | Assert functional behavior and submit checked coverage samples/metrics |
| `coverage.py` | Own bins, mandatory goals and coverage reports |
| `env.py` | Connect the agent, scoreboard and coverage collector |
| `sequences.py` | Directed and seeded specification stimulus |
| `test_*.py` | Decorated PyUVM entry points, configuration and initialization |
| `run_*_regression.py` | Module profiles, parameter literals, negative probes and matrix goals |

`constants.py` holds interface names or truth tables where a suite needs them.
Some suites also contain an HDL integration fixture. The counter's small
`test_counter.py` remains a direct smoke test for RTL and delayed gate outputs;
its specification test uses the complete component hierarchy.

```text
test
└── environment
    ├── agent
    │   ├── sequencer
    │   ├── driver
    │   └── monitor ── analysis port ──► scoreboard
    └── coverage ◄── checked samples/metrics ── scoreboard
```

The environment retains an `env.sequencer` property for existing sequence startup
calls. Actual component paths now include `env.agent.driver` and
`env.agent.monitor`. Configuration continues to use `env.*` matching. Coverage
is a separate UVM component and receives information after the corresponding
functional checks. For sequential models, some coverage metrics are recorded
alongside state prediction to preserve their exact event ordering.

The monitors observe DUT ports but use driver-coordinated sampling windows and
transaction metadata. These agents therefore require active mode. Supporting
autonomous `UVM_PASSIVE` monitoring requires a module-specific sampling policy;
changing a flag alone is insufficient.

## Shared infrastructure

[`lib/mosaic_uvm`](lib/mosaic_uvm) contains reusable infrastructure:

- `logic.py`: width-checked four-state conversion and signal reads.
- `patterns.py`: common data-pattern classification.
- `components.py`: agent/environment construction and mandatory coverage reporting.
- `regression.py`: CLI parsing, simulator execution, exact JUnit validation,
  parameter guards, license detection, source hashes and campaign summaries.

Module-specific X/Z semantics, reference models, protocol legality, coverage
goals, static parameter literals and sampling schedules remain in their suites.
The shared parameter-guard helper records elaboration rejection separately from
explicitly permitted simulation-startup rejection. The lane-mask runner retains
its structural-rejection policy and reports its explicit-guard coverage gap.
The async FIFO under `basic/async_fifo` adds an independent accepted-record queue,
destination-edge visibility histories, and coordinated reset cancellation. The
shared runner accepts a category and ordered RTL dependencies for its guards.
The bypass network under `basic/bypass_network` uses per-destination graph lookup,
retained capture state, and pre-edge/post-edge/held observations. Its monitor
checks destination and storage bits independently during quiet intervals.
The context memory under `basic/context_memory` keeps independent data/validity
history, verifies pre-edge masked-write behavior and post-edge atomic commits,
and monitors unchanged entries and unmasked slices continuously.
The context sequencer under `basic/context_sequencer` uses a loop-visit history,
the full controller graph, and pre-edge/post-edge/held observations. Its additional
PyUVM fixture composes the memory and sequencer references to check real two-port
commitment and activation timing.
The data aligner under `basic/data_aligner` uses an independent byte-array
translation model and an accepted-window ledger for ready-valid ordering,
spill conservation, cancellation, and consume-and-replace behavior. Continuous
monitors check held outputs, isolated bytes, and registered capture activity.
The ECC suite under `basic/ecc` derives conceptual Hamming positions in an
independent mathematical model, sweeps every practical one/two-bit codeword fault,
and checks unknown propagation, corrected scrub words, and cone independence.
The synchronous FIFO under `basic/fifo` maintains an independent accepted-item
queue and checks all reachable occupancy/handshake combinations, reset timing,
full replacement, odd-depth wrapping, four-state payloads, and storage enables.
The element packer under `basic/packer` uses mathematical integer conversion and
an accepted-beat queue to check lane mapping, representability, saturation,
metadata, feature guards, cancellation and elastic output timing. Continuous
monitors verify invalid-lane isolation and accepted-only payload capture.
The granular parity suite under `basic/parity` uses a population-count model and
separate fault-position oracle to check generation, error mapping, whole-word
clamping and expected undetected even-weight faults. It also checks X/Z propagation,
activity during writes to selected granules, and continuous independence of both cones.

The performance-counter bank under `basic/performance_counters` uses Python integer
accumulation and independent shadow state to check weighted events, full-width
overflow, thresholds, ownership boundaries and coherent snapshots. Real-port
reads are checked before and after edges; optional internal observations check all
live/shadow storage and isolated arithmetic operands on every sample. Negative
campaigns require the expected live protocol assertion to reject illegal controls.

The RDU suite under `basic/rdu` models each channel as an accepted-advance token
and bubble history. It checks all legal taps, stalls, draining, flush/reset priority,
strict capacity packing and context boundaries. Independent raw-storage predictions
and bit-level waveform masks detect writes on bubbles, bypass, inactive stages,
flushes or reset. Continuous input monitors enforce pending bypass stability.

The scalar register-file suite under `basic/register_file` tracks initialized
words independently of DUT storage. It samples old data at the real rising edge
and new data after NBA updates, checks multi-port independence, and rejects invalid
addresses and same-address write conflicts through live assertions. Optional raw
storage checking verifies holds without assigning a deterministic power-up value.

The register-slice suite under `basic/register_slice` tracks an independent
acceptance queue and reset-discard ledger. It checks old-token consumption at the
real rising edge, one-cycle visibility, continuous replacement throughput and both
reset styles. Continuous monitors enforce producer stability, registered forward
paths, and accepted-only payload writes, including finite changes between samples.

The round-robin arbiter suite under `basic/round_robin_arbiter` models cyclic
priority as an independent requester-order list. It checks every output and
registered ownership state before, on and after service edges, with continuous
assertions for relevant unknown controls and pending payload stability. Directed
and random traffic exercise eligibility, backpressure, locks, cancellation,
sticky errors and accepted-grant fairness. An actual mux and register-slice
receiver check that accepted requester IDs and payloads stay aligned.

The skid-buffer suite under `basic/skid_buffer` tracks an independent acceptance
queue with same-edge bypass and explicit reset discards. It checks capture,
buffered hold and release, the blocked producer on the release edge, and resumed
bypass on the next edge. Continuous monitors enforce producer stability and
capture-only payload writes. Clockless changes and structural checks verify that
upstream ready has no combinational dependency on downstream ready or input traffic.

The SRAM-wrapper suite under `basic/sram_wrapper` keeps independent committed words
and timestamped read obligations. It checks accepted requests, exact backend
maturity, response consumption, cancellation and credit conservation separately.
Optional internal observations verify every word, backend issue pins, latency/tag
tracking and response slots. A structurally different verification backend checks
replacement through the same public interface; it does not qualify vendor macros.

The stream-fork suite under `basic/stream_fork` maintains one reference queue per
output. It checks selected copies independently against observed handshakes,
preserves ordering across same-edge completion/replacement, and accounts for
reset discards per destination. Continuous assertions enforce blocked-producer
stability, stalled-output stability, known relevant controls and capture-only
payload writes. Coverage includes destination populations, first/final consumers,
partial completion, mask/order crosses, reset populations and intentional X/Z data.

The stream-join suite under `basic/stream_join` checks atomic input/output
handshakes at logical harness edges without adding a clock to the combinational
RTL. Per-input queues record only actual handshakes; each joined output must
consume its full required operand set on the same edge. Live assertions enforce
early-producer and required-mask stability, output holds and relevant known
controls. Coverage includes final arrivals, small control matrices, mask/order
crosses, optional activity, long waits/stalls and four-state payloads.

The vector-register-file suite under `basic/vector_register_file` models each
entry's slices independently. It predicts only initialized slices, merges legal
disjoint writes, and compares old read data on the actual clock edge against new
masked data after propagation. Optional bank observations check all unselected
storage holds. Coverage spans lane and slice populations, broadcast source
selection, ignored unknown inputs, port/address relations and intentional X/Z
transport; negative probes check active addresses and overlapping slice writes.

The width-converter suite under `basic/width_converter` uses accepted transfer-unit
records with explicit keep holes, group boundaries and user metadata. Packing and
serialization produce independent expected output queues; unit and terminal-boundary
ledgers account for delivery and explicit cancellation. Actual edge-time observations
check registered visibility and consume/replacement. Optional per-unit raw storage
checks and continuous waveform assertions enforce accepted-only writes, clamping,
producer stability and stalls. Coverage spans both orders, every representative slice
and keep population, terminal trimming, empty packets and reset/flush state crosses.

The accumulator suite under `building_blocks/accumulator` uses arbitrary-precision
integer range tests and independent per-lane validity/type histories. It checks
persistent outputs separately from the enabled-cycle response, rejects vector
updates atomically, and compares real pre-NBA and post-edge observations. Optional
raw-storage and operand observations check write enables and arithmetic isolation.
A verification-only HDL checker independently asserts port-based transitions.
Coverage includes small-width exhaustive transitions, numerical limits, all masks,
feature rejections, unknown controls, type changes and clock-enable stalls.

The AGU suite under `building_blocks/agu` uses unbounded integer descriptor
equations to check linear and signed-stride 1D/2D addresses independently of the
RTL recurrence. Real edge-time observations track exactly-once acceptance,
row boundaries, metadata, completion, classified errors and recovery. Optional
storage and waveform checks enforce accepted-only advancement and adder isolation;
a port-only HDL checker adds handshake-history assertions. Coverage includes
exhaustive small descriptors, signed limits, every supported element size,
misalignment, unknown required/ignored fields, stalls and both reset styles.

The dot-product suite under `building_blocks/dot_product` uses an independent
integer-product and range oracle, enabled-edge response history, every term mask,
small exhaustive vectors and deterministic workload shapes. It checks exact
reduction, final accumulation/saturation, status alignment, clock stalls, reset
removal, four-state controls, operand isolation and arithmetic-data write enables.
A separate wide-sum HDL checker supplements the actual-edge PyUVM scoreboard.
See its README for the 102-profile matrix and qualification limits.

The DMA suite under `building_blocks/dma_engine` uses independent load/store peers,
affine descriptor expansion and accepted/committed byte ledgers. It checks exact
copy-data correspondence, per-channel command order, protection, event starts,
atomic completion/event enqueue, backpressure, cancellation, stale epochs and
coordinated flush. Native HDL assertions and private counter observations supplement
the real-port scoreboard; coverage and conservation checks prevent silent loss.
See its README for the cumulative store-commit and load-data-epoch contracts.

The Makefile supplies the selected suite, its package parent and `src/val/lib`
through `PYTHONPATH`. Imports use qualified suite names, such as
`write_gate.agent`, to avoid collisions between generic filenames. Standalone
regression scripts locate the library relative to their own files, so they can
be invoked from another working directory.

All existing Make targets and decorated test module/class names remain available.
For example:

```sh
make write-gate-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=write_gate
.venv/bin/python src/val/common/write_gate/run_write_gate_regression.py \
  --sim icarus --build-dir build/write-gate-focused --case width8_functional
```

Campaign provenance now hashes every Python component in the selected package,
the shared library, the Makefile and any local HDL fixture. Moving checks between
files does not remove them from the evidence. Profile seeds, coverage goals,
expected failure diagnostics and external `NOT_RUN` checks retain their existing
suite-specific definitions.

The event/barrier suite under `building_blocks/event_barrier` checks an atomic
integer event ledger, ANY/ALL waits and cancellation, round-robin mutation
scheduling, participant masks, generation wrap and ordered completion/release
records. It exercises saturation, both queues under backpressure, context policy,
flush/reset, X/Z fields and protected-state fault injection. Its 44-profile
`event-barrier-regression` includes minimum/odd dimensions, all feature combinations
and both reset styles; the suite README states the remaining release checks.

The exponential suite under `building_blocks/exp_unit` uses an independent integer
reference with directly computed MPFR endpoints and constants. It checks exact
numerics, elastic ordering/latency, inactive arithmetic storage, parity/SECDED,
drain/flush/reset and unknown controls. The 55-profile `exp-unit-regression`
verifies generated assets and covers exhaustive reduced-width inputs, optional
features and representative formats. Its README links scalar accuracy evidence
and identifies remaining formal, physical and application qualification.
