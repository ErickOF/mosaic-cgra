# MOSAIC Flavor Studio

A local tile-grid editor backed by TOML and production MOSAIC RTL. The server,
UI, examples and application checks live here; `src/gen/flavor` owns native
interface validation and portable RTL generation.

## Run locally

Use Python 3.12 or newer. The server uses only the standard library; Node.js,
a frontend build and cloud services are unnecessary.

```sh
cd mosaic-cgra
python3.12 app/server.py
# Open http://127.0.0.1:8765
```

With the repository environment:

```sh
make setup PYTHON=python3.12  # Once, if .venv is missing
make app
make app APP_PORT=8766 APP_OUTPUT_ROOT=/path/to/local/builds
```

`make app` uses `PYTHON_BIN`, normally `.venv/bin/python`. Stop it with Ctrl+C.
The server binds to `127.0.0.1` and accepts same-origin local requests. All browser
assets are local. An occupied port produces a short error with an alternative
command. `make app APP_PORT=0` selects a free port and prints its URL.

## Configure a flavor

1. Enter independent positive **Rows** and **Columns**. Single tiles, single rows,
   single columns and rectangular grids are supported; dimensions are not presets.
2. Place **BCT, MST, VCT, SFT or CPT** at any position. Select a palette class and
   click cells, or drag tiles to swap positions while preserving IDs and parameters.
   Press Esc for selection mode. Zero, one or multiple MSTs are supported.
3. Select a tile and enable or disable each **Functional unit** independently.
   Configure each enabled FU's settings
   in its own inspector section. Settings belong to that tile only.
4. Resolve validation issues, then select **Generate RTL** and **Download RTL**.
5. **Save TOML**, **Open TOML**, and the **TOML** source tab round-trip the same
   architecture. Apply or discard source edits before editing the visual layout.

Undo/redo covers architecture edits. Applied drafts are saved in browser local
storage for that origin. Unapplied TOML text is not retained. Save TOML in version
control for a portable source of truth; export normalizes comments and whitespace.

Examples: [balanced_compute.toml](examples/balanced_compute.toml) configures private
BCT RF/latency settings; [heterogeneous.toml](examples/heterogeneous.toml) contains
all five classes in a 2×3 grid and custom nonlinear FU settings;
[independent_fus.toml](examples/independent_fus.toml) selects one independent FU
per tile, including reciprocal without polynomial or RSQRT.

## Understand configuration implications

Grid, memory, identity and clock controls now include expandable explanations.
The tile inspector explains each tile class and independent FU selection, then
shows the meaning and trade-offs of every parameter. Where applicable, it also
calculates the currently selected payload width, fixed-point step/range headroom,
table size, counter range or loop-frame size. Expanded help stays open as values
change, and works with keyboard navigation and touch.

The [configuration reference](configuration.md) covers every editable parameter,
FU switch and descriptor field using the same production help catalog. It explains
capability, resource, precision, range, latency, buffering, protection and mapping
implications. These are qualitative RTL effects; physical area, frequency, power
and energy still require technology-specific implementation and measurement.

Circular addressing is marked unavailable because the released MST requires a
separate adapter for that mode; imported descriptors requesting it are rejected
before generation. The current 128-bit-stream/64-bit-memory adapter also requires
width conversion.

## Tile and FU settings

| Tile | Functional units and representative settings |
| --- | --- |
| BCT | ALU width, latency, saturation/min-max; multiplier operand width and latency; MAC latency and accumulator count; RF, queues, bypass and protection |
| MST | Load/store FIFO depths; address-generation modes; alignment, width/element conversion; command, FIFO, control and context protection |
| VCT | Lane count, element/accumulator/slice widths and latency; multiplier/MAC enable and latency; reduction/dot latency; vector/scalar accumulators, VRF and protection |
| SFT | Number formats; LUT geometry/interpolation/pipeline; polynomial degree/banks/coefficients/architecture; reciprocal and RSQRT internal precision/seeds; exponential range/table/pipeline; reduction geometry and storage |
| CPT | Predicate lanes/depth; loop depth, index/trip widths and exported levels; event/wait/barrier resources; action queues, outstanding operations and timeouts; control registers and protection |

