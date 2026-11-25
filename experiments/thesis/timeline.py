"""Render an inspectable SVG timeline directly from observed domain transitions."""

from html import escape
import json
from pathlib import Path


def render(trace_path, destination, title):
    trace = json.loads(Path(trace_path).read_text())
    power = [e for e in trace if e["kind"] == "power"]
    if not power:
        return
    selected = sorted({e["tile"] for e in power})
    end = max(e["cycle"] for e in trace) + 1
    left, width = 140, 1000
    height = 100 + len(selected) * 44
    x = lambda cycle: left + width * cycle / end
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="{height}" '
           f'viewBox="0 0 1180 {height}">', '<rect width="100%" height="100%" fill="white"/>',
           '<g font-family="sans-serif" font-size="12" fill="#202c3b">',
           f'<text x="20" y="22" font-size="16">{escape(title)}</text>',
           '<text x="20" y="42">Observed RTL supply model: green = powered, '
           'gray = OFF; orange line = isolated; labels = pending packets.</text>']
    for index, tile in enumerate(selected):
        y = 70 + 44 * index
        events = [e for e in power if e["tile"] == tile]
        svg.append(f'<text x="20" y="{y + 12}">Tile {tile}</text>')
        for offset, event in enumerate(events):
            stop = events[offset + 1]["cycle"] if offset + 1 < len(events) else end
            start = event["cycle"]
            powered, isolated = event["state"][1:]
            color = "#54a879" if powered else "#c8cdd5"
            svg.append(f'<rect x="{x(start):.2f}" y="{y}" '
                f'width="{max(0.5, x(stop) - x(start)):.2f}" height="16" fill="{color}">'
                f'<title>cycle {start}–{stop}; power={powered}, isolate={isolated}; '
                f'pending={event["pending_packets"]}; phase={escape(event["phase"])}</title></rect>')
            if isolated:
                svg.append(f'<path d="M{x(start):.2f},{y + 20} H{x(stop):.2f}" '
                           'stroke="#bd5d15" stroke-width="3"/>')
    y = height - 18
    for tick in range(6):
        cycle = end * tick // 5
        svg.append(f'<text x="{x(cycle):.2f}" y="{y}">{cycle}</text>')
    svg += [f'<text x="20" y="{y}">Reference cycles (10 ns)</text>', '</g>', '</svg>']
    Path(destination).write_text("\n".join(svg) + "\n")
