# Tile power controller verification

This Python-only PyUVM suite checks
[`tile_power_controller.sv`](../../../rtl/building_blocks/tile_power_controller.sv)
against the [tile power controller specification](../../../../../specs/building-blocks/mosaic-tile-power-controller/README.md).
It simulates the actual RTL, including the common counters, DFFs and reset
synchronizers. No SystemVerilog verification checker, lint, formal, synthesis,
UPF simulation, CDC, RDC, DFT, physical implementation or power analysis is run.
Design Compiler synthesis is deferred.

```sh
make tile-power-controller-regression SIM=icarus PYTHON_BIN=.venv/bin/python
make tile-power-controller-regression  # VCS in the licensed server environment
make pyuvm SIM=icarus COCOTB_TOPLEVEL=tile_power_controller
```

The regression runs 80 representative profiles. It covers clock groups 1/4/8/16,
wake sources 1/4/8, baseline gating, OFF, and retained OFF, synchronous/asynchronous
controller reset, both event-wake modes, minimum and larger thresholds, different
clock masks and synchronizer depths. Six additional profiles exercise non-power-of-two
counts and one-cycle timing windows, including drain/retention timeouts of one.
The two default-geometry profiles retain the specified large timeouts. This is a
representative matrix rather than a Cartesian cross of every parameter.

Each profile executes directed cases plus 2,000 seeded random cycles. The runner
also executes 86 Python-driven illegal-parameter probes; a probe passes only if
elaboration rejects the parameters with the controller's named guard. Unrelated
compiler failures do not count as rejection. The simulator compiler is used by
these Python probes; no standalone RTL lint or synthesis target is invoked.

```sh
.venv/bin/python src/val/building_blocks/tile_power_controller/run_tile_power_controller_regression.py \
    --sim icarus --build-dir build/icarus/tile_power_controller/selected \
    --case default --case minimum_feature2_r1
```

Configure the Make target using `TILE_POWER_CONTROLLER_SEED`,
`TILE_POWER_CONTROLLER_RANDOM_CYCLES` (minimum 1,000), and
`TILE_POWER_CONTROLLER_REGRESSION_BUILD`. `TILE_POWER_CONTROLLER_JOBS` sets concurrent
simulations, defaulting to four for Icarus and one for VCS. The runner also accepts
`--compile-args`, `--sim-args` and `--sim-bin-dir`. Use the runner for parameterized
tests: it applies matching HDL overrides and Python widths. The direct `pyuvm`
command uses the RTL's default geometry.

## Structure and checks

- `transaction.py` and `config.py` define public ports, local encodings and widths.
- `sequences.py` drives directed timing boundaries, command/state combinations,
  fault scenarios and reproducible random controls.
- `driver.py` supplies real AON clock edges and a physical peer that follows actual
  power-switch, save and restore requests. Directed tests override that peer to
  delay or withhold acknowledgements and inject power-good faults.
- `monitor.py` observes ports and internal timer counts before, at and after clock
  edges, and with the clock held.
- `model.py` owns an independent state-transition table, per-phase timers, power
  input history, policy, wake and command ownership, and expected physical controls.
- `scoreboard.py` compares every public output and timer and checks safe clock,
  acceptance, isolation, write and retention combinations on every sample.
- `coverage.py` requires all reachable states, reset from each reachable state,
  supported error classes, every stall/group/source, exact idle qualification,
  configuration and command priority, state/command and state/wake-source crosses,
  every stall/group combination, test operation and fatal recovery.
- `agent.py`, `env.py` and `test_tile_power_controller.py` use the shared `mosaic_uvm`
  agent, sequencer, environment and coverage components.

Directed checks exercise exact idle entry, interrupted qualification, residency,
enabled and disabled wake sources, retained pending status across a mask update,
context mismatches, unknown policies/commands, legal and illegal commands from each
supported stable state, test entry and clock overrides, queued wake during shutdown,
and reset from every reachable phase. Acknowledgements are tested immediately, on
the final legal cycle, and missing through timeout. Advanced tests cover short
power-good glitches and assertion/deassertion on the final legal timeout cycle.
Power loss and X/Z controls are injected in powered phases. A short isolation phase
can safely reach POWERING_DOWN before synchronized power loss becomes visible;
that expected shutdown is checked as containment rather than a false power-loss
fault. Every physical output must remain known after reset.

Each build contains JUnit results, coverage JSON, simulator logs and parameter
snapshots. `summary.json` verifies all requested tests ran once, all mandatory goals
passed and source hashes remained unchanged. It records RTL, dependency, Python,
shared-helper and Makefile hashes. Coverage includes timer maxima and transition
edges. UPF corruption behavior and technology cell timing remain unverified.

## Local contract and timing

`tile_power_controller_pkg.sv` defines 4-bit state and error enums, 3-bit commands
(RUN=0, IDLE=1, RETENTION=2, OFF=3; 4..7 are invalid), and a 32-bit saturating stable
residency count. Numeric state/error values are declared explicitly in the package.
As requested for earlier modules, no external `mosaic-contracts` package or dependency
manifest is introduced. Geometry-dependent packed policy/control records stay local.

