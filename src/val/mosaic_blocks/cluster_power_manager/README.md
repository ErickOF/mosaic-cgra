# Cluster power manager PyUVM validation

This implementation follows the [cluster power manager specification](../../../../../specs/mosaic-blocks/mosaic-cluster-power-manager/README.md)
for the Clocked baseline and optional Protected Clocked profile. Synthesis is
reserved for Design Compiler later. This suite runs Python reference-model tests
and PyUVM-driven RTL simulation; it does not run HDL assertion, lint, formal,
synthesis, CDC, UPF, STA or physical power signoff.

```sh
make cluster-power-manager-generate
make pyuvm SIM=icarus COCOTB_TOPLEVEL=cluster_power_manager
make cluster-power-manager-regression SIM=icarus
# Run on the licensed server with the same Python suite:
make cluster-power-manager-regression SIM=vcs
```

The campaign writes JUnit, per-profile checked coverage, generated profiles,
Python model-test results, named invalid-parameter elaboration logs and a final
`build/<sim>/cluster_power_manager/regression/summary.json`. The summary records
source and verification hashes and fails if those sources change during the run.
The default random duration is 1,000 iterations per profile. Override
`CLUSTER_POWER_MANAGER_SEED`, `CLUSTER_POWER_MANAGER_RANDOM_CYCLES`,
`CLUSTER_POWER_MANAGER_REGRESSION_BUILD` or pass `--case <name>` through
`CLUSTER_POWER_MANAGER_REGRESSION_ARGS`. `ICARUS_BIN_DIR`/`VCS_BIN_DIR` select the
simulator installation. No synthesis target is a prerequisite. The direct `pyuvm` target exports short
simulation-only drain/tile/power/clock/reload timeout overrides (256/128 cycles)
to both RTL compilation and Python. Production RTL defaults remain unchanged;
the campaign publishes its explicit per-profile timer values.

## Actual RTL composition and integration boundary

The manager instantiates one released `tile_power_controller` per tile region,
common root/group clock gates, functional reset synchronizers and separate
valid/ready isolation clamps. Counters, decoder, DFF, FIFO, event-barrier queue,
performance counters and the existing tile-shell parity/SECDED storage are reused.
The AON clock and functional source clock run independently in the testbench. A
passive monitor measures the actual root/group clock pulses and checks that no
high pulse is truncated, including shutdown, reset and fault containment.

Cluster workload, scratchpad/memory/local-network drain, array authorization,
package/endpoint revalidation and physical acknowledgements are independent Python
peers. They are not a full `cluster.sv`/array RTL integration or UPF simulation.
Integrators must connect the corresponding real protocol obligations and physical
status signals. The global NoC transit router remains outside the stopped domain;
only its local endpoints are controlled here. The behavioral common cells require
PDK mapping and physical checks before implementation signoff.

## Clocked behavior

The balanced profile contains 16 tile regions, eight groups, 16 wake sources and
one always-on main supply. ACTIVE and STALLED preserve all requested/busy tile
clocks. STALLED never qualifies as idle. IDLE_ON becomes CLOCK_GATED after exactly
32 consecutive qualifying cycles by default. Any blocker clears qualification.

Gate entry first holds new execution and injection while existing operations may
retire. It waits for every cluster, tile, scratchpad, memory, configuration,
event/counter/debug and local/global endpoint drain proof. Only then does it
suppress writes, disable endpoints, collect every tile IDLE terminal, stop the
root/groups and qualify clock-stopped acknowledgement. CLOCK_GATED keeps the
supply on, reset released and physical isolation inactive. Disabled endpoints
still clamp handshake signals.

AON wake capture authenticates the entire identity, masks each source and records
its attribution. Ordinary wake obeys minimum residency; runtime wake, authorized
urgent RUN, test and queued cancellation can bypass hysteresis, never safety.
Wake starts the real clocks, qualifies source/voltage/clock acknowledgements,
configures and runs all tile controllers, obtains fresh package/endpoint proof,
waits for deisolation/endpoint acknowledgements and stabilization, and only then
releases authorized execution. Array execution hold remains authoritative.

Reset and authorized destructive RECOVER assert safe clamps and resets, qualify
power/switch acknowledgement before starting clocks, release reset groups in
order through functional-clock synchronizers and require reload/revalidation.
Recovery does not silently clear the first error. `CLEAR_ERROR` works only after
fatal containment has been resolved. Power loss, clock loss, voltage fault,
thermal emergency, unknown live control and protected-state failures enter the
registered ERROR row. Later acknowledgements cannot release it.

Only a drain timeout before physical effects can roll back when
`SUPPORT_ROLLBACK=1`. Missing acknowledgements after that point contain the domain.
Cancel in reversible DRAIN restores the prior state; cancel after root stop
completes the original gate operation and queues a wake. Accepted tile commands
remain valid until their handshake and terminal; cancellation cannot retract them.

