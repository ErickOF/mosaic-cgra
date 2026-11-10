# MOSAIC synthesis campaign

`campaign.py` runs reproducible Design Compiler sweeps and collects timing,
power, and area into one data set. It uses the same `make synth` flow as an
individual design, including the selected technology setup and constraints.

## Campaign matrix

The default plan contains 177 cases.

| Scope | Cases | Method |
|---|---:|---|
| BCT | 29 | One parameter at a time |
| VCT | 27 | One parameter at a time |
| SFT | 26 | One parameter at a time |
| MST | 20 | One parameter at a time |
| CPT | 30 | One parameter at a time |
| Arrays | 45 | Five application profiles at nine square sizes |

The array dimensions are `2`, `3`, `4`, `5`, `6`, `8`, `10`, `12`, and `16`.
The profiles are `balanced`, `ai`, `scientific`, `dsp_streaming`, and `control`.
These profiles define architecture mixes and tile parameters. They do not
replace workload mapping or activity-based application measurements.

Some nominally independent parameters constrain another geometry parameter.
Those cases record a companion override in `plan.json`. BCT widths below 32
bits use a multiplier operand equal to half the data width, and a CPT predicate
width follows its predicate lane count.

## Plan first

Generate and validate every case without checking out a DC license:

```sh
make synth-campaign-plan
```

For a small trial campaign:

```sh
python3 flows/synth/campaign.py plan \
  --families bct,array \
  --applications ai \
  --sizes 2,4 \
  --output build/synth/campaign-smoke
```

`--case-pattern` accepts shell-style case IDs, such as
`tile-bct-data-width-*` or `array-ai-*`.

## Run synthesis

The technology file must set `target_library` and `link_library` for Design
Compiler. Site-specific setup remains optional.

```sh
make synth-campaign \
  TECH_SETUP_TCL=/path/to/technology.tcl \
  DC_SETUP_TCL=/path/to/dc_setup.tcl
```

The default is one active DC process. Increase concurrency only when the
license server and machine capacity permit it:

```sh
make synth-campaign \
  TECH_SETUP_TCL=/path/to/technology.tcl \
  SYNTH_CAMPAIGN_JOBS=2 \
  SYNTH_CPUS=4
```

Successful cases are resumed automatically. The resume identity covers the
case architecture, RTL source tree, technology and DC setup files, constraints,
clock period, and DC executable. A mismatch is marked `stale` and rerun. Use
`--force` through `SYNTH_CAMPAIGN_ARGS` to rerun an otherwise matching case. A
filtered campaign should use a separate output directory so its plan does not
replace the complete plan.

## Outputs

The default output root is `build/synth/campaign`:

```text
plan.json                 validated case matrix
flavors/*.toml            complete array architecture inputs
bundles/                  immutable generated array RTL
runs/<case>/run.log       Design Compiler console log
runs/<case>/reports/      native DC reports
runs/<case>/result.json   result for one case
results.json              complete structured result set
results.csv               analysis-friendly flat table
summary.md                status and PPA ranges by family or profile
```

Reparse reports without rerunning synthesis:

```sh
make synth-campaign-collect
```

Area and timing retain the target library units. Power is normalized to watts.
The synthesis power report is vectorless unless the technology setup provides
switching activity. Use the gate simulation and PrimePower flow for
activity-based signoff power.

## Checks

The checks validate the 177-case matrix, all generated application flavors,
dependent parameter overrides, report parsing, power unit conversion, bundle
generation, and orchestration through a fake synthesis command:

```sh
make synth-campaign-test
```
