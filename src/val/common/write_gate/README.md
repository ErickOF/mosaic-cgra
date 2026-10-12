# Write gate PyUVM validation

This suite validates [write_gate.sv](../../../rtl/common/write_gate.sv) against
the [MOSAIC write gate specification](../../../../../specs/common/mosaic-write-gate/README.md).
It uses PyUVM sequences, a sequencer, driver, passive monitor, independent
reference models, scoreboard, and mandatory functional coverage. The RTL is
unchanged. Its zero-width guard is checked at elaboration.

## Running the regression

From `mosaic-cgra`, with Python 3.10 or newer:

```sh
make setup
make write-gate-regression                 # VCS on the licensed server
make write-gate-regression SIM=icarus      # Local four-state simulation
```

The matrix contains widths `1, 2, 4, 8, 16, 32, 64, 128`, each with a
combinational test and a register/memory integration test: 16 profiles. Defaults
are seed `20261011` and 2000 random transactions per profile; at least 1000 are
required. The full matrix index is added to the seed, including focused runs.

```sh
make write-gate-regression SIM=icarus \
  WRITE_GATE_SEED=1234 WRITE_GATE_RANDOM_CYCLES=3000 \
  WRITE_GATE_REGRESSION_BUILD="$(pwd)/build/write-gate-custom"

.venv/bin/python src/val/common/write_gate/run_write_gate_regression.py \
  --sim icarus --build-dir build/write-gate-focused \
  --case width8_functional --case width8_integration
```

Repeat `--case` to select profiles. `--rtl /absolute/path/write_gate.sv` tests
another implementation with the same interface. Every campaign also executes
the zero-width elaboration check and all five live assertion probes. A focused
campaign is identified as `selected_profiles` in the summary.

`VCS_BIN_DIR` or `ICARUS_BIN_DIR` selects simulator executables. `COMPILE_ARGS`
and `SIM_ARGS` extend compiler/runtime flags. The runner resolves binary and
build paths before changing directory. It rewrites parameter dependencies so
reusing a build directory cannot silently keep another width.

Normal discovery runs the default one-bit combinational instance:

```sh
make pyuvm SIM=icarus COCOTB_TOPLEVEL=write_gate

WRITE_GATE_WIDTH=8 make pyuvm SIM=icarus COCOTB_TOPLEVEL=write_gate \
  COMPILE_ARGS="-Pwrite_gate.WIDTH=8" \
  SIM_BUILD="$(pwd)/build/write-gate-direct8"
```

Direct tests accept `WRITE_GATE_WIDTH`, `WRITE_GATE_SEED`,
`WRITE_GATE_RANDOM_CYCLES`, and `WRITE_GATE_COVERAGE_FILE`. The runner supplies
them automatically. `WRITE_GATE_INTEGRATION=1` selects the verification-only
[destination fixture](write_gate_destinations.sv); the runner supplies its
top name, RTL sources, and expected width. This fixture adds registered capture
boundaries without changing the combinational DUT.

`TEST_SETTLE_NS` defaults to zero; at least 1 ps is allowed for delta-cycle
settling before sampling. Every transaction is sampled again after its hold.
Long directed intervals use 1 ns holds. Delayed netlists require an appropriate
settle interval and their own timing validation. The suite does not certify
glitch-free control switching or a destination setup/hold budget.

## Requirement mapping

| Specification requirement | Active checks and mandatory coverage |
| --- | --- |
| Four truth-table rows; partition and mutual exclusion | Explicit per-bit reference table; both outputs checked at settled/held samples; live known-bit partition and exclusion assertions |
| Independent permitted and suppressed bits | Walking masks at every position; each bit receives every binary and four-state input pair |
| Zero, one, alternating and random masks | Directed pattern-class cross; every suppression population from zero through WIDTH; seeded random masks |
| All control transitions; simultaneous changes | All 16 ordered binary input-pair transitions at every bit; simultaneous, individual and unchanged vector transitions |
| Back-to-back permitted/suppressed writes | Repeated permit/suppress alternation at every bit and consecutive destination writes |
| Long no-write and suppression periods | Repeated short and long idle, permitted and suppressed transactions; held-output and continuous waveform checks |
| X/Z controls | Exact four-state port comparison; active unknown-request and unknown-requested-suppression assertions; four unacknowledged fatal probes |
| Widths 1 through 128 listed by the specification | Eight required widths crossed with both functional and destination fixtures |
| Representative registers and memory enables | Actual HDL register and four independently addressed words; all state compared after every capture and hold |
| Suppression safety | Pre-capture assertion rejects a suppressed accepted write whose data differs from destination state; a fifth fatal probe proves it executes |
| Destination type × reason; protocol × decision | Register/memory crossed with no suppression, redundant-value suppression, and inactive destination; accepted/cancelled permitted, suppressed and mixed decisions; idle destinations |
| Activity comparison | Baseline/gated destination write-bit events and state toggles; fewer writes and equal architectural state activity required for both destinations |
| Invalid static WIDTH | WIDTH=0 must fail compilation with the DUT's named elaboration guard |

