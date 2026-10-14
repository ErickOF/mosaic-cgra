# Performance-counter bank verification

The specification is
[`specs/basic/mosaic-performance-counters/README.md`](../../../../../specs/basic/mosaic-performance-counters/README.md).
The RTL is [`performance_counters.sv`](../../../rtl/basic/performance_counters.sv).
The decorated test is `test_performance_counters.PerformanceCountersTest`.

```sh
make setup
make performance-counters-regression             # native VCS
make performance-counters-regression SIM=icarus  # local four-state RTL validation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=performance_counters
```

Run a selected geometry, preserving the parameter and assertion guards:

```sh
.venv/bin/python src/val/basic/performance_counters/run_performance_counters_regression.py \
  --sim icarus --build-dir build/performance-counters-focused \
  --case w5_c3_e5_i8_s0_n1_t1_a1 --seed 42 --random-cycles 1000
```

`--case` is repeatable. The effective seed is the base seed plus the profile's
index in the complete matrix, so filtering retains reproducible traffic.
The runner resolves source paths relative to itself and supports another working
directory, `--rtl`, compiler/runtime flags and a simulator binary directory.
`--random-cycles` must be at least 1000. Make variables are
`PERFORMANCE_COUNTERS_REGRESSION_BUILD`, `PERFORMANCE_COUNTERS_RANDOM_CYCLES`
and `PERFORMANCE_COUNTERS_SEED`. `make -n` preserves existing reports.

For direct `make pyuvm`, expected parameters use environment variables named
`PERFORMANCE_COUNTERS_<PARAMETER>`, with the specification defaults. Compiler
overrides must match these expected values; the runner supplies both. The suite
also accepts `PERFORMANCE_COUNTERS_SEED`, `PERFORMANCE_COUNTERS_RANDOM_CYCLES`,
`PERFORMANCE_COUNTERS_COVERAGE_FILE` and `PERFORMANCE_COUNTERS_CHECK_INTERNALS`.
`TEST_SETTLE_NS` must be zero, with 1 ps or finer simulator precision. This suite
checks zero-delay RTL, rather than timing-annotated gate models.

## RTL behavior and reuse

Each counter independently selects an unsigned event increment. Counter zero,
event zero and their low bits occupy the least-significant packed positions:

| Field | Slice |
|---|---|
| Event selection for counter `c` | `[c*EVENT_ADDR_WIDTH +: EVENT_ADDR_WIDTH]` |
| Threshold for counter `c` | `[c*COUNTER_WIDTH +: COUNTER_WIDTH]` |
| Increment for event `e` | `[e*INCREMENT_WIDTH +: INCREMENT_WIDTH]` |

The complete increment participates in addition before saturation or truncation.
Overflow is sticky; reaching maximum exactly does not set overflow, but a later
positive increment does. Wrapping threshold comparisons use the full sum before
truncation. Threshold pulses clear on the next edge unless a new crossing occurs.
For example, a 5-bit wrapping counter at 30 with threshold 31 and increment 2
stores zero, sets overflow and emits a threshold pulse on the same edge.

Common `dff` instances implement live values, sticky overflow, optional threshold
pulses and snapshot validity with the selected reset style. Common
`operand_isolation` instances gate both adder operands for disabled/frozen
counters, clear, invalid configuration, absent events, zero increments and already
saturated counters. The existing unit-step `counter` does not implement weighted
addition and is not instantiated merely to use its load port. The Makefile
discovers the ordered DFF and operand-isolation sources for simulation and synthesis.

Clear has priority over event accumulation. Reset has priority over all edge
operations. Snapshot captures post-update/post-clear values and overflow for every
counter at one edge; it neither freezes nor clears live state. Shadow payload has
no reset and holds even across reset; only validity is reset. Disabled snapshot
support removes shadow storage. Disabled threshold support removes comparison
and pulse storage. All Boolean parameters select static generate branches.

