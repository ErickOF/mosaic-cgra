# Context sequencer RTL and PyUVM validation

[context_sequencer.sv](../../../rtl/basic/context_sequencer.sv) implements the
[MOSAIC context sequencer specification](../../../../../specs/basic/mosaic-context-sequencer/README.md).
It selects committed contexts, waits for candidates, counts loop visits, and
coordinates stop, suspend, resume, and resident switches with accepted steps and
tile safe points. Common `dff` storage holds control state; a common saturating
down `counter` holds remaining loop visits. Static generate branches select the
optional features. Candidate addresses never depend on candidate validity.

## Local interface and dependencies

As requested, encodings are defined in repository-local
[context_sequencer_pkg.sv](../../../rtl/basic/context_sequencer_pkg.sv), interface
version 1. No external `mosaic-contracts` package is required.

| Transition | Encoding |
| --- | ---: |
| `CONTEXT_HOLD` | 0 |
| `CONTEXT_INCREMENT` | 1 |
| `CONTEXT_JUMP` | 2 |
| `CONTEXT_LOOP` | 3 |
| `CONTEXT_END` | 4 |

| Error | Encoding |
| --- | ---: |
| `SEQ_ERR_NONE` | 0 |
| `SEQ_ERR_ACTIVE_INVALID` | 1 |
| `SEQ_ERR_ADDRESS` | 2 |
| `SEQ_ERR_TRANSITION` | 3 |
| `SEQ_ERR_LOOP` | 4 |
| `SEQ_ERR_COMMAND` | 5 |
| `SEQ_ERR_PROTOCOL` | 6 |

The package defines `context_transition_mode_t` and `sequencer_error_code_t` as
three-bit enums; their width constants derive from `$bits`. Mode encodings 5–7
are illegal. The transition input remains a logic vector so invalid and X/Z
values can be checked at the interface. Internal state and loop actions use
`sequencer_state_t` and `loop_action_t` enums. State encodings are private
implementation details, while public status outputs define behavior.

Reports hash the current DFF, counter, decoder, context-memory, local package,
RTL, fixture, all suite components, shared helpers, Makefile, and imported
memory-reference components. These hashes identify the files used in each run;
they do not restrict dependency edits or claim technology-qualified releases.

## Running

From `mosaic-cgra`:

```sh
make setup
make context-sequencer-regression                 # VCS on the licensed server
make context-sequencer-regression SIM=icarus      # Native four-state simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=context_sequencer
```

The Makefile discovers the suite and ordered package/DFF/counter sources. Explicit
`VERILOG_SOURCES` overrides take precedence. Synthesis uses the same discovery
when `COCOTB_TOPLEVEL=context_sequencer`.

```sh
make context-sequencer-regression SIM=icarus CONTEXT_SEQUENCER_SEED=1234 \
  CONTEXT_SEQUENCER_RANDOM_CYCLES=3000 \
  CONTEXT_SEQUENCER_REGRESSION_BUILD="$(pwd)/build/sequencer-custom"

.venv/bin/python src/val/basic/context_sequencer/run_context_sequencer_regression.py \
  --sim icarus --build-dir build/sequencer-focused \
  --case non_power_three_async --case memory_baseline
```

Repeat `--case` for focused runs. They retain all guards and assertion probes and
report `selected_profiles` scope. The runner works from another directory and
accepts compatible alternatives through `--rtl`. Seeds add the full matrix index,
so focused runs keep their original seeds. Unit profiles require at least 1000
random operations; defaults are 2000 and base seed 20261012. Every operation has
a falling and a rising phase, with directed traffic in addition to random traffic.

## Profiles

There are 55 controller profiles and three real-memory fixtures:

| Group | Depth | Loop width | Optional features | Reset |
| --- | --- | --- | --- | --- |
| `features_l<L>s<S>w<W>_<reset>` | 4 | 4 | All eight loop/suspend/switch combinations | Both |
| `minimum_<reset>` | 1 | 1 | All disabled | Both |
| `spatial_<reset>` | 1 | 2 | All enabled | Both |
| `non_power_three_<reset>` | 3 | 3 | All enabled | Both |
| `single_visit_<reset>` | 5 | 1 | All enabled | Both |
| `default_<reset>` | 4 | 16 | All enabled | Both |
| `exploration_<reset>` | 32 | 8 | All enabled | Both |
| `depth<N>_exploration` | Remaining depths 1–32 | 4 | All enabled | Synchronous |
| `memory_spatial` | 1 | 2 | All enabled | Synchronous |
| `memory_non_power_async` | 3 | 3 | All enabled | Asynchronous |
| `memory_baseline` | 4 | 4 | All enabled | Synchronous |

