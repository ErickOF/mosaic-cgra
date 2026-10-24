# Tile network interface verification

This Python-only PyUVM suite validates
[`tile_network_interface.sv`](../../../rtl/building_blocks/tile_network_interface.sv)
against the [TNI specification](../../../../../specs/building-blocks/mosaic-tile-network-interface/README.md).
The simulator elaborates the actual RTL top. No verification SystemVerilog, synthesis,
formal, lint, timing, or power flow is enabled by this target. Design Compiler synthesis
is deferred.

```sh
make tile-network-interface-regression SIM=icarus PYTHON_BIN=.venv/bin/python
make tile-network-interface-regression  # VCS in the licensed server environment
make pyuvm SIM=icarus COCOTB_TOPLEVEL=tile_network_interface
```

The regression runs 61 representative profiles, each with directed traffic followed
by 2,000 seeded random cycles. It crosses tile widths 32/64/128/256 with flit widths
32/64/128, both flow modes, and parity on/off. Channel counts 1/2/4/8, VC counts
1/2/4, depths 1/2/4/8, and both reset styles vary through that matrix. Additional
profiles cover 40:24 and 24:16 bit ratios, 8:128 padding, non-power-of-two channel,
VC and queue counts, narrow metadata, epoch wrap, nonzero node identity, and custom
class mappings, including classes sharing one VC and unused VCs. This is a
representative matrix, not a Cartesian cross of every parameter.

The Python runner also checks 97 illegal parameter configurations. A successful
probe must fail elaboration with the module's named parameter guard. A compiler
error unrelated to that guard does not count as a pass. The simulator's compiler
is invoked by these Python probes; no separate RTL lint or synthesis is run.

Select profiles directly when debugging:

```sh
.venv/bin/python src/val/building_blocks/tile_network_interface/run_tile_network_interface_regression.py \
    --sim icarus --build-dir build/icarus/tile_network_interface/selected \
    --case edge0_flow0_r0 --case d256_f32_flow1_parity1
```

`TILE_NETWORK_INTERFACE_SEED`, `TILE_NETWORK_INTERFACE_RANDOM_CYCLES` (minimum
1,000), and `TILE_NETWORK_INTERFACE_REGRESSION_BUILD` configure the Make target.
`TILE_NETWORK_INTERFACE_JOBS` controls concurrent processes (default four with
Icarus, one with VCS). The direct `pyuvm` target runs the default RTL geometry;
parameterized runs should use the runner, which sets matching HDL overrides and
Python widths. `--compile-args`, `--sim-args`, and `--sim-bin-dir` are available.

## Structure and checking

- `transaction.py` and `config.py`: public port schema, sequence items and widths.
- `sequences.py`: directed/adversarial cases and reproducible random traffic.
- `driver.py`: clocked tile sources and a separate NoC peer. The peer holds RX
  records through valid-ready stalls, limits current-epoch credit launches, and
  returns TX credits after random delays. Explicit negative tests violate credits.
- `monitor.py`: passive real-port observations before, at, and after rising edges,
  and during held clocks.
- `model.py` and `scoreboard.py`: expand accepted TX beats into exact flit streams;
  reconstruct RX packets independently using per-VC contexts and ordered endpoint
  completion deques. The RTL instead uses predecessor masks for cross-VC ordering.
  Every public output is compared, including invalid zero values, events,
  occupancies, credit counts, sticky diagnoses, and configuration state.
- `coverage.py`: required functional goals and exact beat/flit ownership accounting.
- `agent.py`, `env.py`, and `test_tile_network_interface.py`: normal UVM component
  composition using the shared `mosaic_uvm` library.

Directed checks include all TX channels, classes and RX endpoints, sparse keeps,
stream-last and metadata, packet arbitration, every valid-ready fragment stall,
credit exhaustion/return, full queues, interleaved VCs, simultaneous traffic,
malformed head/tail/index/sideband/padding, parity corruption by field, rejected
configuration, disabled channels, context mismatches, stale epochs, unknown
controls, drain, flush and reset. Credit-mode overflow tests fill a VC, violate
its receive credit limit, check fatal admission blocking, then recover by flush.
A corrupted VC can split a packet between contexts; coordinated flush clears
those quarantined partial packets. Random traffic also injects corruption,
backpressure, drains, coordinated flushes, and context changes.

Each profile must end empty. Accepted TX beats equal completed plus canceled
beats; their expanded flits equal launched plus canceled flits. Completed legal
RX packets equal delivered plus canceled beats. Admitted FIFO flits equal popped
plus canceled flits. Partial packets are accounted at the flit level until they
complete. Stale flits bypass current-epoch ownership and return no current credit.

The build directory contains individual JUnit results, coverage JSON, simulator
logs and parameter snapshots, plus `summary.json`. The campaign checks that all
requested tests ran once, every mandatory goal passed, accounting balanced, and
source hashes stayed unchanged. Evidence identifies seeds and hashes for RTL,
dependencies, Python components, shared helpers and the Makefile.

## RTL composition and integration

The TNI reuses `event_barrier_queue` over common `fifo` storage for TX, per-VC RX,
and ejection queues. The wrapper provides synchronous flush without reset gating.
Its state helper uses common DFFs; three common round-robin arbiters select TX
packets, receive processing and completed packets. Common counters implement
credits and epoch; common parity protects all flit fields when enabled. The FIFO
also reuses operand isolation. No clocks are generated.

Geometry-dependent packed records stay local to the RTL. Flow and error enums
live in `tile_network_interface_pkg.sv`. As requested for the preceding modules,
encodings are repository-local: there is no external `mosaic-contracts` package
or dependency manifest. Payload bit zero and channel/VC zero occupy the least
significant bits. A class maps through `TRAFFIC_CLASS_TO_VC[t*VC_WIDTH +: VC_WIDTH]`;
the override must have exactly `NUM_TRAFFIC_CLASSES * VC_WIDTH` bits.

Reset disables all channels until legal configuration. Configuration is atomic
and quiescent; its handshake takes priority over traffic. Disabled TX offers are
consumed as diagnosed drops. `i_error_clear` only clears a quiescent interface
with no simultaneous new error. Flush preserves configuration and sticky diagnosis,
clears fatal admission state, increments epoch on each asserted clock edge, and
reinitializes credits. Credit flush must be coordinated with the remote endpoint.

A queued TX beat first becomes visible after its enqueue edge. With no contention
or stalls, its fragments launch on the next `FLITS_PER_PACKET` rising edges.
RX admission, VC processing, completion staging and the destination FIFO are
registered stages: a single-flit packet admitted at edge t becomes tile-valid
after edge t+2 and can transfer at edge t+3. For multi-flit packets without stalls,
substitute the final-flit admission edge for t. Arbitration and downstream stalls
can extend latency without a finite maximum. Single-flit RX completion staging
adds a processing bubble per VC; other VCs can use intervening service cycles.
Continuous TX can launch one flit per clock; packet throughput is at most one beat
per `FLITS_PER_PACKET` launches, subject to credit availability and backpressure.
These are RTL simulation timing rules, not physical timing or power estimates.