Every FU checkbox is independent. For example, an SFT can contain reciprocal
without LUT, polynomial, RSQRT or exponential; a BCT can contain MAC without the
standalone ALU or multiplier; a VCT can contain dot product without reduction.
All compute FUs can also be disabled. The generated native RTL uses conditional
elaboration, and configuration/command validation rejects unavailable operations.

MST checkboxes select complete load and store engines. Address generators and
formatters are internal channel components with configurable settings. Likewise,
a selected MAC may retain an internal multiplier/add helper even when standalone
multiply/ALU operations are disabled. Tile shells, routing, storage and control
infrastructure remain available.

`ENABLE_*` parameters record explicit choices in TOML, the resolved descriptor
and the exported manifest. VCT retains `SUPPORT_MUL` / `SUPPORT_MAC` for its lane
multiply and MAC enables. Existing `FU_PROFILE` values remain valid in imported
TOML and native RTL: they supply defaults only for unspecified enables. An explicit
enable always takes precedence, including when it enables a FU above the old
profile or disables a unit below it. The editor saves each checkbox directly and
does not raise or lower peer profiles.

For example, use these tile parameters for a reciprocal-only SFT:

```toml
[cluster.tiles.parameters]
ENABLE_ALU = 0
ENABLE_MULTIPLIER = 0
ENABLE_LUT = 0
ENABLE_POLYNOMIAL = 0
ENABLE_RECIPROCAL = 1
ENABLE_RSQRT = 0
ENABLE_EXPONENTIAL = 0
ENABLE_REDUCTION = 0
ENABLE_FORMATTER = 0
ENABLE_ACCUMULATOR = 0
RECIP_INTERNAL_WIDTH = 32
```

The editor checks dependent constraints: multiplier precision must fit the ALU,
vector pipeline depth must cover its arithmetic paths, fixed-point fractions and
coefficients must fit their representations, and queues must cover outstanding
operations. Invalid combinations block generation and identify the tile.

Native tile IDs use 16 bits, allowing up to 65,536 distinct tiles. CPT producer
IDs must also fit its eight-bit native event-record field (0–255). These are
hardware identity constraints, not grid-size presets. Each position has exactly
one tile, all tiles share a synchronous clock/reset domain, and contexts have
depth four. Hardware parameters are separate from runtime context programs.

## Generated hardware and interfaces

The `Configurable` profile instantiates actual native tile modules, one released
`local_switch` per position and real shared `banked_scratchpad` SRAM. Each MST has
an owned `cluster_memory_bridge` client; an additional host client initializes
memory and reads results. SRAM words are 64 bits: capacity is
`banks × words_per_bank × 8` bytes. Geometry currently supports power-of-two
banks/words, up to 16 banks and 16 B–1 MiB total.

The generated top is `cluster`. Its manifest and `ports.json` are the interface
reference:

- `i_clk`, `i_rstb`, `i_enable`, `i_test_mode`, `i_scan_enable` are common controls.
  Keep `i_enable` high during configuration, runtime transactions and traffic;
  with clock gating enabled it also requests the fabric clock. `o_cluster_id`
  identifies the configured architecture.
- `i_tile_<id>_*` / `o_tile_<id>_*` preserve each tile's native configuration,
  runtime, predicate, event, power and status interfaces. A host controls these
  interfaces directly. Local FU context/instruction formats remain the native
  module formats.
- `i_route_<id>_*` / `o_route_<id>_*` configure and monitor local switches.
  Slots 0 and 1 connect the native tile; 2, 3, 4 and 5 are north, east, south and
  west. CPT has one native data output, so the unused second TX slot is tied idle.
- `*_boundary_<row>_<col>_<direction>_*` expose edge ingress/egress streams.
- `*_memory_*` expose SRAM region/power/event management; `*_memory_host_*` expose
  the host client. Both SRAM permissions and native MST regions must be configured
  before issuing memory operations.

The mesh word is as wide as the widest selected native tile. Narrower native
outputs are zero-extended. A narrower receiver accepts a token only when all
upper data and metadata bits are zero; otherwise it holds the token and asserts
`o_tile_<id>_width_error_<channel>`. No payload is silently truncated. Compatible
formats and routes must be programmed by the host/compiler; selecting a flavor
does not generate a workload mapping.