Command legality is explicit:

| Current stable state | RUN | IDLE | RETENTION | OFF |
|---|---|---|---|---|
| ACTIVE or STALLED | Legal | Legal | If supported | If supported |
| IDLE | Legal | Immediate completion | If supported | If supported |
| RETENTION | Legal | Rejected | Immediate completion | Rejected |
| OFF | Legal | Rejected | Rejected | Immediate completion |

Unsupported targets, wrong contexts and unknown commands are consumed and rejected.
Other commands are blocked during a transition, test mode or fatal error. A valid
configuration takes priority over a command. Configuration requires quiescent ACTIVE
or IDLE. It atomically installs the policy, wake mask and context; a rejected update
preserves the prior policy. A RUN targeting functional ACTIVE/STALLED completes
immediately in ACTIVE; subsequent activity can classify it as STALLED again.

New wake events use the currently installed mask. Previously captured events survive
a later mask change; masked pending bits cannot initiate wake. Starting RUN transfers
enabled pending ownership to the functional state machine; new simultaneous events
remain captured. With `WAKE_ON_EVENT=0`, status still captures enabled sources, and
explicit RUN is required. Shutdown completes before a queued event starts power-up.

State decisions and physical controls update on AON edges. Only reset can override
physical controls asynchronously. Unknown reset is treated as asserted. With
`ASYNC_RESET=1`, the controller reset asserts asynchronously and releases through
two common synchronizer stages. Power good always traverses the parameterized
AON synchronizer and then requires `POWER_STABLE_CYCLES` consecutive known samples.
Raw power good never directly gates a clock or isolation output.

A phase counter starts at zero on entry. A threshold N completes after N full AON
intervals in that phase. A known matching handshake on the Nth wait edge wins over
timeout; a missing or unknown handshake on that edge times out. Power timeout also
covers initial reset power qualification. Legal short timeouts can therefore fail
startup if they do not allow enough synchronization and qualification latency.

Automatic idle counts consecutive known, nonbusy, nonstalled, quiescent cycles in
functional operation, including the first cycle after a stall clears. IDLE asserts
after the Nth qualifying edge. Ordinary busy wakes after minimum residency; a RUN
or enabled event bypasses residency. Every accepted low-power command first enters
DRAINING. IDLE entry has no boundary isolation or supply change. Retention saves,
isolates, waits the isolation interval, then removes supply; OFF omits save.

Nonretained startup/wake enables the root clock after qualified power, requests
reset for `RESET_HOLD_CYCLES`, releases reset through the common two-stage AON reset
wrapper, waits until release is observed, then stabilizes for the wake interval.
Retention wake restores first and holds restore through stabilization. Isolation
remains asserted through restore/reset and wake; ACTIVE releases it and permits
traffic only if policy is valid. Arbitration, handshake and external physical delays
extend these cycle latencies; timeouts bound wait phases.

Fatal timeout or unexpected qualified-power loss enters ERROR, blocks traffic and
writes, asserts isolation, and holds the preceding power-switch direction. A powered
ERROR may keep safe clocks available; an unqualified or switch-off ERROR disables
them. Sticky first-error status survives later faults. Fatal errors require reset;
`i_error_clear` only clears recoverable errors while quiescent.

Test authorization requires a completed explicit RUN and stable qualified ACTIVE.
A test request elsewhere reports an illegal-test error and cannot bypass power-up
or isolation. Test clocks may then be enabled/disabled with traffic and writes
blocked. Command ready remains low in test mode, preventing low-power commands
from launching. Exit test mode before presenting a new RUN or power command.

## Tile wrapper responsibilities

The controller produces requests, not clocks or supply models. Connect its root
and group enables to approved implementations of the common `clock_gate`; use
technology-specific isolation, retention and level-shifter wrappers and UPF at the
domain boundaries. Test-clock authorization is already folded into the registered
clock request; a raw test input must not bypass that policy at a gate. No unused
internal clock gate is instantiated in the controller.
The internal reset wrapper releases in the AON domain; a tile with a different
functional clock relationship needs its own common reset synchronizer at that boundary.

Activity, quiescence, drain/retention acknowledgements, group requests and wake events
must obey their declared AON timing. External wake pulses need pulse-preserving
synchronization. Quiescence must account for new transfers and architectural writes
on the shutdown decision edge. Drain completion must include transport and pending
memory work; the wrapper must allow operations explicitly needed to finish drain
while new acceptance and ordinary writes are blocked. Nonretained tile context lost
in OFF must be reloaded before the wrapper admits execution. Policy registers in
this controller remain always-on across tile power transitions.

These tests validate the digital request protocol. They do not establish UPF coverage,
physical isolation/retention behavior, analog supply safety, clock-cell timing, or
power and energy benefit. Those checks and Design Compiler synthesis are later flows.
