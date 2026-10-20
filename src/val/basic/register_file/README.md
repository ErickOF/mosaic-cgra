# Scalar register-file verification

The specification is
[`specs/basic/mosaic-register-file/README.md`](../../../../../specs/basic/mosaic-register-file/README.md).
The implementation is [`register_file.sv`](../../../rtl/basic/register_file.sv).
The decorated PyUVM test is `test_register_file.RegisterFileTest`.

```sh
make setup
make register-file-regression              # native VCS
make register-file-regression SIM=icarus   # local four-state RTL regression
make pyuvm SIM=icarus COCOTB_TOPLEVEL=register_file
```

Run selected configurations while retaining every parameter and protocol probe:

```sh
.venv/bin/python src/val/basic/register_file/run_register_file_regression.py \
  --sim icarus --build-dir build/register-file-focused \
  --case w65_d5_r4_w2 --seed 42 --random-cycles 1000
```

`--case` is repeatable. Names encode data width, depth, read ports and write ports.
The effective seed is the base seed plus the profile's index in the full matrix,
so filtering preserves reproducibility. Paths resolve relative to the runner;
it also works from another directory. At least 1000 random cycles are required.
The runner accepts `--rtl`, compiler/runtime flags and a simulator binary directory.

Make settings are `REGISTER_FILE_REGRESSION_BUILD`, `REGISTER_FILE_RANDOM_CYCLES`
and `REGISTER_FILE_SEED`. Reports default to
`build/<simulator>/register_file/regression`; `make -n` preserves existing reports.
For direct `make pyuvm`, expected geometry uses `REGISTER_FILE_DATA_WIDTH`,
`REGISTER_FILE_DEPTH`, `REGISTER_FILE_NUM_READ_PORTS` and
`REGISTER_FILE_NUM_WRITE_PORTS`, with specification defaults. These describe the
expected parameters; compiler overrides must match them. The runner supplies both.

`REGISTER_FILE_CHECK_INTERNALS=0` selects port-only checking. Elaboration and raw
storage assertions then report `NOT_RUN`. `REGISTER_FILE_COVERAGE_FILE` overrides
the coverage path. Use `TEST_SETTLE_NS=0` and 1 ps or finer precision. Edge-phase
checks target zero-delay RTL and are not timing-annotated gate-simulation checks.

## RTL and ownership

The implementation has exactly `DEPTH * DATA_WIDTH` unreset storage bits, with
`NUM_READ_PORTS` independent combinational reads and `NUM_WRITE_PORTS` full-word
rising-edge writes. Port zero occupies the least-significant packed field.
`ADDR_WIDTH = max(1, ceil(log2(DEPTH)))`; all other packed widths are local derived
parameters. Malformed zero, negative, X or Z dimensions fail elaboration through
the named `register_file_parameters_must_be_valid` guard.

Each write port reuses the common `decoder`. Its exact source hash accompanies
regression evidence, and the Makefile orders the dependency for simulation and
synthesis. Disabled, unknown or out-of-range write addresses select no entry.
Each entry updates only if selected, with no reset, clear, generated clock,
content initialization or write forwarding. Disabled read mux addresses clamp to
zero before selection to suppress activity from changing inactive address pins.

Distinct-address writes commit together. Same-address writes are prohibited and
trigger a live verification assertion. The RTL exposes X at a conflicting word
in simulation instead of defining a winner. This is diagnostic behavior for an
illegal condition, not an architectural collision-resolution policy.

Reads of an enabled legal address expose stored data. Disabled or known invalid
reads return zero. Enabled unknown addresses or unknown read enables produce
conservative unknown data. Enabled invalid addresses are rejected by verification,
even when the defined invalid-read response is zero. At depth one, address one
is invalid; unused non-power-of-two address encodings never wrap to legal entries.

Before a same-address write edge, a read exposes the old word. A receiver sampling
at the edge sees that old word; the read changes to the new word after the
nonblocking write commits. Consumers requiring same-edge forwarding must provide
it externally, for example through `bypass_network`.

Initialization, valid bits, write-port ownership, CDC/RDC, DFT and power-off state
policy belong to the integration. There is no reset port. A standalone uninitialized
read is legal but has unspecified content; the suite does not require zero or X.

## PyUVM structure and checking

The suite separates configuration, transaction, sequence, sequencer/agent, driver,
monitor, reference model, scoreboard, coverage and environment responsibilities.
It reuses `mosaic_uvm` active-agent/environment wiring, four-state helpers,
pattern classification, simulator execution and evidence validation.

The reference model starts with every entry unspecified. Its functional expected
data comes only from stimulus writes to legal addresses, never DUT storage. It
updates only on actual write edges. Directed tests first read unwritten entries,
initialize every word, and then check every legal address on every port. The final
audit reads all entries through every read port.

