# Context memory RTL and PyUVM validation

[context_memory.sv](../../../rtl/basic/context_memory.sv) implements the
[MOSAIC context memory specification](../../../../../specs/basic/mosaic-context-memory/README.md)
as a SystemVerilog module using common decoder and DFF blocks. It stores opaque
words, writes selected slices, and tracks committed validity independently. It
introduces no private context fields, opcodes, source encodings, or configuration
validator.

Three common `decoder` instances select write, commit, and invalidate entries.
Their fail-closed address handling prevents unknown and unused encodings from
aliasing legal storage. A common `dff` bank stores validity with the selected reset
style. The common DFF samples unknown reset inside its sequential process and
poisons state, avoiding a race between asynchronous reset and an external D-input
guard. Context data remains inferred storage without reset.

The common `mux` is not a direct read replacement: it clamps unknown addresses,
whereas this interface exposes X, and it has no read-enable input. The existing
guarded reads retain these semantics and disabled-port qualification. Reset release,
clock gating, retention, and power-domain boundaries remain integration policies.

The suite follows the [shared PyUVM structure](../../README.md): separate
configuration, transactions, sequences, sequencer, driver, monitor, agent,
independent model, scoreboard, coverage, environment, and decorated test.

## RTL behavior

The default instance has four 256-bit contexts, eight 32-bit write slices, two
combinational read ports, raw readback, and synchronous validity reset.
Context data has no reset. Asserted reset suppresses writes; commit and invalidation
change only validity. A masked write clears validity unless the same edge commits
that entry. Commit may finalize the last partial write atomically.

Read port zero and write slice zero occupy the least-significant packed positions.
Disabled reads and known out-of-range reads return zero/invalid. Unknown enabled
read addresses expose X data/validity. Uncommitted entries clamp to zero except
when permitted raw readback is requested; raw readback never grants validity.

Validity storage resets at a rising edge in synchronous mode and immediately on
assertion in asynchronous mode. Read qualification also gates validity while reset
is asserted, satisfying the specification's requirement that no context be valid
during reset. Raw debug reads can still inspect retained data with validity low.
The external reset controller must supply the required clock edges and synchronized
release; this module does not generate reset.

Same-address commit/invalidation is an illegal command. The validity decoder
exposes X for that collision rather than defining a functional priority. Active
PyUVM assertions reject the command. Such inputs cannot be used to infer hardware
arbitration or commit/invalidation priority.

All primary parameters retain caller values until explicit elaboration guards
check their dimensions, divisibility, and Boolean restrictions. Safe declaration
sizes let malformed profiles reach the named guard rather than divide by zero or
instantiate invalid slice logic. Derived dimensions remain local parameters.

## Running

From `mosaic-cgra`:

```sh
make setup
make context-memory-regression                 # VCS on the licensed server
make context-memory-regression SIM=icarus      # Native four-state local simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=context_memory
```

The Makefile discovers the RTL, common decoder/DFF dependencies, and test package
automatically. The regression also includes and hashes both common sources for
profiles, assertion probes, and parameter guards. Direct discovery runs the default
instance.

Defaults are seed `20261012` and 2000 random scheduled operations per profile;
at least 1000 are required. Each operation drives a falling phase and a rising
phase. Directed checks run in addition to the random campaign. Profile seeds add
the full matrix index to the base seed, even in focused runs.

```sh
make context-memory-regression SIM=icarus CONTEXT_MEMORY_SEED=1234 \
  CONTEXT_MEMORY_RANDOM_CYCLES=3000 \
  CONTEXT_MEMORY_REGRESSION_BUILD="$(pwd)/build/context-custom"

.venv/bin/python src/val/basic/context_memory/run_context_memory_regression.py \
  --sim icarus --build-dir build/context-focused \
  --case minimum_raw0_sync --case baseline_raw1_async
```

Repeat `--case` to select profiles. Focused runs retain every parameter guard and
assertion probe and identify their scope as `selected_profiles`. `--rtl` accepts a
compatible implementation. The standalone script works from another directory.
`VCS_BIN_DIR`, `ICARUS_BIN_DIR`, `COMPILE_ARGS`, and `SIM_ARGS` retain their normal
Makefile meanings.

## Parameter matrix

Each configuration below runs all four raw-readback/reset combinations, named
`_raw0_sync`, `_raw0_async`, `_raw1_sync`, and `_raw1_async`:

| Configuration | Context width | Depth | Slice width | Read ports |
| --- | ---: | ---: | ---: | ---: |
| `minimum` | 1 | 1 | 1 | 1 |
| `spatial` | 64 | 1 | 16 | 2 |
| `baseline` | 256 | 4 | 32 | 2 |
| `non_power_three` | 24 | 3 | 8 | 3 |
| `fine_grain` | 40 | 5 | 1 | 4 |
| `whole_word` | 64 | 8 | 64 | 1 |
| `exploration` | 32 | 32 | 8 | 4 |

