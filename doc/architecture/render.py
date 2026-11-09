"""Render source-backed MOSAIC architecture figures without a graphics service.

SVG generation uses Python 3.12's standard library. ``--export`` additionally
uses the repository's optional Playwright/Chromium browser-check installation
to export PNG images and a two-page PDF, and check text placement.
"""

import argparse
from html import escape
from pathlib import Path
import tomllib


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
WIDTH = 1800
HEIGHT = 1500
INK = "#14263e"
MUTED = "#52657c"
LINE = "#ccd7e4"
BLUE = "#235cb2"
TEAL = "#087f82"
PURPLE = "#7340b4"
AMBER = "#a15a0a"
PINK = "#a33168"
PALE = {
    BLUE: "#eef4ff",
    TEAL: "#eaf8f5",
    PURPLE: "#f5effc",
    AMBER: "#fff5e8",
    PINK: "#fceff5",
    MUTED: "#f4f7fa",
}
TILE_COLOR = {"BCT": BLUE, "VCT": TEAL, "SFT": PURPLE, "MST": AMBER, "CPT": PINK}


class Figure:
    def __init__(self, name, title, description):
        self.name = name
        self.parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
            f'viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-labelledby="title desc">',
            f'<title id="title">{escape(title)}</title>',
            f'<desc id="desc">{escape(description)}</desc>',
            '<defs>',
        ]
        for color in (BLUE, TEAL, PURPLE, AMBER, PINK, MUTED):
            key = color.removeprefix("#")
            self.parts.append(
                f'<marker id="arrow-{key}" viewBox="0 0 10 10" refX="8" refY="5" '
                'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
                f'<path d="M 0 0 L 10 5 L 0 10 Z" fill="{color}"/></marker>'
            )
        self.parts.extend([
            '</defs>',
            '<g font-family="Arial, Helvetica, sans-serif">',
            f'<rect width="{WIDTH}" height="{HEIGHT}" fill="#ffffff"/>',
        ])

    def rect(self, x, y, width, height, *, fill="white", stroke=LINE, radius=16,
             dashed=False):
        pattern = ' stroke-dasharray="7 6"' if dashed else ""
        self.parts.append(
            f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"{pattern}/>'
        )

    def text(self, x, y, text, *, size=18, color=INK, weight=400, anchor="start"):
        self.parts.append(
            f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{escape(str(text))}</text>'
        )

    def lines(self, x, y, lines, *, size=18, step=26, color=MUTED):
        for index, line in enumerate(lines):
            self.text(x, y + index * step, line, size=size, color=color)

    def path(self, points, *, color=TEAL, width=3, arrows=None, dashed=False):
        path = "M " + " L ".join(f"{x} {y}" for x, y in points)
        attributes = f'stroke="{color}" stroke-width="{width}" fill="none"'
        attributes += ' stroke-linecap="round" stroke-linejoin="round"'
        if dashed:
            attributes += ' stroke-dasharray="7 6"'
        key = color.removeprefix("#")
        if arrows in ("end", "both"):
            attributes += f' marker-end="url(#arrow-{key})"'
        if arrows == "both":
            attributes += f' marker-start="url(#arrow-{key})"'
        self.parts.append(f'<path d="{path}" {attributes}/>')

    def pill(self, x, y, width, label, *, color=BLUE):
        self.rect(x, y, width, 30, fill=PALE[color], stroke=PALE[color], radius=15)
        self.text(x + width / 2, y + 20, label, size=14, weight=700,
                  color=color, anchor="middle")

    def card(self, x, y, width, height, title, lines, *, color=BLUE, number=None):
        self.rect(x, y, width, height, fill=PALE[color], stroke=PALE[color])
        tx = x + 20
        if number:
            self.rect(tx, y + 17, 34, 30, fill=color, stroke=color, radius=8)
            self.text(tx + 17, y + 38, number, size=16, weight=700,
                      color="white", anchor="middle")
            tx += 46
        self.text(tx, y + 39, title, size=21, weight=700, color=color)
        self.lines(x + 20, y + 70, lines, size=18, step=25)

    def header(self, page, title, subtitle):
        self.text(48, 43, "MOSAIC / HARDWARE ATLAS", size=15, weight=700, color=TEAL)
        self.text(1752, 43, page, size=15, color=MUTED, anchor="end")
        self.text(48, 102, title, size=43, weight=700)
        self.text(48, 139, subtitle, size=21, color=MUTED)

    def save(self):
        self.parts.extend(['</g>', '</svg>'])
        destination = HERE / f"{self.name}.svg"
        destination.write_text("\n".join(self.parts) + "\n", encoding="utf-8")
        return destination


