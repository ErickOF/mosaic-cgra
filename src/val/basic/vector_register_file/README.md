# Vector register-file verification

The specification is
[`specs/basic/mosaic-vector-register-file/README.md`](../../../../../specs/basic/mosaic-vector-register-file/README.md).
The implementation is [`vector_register_file.sv`](../../../rtl/basic/vector_register_file.sv).
The decorated PyUVM entry point is `test_vector_register_file.VectorRegisterFileTest`.

```sh
make setup
make vector-register-file-regression              # native VCS
make vector-register-file-regression SIM=icarus   # four-state RTL simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=vector_register_file
```

Run selected profiles while retaining all parameter guards and protocol probes:

```sh
.venv/bin/python src/val/basic/vector_register_file/run_vector_register_file_regression.py \
  --sim icarus --build-dir build/vector-focused \
  --case l4_w32_s8_d16_r2_w1_b1 --seed 42 --random-cycles 1000
```

Profile names encode lane count, lane width, slice width, depth, read/write ports
and broadcast selection. `--case` is repeatable. Seeds are the base seed plus the
profile's position in the full matrix, preserving reproducibility under filtering.
The runner resolves source paths from its location, works outside the repository,
and accepts `--rtl`, compiler/runtime options and a simulator binary directory.
At least 1000 random cycles are required; the default is 2000 per profile.

Make settings are `VECTOR_REGISTER_FILE_SEED`, `VECTOR_REGISTER_FILE_RANDOM_CYCLES`
and `VECTOR_REGISTER_FILE_REGRESSION_BUILD`. Reports default to
`build/<simulator>/vector_register_file/regression`. Dry runs preserve existing
evidence. Direct `make pyuvm` expects the following environment variables to match
the HDL parameters; the runner supplies both configurations:

| Variable suffix after `VECTOR_REGISTER_FILE_` | Default |
|---|---:|
| `LANE_WIDTH` | 32 |
| `NUM_LANES` | 4 |
| `WRITE_SLICE_WIDTH` | 8 |
| `DEPTH` | 16 |
| `NUM_READ_PORTS` | 2 |
| `NUM_WRITE_PORTS` | 1 |
| `HAS_BROADCAST` | 1 |

`VECTOR_REGISTER_FILE_CHECK_INTERNALS=0` selects port-only functional checking and
records elaborated-parameter and raw-storage assertions as `NOT_RUN`.
`VECTOR_REGISTER_FILE_COVERAGE_FILE` changes the coverage path. Use
`TEST_SETTLE_NS=0` with 1 ps or finer precision. Timing-annotated netlists require
an appropriate sampling policy; this campaign targets zero-delay RTL.

## RTL reuse and banking

Each writable slice instantiates the existing scalar `register_file`, which
already uses common `decoder`. Scalar banks provide combinational reads,
edge-triggered writes, inactive-address clamping, invalid-address suppression and
unreset storage. The vector shell adds per-lane read enables, per-slice write
enables, broadcast selection and packed port/lane/slice mapping. Ordered sources
are supplied automatically to simulation, SAIF and synthesis. Reports record
dependency hashes without introducing a dependency lockfile.

The RTL organization is:

| Property | Implementation |
|---|---|
| Logical slice-bank count | `NUM_LANES * LANE_WIDTH / WRITE_SLICE_WIDTH` |
| Each bank | `DEPTH` words of `WRITE_SLICE_WIDTH` bits |
| Logical capacity | `DEPTH * NUM_LANES * LANE_WIDTH` bits |
| Per-bank read/write ports | `NUM_READ_PORTS` / `NUM_WRITE_PORTS` |
| Read latency | Zero cycles, independently lane gated per read port |
| Write commit | Rising edge, independently enabled per slice |
| Additional bank conflicts | None beyond overlapping writes to the same entry/slice |
| Reset, initialization, forwarding, generated clocks | None |

This describes the RTL banks, not qualified technology macros. Synthesis may
flatten or share decode logic. Physical bank count, mapped storage type, area,
timing and access energy require target-specific reports before exposing a final
mapper profile. Declared concurrent accesses are never serialized in the RTL.

Port zero, lane zero and slice zero occupy the least-significant packed positions.
Every bank shares its port's vector-entry address. Multiple ports may write the
same entry only with disjoint slice masks; those writes merge concurrently.
Overlapping writes have no defined winner. The reused scalar bank poisons a
conflicting slice in simulation, while the validation assertion rejects the
operation without assigning a conflict result to the architectural oracle.

With broadcast enabled and asserted, each selected destination slice uses the
corresponding slice of write lane zero. Other source lanes are ignored and the
destination mask still applies. Disabled broadcast support removes the runtime
selection branch and ignores broadcast controls, including X/Z.

Read ports with enable zero or no enabled lanes return zero and ignore their
addresses. Disabled write ports and zero-mask writes preserve every bank and
ignore address, broadcast and data. Unselected source slices and unused broadcast
source lanes may contain X/Z without affecting selected storage. Used controls
and active addresses must be known. Active addresses must also be in range;
invalid binary reads return zero, unknown active reads return X, and invalid
writes must not alias or update an entry. Normal selected write data must be
known unless the transaction explicitly opts into intentional X/Z transport.

There is no bypass: reads reflect old data before and at the write edge. After
nonblocking updates, they show merged new slices and old unmasked slices. Use an
external bypass network when a same-edge consumer needs new results.

## PyUVM structure and assertions

Separate files contain configuration, transactions, sequences, driver, monitor,
reference model, scoreboard, coverage, agent, environment and test. They reuse
`mosaic_uvm` wiring, four-state conversion, pattern classification and regression
execution/evidence validation.

