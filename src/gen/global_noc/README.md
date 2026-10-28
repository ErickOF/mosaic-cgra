# Global NoC generation

`global_noc_contract.py` is the repository-local v1 layout and parameter catalog;
`global_noc_sources.py` is the ordered production source closure. No dependency
JSON or verification fixture is needed to elaborate the design.

`make global-noc-generate` publishes `generated/profile.json`: coordinates,
directional links, endpoint channels, parameter/layout identity, metadata fields,
router-channel dependency graph, integration assumptions, unsupported settings and
source SHA256 hashes. `generate.generate(parameters, output)` publishes each
regression profile identically. The compiled layout signature is not a security
hash; manifests additionally identify their content and sources with SHA256.

The routing DAG is a structural router-channel check. Endpoint transaction,
completion/fence, power and lifecycle dependencies still require an integrating
system proof. See the [validation ABI](../../val/mosaic_blocks/global_noc/README.md).
