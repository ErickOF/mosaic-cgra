# Round-robin arbiter verification

The specification is
[`specs/basic/mosaic-round-robin-arbiter/README.md`](../../../../../specs/basic/mosaic-round-robin-arbiter/README.md).
The implementation is [`round_robin_arbiter.sv`](../../../rtl/basic/round_robin_arbiter.sv).
The decorated test is `test_round_robin_arbiter.RoundRobinArbiterTest`.

```sh
make setup
make round-robin-arbiter-regression              # native VCS
make round-robin-arbiter-regression SIM=icarus   # four-state RTL simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=round_robin_arbiter
```

To filter profiles while retaining all parameter and protocol probes:

```sh
.venv/bin/python src/val/basic/round_robin_arbiter/run_round_robin_arbiter_regression.py \
  --sim icarus --build-dir build/arbiter-focused \
  --case n3_p2_l0_a1 --case payload_n5_p4_l1_a1 --seed 42 --random-cycles 1000
```

Names encode requester count, initial priority, lock enable and asynchronous reset.
`--case` is repeatable. Each seed is the base seed plus the profile's position in
the full matrix, preserving reproducibility when filtering. Paths resolve relative
to the runner, including when invoked from another working directory. At least
1000 randomized cycles are required per profile. The runner accepts compiler and
runtime flags, `--rtl` for checker qualification and a simulator binary directory.

Make settings are `ROUND_ROBIN_ARBITER_REGRESSION_BUILD`,
`ROUND_ROBIN_ARBITER_RANDOM_CYCLES` and `ROUND_ROBIN_ARBITER_SEED`. The default report
directory is `build/<simulator>/round_robin_arbiter/regression`. Dry runs preserve
existing evidence. Direct `make pyuvm` expects `ROUND_ROBIN_ARBITER_NUM_REQUESTERS`,
`ROUND_ROBIN_ARBITER_INITIAL_PRIORITY`, `ROUND_ROBIN_ARBITER_HAS_LOCK` and
`ROUND_ROBIN_ARBITER_ASYNC_RESET`, defaulting to `4, 0, 1, 0`; HDL compiler overrides
must match. The runner supplies both expected values and compiler overrides.

`ROUND_ROBIN_ARBITER_CHECK_INTERNALS=0` selects port-only checks and records geometry
and raw-storage assertions as `NOT_RUN`. `ROUND_ROBIN_ARBITER_COVERAGE_FILE` selects
another coverage path. Use `TEST_SETTLE_NS=0` and 1 ps or finer precision. These
checks target zero-delay RTL rather than timing-annotated gate models.

## RTL reuse and interface obligations

The rotating selection and raw contention cones reuse common `priority_encoder`.
All arbitration storage uses common `dff`, with enable-based holds and the selected
reset style. `INDEX_WIDTH` is derived and cannot be overridden independently.
Malformed counts, priorities and Boolean parameters, including X/Z values, fail
elaboration through `round_robin_arbiter_parameters_must_be_valid`.

The candidate search examines eligible requests starting at the saved pointer and
wraps explicitly at `NUM_REQUESTERS`. An accepted unlocked service advances the
pointer to the requester following the winner. An unaccepted candidate captures
only its index and lock indication. Pending and locked ownership bypass the
rotating selection cone. Pending metadata holds its last value while inactive to
avoid unnecessary writes; reset and flush clear it.

The requester must keep a pending request, eligibility, lock and payload stable.
Known live faults suppress grants immediately, and sampled faults set a sticky
error. Error freezes ownership and priority until reset or flush. Raw contention
continues to reflect eligible requests while pending, locked or in error.
`o_protocol_error` is registered: a synchronous reset or flush clears it on the
edge; grant, acceptance, contention, pending, lock and owner outputs clamp
immediately while reset or flush is asserted. An asynchronous reset also clears
the underlying state immediately.

A lock starts on an accepted lock-high beat. An owner gap is legal with request
low, eligibility high and lock high. Dropping lock during a request-low gap is a
protocol error. A final lock-low request may stall pending before acceptance; its
acceptance releases ownership. The saved pointer already follows the owner, so
continuation and final beats need no further pointer writes. With `HAS_LOCK=0`,
all lock inputs must be tied low and no lock-related storage is instantiated.

Payload buffering, response routing, bounded lock duration, reset release,
ownership policy and flush cancellation belong to the integrating resource.
Fairness requires a continuously asserted, eligible requester and eventual
acceptance of valid grants. Its bound is at most `NUM_REQUESTERS-1` accepted other
services, pausing during locks; it is not a bound in clock cycles. Requester IDs
are generic local indices. Dependency source hashes provide release evidence
without a dependency lockfile or private requester-encoding package.

## PyUVM structure and checking

The suite separates configuration, transactions, sequences, driver, monitor,
agent, independent model, scoreboard, coverage and environment. Shared
`mosaic_uvm` supplies component wiring, four-state values and regression execution.
The Python model keeps a cyclic requester-order list and an ownership history;
it does not reproduce the RTL's rotated-vector priority encoder.

