# Async FIFO PyUVM validation

This suite validates [async_fifo.sv](../../../rtl/basic/async_fifo.sv) against the
[MOSAIC async FIFO specification](../../../../../specs/basic/mosaic-async-fifo/README.md).
It uses the shared [PyUVM component structure](../../README.md): configuration,
transactions, sequence, sequencer, driver, monitor, agent, independent model,
scoreboard, coverage collector, environment, and decorated test.

## Running

From `mosaic-cgra`:

```sh
make setup
make async-fifo-regression                 # VCS on the licensed server
make async-fifo-regression SIM=icarus      # Native four-state local simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=async_fifo  # Default nominal profile
```

The Makefile automatically includes `common/counter.sv`, `common/dff.sv`, and
`basic/async_fifo.sv` in that order when the selected top is `async_fifo`.
An explicit `VERILOG_SOURCES` overrides this list.

The campaign defaults to seed `20261012` and 2000 randomized clock events per
profile. At least 1000 are required. These are event counts; each event can toggle
one clock or both clocks. Every profile also runs directed sequences. Its seed
is the base seed plus its full matrix index, including in focused campaigns.

```sh
make async-fifo-regression SIM=icarus ASYNC_FIFO_SEED=1234 \
  ASYNC_FIFO_RANDOM_CYCLES=3000 \
  ASYNC_FIFO_REGRESSION_BUILD="$(pwd)/build/async-custom"

.venv/bin/python src/val/basic/async_fifo/run_async_fifo_regression.py \
  --sim icarus --build-dir build/async-focused --case minimum --case stages4
```

Repeat `--case` to select profiles. Focused campaigns retain parameter rejection
checks and assertion probes, and report `scope=selected_profiles` rather than a
complete matrix. `--rtl /absolute/path/async_fifo.sv` selects another compatible
implementation; the counter and DFF dependencies remain the repository versions.
`VCS_BIN_DIR`, `ICARUS_BIN_DIR`, `COMPILE_ARGS`, and `SIM_ARGS` retain their existing
Makefile meanings. The standalone runner works from another working directory.

## Parameter matrix

| Profile | Data width | Depth | Synchronizer stages | Almost full | Almost empty |
| --- | ---: | ---: | ---: | ---: | ---: |
| `minimum` | 1 | 2 | 2 | 1 | 0 |
| `depth4` | 8 | 4 | 2 | 3 | 1 |
| `nominal` | 32 | 8 | 2 | 7 | 1 |
| `wide_deep` | 128 | 32 | 2 | 31 | 1 |
| `stages3` | 32 | 8 | 3 | 7 | 1 |
| `stages4` | 32 | 8 | 4 | 7 | 1 |
| `late_full_zero_empty` | 32 | 8 | 3 | 8 | 0 |
| `early_full_high_empty` | 32 | 8 | 4 | 1 | 7 |
| `narrow_deep` | 1 | 32 | 4 | 16 | 16 |
| `wide_minimum` | 128 | 2 | 3 | 2 | 0 |

The specification does not define a release manifest or maximum released width,
depth, or synchronizer stage count. This representative matrix establishes
functional evidence for the listed profiles. It does not establish release
limits or claim every possible parameter combination has been tested.

## Independent checking

The record model is a Python queue. Only a real write-clock handshake enqueues a
four-state word, and only a real read-clock handshake dequeues it. Coincident
edges consume the previously queued head before accepting a new write. The
scoreboard compares every visible head and consumed record and rejects overflow,
underflow, duplication, loss, corruption, and reordering.

Unbounded accepted-transfer counts predict local pointers independently of the
RTL counters. A destination-edge history records the remote count and domain-up
value that existed before either clock updates at coincident edges. Looking back
by `SYNC_STAGES` predicts conservative registered status, occupancy, and nominal
digital visibility. This checks the CDC boundary delay rather than treating the
FIFO as an instantaneous shared occupancy counter.

The producer retains each offered record until acceptance. The monitor samples
after nonclock inputs settle, before applying clock changes, and again 1 ps after
the clock event. It continuously watches registered outputs and local pointers
to reject activity outside a local rising edge or local reset assertion. The
scoreboard checks reset-safe values before either clock changes, so a reset that
waits for a clock edge cannot pass.

