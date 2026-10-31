# Cluster power manager generation

`generate.py` publishes the repository-local v1 ABI, Clocked platform tables,
source provenance and explicit physical signoff status. It does not run synthesis.

```sh
make cluster-power-manager-generate
```

The balanced profile has 16 tile regions, eight clock groups and 16 wake sources.
Every region instantiates the existing `tile_power_controller`. The root and group
clocks use the existing `clock_gate`; ordered reset release uses
`reset_synchronizer`; boundary valid/ready use separate `isolation_cell` instances.
All physical control requests originate in AON registers.

`cluster_power_manager_contract.py` owns the Python packing, parameter validation
and port dimensions. `cluster_power_manager_pkg.sv` publishes the matching fixed
SystemVerilog enums and packed records. Packed fields are listed least significant
first. The profile JSON describes all offsets, tables, controls, counter indices,
identity/recovery rules and unsupported features. Neither format requires an
external contracts repository or a dependency JSON file.

The generated power-state, reset, region, endpoint, clock-wrapper, transition,
emergency, counter and operating-point tables describe the implemented Clocked
profile. The single fixed point is a platform reference; its voltage, frequency
and energy remain uncharacterized. Retention state is empty. No table fabricates
watts, joules, break-even thresholds, PDK cells or physical signoff.

Protected Clocked uses the same physical sequence with parity or striped SECDED
for the policy, state, command, response and first-fatal records. Advanced
Retention, OFF, DVFS, SRAM low-power and asynchronous command-bus profiles fail
elaboration. Adding them requires released physical state/transition tables and
technology integration before their parameter guards can be removed.

See the [validation contract](../../val/mosaic_blocks/cluster_power_manager/README.md)
for exact interfaces, platform obligations and executable Python evidence.
