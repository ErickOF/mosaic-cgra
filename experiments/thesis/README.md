# Thesis experiments

Reproducible campaign for
[`doc/tesis-pruebas-y-resultados.md`](../../doc/tesis-pruebas-y-resultados.md).
The first acceptance levels are real kernels on the **Configurable 4×4 flat
grid**, then selective native power transitions with a portable supply model.
The inventory retains the prerequisites of every E1–E10 quantitative comparison.
A planned experiment is not a measured result.

| Experiment | Implemented scope / pending evidence |
| --- | --- |
| E0 | H/M AXPY, full and partial vectors, strided copy, SRAM guards and backpressure |
| D0 | Two domains, copy/AXPY, always-on/offline scheduling, pending-work rejection and drain |
| E1 | Versioned comparison recipe; independent activity profiles and gate evidence pending |
| E2 | Versioned ablation recipe; independent mechanism controls and gate validation pending |
| E3 | Full/partial vector functional runs; energy per output pending |
| E4 | Measured addresses/bank access patterns with identical copy volume; energy pending |
| E5 | Executed short/detour routes for the same work; energy pending |
| E6 | Body counter update control checked against actual retirements; shell/SRAM counters stay enabled |
| E7 | Three verified repetitions with compute-context reload or residency; phase energy pending |
| E8 | Mapping/selection prerequisites and deterministic composition-ranking helper; calibrated mapper pending |
| E9 | Frozen reserved inputs and full-coverage selection rule; dot/FIR schedules and characterization pending |
| E10 | External comparison recipe; versioned external implementation and comparable conditions pending |

Use the existing Python 3.12 environment (`make setup`). Portable execution needs
Icarus, cocotb and PyUVM; it does not run synthesis, lint or formal checks:

```sh
make thesis-test
make thesis-plan
make thesis-run SIM=icarus
make thesis-report

# Restrict diagnosis or select other functional comparisons.
make thesis-run SIM=icarus THESIS_ARGS='--experiment E0 --variant M --case axpy_9'
make thesis-run SIM=icarus THESIS_ARGS='--experiment D0'
make thesis-run SIM=icarus THESIS_ARGS='--experiment E4 --experiment E5 --experiment E6 --experiment E7'
```

`THESIS_BUILD` defaults to `build/thesis`. `thesis-plan` writes hardware
descriptors, fixed numerical inputs and E0–E10 requirements to `plan.json`; it
does not claim elaboration or execution. `campaign.toml` versions the matrix,
seed and characterization/reserved sizes before tuning. Dot/FIR have independent
numerical references; their native flat-grid schedules remain pending and cannot
substantiate a complete E9 characterization campaign.

## Hardware and packet contract

H contains 14 BCT and two MST; M contains ten BCT, four VCT and two MST. Memory is
eight banks × 32 words × eight bytes = 2048 bytes. MSTs occupy `(0, 1)` and
`(3, 2)`. Six candidates place two, four or six VCT by ascending/descending minimum
Manhattan distance to the MSTs, breaking ties by row then column. All remaining
positions are BCT.

Unlike the preliminary test, BCT payloads are explicitly **128 bits** so a packed
vector can traverse a BCT pass context. VCT uses `FU_PROFILE=2`, four eight-bit
lanes, 32-bit accumulators and the released `BYPASS_PROFILE=2` external accumulator
operand graph. Actual parameters and widths are recorded in `manifest.json`;
H and M use equal memory and link geometry.

The normal grid transports opaque metadata. An experiment-only wrapper adds
public per-packet metadata adapters, handshake observation and output stalls.
The test supplies the receiver's native metadata from its validated context or
MST descriptor, explicitly bridging context versions, vector format/masks and
MST identity/keep fields. It never changes payload data. Data narrowing checks
remain enabled; metadata width checks apply to the adapted record. No
hierarchical forces are used. Adapters and RTL are included in the export's
identity and must be included in any eventual gate-level comparison.
An experimental memory-request gate applies deterministic wait cycles on both
sides of ready/valid during backpressure cases, including local-copy traffic.

H executes signed scalar AXPY with the BCT MAC. M routes packed x through
MST → BCT pass → VCT and y through the other MST → VCT, then stores VCT MAC
results through the first MST. Native contexts are loaded, CRC-validated,
activated and started. Inputs are signed eight-bit; y/results are signed 32-bit
with wrap semantics. Full vectors and a one-lane tail are separate cases.
Copy uses a real MST local-copy descriptor with explicit strides. The complete
SRAM image, including sentinels outside the output, is compared independently.

The initial executor processes one packet group at a time with explicit route
updates. It proves the kernel and packet contract and includes orchestration
cycles; it is not an optimized mapper or a peak-throughput demonstration.
AXPY's useful/masked lane counts describe the scheduled masks and verified useful
work. E6 separately checks observed native retirement counters. E4's single-copy
schedule does not claim concurrent contention: zero observed conflicts remain
zero even when accesses concentrate in one bank.