def contracts():
    example = tomllib.loads((ROOT / "app/examples/heterogeneous.toml").read_text())
    grid = example["cluster"]
    # This is an illustrated flat-grid example, rather than an arbitrary netlist viewer.
    if (grid["rows"], grid["cols"]) != (2, 3):
        raise ValueError("Update the flavor figure layout for the changed example")
    expected = {
        (0, 0): "BCT", (0, 1): "MST", (0, 2): "VCT",
        (1, 0): "SFT", (1, 1): "CPT", (1, 2): "BCT",
    }
    layout = {(tile["row"], tile["col"]): tile["class"] for tile in grid["tiles"]}
    if len(grid["tiles"]) != 6 or layout != expected:
        raise ValueError("Update the flat-grid drawing and MST memory path for this placement")
    return grid


def draw_tile(figure, x, y, width, height, tile):
    kind = tile["class"]
    color = TILE_COLOR[kind]
    purpose = {
        "BCT": "Scalar compute",
        "MST": "Memory / streams",
        "VCT": "Vector compute",
        "SFT": "Special functions",
        "CPT": "Control / coordination",
    }[kind]
    figure.rect(x, y, width, height, fill=PALE[color], stroke=color)
    figure.text(x + 18, y + 32, f"{kind} · tile {tile['id']}", size=24,
                color=color, weight=700)
    figure.text(x + 18, y + 61, purpose, size=18)
    figure.text(x + 18, y + 86, "Native tile + local switch", size=16, color=MUTED)