The feature group has 16 profiles; 27 additional depth profiles complete every
exploration depth from 1 through 32. Both default 16-bit profiles execute exact
middle and maximum loop trip counts, including all 65,535 visits of a maximum loop.
This is finite evidence for representative dimensions and every feature/reset
combination, rather than exhaustive coverage of all possible parameter products.

## Runtime and error policy

The default instance has depth four, a 16-bit count, all optional features, and
synchronous reset. Primary parameters retain caller values until structural guards
validate dimensions and exact Boolean restrictions. Derived widths are local.

Start and scheduled transitions activate immediately when a candidate is already
committed. Otherwise the latched address waits for a later edge with valid high.
Increment and loop fall-through do not wrap. Hold generates no activation event;
a self-jump generates activation without an address-change event. Only normal end
produces completion. Event pulses clear on every later edge, including stalls.

Loop counts express total visits. Later accepted owner visits use stored progress
and ignore the current count input. Suspension preserves the active address,
pending scheduled candidate, owner, and remaining visits. Resume of a saved
candidate wait returns to `CONTEXT_WAIT` before making that candidate executable.
External switching with live loop state is a command error.

Requests are single-cycle commands; pending states retain them internally. Stop,
suspend, and switch disable execution and request quiescence before their edge.
A safe point can be acknowledged on that edge. Every stop requires an explicit
safe point, including stops from non-executing states: this block has no signal
proving that earlier in-flight work is already drained. `SWITCH_WAIT` keeps
quiescence asserted until the destination is committed.

Safe-point values outside a pending/new runtime drain are ignored; unknown values
during a drain are protocol errors. `SWITCH_WAIT` no longer consumes safe point.
Transition metadata is consumed on accepted steps. Combinational prevalidation
enables only legal destinations. Disabled command addresses and unused metadata
are ignored.

Fault classification first rejects unknown reset/command/step inputs, conflicting
or illegal commands, and unknown enabled validity/safe-point inputs. Active
invalidation, unqualified steps, address faults, invalid resume, and consumed
transition/loop errors follow. Zero or unknown initial count is a loop error;
disabled loop mode is a transition error. Later errors cannot replace the first
latched code. Error entry retains address and live-loop debug state; error clear
returns to idle, clears pending/loop state, and requires a fresh start.

Known low reset clears registers in the selected synchronous/asynchronous style.
Reads and execution are clamped immediately. X/Z reset clamps execution and
produces a sampled protocol error, preventing speculative activation. Physical
reset-release synchronization and safe-point generation belong to tile integration.

## Reference model and assertions

The main suite follows the [shared PyUVM hierarchy](../../README.md): separate
configuration, transactions, sequencer, driver, monitor, agent, model, scoreboard,
coverage, environment, and decorated test. The model stores total visits and
visits completed, rather than copying the RTL's remaining-counter decrement.
Command legality follows a specification state table.

Every driven phase checks all 22 outputs before the edge, after the edge, and
after hold. Portable private state, latched candidate, and scheduled-wait flag
are also checked. Continuous monitors reject unclocked register changes and
finite pulses in quiet windows. Same-delta transients and physical delay are
outside this digital waveform scope.

Directed traffic covers the reachable graph, all commands in every state,
immediate/delayed candidates, every activated address, forward/backward/self jumps,
completion/restart, exact loop trips, owner violations, reset and error clear from
every state, and first-error preservation under subsequent command/protocol faults.
Stop/suspend/switch exercise safe-point latencies zero, one, and five. Stalls cover
every length zero through 32.

Mandatory coverage includes states/edges/errors/events, enabled-read state x
known validity, transition x candidate timing, jump/increment relationships,
loop-count class x stall class, runtime command x safe latency, and exact
random/pre/post/held counts. Disabled features, depth-one address relationships,
one-bit multi-visit counts, and depth-one fall-through have explicit waivers.

Positive error injections acknowledge their exact expected protocol assertion
and continue checking classified hardware error behavior. Untagged violations fail.
Fifty-six separate expected-failure probes cover unknown controls, validity,
safe points, addresses, modes and counts; all unused mode values; command legality
and conflicts; unqualified steps; nested loops; live-loop switch rejection;
invalid resume; and disabled features. A probe passes only when the exact PyUVM
test fails with the expected assertion and JUnit records that failure. Unrelated
compiler failures cannot pass.

