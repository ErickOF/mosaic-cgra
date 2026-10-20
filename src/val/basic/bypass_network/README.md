# Bypass network PyUVM validation

This suite validates [bypass_network.sv](../../../rtl/basic/bypass_network.sv)
against the [MOSAIC bypass network specification](../../../../../specs/basic/mosaic-bypass-network/README.md).
It follows the [shared UVM structure](../../README.md), with separate configuration,
transactions, sequences, sequencer, driver, monitor, agent, reference model,
scoreboard, coverage collector, environment, and decorated test.

## Running

From `mosaic-cgra`:

```sh
make setup
make bypass-network-regression                 # VCS on the licensed server
make bypass-network-regression SIM=icarus      # Local native four-state simulation
make pyuvm SIM=icarus COCOTB_TOPLEVEL=bypass_network
```

The Makefile includes `src/rtl/common/dff.sv` automatically for this top. An
explicit `VERILOG_SOURCES` takes precedence. Direct discovery runs the default
32-bit, eight-source, four-destination, all-connected combinational instance.

Defaults are seed `20261012` and 2000 random scheduled operations per profile;
at least 1000 are required. Each operation drives a falling phase followed by a
rising phase. Directed operations run in addition to the randomized campaign.
Profile seeds add their full matrix index to the base seed, including in subsets.

```sh
make bypass-network-regression SIM=icarus BYPASS_NETWORK_SEED=1234 \
  BYPASS_NETWORK_RANDOM_CYCLES=3000 \
  BYPASS_NETWORK_REGRESSION_BUILD="$(pwd)/build/bypass-custom"

.venv/bin/python src/val/basic/bypass_network/run_bypass_network_regression.py \
  --sim icarus --build-dir build/bypass-focused \
  --case minimum_combinational --case nominal_balanced_async
```

Repeat `--case` to select profiles. Focused campaigns retain all parameter guards
and live assertion probes and identify themselves as `scope=selected_profiles`.
`--rtl /absolute/path/bypass_network.sv` selects a compatible implementation;
the DFF dependency remains the repository version. The standalone runner resolves
paths relative to its script and works from another working directory.
`VCS_BIN_DIR`, `ICARUS_BIN_DIR`, `COMPILE_ARGS`, and `SIM_ARGS` retain their normal
Makefile meanings.

## Parameter matrix and graphs

Every configuration below runs `_combinational`, `_sync`, and `_async` profiles:
`REGISTER_OUTPUTS/ASYNC_RESET` are respectively `0/0`, `1/0`, and `1/1`.

| Configuration | Data width | Sources | Destinations | Graph |
| --- | ---: | ---: | ---: | --- |
| `minimum` | 1 | 1 | 1 | all |
| `two_sources` | 8 | 2 | 2 | minimal |
| `three_sources` | 16 | 3 | 3 | balanced |
| `nominal_minimal` | 32 | 5 | 4 | minimal |
| `nominal_balanced` | 32 | 5 | 4 | balanced |
| `nominal_flexible` | 32 | 5 | 4 | flexible |
| `nominal_all` | 32 | 5 | 4 | all |
| `wide_balanced` | 64 | 8 | 4 | balanced |
| `vector_flexible` | 128 | 8 | 4 | flexible |
| `default` | 32 | 8 | 4 | all |

An additional `combinational_async_parameter` profile uses the nominal balanced
graph with `REGISTER_OUTPUTS=0, ASYNC_RESET=1`, verifying that this valid static
reset option has no forwarding effect in combinational mode. The full matrix has
31 profiles and crosses all four graph classes with both forwarding modes.

The graph generator creates deterministic **unit-test fixtures**. For destination
`d`, minimal connects sources `{0, d % S}`; balanced adds `(d + 1) % S`; flexible
connects all sources except one nonzero source determined by `d`; all connects
every source. Source zero is shared to exercise maximum destination fanout.
Some sparse fixtures intentionally leave source ports completely disconnected.

These graph names do not establish released tile connectivity or architectural
source identifiers. Tile-generated graphs and versioned `mosaic-contracts` port
assignments must still be verified by the integrating tile. The specification
does not supply release limits; the listed widths/counts are representative
verification profiles rather than invented maximum supported parameters.

## Independent checking and timing

The reference uses one source-index lookup per destination and a separate retained
data/valid record for each registered destination. It does not reproduce the
RTL's one-hot decode terms or OR tree. Source and destination zero occupy the
least-significant packed fields, and every input is checked for coercion.

Each transaction is checked after controls settle before the clock change, 1 ps
after the clock change, and again after its held interval. The registered model
advances only on rising edges, except for asynchronous validity reset assertion.
Pre-edge sampling proves that captures and synchronous flush/reset do not take
effect early; post-edge sampling proves the one-stage timing and priority rules.
The combinational model checks forwarding without waiting for a capture edge.

Continuous monitors watch all output buses and the portable registered data and
validity buses. Per-bit quiet masks describe intervals in which a destination or
storage word must remain stable. These checks detect finite pulses persisting
into a read-only phase, including activity caused by unselected sources, invalid
source payloads, disabled destinations, capture stalls, and stable held inputs.
Combinational propagation glitches within a single simulator delta are outside
this digital waveform check; physical timing remains separate.

