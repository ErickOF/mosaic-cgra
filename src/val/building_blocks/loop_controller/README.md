# Nested loop controller RTL and PyUVM validation

[`loop_controller.sv`](../../../rtl/building_blocks/loop_controller.sv) implements
[the loop-controller specification](../../../../../specs/building-blocks/mosaic-loop-controller/README.md).
Level zero occupies the least-significant packed slice and advances fastest.
Configuration supplies one rectangular nest; every accepted iteration token
owns one point in its Cartesian product.

## Run

```sh
make setup
make loop-controller-regression                    # VCS and license required
make loop-controller-regression SIM=icarus
make pyuvm SIM=icarus COCOTB_TOPLEVEL=loop_controller
```

The decorated test is `test_loop_controller.LoopControllerTest`. Test, environment,
agent, sequencer, driver, passive monitor, mathematical reference, scoreboard and
coverage components use the shared `mosaic_uvm` infrastructure. The monitor checks
actual interface values before the clock edge, at the edge, after settling and
during a held interval. Every public output is compared, including invalid payloads,
sticky errors, epochs, status and event pulses.

The **53-profile** regression includes:

- The exact default parameter configuration.
- Depths 1, 2, 3, 4 and 8, indices 16/32/64 bits and trips 16/32 bits.
- Both protection and reset choices for each depth/width geometry.
- Every combination of bounded-mode, suspension, abort, protection and reset at
  depth three, including a two-bit initiation-interval field.
- Odd event counts, small context/run identifiers and reduced linear widths for
  observable product overflow. Other geometry profiles use an eight-bit interval
  field to exercise intervals 1, 2, 3, 8 and 255.

Each profile runs **2000 random cycles plus directed scenarios**. The runner also
executes **59 strict parameter elaboration guards** for zero/negative/unknown
widths, invalid feature switches, epoch width one and packed-size overflow.
Configure `LOOP_CONTROLLER_SEED`, `LOOP_CONTROLLER_RANDOM_CYCLES` (minimum 1000)
and `LOOP_CONTROLLER_REGRESSION_BUILD`. `LOOP_CONTROLLER_JOBS` sets profile
parallelism from 1 to 32, defaulting to four Icarus workers and one VCS worker.
Each profile has a separate build directory; seeds advance by their original
profile index, including when selecting cases. For one case:

```sh
.venv/bin/python src/val/building_blocks/loop_controller/run_loop_controller_regression.py \
  --sim icarus --build-dir build/loop-selected --case default
```

The runner records source/dependency/verification SHA-256 hashes, parameters,
individual logs, JUnit identity and mandatory coverage goals in `summary.json`.
A profile passes only after its decorated PyUVM test and coverage pass with
matching parameters, seed and random-cycle count, Python selection checks enabled
and HDL assertions disabled. The runner checks the hashes again before accepting
the campaign to detect source edits during simulation. Missing
simulators/licenses remain `NOT_RUN`; no old result can satisfy a new invocation.

Direct runs with custom parameters need matching compiler overrides and
`LOOP_CONTROLLER_<PARAMETER>` environment variables, plus a fresh build directory.
The runner sets these automatically and tracks parameters as compile dependencies.
Private fault injection defaults on. The default direct run and regression use
Python checks only. The regression forces `LOOP_CONTROLLER_HDL_ASSERTIONS=0`, and
the test verifies that the optional HDL checker is absent. The existing native
HDL checker remains available for a separate direct RTL invocation:

```sh
LOOP_CONTROLLER_HDL_ASSERTIONS=1 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=loop_controller

LOOP_CONTROLLER_CHECK_INTERNALS=0 LOOP_CONTROLLER_HDL_ASSERTIONS=0 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=loop_controller
```

Public-port mode omits hierarchical fault injection and common-block selection
checks. Disabled checks report `NOT_RUN`. Clock opportunities are nominally 10 ns
with 1 ps observation ticks.
This suite checks zero-delay RTL, not SDF timing.

## Reuse and local encodings

Configuration and execution records reuse `event_barrier_state`, an existing
width-generic DFF/parity helper. That helper reuses `common/dff`, `basic/parity`
and `common/operand_isolation`. The captured candidate uses the same protected
helper; diagnostic flops reuse DFFs directly. The common `decoder` selects pause,
resume and abort, rejecting reserved or unknown opcodes. The common
`priority_encoder` selects the innermost nonfinal level. A vector `write_gate`
authorizes that level and its lower wrapping levels only on token transfer;
higher levels and the final coordinate hold. No existing RTL primitive is modified.

Packed records retain atomic configuration, carry, pacing and ownership updates,
including their parity. Their parameterized structs stay in the module. Counters
remain fields in that protected record so the data and parity share one atomic
update; separate counter instances would also require coordinated protection.
Optional parity hardware disappears when protection is disabled.

[`loop_controller_pkg.sv`](../../../rtl/building_blocks/loop_controller_pkg.sv)
contains repository-local enums. No external `mosaic-contracts` package or
runtime dependency manifest is needed. Integration with another encoding must
map these values explicitly. Mode, comparison and control widths are read-only
localparams derived from the package.

| Field | Local encoding |
|---|---|
| Mode (2 bits) | `LOOP_COUNTED=0`, `LOOP_BOUNDED=1` |
| Comparison (3 bits) | `LT=0`, `LE=1`, `GT=2`, `GE=3` |
| Control (2 bits) | `PAUSE=0`, `RESUME=1`, `ABORT=2` |
| Completion (2 bits) | `COMPLETE=0`, `ABORTED=1`, `FLUSHED=2` |
| Error (5 bits) | Enum values 0–15 in declaration order in the package |