Twenty-eight native elaboration checks reject zero/negative/X/Z dimensions and
non-Boolean, negative, oversized, or X/Z feature/reset values. Declaration sizes
allow these profiles to reach the named guard without invalid indexing. This
finite campaign does not prove every possible literal or physical capacity.

## Real context-memory connection

[context_sequencer_memory_tb.sv](context_sequencer_memory_tb.sv) connects actual
sequencer and memory instances with two reads and raw access tied low. Its PyUVM
test composes the independent memory history and sequencer visit model. Both
sequential models sample pre-edge validity before memory writes/commits update,
so a same-edge commit cannot activate an unchecked candidate.

Checks cover cold start wait, slice assembly, atomic final write/commit,
commit-to-activation timing, switch drain/commit wait, loop suspension/resume,
a candidate preserved through suspension and loading, immediate execution clamp
after active invalidation, error recovery, and reset retaining stored data while
clearing validity. All controller outputs, both data reads, qualified validity,
and portable storage/control state are checked. Stored words and held outputs
also have continuous activity checks.

The unit suite challenges the two validity inputs independently. The real-memory
fixtures additionally enforce their coupled data/validity behavior. A one-entry
array cannot have an uncommitted self destination while that same active entry
remains committed; that integration path is explicitly waived. The fixture uses
abstract safe points and decoded transition inputs, so tile drain, semantic
context validation, and execution correctness remain outside its scope.

## Reports and direct configuration

| Artifact | Evidence |
| --- | --- |
| `<profile>/results.xml` | Exactly one successful, unskipped expected test |
| `<profile>/coverage.json` | Mandatory goals, bins, parameters, seed, and scope |
| `<profile>/parameters.json` | Fresh parameter-change compile dependency |
| `<profile>/simulation.log` | Actual compiler and simulator output |
| `invalid_parameters/<case>/elaboration.log` | Intended structural rejection |
| `assertion_probes/<case>/results.xml` | Expected failure of the exact probe |
| `summary.json` | Matrix gates, guards/probes, source hashes, and external scope |

Default reports are under `build/<simulator>/context_sequencer/regression`.
Stale JUnit and coverage are removed before each simulation. Missing executables
or recognized license failures report `NOT_RUN` and return nonzero.

Direct settings use the `CONTEXT_SEQUENCER_` prefix for all primary parameters,
`SEED`, `RANDOM_CYCLES`, `ASSERTION_PROBE`, `COVERAGE_FILE`, and `CHECK_INTERNALS`.
The last defaults to one; zero enables port-only checking and reports private
structural observation as `NOT_RUN`. Match direct compiler overrides with expected
environment settings and use a fresh build. `TEST_SETTLE_NS` must be zero;
these suites do not model SDF delays.

Formal/HDL SVA, commercial lint, CDC/RDC, DFT, UPF, technology synthesis,
sequential equivalence, physical timing/power, reset-release integration, and
tile safe-point/semantic validation remain separate `NOT_RUN` checks. Functional
pass does not claim architectural or physical signoff.

## Local verification

Native Icarus Verilog 12.0, cocotb 2.1.0, and PyUVM 5.0.0 passed all 55 controller
profiles with all 21 mandatory goals, plus all three real-memory fixtures. Unit
checks covered 876,464 driven phases before the edge, after the edge, and after
hold: 2,629,392 observations, including 110,000 randomized operations. Coupled
fixtures checked another 438 observations. All 28 strict elaboration guards and
56 live assertion probes passed.

Verilator `--lint-only --timing -Wall` passed all 58 RTL/fixture profiles without
warnings or waivers. Twenty-three intentional faults were rejected, including
address wrapping/aliasing, uncommitted activation, unaccepted advancement,
invalid/quiesced execution, wrong loop counts, stalled-counter updates, lost
loop/candidate suspension state, nested loops, prolonged/incorrect events,
overwritten first errors, wrong clock/reset timing, and 1 ps output pulses.
Finite pulses were detected by the continuous waveform assertions.

All 31 existing synthesis/power tests passed with their tool stubs. Ordered source
discovery for the existing basic modules and the sequencer, explicit overrides,
regression dry-run preservation, and port-only checking also passed. A focused
memory fixture run from `/tmp` with seed 99 passed with all guards/probes retained.
Native VCS was unavailable and
reported `NOT_RUN`; no licensed synthesis or physical result is claimed.

Evidence is under `build/validation/context-sequencer-final`, with lint, mutation,
and additional checks in the neighboring `context-sequencer-*` directories.
Reports record source/helper/dependency hashes for each tested snapshot. Build
artifacts remain ignored by Git.