def system_figure(grid):
    figure = Figure("mosaic-top", "MOSAIC single-grid CGRA architecture", (
        "One continuous rectangular mesh connects BCT, MST, VCT, SFT and CPT tiles. "
        "Every position contains a native tile and a local switch. Shared banked SRAM "
        "has host access and a dedicated MST memory bridge. The illustrated 2 by 3 "
        "placement follows the heterogeneous flavor example. Host, external data/memory "
        "and clock sources surround the CGRA. A dashed group identifies the proposed "
        "host-facing adapter; the grid and native interfaces follow existing RTL."
    ))
    figure.header("01 / SINGLE-GRID CGRA", "One grid. Every tile configurable.", (
        "MOSAIC flat architecture · one R × C mesh · example placement includes all five tile types"
    ))
    figure.card(48, 177, 550, 116, "Host processor + software", [
        "Choose hardware, program contexts and routes",
        "Launch work and collect results through the adapter",
    ], color=BLUE)
    figure.card(630, 177, 600, 116, "System memory + visibility service", [
        "Application inputs, outputs and configuration images",
        "Platform-defined memory access and synchronization",
    ], color=TEAL)
    figure.card(1262, 177, 490, 116, "Clock, reset + test sources", [
        "One common functional clock / reset domain",
        "Optional shared gate controls fabric clock activity",
    ], color=MUTED)

    figure.rect(48, 352, 1704, 828, fill="#f8fafc", stroke="#9baec4", radius=22)
    figure.text(78, 391, "MOSAIC · single-grid CGRA", size=28, weight=700)
    figure.pill(1030, 367, 210, "R × C tile positions", color=TEAL)
    figure.pill(1254, 367, 240, "Independent FUs per tile", color=PURPLE)
    figure.pill(1508, 367, 214, "Example: 2 × 3 tiles", color=TEAL)

    figure.rect(80, 423, 506, 683, fill="#ffffff", stroke=MUTED, dashed=True)
    figure.text(100, 462, "Host-facing integration", size=25, weight=700)
    figure.text(100, 490, "Dashed group: proposed platform adapter", size=17, color=MUTED)
    figure.card(100, 515, 466, 113, "Configuration + routes", [
        "Write / validate tile context images",
        "Program each local switch through its native ports",
    ], color=PURPLE, number="01")
    figure.card(100, 648, 466, 113, "Runtime + context control", [
        "Allocate / start / suspend / drain native tiles",
        "Activate committed contexts at safe points",
    ], color=BLUE, number="02")
    figure.card(100, 781, 466, 113, "Memory + stream service", [
        "Host SRAM access and native MST DMA streams",
        "A platform adapter connects external memory",
    ], color=TEAL, number="03")
    figure.card(100, 914, 466, 113, "Events + observability", [
        "Collect completion / error records and status",
        "Expose counters and platform interrupt policy",
    ], color=AMBER, number="04")
    figure.lines(100, 1058, [
        "Grid exports native per-tile and route interfaces.",
        "Host transport is selected by platform integration.",
    ], size=17, step=26)

    figure.rect(690, 423, 1030, 683, fill="#ffffff")
    figure.text(714, 462, "05  Single R × C tile mesh", size=25, weight=700)
    figure.text(714, 492, "Neighbor links carry data through statically configured local switches.",
                size=19, color=MUTED)
    for tile in grid["tiles"]:
        draw_tile(figure, 732 + tile["col"] * 318, 550 + tile["row"] * 210,
                  252, 112, tile)
    for row in range(2):
        y = 606 + row * 210
        for col in range(2):
            x = 732 + col * 318
            figure.path([(x + 254, y), (x + 316, y)], arrows="both")
    for col in range(3):
        x = 858 + col * 318
        figure.path([(x, 664), (x, 758)], arrows="both")
    figure.path([(1176, 548), (1176, 525), (1688, 525), (1688, 1018), (1666, 1018)],
                color=TEAL, arrows="both", dashed=True)
    figure.text(1673, 954, "MST memory bridge", size=16, color=TEAL, anchor="end")
    figure.text(714, 919, "Perimeter streams connect external data producers and consumers.",
                size=19, color=TEAL)
    capacity = grid["scratchpad_banks"] * grid["scratchpad_bank_words"] * 8
    figure.card(714, 977, 950, 90, "Shared banked scratchpad", [
        f"{grid['scratchpad_banks']} banks × {grid['scratchpad_bank_words']} words × 8 B = "
        f"{capacity:,} B · host client + one memory client per MST",
    ], color=TEAL, number="06")
    figure.text(714, 1091, "Common mesh payload width follows the widest selected native tile.",
                size=18, color=MUTED)

    # These arrows summarize direct native interface bundles, not a new control NoC.
    for y, label, color, direction in (
        (571, "config", PURPLE, "end"),
        (704, "runtime", BLUE, "end"),
        (837, "data", TEAL, "both"),
        (970, "events", AMBER, "start"),
    ):
        points = [(588, y), (688, y)]
        if direction == "start":
            points.reverse()
            direction = "end"
        figure.path(points, color=color, arrows=direction)
        figure.text(638, y - 12, label, size=15, color=color, anchor="middle")
    for x, label, color in (
        (323, "Commands · responses · events", BLUE),
        (930, "Platform memory / data service", TEAL),
        (1507, "Clock / reset / test", MUTED),
    ):
        figure.path([(x, 295), (x, 350)], color=color,
                    arrows="end" if color == MUTED else "both", dashed=color == MUTED)
        figure.rect(x - 197, 307, 394, 25, fill="white", stroke="white", radius=6)
        figure.text(x, 325, label, size=16, color=color, anchor="middle")
    figure.text(80, 1144, "Blue: runtime/control", size=17, color=BLUE)
    figure.text(350, 1144, "Purple: configuration", size=17, color=PURPLE)
    figure.text(640, 1144, "Teal: data/memory", size=17, color=TEAL)
    figure.text(900, 1144, "Amber: events/status", size=17, color=AMBER)
    figure.text(1720, 1144, "Arrows summarize native interface bundles", size=16,
                color=MUTED, anchor="end")

    figure.text(48, 1221, "FROM A HARDWARE FLAVOR TO EXECUTING DATAFLOW", size=16,
                color=TEAL, weight=700)
    steps = [
        ("1  Choose hardware", ["Select dimensions, tile placement, FUs", "and private widths / storage settings."]),
        ("2  Program the grid", ["Write / validate contexts, configure", "routes and memory permissions."]),
        ("3  Execute", ["Launch the native tiles; stream data", "through the routed neighbor mesh."]),
        ("4  Collect results", ["Store outputs and observe completion.", "Software synchronizes external buffers."]),
    ]
    for index, (title, lines) in enumerate(steps):
        x = 48 + index * 438
        figure.card(x, 1243, 390, 121, title, lines, color=TEAL)
        if index < 3:
            figure.path([(x + 398, 1303), (x + 426, 1303)], color=TEAL, arrows="end")
    figure.text(48, 1411, "All tile positions belong to the same mesh. Hardware selection and runtime context programming are separate steps.",
                size=22, weight=700)
    figure.lines(48, 1443, [
        "Grid and native tiles follow the Configurable backend. The dashed host-facing adapter is an integration concept.",
        "Placement is logical connectivity. Silicon area, timing, power and energy require later technology-specific implementation.",
    ], size=18, step=27)
    return figure.save()