The architectural model stores an independent value for each entry/slice.
Unwritten slices are unspecified rather than assumed zero or X. Writes update
only selected slices; simultaneous disjoint writes merge before checking post-edge
reads. Unknown intentional payload bits retain their exact four-state strings.
Functional predictions never use DUT storage as expected initialized contents.

The monitor reads actual ports before the clock, immediately on the rising edge
before NBA updates, afterward and during a held interval. The edge observation
must equal the pre-edge old read data. Optional raw observations cover every bank
entry, sampled only initially as a hold baseline and then independently predicted
from writes. Continuous watchers reject changes outside the exact writable slice
set and held-output activity. Read-control legality is checked live; write
legality is checked at the sampled write edge.

Illegal reads have their zero/X output checked before rejection. Illegal writes
reach a real edge and check preservation of every unrelated slice before the
protocol assertion rejects them. This prevents a passing rejection probe from
hiding address aliasing or writes outside the selected mask. The suite initializes
all slices before its main campaign and ends by reading every entry again.

Integration owns initialization/validity policy, packed datatype interpretation,
context compatibility, write ownership, CDC/RDC and power-state recovery.
Standalone tests do not make uninitialized data architecturally valid or qualify
retention, isolation or power transitions.

## Matrix and coverage

The 56 profiles combine both broadcast modes with 28 representative geometries.
They include lanes `1, 2, 4, 8`, lane widths `8, 16, 32`, slice widths `8, 16`
and full-lane writes where legal, depths `1, 3, 5, 16`, read-port counts `1, 2, 4`
and write-port counts `1, 2`. Additional profiles cover the exact default,
one-bit minimum geometry, a 31-entry file and a three-lane/three-port geometry
with 12-bit lanes split into 3-bit slices. The matrix is representative rather
than the full Cartesian product of parameter values.

Every profile requires 23 coverage goals, including:

- Every legal entry/slice on each read and write port; initialized and
  uninitialized reads on every read port.
- Every read-lane population with the read port enabled and disabled, plus each
  singleton lane and its complement.
- Every write-mask population crossed with port and supported broadcast mode;
  every individual destination slice in each supported mode.
- Every feasible read/write enable combination, every read/write port address
  equality/inequality pair, and every read-port pair with same/different entries.
- Every write-port pair writing distinct entries where possible and the same
  entry with disjoint masks where at least two slices exist.
- Zero, one, alternating, walking-one and walking-zero slice patterns crossed
  with full, lane, singleton, alternating and feasible partial-lane mask classes.
- Every selected slice bit written and read as 0, 1, X and Z; disabled-port,
  zero-lane, zero-mask, unmasked-data and ignored broadcast-source unknowns.
- Write setup without a clock edge, exact randomized cycle count, and all four
  observation stages.

Thirty-one malformed parameter configurations must fail the named
`vector_register_file_parameters_must_be_valid` elaboration guard. Every derived
width is a non-overridable local parameter.

The 132 negative probes cover X/Z controls, active unknown addresses, accidental
unknown normal and broadcast source data, all unused binary addresses at depths
1, 3 and 5 on every port, and overlapping writes at each entry/slice of the probe
geometry. Each must fail exactly the decorated test with the expected protocol
assertion. Compilation errors, missing tests, unrelated failures and the probe's
fallback exception do not count as successful rejection.

## Evidence and qualification scope

The runner validates native JUnit identity, every coverage goal, elaborated
geometry, seed and random count. Summaries record RTL/dependency/verification
hashes, UTC timestamps and per-case logs. Filtered runs are marked
`selected_profiles`. Generated evidence and supplemental local checking helpers
remain under ignored `build/validation/`.

The local Icarus campaign passed all 56 profiles, 112,000 randomized cycles,
31 parameter guards and 132 protocol probes. Across 493,046 observations,
78,317 active port writes updated 296,531 selected slices. Port-only validation,
five Make integration checks and all 31 existing synthesis/power flow tests also
passed; the latter use licensed-tool stubs. The checker detected all 22 injected
defects, including lane/slice/port ordering errors, ignored masks or enables,
incorrect broadcast, write-through behavior, Z-to-X data conversion and invalid
or unknown write-address aliasing.

Verilator lint passes all 56 profiles without warnings or waivers. Yosys
structural checks confirm exact logical capacity, the expected slice-bank count
and dimensions, all declared ports, no storage initialization/reset, no latches
or generated clocks, and no combinational write-to-read forwarding. Disabled
broadcast mode removes its control cone.

Supplemental unbounded binary proofs pass 12 representative geometries covering
minimum storage, partial slices, non-power-of-two depths, three ports, both
broadcast modes and the default file. They start from equal arbitrary defined
binary storage and assume overlapping same-entry/slice writes absent. They check
all storage updates/holds and combinational read values, including no aliasing
for unused binary addresses. The two default-size cases prove every slice
separately to keep the solver workload manageable.

Proof-only source views expose bank storage for comparison. For decomposed
properties, unrelated primary output bits are hidden from optimization roots;
their driving logic is unchanged and every slice is proved. Observer/proof view
hashes are recorded separately. Simulation and lint use original RTL. These
proofs do not establish X/Z behavior, exact NBA event timing, technology
equivalence or release signoff; the four-state edge-time cases are checked by
PyUVM separately.

VCS, native HDL SVA, licensed lint/CDC/RDC/DFT/VC LP, technology synthesis and
equivalence, physical implementation, PrimeTime and PrimePower require their
tools, libraries and integration artifacts. Missing checks are `NOT_RUN`;
standalone functional results do not establish technology release qualification.
