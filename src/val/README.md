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
