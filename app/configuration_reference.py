"""Render the editor's configuration reference from its production help catalog."""

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/gen'))
from flavor.model import catalog, starter


def cell(text):
    if isinstance(text, bool):
        return str(text).lower()
    return str(text).replace('|', '\\|').replace('\n', ' ')


def choices_text(values):
    if len(values) > 4 and list(values) == list(range(values[0], values[-1] + 1)):
        return f'{values[0]}–{values[-1]}'
    return ', '.join(map(str, values))


def render_reference():
    data = catalog()
    document = starter()
    lines = [
        '# CGRA configuration implications', '',
        'This reference uses the same help catalog as the local Flavor Studio editor. '
        'Defaults are editor defaults; legacy FU profiles supply defaults for unspecified enables.', '',
        data['guidance_scope'], '',
        '## How settings interact', '',
        '- Hardware settings are resolved before elaboration. Regenerate RTL and matching context '
        'images/software bindings after changing capabilities or record geometry. Runtime contexts '
        'cannot enable a FU omitted from the generated hardware.',
        '- More tiles or lanes expose resources; useful throughput also needs independent work, '
        'appropriate schedules, routing and sufficient memory/transport bandwidth.',
        '- The data fabric uses the widest native tile payload. A destination that cannot represent '
        'the upper payload/metadata bits stalls and reports a width error; transport does not '
        'automatically quantize, pack, narrow or reinterpret numerical formats.',
        '- BCT/VCT response-delay settings do not automatically retime arithmetic. SFT operations '
        'share an ordered issue engine, even when multiple FUs are present or a native polynomial '
        'pipeline is unrolled.',
        '- Clock gating controls clock activity. It does not provide power gating, retention, '
        'voltage scaling or a physical implementation.', '',
        '## CGRA and identity settings', '',
        '| Setting | Editor default | Meaning and implications |',
        '| --- | --- | --- |',
    ]
    for name, help in data['configuration_guidance'].items():
        default = (document['name'] if name == 'name' else document['cluster'].get(name, 'Per tile'))
        explanation = ' '.join([help['description'], *help['implications']])
        lines.append(f'| `{name}` | {cell(default)} | {cell(explanation)} |')
    lines += ['', 'For R rows and C columns, there are R × C tiles and '
        'R × (C − 1) + C × (R − 1) undirected neighbor links. Maximum Manhattan distance is '
        'R + C − 2 hops; configured paths and queueing determine actual transport latency. '
        'The 16-bit tile ID space bounds a complete grid to 65,536 unique tile identities.', '',
        'Scratchpad capacity is banks × words per bank × 8 bytes. Increasing bank depth adds '
        'capacity; increasing bank count also changes banking opportunities. With zero MSTs the '
        'scratchpad remains host-accessible, while native compute tiles still require stream routes '
        'rather than gaining direct SRAM clients.', '',
        '## Tile classes and independent FUs', '']
    for tile in data['tile_classes']:
        kind = tile['id']
        lines += [f'### {kind}: {tile["title"]}', '', tile['guidance']['description'], '']
        lines += [f'- {text}' for text in tile['guidance']['implications']]
        lines += ['', '| FU switch | Function | Enabled | Disabled |', '| --- | --- | --- | --- |']
        for unit in tile['functional_units']:
            lines.append(f'| `{unit["activation_parameter"]}` | {cell(unit["description"])} | '
                         f'{cell(unit["enabled"])} | {cell(unit["disabled"])} |')
        lines += ['', 'Shared helpers required by another selected operation can remain present. '
            'For example, a MAC can retain its internal multiplier while standalone multiplication '
            'is disabled. MST load/store engines retain their own address generators and formatters.', '',
            f'#### {kind} parameters', '']
        groups = {}
        for name, spec in tile['parameters'].items():
            groups.setdefault(spec['group'], []).append((name, spec))
        for group, entries in groups.items():
            lines += [f'**{group}**', '', '| Parameter | Default | Choices | Meaning and implications |',
                      '| --- | ---: | --- | --- |']
            for name, spec in entries:
                parts = [spec['description'], *spec['implications']]
                parts.extend(f'{value}: {text}' for value, text in spec.get('choice_help', {}).items())
                parts.extend(f'{value} is unavailable: {reason}'
                             for value, reason in spec.get('unavailable_choices', {}).items())
                lines.append(f'| `{name}` | {spec["default"]} | {choices_text(spec["choices"])} | '
                             f'{cell(" ".join(parts))} |')
            lines.append('')
        lines += [f'Native implementation: [{kind.lower()}.sv]'
                  f'(../src/rtl/mosaic_blocks/{kind.lower()}.sv).', '']
    lines += ['## Numerical formats and capacity examples', '',
        '- A 16-bit signed fixed-point value with 12 fraction bits has a step of 1/4096 and '
        'range −8 to 8 − 1/4096. Raising fraction bits at fixed width improves representable '
        'resolution while reducing integer range. Exact integer/bitwise operations do not '
        'implicitly rescale their bit patterns.',
        '- A VCT with four lanes and 32-bit accumulators has a 128-bit native payload. Raising '
        'accumulators to 64 bits produces a 256-bit payload and can widen every data link in the '
        'grid, even if element width remains eight bits.',
        '- A LUT address width of four selects 16 entries per bank; five selects 32. With 16-bit '
        'outputs that is 256 versus 512 nominal data bits per bank, before protection and bank '
        'metadata. The native SFT allocates context-depth × LUT-bank physical slots.',
        '- Eight banks of 1,024 64-bit words hold 64 KiB. Doubling words per bank doubles capacity '
        'without creating more banks. Doubling bank count changes both capacity and banking.',
        '- Parity detects odd-bit corruption without correction. SECDED corrects one-bit and '
        'detects two-bit errors per protected codeword/stripe, using more redundant storage and '
        'decoding logic. Neither replaces ownership or protocol validation.', '',
        '## Regenerate this reference', '',
        '```sh', '.venv/bin/python app/configuration_reference.py', '```', '',
        'The editor provides current-value calculations and expandable implications beside '
        'controls. Those calculations describe nominal geometry and formats, not measured '
        'performance or physical implementation results.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).with_name('configuration.md'))
    args = parser.parse_args()
    args.output.write_text(render_reference(), encoding='utf-8')
    print('Generated', args.output)


if __name__ == '__main__':
    main()