E7 reloads the compute-context images while keeping the MST permissions and
service contexts resident. Selected images remain protected after completion;
the loader selects another validated slot before writing, then selects the new
image before rewriting the remaining slots. Both variants execute identical
per-packet route programming. All three repetitions are read back and verified,
and configuration segments/reuse counts remain separate from kernel segments.

## Domains and scheduler

Only D0 exports enable native `SUPPORT_POWER_OFF` for BCT/VCT. Normal editor
descriptors keep their existing behavior. `domains.json` records two domains:

* Available: configuration/wakeup shells, switches, SRAM, memory bridges, both
  MSTs and root control.
* Switchable: BCT/VCT private bodies, with native request, power-enable,
  isolation, power-good and isolation-acknowledgement boundaries.

The deterministic **offline** phase scheduler is compared with `always_on` on
the same hardware, inputs and placement. Copy completes with compute OFF. AXPY
sleeps, wakes and computes from external operands. An OFF request with accepted,
pending work must be rejected without losing data. Native OFF clears private
state; no retained RF/accumulator values are assumed. Configuration/wakeup stays
available. Supply/isolation acknowledgements are delayed three reference cycles.

This is **RTL simulation with a supply model**. It is not UPF simulation,
transistor power removal or measured energy savings. Retention and UPF-aware
integration remain separate pending evidence; `power_intent` stays `NOT_RUN`.

## Evidence and quantitative prerequisites

Each run retains its immutable bundle, inputs/schedule, configuration responses,
MST descriptors, expected/observed output, SRAM hashes, transfers, routes, power
transitions, simulation XML/log, phase windows and `summary.json`. Git revision,
verification-source hashes and simulator version identify dirty-worktree runs.
`thesis-report` regenerates CSV and Markdown from summaries, retaining failed and
blocked rows. Missing metrics stay `null`/empty, never zero.
Extraction rechecks native MST identity/format/keep records against submitted
descriptors, compute context/version tags across adapters, and complete ordered
payloads along the mapped edges. A metadata adapter cannot conceal a malformed
producer record in the accepted report.
Domain reports also regenerate inspectable SVG timelines from the transition
trace. The plan includes two fixed-size grouping descriptors, resource/proximity
and simultaneous dependencies; their separate group-control/energy evaluation
remains `NOT_RUN` and does not inherit the aggregate D0 result.

Kernel windows start after initial provisioning/configuration and end after the
last store completion and drain. Configuration has a separate window. Dynamic
route/control overhead is included in execution; host readback and simulator
wall time are excluded. Reset/configuration are not silently called kernel time.

`results.py` consumes the existing `flows/power/summarize.py` schema. It requires
finite SI quantities, useful outputs, nonzero annotation and matching phase,
SAIF and power-summary durations. Relative results require matching inputs,
numerical contracts and operating point. M1* selection requires all six candidates
and complete characterization, then applies equal-weight mean energy ratios,
time ratios, VCT count and near-placement tie breaks.

On the licensed server, reuse `make synth`, `gate-saif`, `power` and
`power-report` with the exported source list and matching cell models,
netlist/SDF/SPEF, technology, corner, voltage and timing constraints. The current
global `flows/vcs/saif.tcl` includes reset/initialization; it does not substantiate
kernel-only energy. Phase-matched gate captures, timing and annotation evidence
are required. No joules are inferred from RTL events.

After a passing gate rerun, fill `gate-evidence.example.json` with the matching
run/build/scenario IDs, operating point, timing result and hashes of the raw
artifacts. Keep the gate test's `functional.json`; its phase markers, exact
outputs and memory guards are checked again. Attach each measurement explicitly:

```sh
.venv/bin/python experiments/thesis/attach_power.py \
  --summary build/thesis/runs/E0/SELECTED_RUN/summary.json \
  --evidence /server/case/kernel-evidence.json --phase kernel
make thesis-report
```

Use `--phase configuration` for a separate configuration capture. The importer
rejects changed files, another workload/netlist, missing timing, zero annotation,
unmatched durations and inconsistent operating points. Repeated E7 executions
publish separate phase segments rather than claiming one continuous SAIF window.

E1/E2 still need independent activity-mechanism controls; native operand/write
suppression is structural. E8 needs calibrated costs and a frozen mapping search.
E9 needs complete dot/FIR execution and characterization energy before selection.
E10 needs a versioned REVAMP/HyCUBE artifact with comparable conditions. Pending
experiment invocations write `BLOCKED` rows with their requirements. The separate
`MastersDegreeThesis` sources were not found locally; the implementation brief
above is the available scope source.