The initial unreset payload is modeled as unknown. After every successful known
capture, its exact bits must remain stored until another qualified capture.
Reset, flush, invalid-source capture, and illegal capture change validity without
clearing payload. This checks the storage implementation as well as the visible
zero clamp on invalid state. Combinational internal placeholders must remain zero.

## Requirement mapping

| Requirement | Stimulus and assertions |
| --- | --- |
| Connectivity | Select every connected edge, reject every disconnected edge, and check every unused binary select encoding per destination. |
| Packed ordering | Walking-one patterns at every data-bit position on every connected edge, zero/ones/alternating patterns, and independent source words. |
| Destination independence | Exercise every legal source-selection pair for every pair of destinations; compare all outputs and capture states independently. |
| Fanout | Exercise every graph-reachable fanout population with valid and invalid sources, and every reachable distinct-source population. |
| Enables and validity | Close connected-edge x destination-enable x capture-enable x source-valid crosses; disabled destinations and invalid sources clamp correctly. |
| Unselected activity | Toggle every other source's data and validity through 0/1/X/Z while checking selected output and held state. |
| Invalid source payloads | Drive all-X/all-Z data with selected source-valid low; ignore payload without poisoning output or state. |
| Illegal selections | Check zero/invalid/error outputs for known disconnected/out-of-range requests; acknowledge deliberate assertion violations. |
| Unknown selections | Exercise every four-state unknown select field when consumed, including with candidate payloads zero; expose unknown behavior rather than aliasing source zero. |
| Registered state | Check independent capture, replacement, hold, disabled capture, invalid capture, and exact unreset payload preservation. |
| Reset/flush priority | Cover all eight reset x flush x capture combinations with initialized data, including reset coincident with flush and capture. |
| Context flush | Flush valid, invalid, and mixed registered entries; capture fresh values afterward and prevent stale output visibility. |
| Ignored controls | Ignore clock/reset/flush/capture controls in combinational mode; ignore unknown select during registered hold and unknown capture while disabled. |
| Random operation | Generate known source validity, masked unknown invalid payloads, legal/illegal/unknown selections, enables, captures, resets, and flushes; check every phase. |

Fanout limits are computed from the actual mask. Maximum distinct population uses
bipartite matching, so coverage does not demand impossible assignments. Larger
populations receive graph-specific waivers in JSON. One destination cannot contain
a mixed valid/invalid vector. One source has no unselected-source bins; an
all-connected graph has no disconnected-edge bins. Empty sets in those goals
represent unreachable cases, not missing functional checks.

Operation boundaries are defined by the sequence. Selections remain stable
through each held consumption interval. Context tags, FU dependency graphs,
feedback-loop rejection, and baseline context-event generation are outside this
interface. The unit context scenarios verify flush/capture behavior; they do not
claim integration verification of FU feedback/chaining, RF, writeback, or tile
pass-through contracts. Those required tile checks remain `NOT_RUN`.

## Protocol assertions and unknown values

Active testbench assertions require known destination enables, registered reset
and flush, active registered capture enables, consumed selects, selected source
validity, and selected valid payloads. Disabled or unconsumed selections and
invalid/unselected payloads are ignored exactly where the specification permits.

Positive profiles deliberately acknowledge disconnected, out-of-range, and unknown
consumed selections so the suite can check their specified outputs and registered
invalidation. Each expected assertion is logged and counted; an untagged violation
fails. For unknown captured selection, data holds and validity becomes X. Visible
data uses the four-state merge of retained payload and the invalid zero branch.

Active unknown source validity/data and unknown required controls are exercised
by separate X/Z probes. Their values violate the contract, so successful assertion
detection is the required result; they are not credited as legal forwarding.
26 negative probes cover both modes, registered-only controls, and unacknowledged
known illegal selections. A probe passes only when the exact decorated test fails,
JUnit contains that failure, and its expected assertion appears in the log. An
unrelated compilation or Python error cannot pass.

## Direct settings and parameter guards

| Environment variable | Default | Meaning |
| --- | ---: | --- |
| `BYPASS_NETWORK_DATA_WIDTH` | 32 | Expected data width |
| `BYPASS_NETWORK_NUM_SOURCES` | 8 | Expected source count |
| `BYPASS_NETWORK_NUM_DESTINATIONS` | 4 | Expected destination count |
| `BYPASS_NETWORK_CONNECTIVITY_MASK` | All connected | Expected integer mask; decimal or `0x...` accepted |
| `BYPASS_NETWORK_REGISTER_OUTPUTS` | 0 | Expected 0/1 forwarding mode |
| `BYPASS_NETWORK_ASYNC_RESET` | 0 | Expected 0/1 reset style |
| `BYPASS_NETWORK_SEED` | 20261012 | Reproducible stimulus seed |
| `BYPASS_NETWORK_RANDOM_CYCLES` | 2000 | Random scheduled operations |
| `BYPASS_NETWORK_COVERAGE_FILE` | Beside JUnit | Mandatory coverage JSON |
| `BYPASS_NETWORK_CHECK_INTERNALS` | 1 | Require portable data/valid storage and parameter observation |
| `TEST_SETTLE_NS` | 0 | Must be zero for this RTL timing model |