def flavor_figure(grid):
    figure = Figure("mosaic-tiles", "MOSAIC configurable fabric and native tiles", (
        "A configurable rectangular fabric contains BCT, MST, VCT, SFT and CPT tiles, "
        "one local switch per tile and shared banked SRAM. Every native tile composes "
        "a common shell with a specialized body. Independent FU enables and widths are "
        "design-time hardware choices; runtime contexts program the hardware that exists. "
        "Every tile belongs to one continuous mesh."
    ))
    figure.header("02 / TILES + FUs", "Build the CGRA around your workload", (
        "Local Configurable backend · independent rows and columns · any tile class at any position"
    ))
    for x, title, lines in (
        (48, "Grid + placement", ["Choose rows × columns and every tile class / ID.",
                                  "Coordinates determine neighbors and hop distance."]),
        (625, "Private hardware per tile", ["Choose FUs, widths, lanes, storage and protection.",
                                           "Settings belong to that individual tile instance."]),
        (1202, "Shared memory + clocks", ["Choose SRAM banking / depth and clock gating.",
                                         "One synchronous domain; four contexts per tile."]),
    ):
        figure.card(x, 177, 550, 114, title, lines, color=BLUE)

    figure.rect(48, 327, 948, 585, fill="#f8fafc")
    figure.text(76, 367, "Example fabric · one 2 × 3 tile grid", size=26, weight=700)
    figure.text(76, 396, "2 × 3 example from app/examples/heterogeneous.toml; dimensions are not presets.",
                size=18, color=MUTED)
    for tile in grid["tiles"]:
        x = 88 + tile["col"] * 300
        y = 445 + tile["row"] * 186
        draw_tile(figure, x, y, 248, 104, tile)
    for row in range(2):
        y = 497 + row * 186
        for col in range(2):
            x = 88 + col * 300
            figure.path([(x + 250, y), (x + 298, y)], arrows="both")
    for col in range(3):
        x = 212 + col * 300
        figure.path([(x, 551), (x, 629)], arrows="both")
    # Dedicated memory access is separate from the tile's routed stream ports.
    figure.path([(512, 443), (512, 421), (972, 421), (972, 842), (950, 842)],
                color=TEAL, arrows="both", dashed=True)
    figure.text(738, 439, "MST memory bridge", size=15, color=TEAL)
    figure.text(88, 775, "Edge streams and each tile's native control ports remain exposed.",
                size=18, color=MUTED)
    capacity = grid["scratchpad_banks"] * grid["scratchpad_bank_words"] * 8
    figure.card(88, 803, 860, 78, "Shared banked scratchpad", [
        f"{grid['scratchpad_banks']} banks × {grid['scratchpad_bank_words']} words × 8 B = "
        f"{capacity:,} B · one host client + one client per MST",
    ], color=TEAL)

    figure.rect(1024, 327, 728, 585, fill="#f8fafc")
    figure.text(1052, 367, "Inside every native tile", size=26, weight=700)
    figure.card(1052, 399, 672, 66, "Native configuration / runtime / predicate / event ports",
                [], color=BLUE)
    figure.path([(1388, 467), (1388, 491)], color=BLUE, arrows="both")
    figure.card(1052, 493, 672, 170, "Tile shell · shared contract", [
        "Context memory + safe-point context selection",
        "Owned queues + lifecycle and identity checks",
        "Monitoring + power-control handshakes",
        "Protection according to the selected native parameters",
    ], color=BLUE, number="07")
    figure.path([(1388, 665), (1388, 693)], color=BLUE, arrows="both")
    figure.card(1052, 695, 672, 123, "Tile-specific body", [
        "Selected FUs + registers, accumulators and local state",
        "Unavailable operation classes are rejected",
    ], color=PURPLE, number="08")
    figure.text(1052, 855, "Data streams connect through the separate local switch.", size=18,
                color=MUTED)
    figure.text(1052, 883, "A shell power protocol does not imply enabled physical power gating.",
                size=17, color=MUTED)

    figure.text(48, 956, "09 / CHOOSE EACH FUNCTIONAL UNIT INDEPENDENTLY", size=16,
                weight=700, color=TEAL)
    catalog = [
        ("BCT", "Basic compute tile", ["Scalar ALU", "Multiplier", "MAC"],
         "Scalar integer dataflow"),
        ("VCT", "Vector compute tile", ["Lane ALU", "Lane multiply · lane MAC",
                                        "Vector reduction", "Dot product"],
         "Masked SIMD + scalar results"),
        ("SFT", "Specialized function tile", ["ALU · multiplier", "LUT · polynomial",
                                          "Reciprocal · RSQRT · exponential",
                                          "Reduction · formatter", "Accumulator"],
         "Fixed-point nonlinear functions"),
        ("MST", "Memory + stream tile", ["Load engine", "Store engine", "AGUs + formatters live",
                                       "inside the selected engines"],
         "SRAM / stream movement"),
        ("CPT", "Control + predicate tile", ["Predicate operations", "Loop controller",
                                           "Events / barriers", "Tagged actions"],
         "Control + synchronization"),
    ]
    for index, (kind, title, units, use) in enumerate(catalog):
        x = 48 + index * 346
        color = TILE_COLOR[kind]
        figure.rect(x, 982, 320, 272, fill=PALE[color], stroke=PALE[color])
        figure.text(x + 20, 1026, kind, size=30, color=color, weight=700)
        figure.text(x + 20, 1055, title, size=19, weight=700)
        figure.lines(x + 20, 1092, units, size=17, step=27)
        figure.text(x + 20, 1231, use, size=16, color=color, weight=700)

    figure.text(48, 1292, "WHAT A CONFIGURATION CHANGES", size=16, weight=700, color=TEAL)
    for x, title, lines in (
        (48, "Widths + lane count", ["Change number range, payload size and replicated logic.",
                                    "The widest tile sets the common grid payload width."]),
        (625, "Tables, queues + latency", ["Change capacity, storage and backpressure behavior.",
                                          "A response delay does not necessarily retime arithmetic."]),
        (1202, "Hardware versus runtime contexts", ["Generation determines which hardware exists.",
                                                   "Contexts program operations within that hardware."]),
    ):
        figure.card(x, 1314, 550, 113, title, lines, color=MUTED)
    figure.lines(48, 1460, [
        "Native per-tile controls connect to a host adapter; mesh edge streams connect external producers and consumers.",
        "Layout is logical connectivity, not a floorplan. Area, timing, power and energy require later technology-specific implementation.",
    ], size=18, step=27)
    return figure.save()