Internal checks require visibility of the portable RTL's pointer registers,
memory array, and four synchronizer arrays. They check exact stage history, Gray
conversion and one-bit transitions, handshakes as the only pointer enables, and
storage updates only at accepted write addresses. Written memory contents must
survive reset; canceled contents lose their transactional meaning.

## Requirement mapping

| Requirement | Stimulus and active checks |
| --- | --- |
| Clock relationships | Every profile uses write faster, read faster, equal nominal periods with phase drift, a 7:11 period ratio, and seeded random periods. Each relationship reaches empty and full. |
| Conservative boundaries | Full rejects writes until freed space crosses to the writer; empty delays validity until the pointer crossing and registered capture complete. Exact local flags/levels are checked at every event. |
| Throughput and wrapping | Continuous source/consumer runs, full-rate depth-length bursts, coincident accepted push/pop, and at least eight address-ring wraps in each domain. Both local/remote wrap phase crosses must close. |
| Storage coverage | Rotate the read pointer, fill and drain at every rotation, and require every write/read address pair. |
| Thresholds and stalls | Check threshold equations, entry/exit, prolonged full source stall, random stalls, and stalled reads at every visible nonzero occupancy. |
| Output stability | Compare the registered head during every stall; reject data changes without qualified read capture or reset, including unclocked waveform activity. |
| Coordinated reset | Cancel pending records at empty, partial, full, and valid stalled output; verify asynchronous clearing and successful fresh traffic. |
| Reset skew/recovery | Release either side first while its peer is stopped/reset; inject either one-sided reset, require remote initialization to drop, and prohibit restart until both sides reset. |
| Clock stops | Fill with the reader stopped, drain visible records with the writer stopped, preserve stopped-domain state, and resume fair-clock operation. |
| Four-state payloads | Accept all-X/all-Z and known records; compare bits exactly, preserve every unknown bit position, and require known controls and final synchronizer stages. |
| Synchronizer faults | Force X/Z into each first stage between edges, restore it before clock restart, and require unchanged functional behavior. Separate final-stage X/Z probes must trigger live assertions. |

The address, phase, threshold, boundary, reset, stall, stage, and payload goals
are mandatory. Coverage JSON contains actual bins and counts. Initialized source
backpressure occurs at local level `DEPTH`; source-stall bins for other initialized
levels are unreachable under `ready = init_done && !full`. Reads with valid data
cannot stall at level zero. Push while full and pop while empty are prohibited
states, checked as assertions rather than requested coverage hits.

Reset destroys the current epoch. Pending records and transfers during propagation
of an unexpected one-sided reset are canceled. The scoreboard resumes obligations
only after observing both resets asserted. Endpoint traffic resumes after the
corresponding initialization checks. The final conservation check requires:

```text
accepted writes = consumed reads + canceled writes
pending records = 0
```

The finite progress bounds assume both clocks run and the consumer is ready.
They do not impose a timeout while a domain is deliberately stopped. Reset
stimulus uses safe inactive clock phases; a system must still supply separate,
released reset synchronizers as required by the specification.

## Direct configuration and scope

| Environment variable | Default | Meaning |
| --- | ---: | --- |
| `ASYNC_FIFO_DATA_WIDTH` | 32 | Expected `DATA_WIDTH` |
| `ASYNC_FIFO_DEPTH` | 8 | Expected power-of-two `DEPTH` |
| `ASYNC_FIFO_SYNC_STAGES` | 2 | Expected `SYNC_STAGES` |
| `ASYNC_FIFO_ALMOST_FULL_LEVEL` | Depth minus 1 | Expected write threshold |
| `ASYNC_FIFO_ALMOST_EMPTY_LEVEL` | 1 | Expected read threshold |
| `ASYNC_FIFO_SEED` | 20261012 | Seeded stimulus |
| `ASYNC_FIFO_RANDOM_CYCLES` | 2000 | Random independent-clock events |
| `ASYNC_FIFO_COVERAGE_FILE` | Beside JUnit | Mandatory coverage JSON |
| `ASYNC_FIFO_CHECK_INTERNALS` | 1 | Require portable pointers, storage, stages, and fault injection |
| `TEST_SETTLE_NS` | 0 | Must be zero for this RTL timing model |