Configuration error is evaluated when global and per-counter enables are high,
including during freeze. A known out-of-range event or enabled zero threshold
reports an error and suppresses accumulation. Disabled counters report no error.
Unknown active selectors remain unknown and fail a live verification assertion.
Readback is combinational, nondestructive and zeroed when disabled or when a
known requested index/storage is unavailable. Active unknown indices propagate X
and fail an assertion; known out-of-range read indices return zero/invalid and
also fail an assertion.

Selection and threshold configuration changes require `i_clear[c]` on that edge,
or a disabled counter whose old value and overflow are already zero. Global
disable and freeze alone do not establish a cleared ownership boundary.
Configuration is provided by the integrating controller and is not registered or
made atomic inside this bank. The verification scoreboard enforces this contract.

## PyUVM structure and checks

`config`, `transaction`, `agent`, `driver`, `monitor`, `model`, `scoreboard`,
`coverage`, `env` and `sequences` follow the repository's standard component split.
The agent, environment wiring, four-state helpers and regression execution reuse
`mosaic_uvm`; there is no duplicate UVM infrastructure.

The model uses arbitrary-precision Python integer addition, modulo and saturation,
and independent live/shadow lists. It never reads DUT state to compute expected
values and never forces or deposits RTL storage. Every transaction is sampled
before the edge, after it and during a held interval. The scoreboard compares all
outputs at each sample, including the currently indexed read. Directed sweeps read
every live and snapshot entry without advancing the clock. Random traffic varies
events, weights, enables, freeze, clears, legal configuration changes, thresholds,
snapshots, reads and resets.

With internal checking enabled, all live values, retained shadow payload and
isolated arithmetic operands are also compared at every sample. Continuous
waveform monitors reject finite pulses during held intervals and shadow writes
outside capture. They verify quiet sequential state between edges, accounting for
asynchronous reset. Set `PERFORMANCE_COUNTERS_CHECK_INTERNALS=0` for a port-only
run; coverage then records elaboration and internal-state/isolation checks as
`NOT_RUN` instead of claiming those checks passed.

Known invalid event configurations and zero thresholds are directed negative
configuration cases: error reporting and state hold must match the model.
Separate assertion probes require the exact decorated test to fail on consumed
X/Z, unsupported feature controls, illegal read indices or uncleared reassignment.
For invalid index/select probes, the defined combinational rejection/propagation
is checked before the live protocol assertion fails. Assertions reside in the
Python scoreboard; this does not claim HDL SVA execution.

## Matrix and coverage

The 61 profiles comprise all 16 saturation/snapshot/threshold/reset combinations
at `(counter width, counters, events, increment width)` geometries `(1,1,1,1)`,
`(5,3,5,8)` and `(8,4,4,3)`; four arithmetic/reset variants each at `(16,10,16,16)`
and `(32,5,10,40)`; both arithmetic modes at `(64,8,3,65)` and `(129,2,1,131)`;
and the exact default `(48,10,16,16)` configuration. This covers single entries,
power-of-two and odd counts, wider/equal/narrower increments and widths beyond 64.

Each profile requires 20 coverage goals covering every counter/event assignment,
shared events, zero/unit/middle/maximum and every one-hot increment, the
global/per-counter/freeze cross, per-counter clear priority, arithmetic boundaries, illegal configurations,
threshold behavior, snapshot/update/clear crosses, snapshot replacement, every
live/snapshot read, ignored unknowns, ownership boundaries, reset pulses, exact
random counts and all sampling stages. Unreachable feature/geometry bins and
finite-run limits are stated in `coverage_limits`, rather than claiming hits.

Overflow setup is driven through event ports. Default 48-bit counters with 16-bit
increments cannot reach overflow in a practical regression. Their boundary bins
are explicitly `NOT_REACHED`; reduced-width profiles exercise exact maximum,
overflow, sticky status and wrap. A same-edge wrap threshold crossing requires
multi-bit increments. One-counter profiles cannot exercise shared selection, and
power-of-two event counts above one have no representable invalid selection.