Another 26 `depth<N>_exploration` profiles exercise every remaining depth from 1
through 32 with width 32, slice width 8, two read ports, raw readback, and synchronous
reset. There are 54 profiles in total. The matrix covers power-of-two and
non-power-of-two depths, spatial and shallow-temporal use, the maximum specified
exploration depth, and representative width/granularity/read-port combinations.

The specification defines no exhaustive released widths or read-port-count range.
The listed profiles establish finite functional evidence, not physical timing
limits or a claim that every possible parameter cross has been tested.

## Independent reference and active checks

The reference stores Python strings for each context and a separate validity
list. It merges selected string chunks instead of reproducing the RTL's indexed
part-select assignments. Initial context data is X, and reset never clears it.
Only observed rising edges with released reset update data and validity.

Every item is checked before its clock change, 1 ps after the change, and after
its held interval. Pre-edge checks reject premature write forwarding and early
synchronous state updates. Post-edge checks verify merged writes, automatic
invalidation, atomic commits, and noninterference between addresses. Held checks
and continuous per-word/per-bit monitors reject activity on disabled outputs,
untouched entries, unmasked slices, and stable storage/validity.

The scoreboard checks all portable `context_data` words and `context_valid` bits
in addition to visible reads. Finite output and state pulses persisting into a
read-only phase are checked; same-delta propagation transients and physical timing
remain outside this digital waveform scope.

| Requirement | Stimulus and assertions |
| --- | --- |
| Full loading and commit | Load every entry, commit independently or with the write, read it on every port, and compare exact bits. |
| Partial assembly | Write every individual slice; inspect intermediate raw data; commit the final merged word atomically. |
| Data/mask ordering | Walking-one patterns at every bit on every entry, all mask populations, and zero/ones/walking-zero/alternating pattern crosses by mask class. |
| Validity lifecycle | Explicit invalidation, write to a valid entry, write/invalidation of the same entry, and recommit without a write. |
| Readback protection | Read every entry in valid/invalid states and each available raw mode; raw reads cannot create execution validity. |
| Multiple ports | Exercise every address pair for every pair of read ports, including equal and unequal addresses. |
| Read-during-operation | Check old data/validity before the edge and updated state afterward for read/write, read/commit, and read/invalidation equal/unequal address crosses. |
| Simultaneous commands | Exercise every legal operation class, same/different write/commit and write/invalidation, and distinct commit/invalidation. |
| Reset priority | Reset during every legal operation class; require retained data, cleared validity, and reset-safe read qualification. |
| Ignored inputs | Disabled read addresses, inactive command addresses/masks/data, zero-mask write address/data, and unknown unmasked data slices. |
| Illegal addresses | Exercise every unused binary read encoding and representative unknown addresses on every port; active bad commands must leave storage unchanged. |
| Random history | Preserve an independent complete data/validity history over random masks, addresses, writes, commits, invalidations, reset, reads, and raw modes. |

Coverage closes read-port x entry x validity x raw mode, mask-population x prior
validity, every entry/slice, operation/reset classes, address relationships, and
read-port address pairs. One-entry commit/invalidation to different addresses is
unreachable; same-address collision remains illegal. One-slice partial masks,
single-port read pairs, disabled raw mode, and unavailable binary address holes
have explicit parameter-based waivers.

Unknown addresses are exhaustive over four-state encodings through address width
three. Larger widths use all-X/all-Z and each X/Z bit position against zero and
the highest legal address. This avoids claiming exhaustive enumeration of larger
four-state address spaces.

## Protocol and commit-integrity assertions

Assertions require known reset and enables, active addresses, enabled raw requests,
active write masks, and selected write-data slices. Raw requests must always be
zero when raw readback is disabled. Unknown unmasked data and inactive fields are
ignored only where the specification permits.

At every actual commit, the reference checks that the complete candidate word is
known, including any same-edge masked merge. This permits a final atomic load while
rejecting commit of an incomplete/uninitialized word. It checks syntactic knownness;
semantic opcode/route/datatype validation belongs to the external configuration
validator, and execution safe-point checks belong to the tile/sequencer.

Positive profiles acknowledge deliberately illegal read/command addresses, log
their active assertions, and continue checking clamp/X behavior and state
preservation. Untagged violations fail. 33 separate expected-failure probes cover
X/Z controls, mask/data/address errors, out-of-range commands, forbidden raw
requests, commit/invalidation collision, and commit of an unknown word. A probe
passes only when the exact PyUVM test fails with its expected assertion and JUnit
records that failure. Unrelated compiler errors cannot pass.

## Direct configuration and reports