The older `Cluster-MVP` configuration/lifecycle interface remains available to
CLI users with original MVP descriptors. Opening those files in the visual editor
upgrades them to `Configurable`, whose top-level controls are the native interfaces
above. The retained `lifecycle_timeout` TOML field belongs to legacy compatibility;
the configurable fabric uses native per-tile runtime/control protocols.

## Portable export

Outputs go to `build/flavors/<name>/<build-id>/`:

- `rtl/cluster.sv` and copied `rtl/common`, `rtl/basic`, `rtl/building_blocks`, and
  `rtl/mosaic_blocks` dependencies.
- `sources.f`, an ordered relative source list usable from the bundle directory.
- `flavor.toml`, `cluster.toml`, `resolved.json`, with effective private settings.
- `manifest.json`, including actual per-instance parameters, widths, boundaries,
  control interface policy and SRAM client ownership; `ports.json` lists port widths.
- `generation.json`, recording source/artifact hashes and build/architecture IDs.

ZIP exports are deterministic. Generation atomically publishes complete bundles,
checks cached artifacts before reuse/download, and leaves the checked-in default
cluster wrapper unchanged. The build identity covers resolved architecture and
production RTL/generator fingerprints. Generation records validation as `NOT_RUN`;
validation results are separate job artifacts tied to their tested build ID.

```sh
make flavor-validate FLAVOR=app/examples/heterogeneous.toml
make flavor-generate FLAVOR=app/examples/heterogeneous.toml
```

Synthesis, timing and physical signoff remain later Design Compiler work.

## Python/PyUVM validation

Use `make setup` for cocotb/PyUVM. Install Icarus (`iverilog`, `vvp`) or licensed
VCS, on `PATH` or via `ICARUS_BIN_DIR` / `VCS_BIN_DIR` before starting the app.
Unavailable simulators are disabled for validation.

**Run PyUVM** checks the actual exported bundle:

1. Independent Python descriptor/ABI model tests.
2. Every assembled tile's identity, class, runtime allocation and native
   configuration query, through public ports.
3. Full-width row/column traffic under randomized backpressure, shared SRAM
   provisioning/write/read, and incompatible-width containment.
4. The native BCT/MST/VCT/SFT/CPT PyUVM agents and numerical scoreboards,
   compiled with the exact selected FU parameters. Legacy profiles run the full
   existing campaigns. Custom subsets execute every enabled FU, reject disabled
   operations and check the elaborated hardware branches. Identical hardware
   profiles share a functional run; every tile is checked in the assembled fabric.

These checks cover native operations and fabric transport separately; they do not
claim an application mapped across heterogeneous FUs. A pass requires matching
coverage goals, parameter values, manifest, seed and stable verification sources.
Results/logs are stored under `build/flavors/jobs/<job-id>/`. Jobs are serialized,
cancelable and bounded to 30 minutes. Reload reconnects to the last 20 jobs in the
server session; stopping the server cancels work. Files survive server restarts.

```sh
.venv/bin/python src/gen/flavor/verify.py \
  --bundle build/flavors/<name>/<build-id> \
  --output build/flavor-validation --sim icarus
```

## Check the app

```sh
make app-test
make app-flavor-regression SIM=icarus
```

The first target checks documents, private FU settings, portable exports, HTTP,
startup errors and job snapshots. The regression covers a single BCT, a 2×3
heterogeneous grid, a 9×1 column, multiple MSTs and all five classes with higher FU
profiles, isolated FUs, empty FU selections and private arithmetic settings. It uses Python/PyUVM only.

Optional browser checks:

```sh
.venv/bin/python -m pip install -r app/requirements-checks.txt
.venv/bin/python -m playwright install chromium
make app-browser-check
# Also wait for a real validation job (Icarus required):
.venv/bin/python app/checks/browser.py --run-pyuvm
```

Browser checks cover all tile classes, rectangular resizing, FU selection and
private settings, persistence, drag/drop, undo/redo, TOML and RTL downloads.
Screenshots are saved in `build/app-checks/browser/`.
