# Runtime platform contract

`make runtime-controller-generate` publishes `generated/profile.json` for the
balanced Static/Partitioned-capable v1 implementation. The default hardware profile
is Partitioned. The JSON contains packed-record offsets, enum values, cluster
capability/compatibility/connectivity tables, configured owner IDs, resource and
scheduler rules, action/reset contracts, source hashes and deferred signoff status.

`runtime_controller_contract.py` is the production normalized adapter ABI;
`runtime_controller_sources.py` is its ordered RTL closure. `generate(parameters,
output)` validates geometry and writes a reproducible profile for a custom platform.
The regression calls this API for every elaborated configuration and checks the
actual parameter and public port values in simulation.

Adapters must implement the authoritative terminal, enforcement and clean-reset
assumptions in the
[validation contract](../../val/mosaic_blocks/runtime_controller/README.md).
A generated manifest records those integration obligations; it does not prove
external service enforcement or physical synthesis/timing properties.