The passive monitor observes each item before the edge, immediately on the real
clock edge before NBA updates, after NBA settling, and during a held interval.
Clockless transactions change read and write pins while holding the clock low,
checking combinational read latency and absence of forwarding or asynchronous
writes. Same-edge observations must equal the pre-edge values. All initialized
read fields are compared independently, including their X/Z bits when intentional
four-state transport is tested.

Optional raw-storage checking samples initial content only as a hold baseline.
That baseline never predicts functional read data. Independent writes update the
expected raw words. Every unrelated entry must hold, including during invalid
writes. Continuous storage monitors reject writes outside permitted rising-edge
windows, and output monitoring detects finite changes during held intervals.

Read protocol assertions run after checking the invalid/unknown output response.
Write protocol assertions run after a real edge and the storage check, so invalid
addresses must preserve all entries before rejection. Write conflicts are rejected
after checking unrelated words. Normal traffic requires known enables, active
addresses and write data. Directed items explicitly opt into intentional four-state
payload transport; accidental unknown write data remains an assertion failure.
Unknown disabled-port addresses and payload are ignored.

## Matrix and coverage

The 55 profiles include every combination of depths `1, 2, 3, 4, 5, 16, 31, 32`,
read-port counts `1, 2, 4` and write-port counts `1, 2`, rotating data widths
`1, 8, 16, 32, 64`. Each required width also runs at depth 32 with two reads and
one write. Additional profiles use widths 65 and 129 and a three-read/three-write
configuration to exercise wider packed buses and non-power-of-two port counts.

Each profile requires 17 coverage goals covering:

- Every legal address on every read/write port and a rewrite by every write port.
- Every read concurrency and feasible write concurrency, including idle.
- Every legal read-enable/write-enable vector cross.
- Same/different-address reads for every read-port pair.
- Same/different-address read-during-write for every read/write port pair.
- Every distance between simultaneous two-port write addresses.
- Uninitialized and initialized reads on every read port.
- Zero, one, alternating and walking-bit patterns on every port.
- Every walking-one/walking-zero bit on every write port.
- Intentional X/Z transport through every read port.
- Every disabled address/data bit carrying both X and Z.
- Active write inputs without a clock, exact random count and all sampling stages.

With depth one, different-address reads and concurrent writes above one are
unreachable. Coverage records those limits explicitly; it never treats conflicting
writes as legal concurrency.

The runner also requires all 16 malformed-dimension configurations to fail at
elaboration. Its 87 negative probes check each active enable, address and data bit
with X and Z; every unused address encoding at depths one, three and five on every
port; and every write-port pair conflicting at every address of a three-entry file.
Each probe must fail the exact decorated test with the expected live assertion.
A compiler failure, unrelated exception or absent test does not satisfy a probe.

## Evidence and qualification scope

The runner validates exact JUnit identity, geometry, coverage, seed and random
count. Summaries record RTL, decoder and verification hashes, per-case logs and
UTC timestamps. Filtered campaigns are marked `selected_profiles`. Generated
evidence and local qualification helpers remain under ignored `build/`.

The local Icarus/PyUVM campaign passed all 55 profiles and all 17 coverage goals
per profile, with 110,000 randomized cycles and 520,530 pre-edge, edge-time,
post-edge and held observations. All 16 parameter guards and 87 live assertion
probes passed. The checker detected all 15 injected defects, including forwarding,
wrong port/bit ordering, lost writes, disabled-port leakage, invalid-address
aliasing, writes outside clock edges and a finite pulse during a held interval.
Separate runs passed with port-only checking and a custom three-port profile
launched from `/tmp` with seed 42. Make dry runs preserved completed evidence.

Verilator lint passed all 55 profiles with no warnings or waivers. Yosys structural
synthesis confirmed the exact storage capacity in all 55 profiles, with no reset,
initialization, inferred latch, unresolved reference or internally generated clock.
The unselected write-data value is a don't-care, which prevents synthesis from
introducing redundant constant-data reset controls on otherwise enabled flops.

Local Verilator lint and Yosys structure/proof checks supplement simulation.
The independent formal reference uses a port-oriented memory model and explicit
read-address cases. It compares every output and stored bit under arbitrary binary
inputs with equal arbitrary initial state. It assumes that legal simultaneous
writes target distinct addresses; live simulation assertions check the prohibited
conflict cases separately. Binary proofs do not establish X/Z or physical timing
behavior, which require separate simulation and implementation checks.

Unbounded local induction passed 51 profiles. Four profiles reached the 20-second
SAT limit: `w64_d31_r4_w2`, `w64_d32_r2_w2`, `w64_d32_r4_w1` and
`w64_d32_r2_w1`. Those proofs and the aggregate local formal campaign are recorded
as `NOT_RUN`, not passing. Simulation, lint and structural synthesis passed for
all four. The simulation runner's external-check fields remain separate from
these supplemental local reports.

Native VCS, commercial lint/CDC/RDC, DFT, VC LP, technology mapping, physical
timing/power and system initialization/ownership policies require the corresponding
tools, libraries and integration artifacts. The runner records these external
checks as `NOT_RUN`. Local results are not physical release qualification.
