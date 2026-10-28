# CPT repository-local profile

`cpt_contract.py` owns public parameters and the shell interface catalog.
`cpt_sources.py` lists the production source closure. `generate.py` publishes the
implemented Local/Cluster inventory, behavior limits and source hashes in
`generated/profile.json`. The validation imports these production definitions.

Run `make cpt-generate`. The generated artifact describes a composition, not a
synthesis or physical release. Verification evidence is emitted separately by
`make cpt-regression SIM=icarus` (or `SIM=vcs` on the licensed server).

The body reuses native predicate, comparison, loop, event/barrier, register, atomic join,
arbitration, queue, formatting and counter blocks behind the released tile shell.
The [validation contract](../../val/mosaic_blocks/cpt/README.md) defines the local
context, command, event and action ABI and lists guarded unsupported profiles.