Test, scan and MBIST entry require system/array authority, explicit test authority
and array execution hold. TEST is a separate isolated, reset-asserted output row;
its clock override operates only with qualified power and a valid clock source.
Test exit performs reset/reload/revalidation before functional release.

## Public ABI and ownership

The package and [generated profile](../../../gen/cluster_power_manager/generated/profile.json)
provide exact field offsets and enum encodings. This is the repository-local ABI;
no missing `mosaic-contracts` encodings are assumed. Parameter-dependent state and
control records remain local to their RTL modules.

| Interface | Contract |
| --- | --- |
| Command/response | Synchronous AON ready/valid; one command outstanding; exactly one immutable terminal per accepted command |
| Identity | Cluster, owner, kernel, package, allocation generation and execution epoch, checked together |
| Policy update | Atomic, quiet stable state only; malformed/unknown updates leave the old policy intact |
| Revalidation | Identity + external boot generation + nonwrapping serial + command tag; all four validity bits required |
| Physical status | Independent stable level inputs, optionally synchronized; not a bundled bus CDC protocol |
| Wake | AON level capture, full identity and source mask; held sources can generate repeated wake observations |
| Events | Capture-time identity/phase/timestamp, delivery-order nonwrapping sequence; immutable while stalled |
| Diagnostics | Bounded telemetry FIFO and sticky overflow; separate reserved terminal queue and first-fatal mailbox |

Command flags bit 0 permits urgent minimum-residency bypass. Bit 2 authorizes
allocated destructive recovery, which also requires array execution hold. Low
flag bits require system privilege; reserved high bits are rejected. Point zero
and state policy zero are the only implemented selections. No frontend field can
assign ownership; the array supplies the authoritative allocation.

A quiet binding change under array execution hold invalidates state and pending
wake identity. A subsequent RUN obtains fresh validation for the new binding.
`i_system_reset_generation` must change after coordinated AON/global reset and
must not be reused while old peer replies remain possible. Reset cancels local
transport obligations only when the system has explicitly reconciled old work;
it cannot prove that remote work disappeared.

Counters 0–22 count state residency cycles. Indices 23–31 count transitions, wakes,
timeouts, rollbacks, command acceptance/rejection, bad wake observations, fatal
cycles and corrected control cycles. Snapshots are coherent AON samples; counters
saturate. Per-source wake and per-group stopped-cycle counters are 32 bits.
Disabling counters ties their interface outputs low. Clock counts demonstrate
functional activity suppression; they do not prove watts, joules or net savings.

## Coverage and limits

The UVM structure separates transactions, configuration, driver, passive monitor,
agent, environment, sequences, independent obligation/qualification models,
scoreboard and mandatory coverage goals. The scoreboard checks real handshakes,
one terminal per command, held records, per-tile command completion, full drain
before root shutdown, identity-qualified validation before acceptance, clamp
mapping, fault rows and ordered event delivery. Python model tests include
negative cases proving the checker rejects mismatched/duplicate terminals,
forged/reused validation identities, incomplete drain and premature qualification.

Directed sequences cover all tile/endpoint drain bits and stall reasons,
identity/authentication/policy rejection, exact automatic threshold, wake masks
and attribution, minimum residency, mandatory wake, response/event backpressure,
telemetry overflow, cancellation, rollback and irreversible timeout, physical
fault/recovery, allocation rebind, stale validation, test modes, unknown values
and real protected-state fault injection. Seeded traffic interleaves commands,
activity, stall classification, wake and bounded event backpressure. Profiles
exercise minimum, balanced and maximum region/group dimensions, shallow queues,
synchronous/deeper status synchronization, asynchronous reset, disabled automatic
policy, disabled counters/rollback, parity and SECDED.

Retention, OFF, DVFS, SRAM sleep modes, trace and asynchronous array commands are
explicitly unsupported. Their parameters fail a named elaboration guard and
commands are rejected without changing the physical state. Break-even policy
applies to those advanced transitions; this clocked baseline neither invents
energy tables nor claims advanced or physical signoff. Physical corner sweeps,
CDC/RDC proofs, all-phase exhaustive fault/reset closure and real cluster/array
vertical integration remain future signoff work.

## Recorded local evidence

The Icarus/Python 3.12 campaign with seed 20261028 passed all ten profiles, all
110 named invalid-parameter guards and 15 Python model tests. It observed 120,514
AON cycles across 10,000 seeded random iterations. Every profile satisfied its
mandatory coverage goals and the complete source/verification hash comparison
passed. The separate direct Makefile `pyuvm` entry point passed as well.

These results are recorded in
`build/icarus/cluster_power_manager/regression/summary.json`; per-profile JUnit,
coverage, generated tables and simulator logs reside beside it. This evidence
applies to the Clocked/Protected implementations and the documented Python peers.
VCS requires the licensed server; VCS and physical signoff were not run locally.