The runner supplies matching compiler parameters and expected settings. Direct
overrides must supply both explicitly and use a fresh build:

```sh
BYPASS_NETWORK_NUM_SOURCES=3 BYPASS_NETWORK_NUM_DESTINATIONS=2 \
BYPASS_NETWORK_REGISTER_OUTPUTS=1 BYPASS_NETWORK_ASYNC_RESET=1 \
  make pyuvm SIM=icarus COCOTB_TOPLEVEL=bypass_network \
  COMPILE_ARGS="-Pbypass_network.NUM_SOURCES=3 -Pbypass_network.NUM_DESTINATIONS=2 \
    -Pbypass_network.REGISTER_OUTPUTS=1 -Pbypass_network.ASYNC_RESET=1" \
  SIM_BUILD="$(pwd)/build/bypass-direct"
```

For another zero-delay implementation without portable internal buses, direct
runs can set `BYPASS_NETWORK_CHECK_INTERNALS=0`. Functional output, latency,
protocol, waveform, and coverage checks remain active, while internal observation
reports `structural_assertions=NOT_RUN`. The full regression requires those buses.

Eighteen strict native elaboration checks cover zero dimensions, illegal Boolean
values including negative/oversized/X/Z caller literals, empty connectivity rows,
and unknown mask bits. The original typed integer flags coerced X/Z to zero in
Icarus, bypassing their guard. Untyped flags now retain caller values until case
comparisons reject anything other than 0/1. Guard fixtures have a distinct module
name so they cannot accidentally resolve the intended undefined guard module.

`CONNECTIVITY_MASK` is declared with its derived bit width. SystemVerilog sizes
caller literals to that declaration; these checks do not prove that an original
literal's width or a truncated caller value matched its intent. Derived dimensions
remain local parameters. Integration must validate the generated connectivity
artifact and expected packed interface dimensions independently.

## Reports and remaining signoff

Reports default to `build/<simulator>/bypass_network/regression`:

| Artifact | Evidence |
| --- | --- |
| `<profile>/results.xml` | Exactly one successful, unskipped `test_bypass_network.BypassNetworkTest` |
| `<profile>/coverage.json` | Parameters, graph, seed, phase counts, mandatory goals, bins, and waivers |
| `<profile>/parameters.json` | Fresh dependency forcing compile parameter changes to rebuild |
| `<profile>/simulation.log` | Native compilation, expected assertions, and simulation results |
| `invalid_parameters/<case>/elaboration.log` | Intended parameter guard rejection before simulation |
| `assertion_probes/<case>/results.xml` | Expected failure of the exact PyUVM test |
| `summary.json` | Matrix result, negative checks, source/dependency/helper hashes, and external limits |

Missing, failed, duplicate, skipped, wrong, or insufficiently covered positive
tests fail the campaign. Stale JUnit/coverage are removed before runs. Missing
executables or recognized license failures report `NOT_RUN` and return nonzero.
`BYPASS_NETWORK_ASSERTION_PROBE` is an internal negative-test selector and is
cleared by the runner for positive profiles.

HDL-bound SVA, formal proof, commercial lint/CDC/RDC, DFT, UPF/VC LP, technology
synthesis, physical timing/power, released tile integration, and contracts version
evidence remain separate `NOT_RUN` checks. The suite validates zero-delay RTL
and does not establish SDF timing or physical power savings.

## Local verification

Native Icarus Verilog 12.0, cocotb 2.1.0, and PyUVM 5.0.0 passed all 31 profiles,
18 elaboration guards, and 26 expected protocol assertion failures. The campaign
checked 218,669 transaction items, each before its clock change, after that change,
and after its held interval: 656,007 checked observations in total. It included
62,000 randomized scheduled operations, and every applicable mandatory goal passed.

Verilator `--lint-only --timing -Wall` passed all 31 profiles without warnings or
waivers. Fourteen temporary RTL defects were rejected, including transposed graph
indices, invalid-source leakage, lost flush/hold priority, reset on payload,
ignored capture/enable controls, and 1 ps pulses on all three output buses and both
registered-state buses. Pulse defects failed the continuous waveform assertions.

A focused asynchronous profile with seed 56 and 1000 random operations passed
when launched from `/tmp`. Direct Makefile discovery and the port-only configuration
also passed; `make -n` preserved existing evidence. The 31 existing synthesis/power
flow tests passed with their tool stubs. Native VCS remains `NOT_RUN` because its
executable was unavailable locally.

The complete campaign is `build/validation/bypass-network-final/summary.json`.
Lint and defect-check evidence live beside it under `bypass-network-lint` and
`bypass-network-mutations`. Reports include matching RTL/component/dependency
hashes, and build artifacts remain ignored by Git.
