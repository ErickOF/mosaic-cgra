# Granular even-parity validation

This PyUVM suite checks `src/rtl/basic/parity.sv` against
`specs/basic/mosaic-parity/README.md`. Generation and checking operate
combinationally on independent words. There is no clock, reset, storage, enable,
valid, ready, correction, retry or memory sequencing inside the codec.

## Layout, parameters and reuse

| Parameter | Default | Restriction |
| --- | --- | --- |
| `DATA_WIDTH` | 32 | Positive integer |
| `PARITY_GRANULE_WIDTH` | 8 | Positive integer dividing `DATA_WIDTH` |
| `PARITY_WIDTH` | Derived | `DATA_WIDTH / PARITY_GRANULE_WIDTH` |
| `CODE_WIDTH` | Derived | `DATA_WIDTH + PARITY_WIDTH` |

The derived widths are local parameters and cannot be overridden independently.
Invalid negative, zero, unknown and nondivisible geometries fail at elaboration
with `parity_parameters_must_be_valid`. Safe declaration sizes avoid invalid
slices or division by zero before that guard is reached. The implementation has
no additional product width cap; the validation matrix ends at 256 data bits.

Granule `g` is `data[g*PARITY_GRANULE_WIDTH +: PARITY_GRANULE_WIDTH]` and is
protected by parity bit `g`. Granule zero is the least-significant group. The
canonical packed codeword is `{parity, data}`; the data remains in the low bits.
No data bits are reordered or reinterpreted.

Each generated parity bit makes its granule's total population even. Each error
bit is the parity of received data plus the corresponding received parity bit.
Granule validity is the bitwise inverse of that vector; aggregate error is its
OR reduction, and no-error is the complement. Any failed granule clamps the
**complete** checked data word to zero. A clean check passes received data exactly.

The core reuses common `operand_isolation` for whole-word clamping. It also
preserves uncertain status: an unknown aggregate check produces unknown checked
data, rather than a fabricated clean result. A known error in any other granule
dominates uncertainty and still clamps the whole word to zero. Per-granule XOR
reductions permit balanced trees; no procedural accumulator or serialized state
is introduced. Make supplies the ordered dependency for simulation and synthesis,
and validation records its exact source hash without a dependency lockfile.

The Boolean status ports, even-parity convention and lane layout come directly
from the supplied specification. No new contract package or encoding is defined.
External canonical `mosaic-contracts` qualification remains `NOT_RUN`, consistent
with the repository's existing convention.

## Running

```sh
make parity-regression                       # VCS on the licensed server
make parity-regression SIM=icarus            # local four-state simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=parity  # default 32-bit/byte-granule case

.venv/bin/python src/val/basic/parity/run_parity_regression.py \
  --sim icarus --build-dir build/parity-focused \
  --case w1_g1 --case w12_g3 --case w32_g8
```

`PARITY_REGRESSION_BUILD`, `PARITY_SEED` (default 20261013) and
`PARITY_RANDOM_CYCLES` (default 2000, minimum 1000) configure the Make target.
The standalone runner additionally accepts repeated `--case`, `--rtl`, `--seed`,
`--random-cycles`, `--sim-bin-dir`, `--make`, `--compile-args`, and `--sim-args`.
Case seeds retain their full-matrix index in focused runs. Paths are resolved
from the script, so it works when invoked from another directory.

Direct parameterized simulation must supply both actual HDL overrides and the
expected test geometry. The environment names are `PARITY_DATA_WIDTH` and
`PARITY_GRANULE_WIDTH`:

```sh
PARITY_DATA_WIDTH=12 PARITY_GRANULE_WIDTH=3 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=parity SIM_BUILD=build/parity-custom \
  COMPILE_ARGS='-Pparity.DATA_WIDTH=12 -Pparity.PARITY_GRANULE_WIDTH=3'
```