Every observation checks all outputs, and optional internal observations compare
pointer, pending metadata, lock owner and sticky error against independent state.
Sampling occurs before the edge, at the real rising edge before NBA updates,
after settling and during a held interval. Clockless items check candidate
selection and immediate fault/reset/flush clamps. Continuous signal monitors
detect unauthorized storage changes, held-output pulses, relevant unknown controls
and finite changes to pending payload. Relevant X/Z controls must trigger the exact
live assertion; masked or unselected unknowns are explicitly exercised as legal.

`round_robin_arbiter_payload_tb.sv` combines the real arbiter, common `mux` and
`register_slice` receiver. Each requester carries a distinct 32-bit payload. The
receiver samples the actual selected payload and requester ID on the accepted
edge. The model checks both the combinational selection and the registered
receiver, including stalls, owner gaps, lock continuation and final-beat release.

## Matrix and coverage

There are 96 unit profiles across counts `1, 2, 3, 4, 5, 8, 16, 31, 32, 33`:
all counts run initial priority zero with both lock and reset modes; counts through
16 additionally cover every legal initial priority; counts 31–33 additionally run
midpoint and last priorities with all feature combinations. Six payload profiles
use counts 1, 3 and 5 with locks enabled and both reset styles.

Every profile requires 19 goals, including:

- Every accepted requester, pointer value and pointer/single-request cross.
- Every requester pair, feasible request/eligibility-population/contention cross
  and accepted-winner transition. Counts through four also exhaust all request and
  eligibility masks at every pointer.
- Wraparound, continuous one-grant-per-cycle acceptance, and pending lengths zero
  through eight plus 32 cycles; every pending winner sees unselected changes when
  at least two requesters exist.
- Every lock owner, owner gap, post-lock winner and lock-high accepted-beat count
  of 1, 2 and 8 before the final lock-low beat; disabled lock features are explicit
  static exclusions.
- Every hardware-error class, reset/flush from every reachable state class and
  reset/flush pulses between edges while pending.
- Exact randomized cycle count, payload alignment in integration profiles, and
  all sampling stages. The model also asserts accepted-service fairness on every
  service, with full-contention streams exercising the bound.

Sixteen malformed parameter configurations must fail the named elaboration guard.
There are 104 expected-failure probes for X/Z global, selected, pending and owner
controls, disabled-lock inputs, unknown accepted payload, changed pending payload
and finite pending-payload pulses. Each must fail precisely the decorated PyUVM
test with its expected assertion. Compile failures, missing tests, unrelated
exceptions or the probe's fallback failure do not count as a successful rejection.

## Evidence and qualification scope

The runner verifies native JUnit identity, elaborated parameters, every mandatory
goal, seed and randomized count. Summaries record RTL, dependency, fixture and
verification source hashes, UTC timestamps and per-case evidence paths. Filtered
campaigns are marked `selected_profiles`. Generated evidence and local
qualification helpers remain under ignored `build/validation/`.

The local Icarus campaign passed all 102 profiles, 204,000 randomized cycles and
2,617,207 observations. It checked 282,566 accepted services, including 5,473 real
payload-receiver acceptances. All 16 parameter guards and 104 protocol probes
passed. The checker detected all 23 injected RTL defects, including incorrect
priority/wrap, pending reassignment, broken locks, premature pointer writes,
incorrect fault clamps, reset-style errors and finite output pulses.

Local Verilator lint and Yosys structural checks passed all 96 unit profiles. The
storage budget is `2*INDEX_WIDTH+2` bits without locks and `3*INDEX_WIDTH+4` with
locks, including the derived one-bit indices for a single requester. Structural
checks also verify reset style, absent disabled lock state, no latch/memory,
no generated clock and no unresolved reference.

All 20 supplemental unbounded binary safety proofs passed for counts 1–5 with
both lock and reset modes against an independent state/output model. They start with equal
in-range arbitrary state and use `async2sync` for the asynchronous reset's edge
model. All 20 separate symbolic-requester proofs passed across the ten counts with
locks enabled and disabled, proving the accepted-other-service bound using cyclic distance.
They assume continuous request/eligibility, legal pending holds and no intervening
lock, reset or flush. Arbitrary stalls are allowed; eventual consumer acceptance
remains an environmental progress assumption. These proofs do not establish
four-state behavior, between-edge reset timing or physical equivalence.

Native VCS and licensed lint/CDC/RDC, DFT, VC LP, technology mapping, physical
timing/power, canonical requester ownership and cancellation-policy checks require
the corresponding tools, libraries and integration artifacts. Simulation reports
record them as `NOT_RUN`, separately from supplemental local qualification.

### Dynamic internal scheduling

`HOLD_PENDING=1` is the default and preserves a stalled stream grant until
acceptance. `HOLD_PENDING=0` suppresses pending-grant capture, allowing an internal
candidate to disappear before acceptance. The round-robin pointer still advances
only on acceptance. This mode is used with `HAS_LOCK=0` by `event_barrier` for
atomic event, wait, and cancellation scheduling. Its contention and candidate
withdrawal are exercised by the event/barrier PyUVM regression.
