# Synchronous array generator

`generate.py` implements the Array-Single-Cluster bring-up and two-cluster Array-MVP
profiles from `specs/mosaic-blocks/mosaic-array/README.md`. These are functional RTL
profiles; they are not a balanced-array or physical-design release.

```sh
make array-generate
make array-generate ARRAY_DESCRIPTOR=/absolute/path/to/array.toml
```

The descriptor declares every cluster ID, coordinate, SRAM geometry and reserved
NoC boundary lane. The qualified composition is three BCTs and one MST per 2×2
cluster, four local contexts, uniform SRAM geometry, and one common synchronous
clock/reset. The supplied MVP uses 512 bytes of SRAM per cluster. The native cluster
generator enforces supported power-of-two bank/word geometries. A one-cluster
descriptor selects `profile = "Array-Single-Cluster"`, `cols = 1`, and one cluster.

Generation creates the array wrapper, specialized native cluster wrappers and
manifests, an ordered relative `sources.f`, `ports.json`, dependency/generator hashes
and architecture tables. Edit the TOML or generator; regenerate checked-in outputs.
No dependency JSON loader is needed. Each native package must use its cluster's
manifest hash, not the outer array hash.

Array mask bits, packed port lanes and runtime records follow descriptor list order.
Logical cluster IDs and coordinates are independent of that order. NoC router nodes
and endpoint slots follow the generated endpoint table; the logical cluster ID is
not a router index. Cluster-local tile IDs remain local to their configuration root.

The global NoC reuses actual routers and tile-network interfaces with four credit
VCs, depth eight, XY routing, 128-bit flits and 640-bit endpoint tokens. A token holds
a 32-bit data word, its complete 512-bit cluster envelope and 96 zero padding bits;
five flits transport it. The array gateway uses data VC0/channel0. Critical events
and configuration use separate control networks. Channel1 is unused. The emitted
traffic-class table describes the underlying NoC; it does not claim array-level
memory-request/response, barrier or QoS protocols on the other VCs.

The generated contract identifies supported features and unsupported profiles.
Balanced/four-cluster, heterogeneous/sparse, standalone services, global barriers,
CDC, asynchronous reset, resizing, migration, power gating, retention and DVFS fail
configuration or have no enabled interface. Native cluster clock gating is reused;
the array does not instantiate a power-manager adapter or infer physical cells.
Runtime-controller policy remains outside the array.