def export(figures):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": WIDTH, "height": HEIGHT},
                                device_scale_factor=2)
        for source in figures:
            page.goto(source.as_uri())
            page.evaluate("document.fonts.ready")
            # Browser font metrics catch clipping in diagrams and their exports.
            issues = page.evaluate("""() => [...document.querySelectorAll('text')].flatMap(t => {
                const b = t.getBBox();
                const x = Number(t.getAttribute('x')), y = Number(t.getAttribute('y'));
                const frames = [...document.querySelectorAll('rect')].map(r => r.getBBox())
                    .filter(r => x >= r.x && x <= r.x + r.width &&
                                 y >= r.y && y <= r.y + r.height)
                    .sort((a, c) => a.width * a.height - c.width * c.height);
                const f = frames[0];
                const outside = b.x < 0 || b.y < 0 || b.x + b.width > 1800 ||
                                b.y + b.height > 1500;
                const clipped = f && (b.x < f.x - 1 || b.y < f.y - 1 ||
                    b.x + b.width > f.x + f.width + 1 ||
                    b.y + b.height > f.y + f.height + 1);
                return outside || clipped ? [t.textContent] : [];
            })""")
            if issues:
                raise ValueError(f"Text outside canvas/card in {source.name}: {issues}")
            page.screenshot(path=str(source.with_suffix(".png")))
        images = "".join(
            '<section>' + source.read_text(encoding="utf-8") + '</section>'
            for source in figures
        )
        page.goto("about:blank")
        page.set_content('''<!doctype html><html lang="en"><meta charset="utf-8">
            <title>MOSAIC architecture</title><style>
            @page {size: 1800px 1500px; margin: 0}
            html, body {margin: 0; padding: 0}
            section {width: 1800px; height: 1500px; break-after: page}
            section:last-child {break-after: auto}
            svg {display: block}
            </style><body>''' + images + '</body></html>')
        page.pdf(path=str(HERE / "mosaic-architecture.pdf"), print_background=True,
                 prefer_css_page_size=True)
        browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", action="store_true", help="Also export PNGs and PDF in Chromium")
    args = parser.parse_args()
    grid = contracts()
    figures = [system_figure(grid), flavor_figure(grid)]
    if args.export:
        export(figures)
    for source in figures:
        print(source)
    if args.export:
        print(HERE / "mosaic-architecture.pdf")


if __name__ == "__main__":
    main()