Use fresh direct-run builds when changing parameters or compiler options. The
regression invalidates stale JUnit/coverage and makes parameter changes force
recompilation. Use `TEST_SETTLE_NS=0` with 1 ps precision or finer. This suite
checks zero-delay RTL; delayed gate-level timing needs a separate sampling policy.
`PARITY_CHECK_INTERNALS=0` permits equivalent port-only implementations and records
elaboration assertions as `NOT_RUN`; standard campaigns require the actual
parameter and derived-width checks.

## Independent model and live assertions

The reference partitions MSB-first Python strings into documented granules and
counts set bits modulo two. It does not reuse the RTL reduction operators. A
separate fault oracle counts flipped protected positions per granule, including
sidecar parity bits. Every output is compared, including complete-word clamping,
aggregate status and the exact mapping of error and granule-valid bits.

Fault tests preserve an original data word and a distinct packed fault mask. The
scoreboard validates that provenance before checking odd/even weight and location.
Every data and parity position is injected alone on zero and all-one base words.
Detected errors must clamp the whole word; undetected even-weight faults must pass
the **received**, possibly corrupted word and are recorded as expected limitations.
The checker never claims to have recovered the original data.

The driver independently changes generation and checking inputs. The monitor reads
real DUT ports after settling and after a held interval. Continuous watchers catch
finite pulses in held outputs and changes in a cone whose own inputs did not
change. Partial-write vectors model complete-granule updates on generation inputs
while keeping checking inputs unchanged. The observed baseline is verified, and
unselected data/parity granules must remain unchanged. This checks codec activity;
it does not validate a memory controller's atomic write protocol.

Each input bit is exercised as X and Z, along with all-unknown/mixed words and a
known-error granule alongside an unknown granule. The oracle checks exact
four-state propagation and known-error dominance. These are intentional tests:
the codec has no valid protocol with which to reject unknown input data. A consuming
integration must require known data/parity whenever it consumes a protected result.

## Matrix and mandatory coverage

The matrix contains 101 geometries: every divisor granule width for each data width
1, 2, 3, 4, 5, 8, 12, 16, 24, 31, 32, 48, 64, 96, 128, 192 and 256. It includes
per-bit parity, byte/halfword/word granules, non-power-of-two groups and whole-word
parity. Minimum geometry has one data and one parity bit; maximum parity count is
256 and maximum packed-codeword width is 512.

The directed campaign includes zero, ones, alternating, walking-one/zero, clean
round trips, every single protected-bit fault, data/data and data/parity same-group
double faults, cross-group data/data, data/parity and parity/parity faults, higher
odd/even weights and multiple simultaneous failing granules. Generation is
exhaustive through eight data bits; checking is exhaustive through 12 codeword bits.
Random traffic alternates unrelated arbitrary received words and recorded faults
against clean reference codewords, with an unrelated generation word in both cases.

Within-group double pairs are exhaustive for granules through 32 bits. Wider groups
cover every data/parity pair, every adjacent data pair and the first/last data pair.
Cross-group pairs are exhaustive through 16 granules; larger profiles cover adjacent
and first-to-each group pairs with every data/parity role combination. Error vectors
are exhaustive through eight granules; larger profiles cover every singleton and
complement, alternating bits, and every population from zero to all granules. These
simulation bounds are explicit; separate binary formal checks cover arbitrary masks.

Each profile has 15 mandatory goals: every protected single-fault location, every
granule clean/failing, required error-vector patterns, every failing-granule count,
same-group limitations, cross-group detection, higher odd/even faults, recorded
undetected cases, partial-write selection by parity transition, generation/check
transition crosses, every X/Z bit in all three inputs, random count and held checks.
Unreachable cases are identified by geometry, including data/data pairs in one-bit
granules, cross-group faults in whole-word parity, and higher weights exceeding the
number of protected bits. Selected-but-unchanged writes are legal partial-write
stimulus, including for one-bit granules.