Widths 1, 2 and 4 exhaust every binary mask pair. Widths 1 and 2 additionally
exhaust every four-state mask pair. Every width applies isolated X/Z bits among
known neighbors and all-X/all-Z vectors. Scalar configurations omit mixed-mask
and pattern classes that cannot be represented.

The port reference is an explicit 16-row four-state table, independent of the
RTL's vector AND equations. It distinguishes a masked unknown suppression bit
from an unknown control that can affect a requested write. With request `0`,
either output remains `0` even when suppression is X/Z, and no control violation
is expected. Unknown requests are illegal regardless of suppression. A requested
write with unknown suppression must produce unknown output indications rather
than a known accepted write.

Positive four-state tests explicitly acknowledge their expected illegal controls;
the assertions still execute and their counts are reported. Untagged controls
fail immediately. A probe earns PASS only when the correct PyUVM test fails with
its intended assertion diagnostic and a failing JUnit record. A compilation
failure, unrelated exception, missing test, or skipped test cannot qualify it.

Two passive waveform tasks monitor the gate outputs throughout held intervals.
Finite pulses persisting into the read-only simulation phase are detected,
including changes between transaction samples. Changes while input controls
are switching are allowed to settle. The suite makes no analog glitch claim.

## Destination integration

The fixture applies `o_write_enable` to per-bit enables of a register or one of
four memory words. Python independently updates an ungated reference using
`i_write_enable` and capture validity, then compares the complete HDL state.
Untouched addresses and the other destination must retain their values.
Destination waveform monitors also reject out-of-capture changes and incorrect
values during a capture before point sampling.

For an accepted write, redundant-value suppression is legal only for bits whose
incoming data equals the previous state. Required changes remain enabled. For
an inactive destination, the test cancels the operation **before acceptance**;
both gated and reference destinations perform no capture. Idle operations make
no write requests. The fixture has no protocol acknowledgements, FIFO pointers,
transaction rollback, memory macro, CDC behavior, or physical supply model.
Its safety assertion and coverage do not prove arbitrary system integration.

Activity reports count enabled destination bit writes at valid capture edges.
State-toggle counts must match the ungated reference, while gated write-event
counts must decrease for both destination types. Fewer write events do not
prove an energy benefit: suppression generation, gate overhead, fanout, routing,
destination-cell internal activity and macro power remain unmeasured.

## Reports and signoff scope

Reports default to `build/<simulator>/write_gate/regression`. Each profile has
`simulation.log`, `results.xml`, `parameters.json`, and `coverage.json` with
mandatory goals, bins, exact seed, checked/held transaction counts, and
destination activity where applicable. `summary.json` records profile and
probe results, source SHA-256 hashes, UTC timestamps, and the width/fixture cross.
Missing binaries or recognized license failures are `NOT_RUN`; failed tests or
missing coverage are `FAIL`. The target returns nonzero unless its entire
requested campaign passes. Invalid command-line settings are rejected before
existing reports are removed, and `make -n write-gate-regression` runs no tests.

Native VCS must be run on the licensed server. Formal proof, HDL SVA binding,
commercial lint, CDC/RDC, DFT, VC LP, technology synthesis, equivalence,
PrimeTime setup/hold analysis, PrimePower destination energy and complete
system integration are separate checks recorded as `NOT_RUN`. Portable Yosys
checks can confirm combinational structure but cannot replace technology timing
or power characterization. The specification's full release criteria remain
subject to those checks; local functional PASS is not full release signoff.

## Local validation evidence

The Icarus 12.0 campaign with Python 3.12, cocotb 2.1.0 and PyUVM 5.0.0 passed
all 16 profiles: 54,001 transactions, 54,001 held-input checks, 32,000 random
transactions and 21,239 destination captures. The width guard and all five
assertion probes passed. Twenty-one injected gate, destination and parameter
defects were detected, including cross-bit wiring, X/Z coercion, 1 ps output
pulses, wrong memory addresses and ignored cancellation.

Verilator lint passed for the DUT and destination fixture at every required
width without waivers. Portable Yosys checks inferred only two AND operations
and one NOT operation, with no storage, for the DUT at all eight widths. The
31 existing tool-flow tests passed with licensed commands stubbed. Direct
discovery, a custom three-bit width, custom seeds/counts, relative simulator
paths, dry-run preservation, invalid-setting preservation and simulated license
failures also passed their execution checks. Native VCS, physical power/energy
and the external signoff flows listed above remain `NOT_RUN`.
