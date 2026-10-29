# Cluster-MVP architecture generation

`mvp.toml` is the versioned source descriptor for the selected 2×2 composition.
`generate.py` validates placement and released dependencies, checks bindings against
the actual RTL port headers, and emits the concrete `cluster.sv`, architecture
manifest, public port catalog and source file list. `sources.py` owns the ordered
production closure. It is not a JSON dependency-loader manifest.

Run `make cluster-generate` after descriptor or generator changes. A generated
wrapper is reviewed with its descriptor, manifest and generator. Manual changes
to the wrapper are overwritten. Unsupported profile keys/classes fail generation.
Generated hashes record both implementation and generator revisions; file paths
and generation timestamps do not change architectural identity.

The [cluster validation README](../../val/mosaic_blocks/cluster/README.md) describes
package loading, lifecycle commands, memory ownership, metadata adaptation and the
scope of the Python-only validation. Generated domains and interfaces are physical
integration inputs; they are not timing, power, UPF or Design Compiler signoff.

The manifest also publishes event admission priority, the protected queue and
completion-directory contract, nonwrapping sequence semantics and event-fault
source 245. These properties describe actual instances; corrupt collector state
feeds the cluster lifecycle containment input. Generated RTL, implementation
hashes and package architecture fingerprints change together after this update.

The architecture remains the selected BCT/MST MVP. Other released tile classes,
the global NoC and cluster power manager require explicit class/domain adapters
and a separately generated composition before they can be enabled here.