| Environment variable | Default | Meaning |
| --- | ---: | --- |
| `CONTEXT_MEMORY_CONTEXT_WIDTH` | 256 | Expected opaque word width |
| `CONTEXT_MEMORY_CONTEXT_DEPTH` | 4 | Expected resident entry count |
| `CONTEXT_MEMORY_WRITE_SLICE_WIDTH` | 32 | Expected write granularity |
| `CONTEXT_MEMORY_NUM_READ_PORTS` | 2 | Expected read-port count |
| `CONTEXT_MEMORY_HAS_RAW_READBACK` | 1 | Expected raw-readback option |
| `CONTEXT_MEMORY_ASYNC_RESET` | 0 | Expected reset style |
| `CONTEXT_MEMORY_SEED` | 20261012 | Stimulus seed |
| `CONTEXT_MEMORY_RANDOM_CYCLES` | 2000 | Random scheduled operations |
| `CONTEXT_MEMORY_COVERAGE_FILE` | Beside JUnit | Mandatory coverage JSON |
| `CONTEXT_MEMORY_CHECK_INTERNALS` | 1 | Require portable storage/validity observation |
| `TEST_SETTLE_NS` | 0 | Must be zero for this RTL suite |

The runner supplies matching compiler parameters and expected settings. Direct
overrides must provide both and use a fresh build:

```sh
CONTEXT_MEMORY_CONTEXT_WIDTH=24 CONTEXT_MEMORY_CONTEXT_DEPTH=3 \
CONTEXT_MEMORY_WRITE_SLICE_WIDTH=8 CONTEXT_MEMORY_NUM_READ_PORTS=3 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=context_memory \
  COMPILE_ARGS="-Pcontext_memory.CONTEXT_WIDTH=24 -Pcontext_memory.CONTEXT_DEPTH=3 \
    -Pcontext_memory.WRITE_SLICE_WIDTH=8 -Pcontext_memory.NUM_READ_PORTS=3" \
  SIM_BUILD="$(pwd)/build/context-direct"
```

Alternative zero-delay implementations can use `CONTEXT_MEMORY_CHECK_INTERNALS=0`
for port-based runs. Functional reads, commit checks, timing, protocol, waveform,
and coverage remain active; internal observation reports `NOT_RUN`. The full
regression requires internal observation. The suite does not model SDF delay.

Reports default to `build/<simulator>/context_memory/regression`:

| Artifact | Evidence |
| --- | --- |
| `<profile>/results.xml` | Exactly one successful, unskipped `test_context_memory.ContextMemoryTest` |
| `<profile>/coverage.json` | Parameters, seed, phase counts, mandatory goals, bins, and waivers |
| `<profile>/parameters.json` | Fresh dependency forcing parameter changes to rebuild |
| `<profile>/simulation.log` | Native compiler and simulation output |
| `invalid_parameters/<case>/elaboration.log` | Intended structural parameter rejection |
| `assertion_probes/<case>/results.xml` | Expected failure of the exact PyUVM test |
| `summary.json` | Matrix result, negative checks, RTL/dependency/helper hashes, and external scope |

28 elaboration checks reject zero/negative/unknown dimensions, nondivisible or
oversized slices, and illegal Boolean caller values. This finite campaign does not
prove rejection of every literal or physical implementation capacity. Missing,
failed, duplicate, skipped, wrong, or insufficiently covered tests cannot pass.
Stale JUnit and coverage are removed before each run. Missing executables and
recognized license failures report `NOT_RUN` and return nonzero.

HDL-bound SVA, formal, commercial lint/CDC/RDC, DFT, UPF, technology/macro synthesis,
equivalence, physical timing/power, semantic validation, safe-point policy, reset
integration, and contract version evidence remain separate `NOT_RUN` checks.

## Local verification

Native Icarus Verilog 12.0, cocotb 2.1.0, and PyUVM 5.0.0 passed all 54 profiles,
with all 15 mandatory goals per profile. The campaign checked 358,429 items before
the clock change, after the change, and after hold: 1,075,287 observations in total,
including 108,000 randomized scheduled operations. All 28 elaboration guards and
33 live assertion probes passed.

Verilator `--lint-only --timing -Wall` passed all 54 profiles without warnings or
waivers. Fourteen intentional RTL defects were rejected, including unmasked writes,
reversed masks, missing automatic invalidation, lost atomic commits, address aliases,
incorrect reset timing, reset of context data, disabled-read leakage, and 1 ps pulses
on data, read validity, and stored validity. The finite pulses failed the continuous
waveform assertions.

Direct discovery, port-only observation, automatic common-source discovery,
explicit source overrides, and dry-run evidence preservation also passed.
Standalone four-state probes checked X/Z reset assertion, sampled poisoning,
write suppression, and reset recovery in both reset modes and both DFF enable
branches. The common DFF regression passed all 11 profiles. Its FIFO and bypass
consumers passed all 10 and 31 profiles, respectively, including their negative
probes. The FIFO activity monitor now diagnoses unknown reset before the resulting
state activity; its checks for unclocked changes remain active.

The 31 existing synthesis/power flow tests passed with their tool stubs. Native
VCS was unavailable locally. The installed Yosys frontend rejected the SystemVerilog
`int'` casts; no Yosys synthesis result is claimed. Licensed synthesis, macro
equivalence, and physical signoff remain separate work.

Evidence is under `build/validation/context-memory-reuse`, with lint, reset, and
consumer checks in the neighboring `context-memory-reuse-*` directories. Defect
checks are under `context-memory-mutations`. Final RTL, common-dependency, and
component hashes match the tested files. Build artifacts remain ignored by Git.