The runner requires all goals, exact parameters/seed/random count, exactly one
unskipped `test_parity.ParityTest`, derived-width assertions and all ten strict
parameter guards. It records RTL/dependency/helper/Makefile hashes, per-case
JUnit, coverage and logs under the selected build directory. The summary's
`external_checks` records checks not invoked by the simulation runner; separate
static/formal reports below have their own scope and status.

## Local evidence

The local 2026-10-13 Icarus campaign passed 202,000 random trials and 800,942
settled/held observations. It exercised all 10,786 protected-bit locations across
the matrix on both zero and all-one base words, and recorded 54,635 expected
undetected fault cases.

| Check | Result | Evidence under `build/validation/` |
| --- | --- | --- |
| 101 PyUVM profiles, 15 goals each, ten elaboration guards | PASS | `parity-final/summary.json` |
| Focused run from `/tmp`, seed 42 and 1000 random trials | PASS | `parity-custom/summary.json` |
| Direct Make invocation with port-only checking | PASS; elaboration assertions NOT_RUN | `parity-port-only/coverage.json` |
| 101 Verilator lint profiles, no warnings or waivers | PASS | `parity-lint/summary.json` |
| 303 Yosys combined/generation-only/checking-only checks | PASS | `parity-structure/summary.json` |
| 101 binary-input SAT proof profiles | PASS | `parity-formal/summary.json` |
| 18 intentionally broken implementations detected | PASS | `parity-mutations/summary.json` |
| Existing stubbed synthesis/power flow tests | PASS, 31 tests | `parity-flow-tests.log` |
| Native VCS | NOT_RUN, executable unavailable | `parity-vcs/summary.json` |

Structural checks find no state, latches, memories or unresolved references,
confirm generation XOR depth at most `ceil(log2(PARITY_GRANULE_WIDTH))`, and remove
unused cones. Per-bit generation is already a wire and contributes no removable
logic. Standalone lint supplies `--timescale 1ns/1ps` as a common timing default
for the reused primitive, without warning suppression.

Formal wrappers independently sum bit populations for arbitrary generation data,
arbitrary check data **and arbitrary received parity**. Classification therefore
does not assume that parity came from this generator. A second instance checks an
independently formed clean codeword XOR an arbitrary full packed fault mask.
The proof covers every one-hot position, arbitrary odd/even masks, granule mapping,
validity, aggregate status and exact pass/clamp behavior. The scope is combinational
binary logic at these 101 geometries; simulation separately checks X/Z behavior.
The widest whole-word proof initially reached a five-second solver limit and passed
after width reduction with a ten-second limit; both attempts remain in the report.

Mutation checks cover odd/wrongly mapped generation, coupled cones, missing or
misindexed received parity, incorrect validity/aggregate/complement, partial or
unconditional clamping, fabricated bit correction, unknown sanitization and four
finite 1 ps output pulses. Static/formal/mutation probes and generated wrappers stay
in the ignored build directory with generator hashes and logs. The maintained
functional campaign is the PyUVM runner documented above.

## Integration and release scope

No-error means parity equations match, not that data is physically fault free.
Even-weight faults in one granule can escape detection. Repair requires a known-good
copy: regenerating parity over corrupted data is not recovery. An external
controller must associate errors with the correct address/context/transaction and
implement retry, reload, cancellation, quarantine or reporting as appropriate.

Data and corresponding parity must update atomically. Complete-granule writes may
avoid read-modify-write when storage supports coupled enables; sub-granule writes
require validating the old granule, merging data and atomically writing regenerated
parity. This codec does not implement or qualify those storage/recovery policies.

Consumers must sample stable coherent inputs in their own registered domain.
There is no CDC or RDC primitive, retained state, internal clock or power sequencing.
Pipeline latency, valid qualification, isolation and level shifting belong outside
the codec. Canonical contracts, bound simulation SVA, commercial lint, CDC/RDC,
DFT, VC LP, technology synthesis, physical timing/power and controller qualification
remain separate release work recorded as `NOT_RUN` when unavailable. Local SAT and
portable synthesis do not establish physical fault rates or technology signoff.