The runner supplies matching compile parameters and expected environment values.
For direct overrides, supply both explicitly and use a fresh `SIM_BUILD`:

```sh
ASYNC_FIFO_DEPTH=4 ASYNC_FIFO_SYNC_STAGES=3 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=async_fifo \
  COMPILE_ARGS="-Pasync_fifo.DEPTH=4 -Pasync_fifo.SYNC_STAGES=3" \
  SIM_BUILD="$(pwd)/build/async-direct"
```

For another zero-delay implementation without portable internals, direct runs
may set `ASYNC_FIFO_CHECK_INTERNALS=0`. Queue, interface timing, reset, coverage,
and waveform assertions remain active, while internal/stage/fault checks report
`structural_assertions=NOT_RUN`. The full matrix requires internal checks.

Gate-level SDF delay, analog metastability, MTBF, commercial lint/CDC/RDC, Gray-bus
skew, physical stage placement, macro equivalence, formal multiclock proof, UPF,
DFT, and physical power are separate `NOT_RUN` checks. First-stage digital force
tests do not model analog resolution or establish MTBF. This suite is for
zero-delay functional RTL and must not be presented as physical CDC signoff.

## Reports and negative checks

Reports default to `build/<simulator>/async_fifo/regression`:

| Artifact | Evidence |
| --- | --- |
| `<profile>/results.xml` | Exactly one successful, unskipped `test_async_fifo.AsyncFifoTest` |
| `<profile>/coverage.json` | Parameters, seed, events, record accounting, mandatory goals and bins |
| `<profile>/parameters.json` | Fresh compile dependency for each parameter selection |
| `<profile>/simulation.log` | Native compiler and simulator output |
| `invalid_parameters/<case>/elaboration.log` | Intended guard rejects invalid structure before simulation |
| `assertion_probes/<case>/results.xml` | Expected failure of the exact PyUVM test |
| `assertion_probes/<case>/simulation.log` | Matching live assertion diagnostic |
| `summary.json` | Matrix status, checks, external limits, source/dependency/helper hashes |

Eleven invalid profiles cover zero width, zero/one/non-power-of-two depth,
zero/one synchronizer stages, and threshold bounds. The original startup `$fatal`
allowed invalid `DATA_WIDTH=0` to elaborate. The RTL now instantiates the named
`async_fifo_parameters_must_be_valid` guard for invalid structure, so those cases
fail native elaboration with the intended diagnostic. This finite guard campaign
does not prove rejection of every possible literal or unsigned conversion.

Sixteen X/Z probes cover write valid, read ready, either reset, and the final
stage of each pointer/domain-up crossing. A probe passes only when the expected
test fails, JUnit identifies that exact failure, and the log names its assertion.
An unrelated compiler failure cannot pass. `ASYNC_FIFO_ASSERTION_PROBE` is an
internal negative-test selector; the runner clears it for positive profiles.

Stale coverage/JUnit are removed before each run. Missing, duplicate, skipped,
incorrect, failed, or insufficiently covered positive tests fail the campaign.
Missing executables or recognized license failures are reported as `NOT_RUN`
and return nonzero rather than counting as functional evidence.

## Local verification

Native Icarus Verilog 12.0, cocotb 2.1.0, and PyUVM 5.0.0 passed all ten profiles
with all 19 mandatory goals per profile. The campaign checked 199,176 events,
including 20,000 randomized events, and accounted for 21,262 accepted records:
21,074 consumed, 188 canceled, and zero pending. Both pointers wrapped at least
158 times in every profile. All eleven elaboration guards and sixteen expected
assertion failures passed.

Additional checks confirmed a custom seed/1000-event focused run from another
working directory, direct Makefile discovery, and continued operation of the
existing reset-synchronizer runner. Three temporary RTL mutations were rejected:
corrupted read data, prematurely visible write pointers, and write-pointer
advancement without acceptance. The 31 existing synthesis/power flow tests also
passed using their tool stubs; they do not establish licensed synthesis or power
results. VCS was unavailable locally and its campaign reports `NOT_RUN`.

The complete local evidence is under `build/validation/async-fifo-final`, with
source/dependency hashes in `summary.json`. Build artifacts remain ignored by Git.
