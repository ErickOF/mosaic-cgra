# SFT local profile contract

`contract.py` owns the versioned parameter defaults, context field offsets and
source graph. `sft_sources.py` owns the ordered production RTL source closure.
Validation imports these definitions, and checks RTL defaults and public ports.
The mathematical result oracles remain independent of the RTL datapaths.

```sh
make sft-generate
.venv/bin/python src/gen/sft/generate.py --profile 3 --output build/sft-transformer.json
```

The generator publishes enabled FUs, supported formats, context fields, source
connectivity, queue/retirement policy, numerical-model IDs, dependency hashes and
unperformed signoff work. It rejects uncharacterized FP and RDU profiles and invalid
reduction/credit/image geometry. The RTL supplies strict elaboration guards too.

The default generated profile is Balanced. The [validation README](../../val/mosaic_blocks/sft/README.md)
describes programming, numerical interpretation, metadata, runtime behavior,
Python-only evidence, and the current implementation limits.