Unused enum encodings are illegal. `FLUSHED` is reserved for integration: the
default coordinated-flush profile suppresses the run's completion record.
`transaction.PORTS`, `config.DEFAULTS` and `config.aliases` describe port directions,
widths and derivations in machine-readable Python form. Candidate vectors include
all active and inactive fields; unknown bits are rejected rather than sanitized.

## Configuration and execution

Configuration capture takes one edge; validation and atomic installation take the
next edge. `o_config_validating` covers that interval. A failed candidate preserves
the old configuration and epoch. A successful candidate increments the epoch.
Start/control handshakes take priority over configuration. An idle start is consumed
even without configuration so that it can return the required start rejection;
context mismatches are likewise consumed and rejected. A blocked start during a
live run cannot block runtime control.

Checks use signed arithmetic widened by index width plus trip width plus two.
Counted loops check the last index and classify post as unused. Bounded loops
check initial/last/post comparisons in the widened domain, including post values
outside the original signed index range. No division or remainder is used.
A zero trip annihilates the product before overflow checking, while all other
active levels still undergo legality checks. Inactive slices must be known zero.
A nonzero product exceeding the linear field is rejected.

An accepted start presents its first token in the following cycle. Each transfer
advances the first nonfinal coordinate, wraps lower final levels and increments
the accepted count atomically. At II=1, transfers can occur on consecutive edges;
otherwise pacing reloads to II−1, then decrements once per issuing cycle. Pacing
holds after a pause/abort transition and during suspension/completion holding.
The configuration candidate and its bound arithmetic remain unchanged during runs.
Live range/arithmetic invariants are checked separately from configuration legality.

Pause/abort preserve any already presented token until it transfers. When no
presented token remains, quiesce request asserts and the controller waits for a
known-high external safe point. Resume continues with the next unissued point.
Pause coinciding with the final transfer yields natural completion; an accepted
abort on that edge yields aborted completion. Abort can supersede a pending pause,
including the edge that reaches its safe point.

Natural completion is created one edge after the completion-pending state observes
external quiescence. Zero-trip completion is created directly at start. Records
hold until accepted, including when completion-event enable is zero. A new run
cannot start before the old record retires. Completion does not invalidate the
installed configuration. Coordinated flush removes configuration/run/record
ownership and increments epoch; reset sets epoch to zero. Fatal status survives
flush and clears only on reset.

Unknown reset/flush clamp interfaces and freeze progression; unknown readiness
cannot transfer a token/record or satisfy a safe point. Unknown request fields are
consumed and rejected when their channel is otherwise ready. Recoverable errors
are first-error sticky and clear while idle or on flush. Fatal state/configuration
corruption immediately clamps issue and latches fatal status on the next edge.
Parity detects odd-bit corruption; it does not correct errors or cover arbitrary
even-bit changes. Diagnostic error/fatal flops are outside the parity banks.
Asynchronous reset assertion is supported; reset release synchronization belongs
to the integrating clock/reset domain.

## Verification scope and qualification

The scoreboard lazily enumerates complete Cartesian products with Python ranges;
it does not copy RTL carry logic. Integer arithmetic independently checks candidate
bounds/products. Directed traffic covers each depth, all four comparisons by level,
both step signs, mixed modes, zero trips at every level, one trips, signed endpoints,
maximum representable totals, overflow and inactive-field rejection, repeated runs,
intervals/backpressure, owner errors, stop/resume at every coordinate of small full
nests, stop during pacing, delayed safe points, event enable choices, completion
holding, reset/flush in live/pending/suspended states, X/Z controls and injected
candidate/installed-configuration/execution corruption. Random cycles mix starts, stalls, controls,
safe-point delays, flush and reset. The Python model checks held tokens and records,
count/pacing limits, transfer events and safe-point transitions at every observed
phase. Additional Python checks compare the decoded command, selected advancement
level and one-hot selection with the mathematical coordinate. They also verify
the level-update mask is zero during stalls, pacing, suspension, completion,
reset, flush and fatal containment. Mandatory coverage includes every configured
depth crossed with every advancement level, reserved/unknown command decoding,
and held level-update masks.

Reachability depends on parameters: a depth-one design has no inactive slice or
outer carry; a power-of-two event count has no unused binary event ID; a narrow II
field cannot encode 8/255; counted-only and disabled control profiles cannot exercise
the removed features. A trip maximum exceeding the linear field cannot be a legal
single-level total. Coverage goals account for these structural restrictions rather
than reporting unreachable bins as covered. The mandatory bins are listed explicitly
in `coverage.py`; this campaign does not claim every specification cross or formal
proof obligation has been closed.

This campaign runs Python/PyUVM validation and Python-driven parameter-guard probes
only. With the default random-cycle count, the 53 profiles exercise 106000 seeded
random cycles in addition to the directed scenarios. Lint, formal and synthesis
are outside this campaign. Synthesis is deferred to Design Compiler. The bound
checker and live arithmetic invariants still require area and timing
characterization before physical integration.

Formal proofs, VCS execution, commercial lint/CDC/RDC/DFT/low-power checks,
technology synthesis, physical timing and PrimePower qualification require external
tools and remain **NOT_RUN** in local evidence. These tests do not constitute the
specification's complete physical release qualification.