The campaign also checks 32 strict elaboration failures: zero/negative/X/Z values
for four dimensions, and two/negative/X/Z values for four Boolean parameters.
Derived interface widths are local parameters, not independent configuration knobs.
The 105 live assertion probes include individual bits of active selection,
increment and threshold buses, both X and Z, both reset styles, frozen
reassignment, and controls for disabled optional features.

## Evidence and integration scope

The runner requires exact JUnit test identity, coverage goals, elaborated geometry,
seed and random count. `summary.json` records source/dependency/verification hashes,
parameters, per-case logs, guard outcomes and UTC timestamps. There are no new
dependency manifests or private contract packages. Reports and build products stay
under ignored `build/` paths. Missing simulators or licenses are `NOT_RUN`, never
`PASS`. A filtered campaign is identified as `selected_profiles`.

Local qualification of the current sources produced the following results under
`build/validation/performance-counters-*`:

| Check | Result |
|---|---|
| Icarus PyUVM matrix | PASS: 61 profiles, 20 goals each, 122,000 random cycles and 451,569 observations |
| Parameter rejection | PASS: 32 elaboration guards |
| Live protocol assertions | PASS: 105 expected test failures |
| Checker mutation sensitivity | PASS: 23 defective RTL variants rejected, including a 1 ps output pulse |
| Verilator lint | PASS: 61 profiles with the explicit feature/reset waivers below |
| Yosys structural synthesis | PASS: 61 profiles, exact storage counts, no latches or generated clocks |
| Yosys sequential induction | PASS: 61 profiles, unbounded binary behavior after reset |
| Custom seed and external working directory | PASS: selected profile plus all guards/probes |
| Port-only default geometry | PASS: internal/elaboration checks explicitly NOT_RUN |
| Existing synthesis/power stub tests | PASS: 31 tests |
| Native VCS | NOT_RUN: executable unavailable |

Lint waivers cover only unused inputs of statically absent features
(`i_snapshot`, `i_threshold_enable`, `i_threshold_value`) and `SYNCASYNCNET` for
`i_rstb` in asynchronous-reset profiles with snapshots. The latter reflects
asynchronous live/control reset plus synchronous inhibition of unreset shadow
writes. It does not establish reset-release safety or replace RDC analysis.
No functional lint warning is suppressed in the RTL.

The independent formal reference uses raw event ports, separate architectural
state and one more arithmetic bit than the implementation. It checks full live
state, sticky overflow, pulses, coherent snapshots, configuration errors and read
outputs. Induction is gated until reset; invalid shadow payload is not compared.
`async2sync` normalizes reset for edge-domain proofs. Larger cases normalize
simulation-only undefined mux branches and constrain induction states to binary
values; initial proof timeouts and superseded attempts remain in the evidence.
These proofs establish neither four-state behavior nor between-edge asynchronous
reset timing. PyUVM checks those simulation cases separately. They are also not
technology-mapped sequential equivalence or physical qualification.

Event slots are opaque inputs. This primitive assigns no numeric IDs for active,
idle, operations, stalls, errors or contexts. Architectural event definitions,
mutual exclusivity, kernel ownership, CDC bridges and software configuration
atomicity belong to the integration. Unsupported snapshot and threshold inputs
must be tied low; reset release must be synchronized externally when asynchronous
reset is selected. Attribution and mandatory tile event traces need integration
tests using the system's actual producer signals and contract.

Local Icarus tests, open-source lint, structural synthesis and formal checks are
distinct from licensed qualification. Native VCS, VC Lint, CDC/RDC, DFT, VC LP,
technology mapping, physical implementation, equivalence, PrimeTime and PrimePower
require their actual tools, libraries and integration reports. The simulation
runner marks these external checks `NOT_RUN`; a simulation pass is not a physical
or architectural release approval. Separate local checks must describe their
own proof and waiver scope.
