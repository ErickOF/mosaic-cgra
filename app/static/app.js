"use strict";

const $ = (id) => document.getElementById(id);
const clone = (value) => structuredClone(value);
const STORAGE_KEY = "mosaic.flavor-studio.draft.v1";
const terminalStates = new Set(["succeeded", "failed", "canceled"]);
const state = {
  catalog: null, document: null, openHelp: new Set(), selected: "0:0", brush: null, revision: 0,
  validation: null, undo: [], redo: [], jobs: [], view: "layout",
  tomlDirty: false, tomlRevision: -1, validationTimer: null, pollTimer: null,
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function icon(name) {
  const paths = {
    compute: ["M6 6h12v12H6z", "M9 2v4m6-4v4M9 18v4m6-4v4M2 9h4m-4 6h4m12-6h4m-4 6h4", "M10 10h4v4h-4z"],
    memory: ["M5 3h14v18H5z", "M8 7h8m-8 5h8m-8 5h8"],
    vector: ["M4 5h5v5H4zm11 0h5v5h-5zM4 14h5v5H4zm11 0h5v5h-5z"],
    function: ["M7 21l4-16c.6-2 3-3 5-1M7 9h9"],
    control: ["M5 4h14v5H5zM5 15h14v5H5zm7-6v6m-3-3l3 3 3-3"],
    lock: ["M6 10h12v11H6zM8 10V6a4 4 0 018 0v4"],
    select: ["M5 3l14 10-7 1-3 7z"],
    undo: ["M8 4L3 9l5 5M3 9h11a7 7 0 010 14"],
    redo: ["M16 4l5 5-5 5m5-5H10a7 7 0 000 14"],
  };
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("fill", "none");
  svg.setAttribute("stroke", "currentColor");
  svg.setAttribute("stroke-width", "1.5");
  svg.setAttribute("stroke-linecap", "round");
  svg.setAttribute("stroke-linejoin", "round");
  svg.setAttribute("aria-hidden", "true");
  for (const path of paths[name] || paths.compute) {
    const node = document.createElementNS(svg.namespaceURI, "path");
    node.setAttribute("d", path);
    svg.append(node);
  }
  return svg;
}

const glyphs = { BCT: "compute", MST: "memory", VCT: "vector", SFT: "function", CPT: "control" };

async function api(path, body) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || `Request failed (${response.status})`);
    return result;
  } catch (error) {
    if (error.name === "AbortError") throw new Error("The local server took too long to respond. Try again.");
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function toast(message, error = false) {
  const node = element("div", `toast${error ? " error" : ""}`, message);
  $("toast-region").append(node);
  while ($("toast-region").children.length > 3) $("toast-region").firstChild.remove();
  setTimeout(() => node.remove(), error ? 9000 : 4500);
}

function tileAt(row, col, document = state.document) {
  return document.cluster.tiles.find((tile) => tile.row === row && tile.col === col);
}

function selectedTile() {
  const [row, col] = state.selected.split(":").map(Number);
  return tileAt(row, col);
}

function selectedIn(document) {
  const [row, col] = state.selected.split(":").map(Number);
  return tileAt(row, col, document);
}

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state.document));
    $("draft-status").textContent = "Draft saved on this device";
  } catch {
    $("draft-status").textContent = "Save TOML to keep your draft";
  }
}

function preserveFocus(render) {
  const active = document.activeElement;
  const id = active?.id;
  const selection = active?.tagName === "INPUT" && active.type === "text"
    ? [active.selectionStart, active.selectionEnd] : null;
  render();
  const replacement = id && $(id);
  if (replacement && replacement !== active) {
    replacement.focus({ preventScroll: true });
    if (selection) replacement.setSelectionRange(...selection);
  }
}

function edit(change) {
  if (state.tomlDirty) {
    toast("Apply or discard your TOML edits before changing the layout.", true);
    render();
    return;
  }
  const next = clone(state.document);
  change(next);
  next.cluster.profile = "Configurable";
  if (JSON.stringify(next) === JSON.stringify(state.document)) return;
  state.undo.push(clone(state.document));
  if (state.undo.length > 80) state.undo.shift();
  state.redo = [];
  state.document = next;
  changed();
}

function changed() {
  state.revision += 1;
  const [row, col] = state.selected.split(":").map(Number);
  if (row >= state.document.cluster.rows || col >= state.document.cluster.cols) state.selected = "0:0";
  state.validation = null;
  persist();
  render();
  scheduleValidation();
  if (state.view === "toml" && !state.tomlDirty) refreshToml();
  renderJobs();
}

function undo(redo = false) {
  if (state.tomlDirty) return;
  const source = redo ? state.redo : state.undo;
  if (!source.length) return;
  (redo ? state.undo : state.redo).push(clone(state.document));
  state.document = source.pop();
  changed();
}

function resizeGrid(rows, cols) {
  if (!Number.isInteger(rows) || !Number.isInteger(cols) || rows < 1 || cols < 1) {
    toast("Rows and columns must be positive integers.", true);
    render();
    return;
  }
  if (rows * cols > 65536) {
    toast("The native 16-bit tile ID namespace holds at most 65,536 tiles.", true);
    render();
    return;
  }
  edit((document) => {
    const existing = document.cluster.tiles.filter((tile) => tile.row < rows && tile.col < cols);
    const used = new Set(existing.map((tile) => tile.id));
    let nextId = 0;
    for (let row = 0; row < rows; row++) {
      for (let col = 0; col < cols; col++) {
        if (existing.some((tile) => tile.row === row && tile.col === col)) continue;
        while (used.has(nextId)) nextId += 1;
        existing.push({ id: nextId, class: "BCT", row, col, parameters: {} });
        used.add(nextId);
      }
    }
    document.cluster.rows = rows;
    document.cluster.cols = cols;
    document.cluster.tiles = existing;
  });
}

function placeClass(row, col, kind) {
  if (!state.catalog.tile_classes.some((type) => type.id === kind && type.available)) return;
  state.selected = `${row}:${col}`;
  edit((document) => {
    const tile = tileAt(row, col, document);
    if (tile && tile.class !== kind) {
      tile.class = kind;
      tile.parameters = {};
    }
  });
  render();
}

function dragPayload(event, value) {
  event.dataTransfer.setData("application/x-mosaic", JSON.stringify(value));
  event.dataTransfer.effectAllowed = "copyMove";
}

function renderPalette() {
  $("tile-palette").replaceChildren(...state.catalog.tile_classes.map((type) => {
    const button = element("button", `palette-item ${type.id.toLowerCase()}${state.brush === type.id ? " active" : ""}`);
    button.type = "button";
    button.disabled = !type.available;
    button.draggable = type.available;
    button.setAttribute("aria-label", `Place ${type.id}${type.available ? "" : " (unavailable)"}`);
    button.setAttribute("aria-pressed", String(state.brush === type.id));
    button.title = type.available ? type.description : "This tile class is not available in Cluster MVP yet.";
    const glyph = element("span", "tile-glyph");
    glyph.append(icon(glyphs[type.id]));
    const text = element("span", "palette-text");
    text.append(element("strong", "", type.id), element("span", "", type.available ? type.title : "Coming later"));
    button.append(glyph, text);
    if (!type.available) {
      const lock = icon("lock");
      lock.classList.add("lock-icon");
      button.append(lock);
    }
    button.addEventListener("click", () => {
      state.brush = state.brush === type.id ? null : type.id;
      renderPalette();
      renderMode();
    });
    button.addEventListener("dragstart", (event) => dragPayload(event, { kind: "class", class: type.id }));
    return button;
  }));
}

function renderMode() {
  $("placement-hint").textContent = state.brush ? `Click a tile to place ${state.brush} · Esc to finish` : "Select a tile to configure it";
  $("select-button").classList.toggle("active", !state.brush);
}

function renderGrid() {
  const { rows, cols } = state.document.cluster;
  $("grid-label").textContent = `${rows} × ${cols} TILE GRID`;
  for (const id of ["tile-grid", "column-labels", "row-labels"]) $(id).dataset.size = rows;
  $("tile-grid").style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
  $("tile-grid").dataset.density = rows * cols >= 12 ? "compact" : "regular";
  $("column-labels").style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
  $("row-labels").style.gridTemplateRows = `repeat(${rows}, 1fr)`;
  $("column-labels").style.minWidth = `${cols * 78 + 28}px`;
  $("column-labels").nextElementSibling.style.minWidth = `${cols * 78 + 28}px`;
  $("column-labels").replaceChildren(...Array.from({ length: cols }, (_, col) => element("span", "", `C${col}`)));
  $("row-labels").replaceChildren(...Array.from({ length: rows }, (_, row) => element("span", "", `R${row}`)));
  const wires = [];
  const cells = [];
  const invalidIds = new Set((state.validation?.issues || []).map((issue) => issue.tile_id));
  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      for (const [nextRow, nextCol] of [[row + 1, col], [row, col + 1]]) {
        if (nextRow >= rows || nextCol >= cols) continue;
        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        for (const [key, value] of Object.entries({ x1: (col + 0.5) * 1000 / cols, y1: (row + 0.5) * 1000 / rows,
          x2: (nextCol + 0.5) * 1000 / cols, y2: (nextRow + 0.5) * 1000 / rows })) line.setAttribute(key, value);
        wires.push(line);
      }
      const tile = tileAt(row, col);
      const key = `${row}:${col}`;
      const kind = ["BCT", "MST", "VCT", "SFT", "CPT"].includes(tile?.class) ? tile.class : "Unknown";
      const cell = element("button", `tile-cell ${kind.toLowerCase()}${state.selected === key ? " selected" : ""}${tile && invalidIds.has(tile.id) ? " invalid" : ""}`);
      cell.type = "button";
      cell.id = `tile-slot-${row}-${col}`;
      cell.draggable = !!tile;
      cell.setAttribute("aria-label", `Tile ${tile?.id ?? "empty"}, ${kind}, row ${row}, column ${col}`);
      cell.setAttribute("aria-pressed", String(state.selected === key));
      cell.append(element("span", "tile-number", tile ? `TILE ${String(tile.id).padStart(2, "0")}` : "EMPTY SLOT"));
      const glyph = element("span", "tile-glyph");
      glyph.append(icon(glyphs[kind]));
      const bottom = element("span", "tile-bottom");
      const parameters = tile?.parameters || {};
      const details = { BCT: `${parameters.RF_DEPTH ?? 8} RF entries`, MST: "Shared memory",
        VCT: `${parameters.NUM_LANES ?? 4} vector lanes`, SFT: "Special functions", CPT: "Control" };
      const detail = details[kind] || "Configure tile";
      bottom.append(element("span", "tile-class", kind), element("span", "tile-detail", detail));
      cell.append(glyph, bottom);
      cell.addEventListener("click", () => {
        state.selected = key;
        if (state.brush) placeClass(row, col, state.brush);
        else preserveFocus(() => { renderGrid(); renderInspector(); });
      });
      cell.addEventListener("keydown", (event) => {
        const direction = { ArrowUp: [-1, 0], ArrowDown: [1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] }[event.key];
        if (!direction) return;
        event.preventDefault();
        $(`tile-slot-${Math.max(0, Math.min(rows - 1, row + direction[0]))}-${Math.max(0, Math.min(cols - 1, col + direction[1]))}`)?.focus();
      });
      cell.addEventListener("dragstart", (event) => dragPayload(event, { kind: "tile", row, col }));
      cell.addEventListener("dragover", (event) => {
        if (Array.from(event.dataTransfer.types).includes("application/x-mosaic")) {
          event.preventDefault();
          cell.classList.add("drag-over");
        }
      });
      cell.addEventListener("dragleave", () => cell.classList.remove("drag-over"));
      cell.addEventListener("drop", (event) => {
        event.preventDefault();
        cell.classList.remove("drag-over");
        try {
          const payload = JSON.parse(event.dataTransfer.getData("application/x-mosaic"));
          if (payload.kind === "class") placeClass(row, col, payload.class);
          else if (payload.kind === "tile") {
            state.selected = key;
            edit((document) => {
              const source = tileAt(payload.row, payload.col, document);
              const target = tileAt(row, col, document);
              if (!source || !target) return;
              [source.row, target.row] = [target.row, source.row];
              [source.col, target.col] = [target.col, source.col];
            });
          }
        } catch { toast("That item could not be placed.", true); }
      });
      cells.push(cell);
    }
  }
  $("mesh-wires").replaceChildren(...wires);
  $("tile-grid").replaceChildren(...cells);
  renderMode();
}

function rememberHelp() {
  // Read the live DOM before replacing it: native toggle events may still be queued.
  for (const details of document.querySelectorAll("details.configuration-help[data-help-key]")) {
    if (details.open) state.openHelp.add(details.dataset.helpKey);
    else state.openHelp.delete(details.dataset.helpKey);
  }
}

function helpDetails(title, paragraphs, key) {
  const details = element("details", "configuration-help");
  details.dataset.helpKey = key;
  details.open = state.openHelp.has(key);
  details.append(element("summary", "", title));
  for (const paragraph of paragraphs.filter(Boolean)) {
    details.append(element("p", "", paragraph));
  }
  details.addEventListener("toggle", () => {
    if (!details.isConnected) return;
    if (details.open) state.openHelp.add(key);
    else state.openHelp.delete(key);
  });
  return details;
}

function renderArchitectureGuidance() {
  rememberHelp();
  const help = state.catalog.configuration_guidance;
  const cluster = state.document.cluster;
  const rows = Number(cluster.rows);
  const cols = Number(cluster.cols);
  const links = rows * (cols - 1) + cols * (rows - 1);
  const grid = element("p", "configuration-effect",
    `${rows * cols} native tiles · ${links} neighbor links · max Manhattan distance ${rows + cols - 2} hops`);
  grid.id = "grid-impact";
  $("grid-guidance").replaceChildren(grid, helpDetails("Grid implications", [
    help.rows.description, ...help.rows.implications, help.cols.description,
    ...help.cols.implications,
    "The fabric bus matches the widest native tile payload. Width mismatches are checked; " +
    "links do not automatically quantize, pack or convert numerical formats.",
  ], "architecture:grid"));
  const bytes = cluster.scratchpad_banks * cluster.scratchpad_bank_words * 8;
  const memory = element("p", "configuration-effect",
    `${cluster.scratchpad_bank_words * 8} bytes per bank · ${bytes} bytes total`);
  memory.id = "memory-impact";
  $("memory-guidance").replaceChildren(memory, helpDetails("Memory implications", [
    help.scratchpad_banks.description, ...help.scratchpad_banks.implications,
    help.scratchpad_bank_words.description, ...help.scratchpad_bank_words.implications,
    "With no MST, the shared scratchpad remains host-accessible; compute tiles do not acquire " +
    "direct scratchpad ports. MST placement and routes determine memory-to-compute transport.",
  ], "architecture:memory"));
  $("name-guidance").replaceChildren(helpDetails("Name implications", [
    help.name.description, ...help.name.implications,
  ], "architecture:name"));
  $("cluster-guidance").replaceChildren(helpDetails("Control implications", [
    help.cluster_id.description, ...help.cluster_id.implications,
    help.clock_gating.description, ...help.clock_gating.implications,
    help.context_depth.description, ...help.context_depth.implications,
  ], "architecture:control"));
  $("guidance-scope").textContent = state.catalog.guidance_scope;
  for (const id of ["grid-rows", "grid-cols"]) $(id).setAttribute("aria-describedby", "grid-impact");
  for (const id of ["memory-banks", "memory-words"]) $(id).setAttribute("aria-describedby", "memory-impact");
}

function selectionEffect(spec, value, parameters) {
  const choice = spec.choice_help?.[String(value)];
  if (choice) return choice;
  if (!spec.metric) return "";
  const n = Number(value);
  if (!Number.isSafeInteger(n) || n < 0 || n > 1024) return "";
  const get = (name) => Number(parameters[name]);
  switch (spec.metric.kind) {
    case "bct_payload": return `${n}-bit native payload and MAC accumulator.`;
    case "double_bits": return `Full product width: ${2 * n} bits; must fit the tile data width.`;
    case "vector_payload": {
      const lanes = get("NUM_LANES");
      return `${lanes} lanes × ${get("ACC_WIDTH")} accumulator bits = ` +
        `${lanes * get("ACC_WIDTH")} native payload bits; ` +
        `${lanes * get("ELEMENT_WIDTH")} bits hold one packed element vector.`;
    }
    case "table_entries": return `${2 ** n} entries per bank; ` +
      `${2 ** n * get("OUTPUT_WIDTH")} nominal table data bits per bank, before protection.`;
    case "endpoint_entries": return `${2 ** n} sample intervals and ${2 ** n + 1} table endpoints.`;
    case "seed_entries": return `${2 ** (n + spec.metric.extra_address_bits)} native seed entries.`;
    case "loop_beats": return `Up to ${1 + 2 * n} output beats per iteration frame.`;
    case "unsigned_range": return `Unsigned count range: 0 to ${(1n << BigInt(n)) - 1n}.`;
    case "integer_range": return `Signed range: ${-(1n << BigInt(n - 1))} to ` +
      `${(1n << BigInt(n - 1)) - 1n}; unsigned maximum: ${(1n << BigInt(n)) - 1n}.`;
    case "fraction": {
      const width = get(spec.metric.width);
      const headroom = width - n - 1;
      return `Quantization step: 2^(-${n}) ≈ ${(2 ** -n).toPrecision(6)}. ` +
        (headroom < 0 ? `Fraction bits must fit the current ${width}-bit format.` :
          `${width}-bit signed format leaves ${headroom} integer bits plus the sign bit.`);
    }
    default: return "";
  }
}

function choiceLabel(name, value, kind) {
  const label = state.catalog.tile_classes.find((type) => type.id === kind)
    ?.parameters[name]?.choice_labels?.[String(value)];
  if (label) return label;
  if (name === "FU_PROFILE") {
    return state.catalog.tile_classes.find((type) => type.id === kind)?.profiles[value] || `Profile ${value}`;
  }
  if (name.startsWith("SUPPORT_")) return value ? "Enabled" : "Disabled";
  if (name.endsWith("PROTECTION")) return ["None", "Parity", "SECDED"][value];
  if (name === "REGISTER_BYPASS") return value ? "Enabled" : "Disabled";
  if (name.includes("LATENCY") || name.endsWith("PIPELINE_DEPTH")) return value === 0 ? "Combinational" : `${value} ${value === 1 ? "cycle" : "cycles"}`;
  if (name.endsWith("WIDTH") || name.endsWith("FRAC_BITS")) return `${value} bits`;
  if (name.includes("DEPTH")) return `${value} ${value === 1 ? "entry" : "entries"}`;
  return name.endsWith("PROFILE") ? `Profile ${value}` : String(value);
}

function renderInspector() {
  rememberHelp();
  const tile = selectedTile();
  const panel = $("inspector");
  const key = tile ? `${tile.row}:${tile.col}:${tile.class}:${tile.id}` : "";
  const scroll = panel.dataset.tileKey === key ? panel.scrollTop : 0;
  panel.dataset.tileKey = key;
  panel.replaceChildren();
  if (!tile) {
    panel.append(element("div", "inspector-empty", "Select a tile to configure its hardware."));
    return;
  }
  const heading = element("div", "inspector-heading");
  const title = element("div");
  title.append(element("span", "eyebrow", "TILE INSPECTOR"), element("h2", "", `Tile ${String(tile.id).padStart(2, "0")}`));
  heading.append(title, element("span", `tile-type-pill ${tile.class.toLowerCase()}`, tile.class));
  panel.append(heading, element("p", "tile-coordinate", `Row ${tile.row} · Column ${tile.col} · individually configured`));
  const basics = element("div", "inspector-basics");
  const typeField = element("div");
  const typeLabel = element("label", "field-label", "Tile class");
  typeLabel.htmlFor = "tile-class";
  const typeSelect = element("select");
  typeSelect.id = "tile-class";
  for (const type of state.catalog.tile_classes) {
    const option = new Option(type.id, type.id);
    option.disabled = !type.available;
    typeSelect.add(option);
  }
  typeSelect.value = tile.class;
  typeSelect.addEventListener("change", () => placeClass(tile.row, tile.col, typeSelect.value));
  typeField.append(typeLabel, typeSelect);
  const idField = element("div");
  const idLabel = element("label", "field-label", "Logical tile ID");
  idLabel.htmlFor = "tile-id";
  const id = element("input");
  Object.assign(id, { id: "tile-id", type: "number", min: "0", max: "65535", value: tile.id });
  id.addEventListener("change", () => edit((document) => {
    // Keep incomplete drafts serializable; NaN is neither a TOML nor JSON integer.
    selectedIn(document).id = Number.isFinite(id.valueAsNumber) ? id.valueAsNumber : "";
  }));
  idField.append(idLabel, id);
  basics.append(typeField, idField);
  panel.append(basics);
  const type = state.catalog.tile_classes.find((type) => type.id === tile.class);
  const catalog = type?.parameters || {};
  const parameters = Object.fromEntries(Object.entries(catalog).map(
    ([name, spec]) => [name, tile.parameters?.[name] ?? spec.default]));
  const purpose = element("p", "tile-purpose", type.guidance.description);
  purpose.id = "tile-purpose";
  typeSelect.setAttribute("aria-describedby", purpose.id);
  panel.append(purpose, helpDetails("Tile implications", type.guidance.implications,
    `tile:${tile.class}`));
  panel.append(helpDetails("Identity and contexts", [
    state.catalog.configuration_guidance.tile_id.description,
    ...state.catalog.configuration_guidance.tile_id.implications,
    state.catalog.configuration_guidance.tile_position.description,
    ...state.catalog.configuration_guidance.tile_position.implications,
    ...state.catalog.configuration_guidance.context_depth.implications,
  ], "tile:identity"));
  const unitStates = new Map();
  const selection = element("section", "fu-selection");
  selection.append(element("h3", "", "Functional units"));
  for (const unit of type?.functional_units || []) {
    const profile = tile.parameters?.FU_PROFILE ?? catalog.FU_PROFILE?.default ?? 1;
    const flag = unit.activation_parameter;
    const fallback = unit.minimum_profile == null ? catalog[flag].default
      : Number(profile >= unit.minimum_profile);
    const enabled = (tile.parameters?.[flag] ?? fallback) === 1;
    unitStates.set(unit.name, enabled);
    const label = element("label", "fu-toggle");
    const input = element("input");
    input.type = "checkbox";
    input.checked = enabled;
    input.disabled = false;
    input.setAttribute("aria-label", `Enable ${unit.name}`);
    input.addEventListener("change", () => edit((document) => {
      const item = selectedIn(document);
      item.parameters ||= {};
      item.parameters[flag] = Number(input.checked);
    }));
    label.append(input, element("span", "", unit.name));
    if (input.disabled) label.append(element("small", "", "Required"));
    const explanation = helpDetails(`${unit.name} implications`, [
      unit.description, enabled ? unit.enabled : unit.disabled, ...unit.implications,
    ], `fu:${tile.class}:${flag}`);
    explanation.id = `fu-help-${flag}`;
    input.setAttribute("aria-describedby", explanation.id);
    const entry = element("div", "fu-entry");
    entry.append(label, explanation);
    selection.append(entry);
  }
  selection.append(element("p", "parameter-help", "Select each FU independently. Each enabled unit has its own hardware settings below."));
  panel.append(selection);
  const groups = new Map();
  for (const [name, spec] of Object.entries(catalog)) {
    if (name === "FU_PROFILE" || (type?.functional_units || []).some(
      (unit) => unit.activation_parameter === name)) continue;
    if (!groups.has(spec.group)) groups.set(spec.group, []);
    groups.get(spec.group).push([name, spec]);
  }
  for (const [groupName, fields] of groups) {
    const group = element("section", "parameter-group");
    group.append(element("h3", "", groupName));
    if (unitStates.get(groupName) === false) {
      group.append(element("p", "parameter-help", "Enable this FU above to configure it."));
      panel.append(group);
      continue;
    }
    for (const [name, spec] of fields) {
      const value = tile.parameters?.[name] ?? spec.default;
      const overridden = value !== spec.default;
      const field = element("div", `parameter-field${overridden ? " overridden" : ""}`);
      const row = element("div", "label-row");
      const label = element("label", "", spec.title);
      label.htmlFor = `parameter-${name}`;
      label.title = name;
      row.append(label, element("span", overridden ? "override-marker" : "default-marker", overridden ? "Custom" : `Default ${spec.default}`));
      const select = element("select");
      select.id = `parameter-${name}`;
      for (const choice of spec.choices) {
        const option = new Option(choiceLabel(name, choice, tile.class), choice);
        option.disabled = Boolean(spec.unavailable_choices?.[String(choice)]);
        option.title = spec.unavailable_choices?.[String(choice)] || "";
        select.add(option);
      }
      select.value = value;
      select.addEventListener("change", () => edit((document) => {
        const item = selectedIn(document);
        item.parameters ||= {};
        if (Number(select.value) === spec.default) delete item.parameters[name];
        else item.parameters[name] = Number(select.value);

      }));
      const description = element("p", "parameter-help", spec.description);
      description.id = `parameter-${name}-help`;
      select.setAttribute("aria-describedby", description.id);
      field.append(row, select, description);
      const effect = selectionEffect(spec, value, parameters);
      if (effect) {
        const selected = element("p", "configuration-effect", effect);
        selected.id = `parameter-${name}-effect`;
        select.setAttribute("aria-describedby", `${description.id} ${selected.id}`);
        field.append(selected);
      }
      const more = helpDetails("Implications", spec.implications,
        `parameter:${tile.class}:${name}`);
      more.id = `parameter-${name}-implications`;
      field.append(more);
      group.append(field);
    }
    panel.append(group);
  }
  const reset = element("div", "inspector-reset");
  const button = element("button", "button secondary", "Reset tile to defaults");
  button.type = "button";
  button.disabled = !Object.keys(tile.parameters || {}).length;
  button.addEventListener("click", () => edit((document) => { selectedIn(document).parameters = {}; }));
  reset.append(button, element("p", "inspector-note", "These are hardware parameters. Context programs and runtime instructions are loaded separately after generation."));
  panel.append(reset);
  panel.scrollTop = scroll;
}

function capacity(bytes) {
  if (bytes >= 1048576) return [Number((bytes / 1048576).toFixed(2)), "MiB"];
  if (bytes >= 1024) return [Number((bytes / 1024).toFixed(2)), "KiB"];
  return [bytes, "B"];
}

function render() {
  if (!state.document) return;

  preserveFocus(() => {
    const cluster = state.document.cluster;
    for (const [id, value] of [["flavor-name", state.document.name], ["grid-rows", cluster.rows],
      ["grid-cols", cluster.cols],
      ["memory-banks", cluster.scratchpad_banks], ["memory-words", cluster.scratchpad_bank_words],
      ["cluster-id", cluster.cluster_id], ["lifecycle-timeout", cluster.lifecycle_timeout]]) {
      if (document.activeElement !== $(id)) $(id).value = value;
    }
    $("clock-gating").checked = cluster.clock_gating;
    renderArchitectureGuidance();
    $("breadcrumb-name").textContent = state.document.name;
    const tiles = cluster.tiles;
    $("summary-tiles").textContent = tiles.length;
    $("summary-compute").textContent = tiles.filter((tile) => tile.class !== "MST").length;
    $("summary-memory").textContent = tiles.filter((tile) => tile.class === "MST").length;
    const [amount, unit] = capacity(cluster.scratchpad_banks * cluster.scratchpad_bank_words * 8);
    $("memory-capacity").textContent = `${amount} ${unit}`;
    $("summary-capacity").replaceChildren(document.createTextNode(amount), element("span", "unit", unit));
    $("undo-button").disabled = state.tomlDirty || !state.undo.length;
    $("redo-button").disabled = state.tomlDirty || !state.redo.length;
    renderPalette();
    renderGrid();
    renderInspector();
    renderValidation();
  });
}

function renderValidation() {
  const valid = state.validation?.valid === true && !state.tomlDirty;
  $("validation-status").className = `validation-status ${!state.validation ? "checking" : valid ? "valid" : "invalid"}`;
  $("validation-status").textContent = state.tomlDirty ? "TOML edits pending" : !state.validation ? "Checking layout…" : valid ? "Layout is valid" : "Layout needs attention";
  $("generate-button").disabled = !valid;
  const sim = state.catalog.simulators.find((item) => item.id === $("simulator").value);
  $("test-button").disabled = !valid || !sim?.available;
  $("test-button").title = !sim?.available ? "Install a simulator or configure its binary directory to run validation." : "Run Python models and PyUVM for this flavor";
  $("test-scope").textContent = state.validation?.summary?.validation_scope ||
    "Native tile interfaces, shared memory, and grid transport checks.";
  $("summary-data-width").textContent = state.validation?.summary?.data_width ?? "—";
  const issues = state.validation?.issues || [];
  $("issues-panel").hidden = !issues.length;
  $("issues-list").replaceChildren(...issues.map((issue) => {
    const item = element("li");
    if (issue.tile_id !== null && issue.tile_id !== undefined) {
      const button = element("button", "", issue.message);
      button.type = "button";
      button.addEventListener("click", () => {
        const tile = state.document.cluster.tiles.find((tile) => tile.id === issue.tile_id);
        if (tile) { state.selected = `${tile.row}:${tile.col}`; render(); $("inspector").scrollIntoView({ block: "nearest", behavior: "smooth" }); }
      });
      item.append(button);
    } else item.textContent = issue.message;
    return item;
  }));
  $("flavor-name").setAttribute("aria-invalid", String(issues.some((issue) => issue.path === "name")));
}

function scheduleValidation() {
  clearTimeout(state.validationTimer);
  const revision = state.revision;
  const document = clone(state.document);
  state.validationTimer = setTimeout(async () => {
    try {
      const result = await api("/api/validate", { document });
      if (revision !== state.revision) return;
      state.validation = result;
    } catch (error) {
      if (revision !== state.revision) return;
      state.validation = { valid: false, issues: [{ message: error.message }] };
    }
    preserveFocus(() => { renderValidation(); renderGrid(); });
  }, 200);
}

async function refreshToml() {
  if (state.tomlDirty || state.tomlRevision === state.revision) return;
  const revision = state.revision;
  try {
    const result = await api("/api/serialize", { document: clone(state.document) });
    if (revision === state.revision && !state.tomlDirty) {
      $("toml-source").value = result.toml;
      state.tomlRevision = revision;
    }
  } catch (error) { toast(error.message, true); }
}

function showView(view) {
  state.view = view;
  for (const name of ["layout", "toml"]) {
    $(`${name}-view`).hidden = name !== view;
    $(`${name}-tab`).setAttribute("aria-selected", String(name === view));
    $(`${name}-tab`).classList.toggle("active", name === view);
  }
  if (view === "toml") refreshToml();
}

function editableShape(document) {
  const cluster = document?.cluster;
  return document && typeof document.name === "string" && cluster &&
    Number.isInteger(cluster.rows) && cluster.rows > 0 && Number.isInteger(cluster.cols) &&
    cluster.cols > 0 && Array.isArray(cluster.tiles) &&
    cluster.tiles.every((tile) => tile && typeof tile.class === "string" && Number.isInteger(tile.row) &&
      Number.isInteger(tile.col) && (!tile.parameters || (typeof tile.parameters === "object" && !Array.isArray(tile.parameters))));
}

async function importToml(text) {
  const result = await api("/api/parse", { toml: text });
  if (!editableShape(result.document)) throw new Error("Use positive row/column counts and an explicit tile list before opening this architecture.");
  result.document.cluster.profile = "Configurable";
  state.undo.push(clone(state.document));
  state.redo = [];
  state.document = result.document;
  state.tomlDirty = false;
  state.tomlRevision = -1;
  $("apply-toml").disabled = true;
  $("discard-toml").hidden = true;
  $("toml-status").textContent = "Architecture source · TOML";
  changed();
  toast(result.validation.valid ? "Architecture loaded." : "Draft loaded. Resolve its validation issues before generating RTL.");
}

async function saveToml() {
  if (state.tomlDirty) { toast("Apply your TOML edits before saving, or discard them to save the layout.", true); return; }
  try {
    const result = await api("/api/serialize", { document: clone(state.document) });
    const url = URL.createObjectURL(new Blob([result.toml], { type: "application/toml" }));
    const link = element("a");
    link.href = url;
    link.download = `${/^[a-z][a-z0-9_-]{0,39}$/.test(state.document.name) ? state.document.name : "cgra-draft"}.toml`;
    document.body.append(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("TOML file saved. Your local draft is also retained in this browser.");
  } catch (error) { toast(error.message, true); }
}

async function submitJob(kind) {
  if (!state.validation?.valid || state.tomlDirty) return;
  const revision = state.revision;
  const document = clone(state.document);
  try {
    const job = await api("/api/jobs", { kind, document, sim: $("simulator").value });
    state.jobs.unshift({ ...job, revision });
    renderJobs();
    schedulePoll();
    toast(kind === "test" ? "Validation queued for this architecture snapshot." : "Generating your RTL bundle.");
  } catch (error) { toast(error.message, true); }
}

function renderJobs() {
  if (!state.jobs.length) return;
  const openLogs = new Set(Array.from($("jobs-list").querySelectorAll(".job-card:has(details[open])"))
    .map((card) => card.dataset.jobId));
  $("jobs-list").replaceChildren(...state.jobs.map((job) => {
    const card = element("article", `job-card ${job.state}`);
    card.dataset.jobId = job.id;
    const main = element("div", "job-main");
    main.append(element("span", "job-indicator", job.state === "failed" ? "!" : job.state === "succeeded" ? "✓" : "—"));
    const text = element("div", "job-text");
    const title = element("div", "job-title", `${job.name} · ${job.kind === "test" ? "PyUVM validation" : "RTL generation"}`);
    if (job.revision === undefined) title.append(element("span", "job-badge", "Restored job"));
    else if (job.revision !== state.revision) title.append(element("span", "job-badge", "Previous revision"));
    const scope = job.validation?.scope;
    text.append(title, element("div", "job-subtitle", `${job.message}${scope ? ` · ${scope}` : ""}${job.build_id ? ` · ${job.build_id.slice(0, 10)}` : ""}`));
    main.append(text);
    if (!terminalStates.has(job.state)) {
      const cancel = element("button", "button subtle small", "Cancel");
      cancel.type = "button";
      cancel.addEventListener("click", async () => {
        try {
          const result = await api(`/api/jobs/${job.id}/cancel`, {});
          Object.assign(job, result);
          renderJobs();
        } catch (error) { toast(error.message, true); }
      });
      main.append(cancel);
    }
    if (job.download) {
      const link = element("a", "job-link", "Download RTL ↓");
      link.href = job.download;
      link.setAttribute("download", "");
      main.append(link);
    }
    card.append(main);
    if (job.log) {
      const details = element("details");
      details.open = openLogs.has(job.id);
      details.append(element("summary", "", "Validation log"), element("pre", "", job.log));
      card.append(details);
    }
    return card;
  }));
}

function schedulePoll() {
  clearTimeout(state.pollTimer);
  if (!state.jobs.some((job) => !terminalStates.has(job.state))) return;
  state.pollTimer = setTimeout(async () => {
    await Promise.all(state.jobs.filter((job) => !terminalStates.has(job.state)).map(async (job) => {
      try {
        const result = await api(`/api/jobs/${job.id}`);
        if (result.state !== job.state && terminalStates.has(result.state)) toast(result.message, result.state === "failed");
        Object.assign(job, result);
      } catch (error) {
        job.message = `${error.message} Reconnecting…`;
      }
    }));
    renderJobs();
    schedulePoll();
  }, 1200);
}

function bindEvents() {
  for (const [id, glyph] of [["select-button", "select"], ["undo-button", "undo"], ["redo-button", "redo"]]) $(id).append(icon(glyph));
  $("open-button").addEventListener("click", () => $("file-input").click());
  $("file-input").addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    try {
      if (file.size > 12 * 1024 * 1024) throw new Error("Choose a TOML file smaller than 12 MiB.");
      await importToml(await file.text());
    } catch (error) { toast(error.message, true); }
    finally { event.target.value = ""; }
  });
  $("save-button").addEventListener("click", saveToml);
  $("generate-button").addEventListener("click", () => submitJob("generate"));
  $("test-button").addEventListener("click", () => submitJob("test"));
  $("simulator").addEventListener("change", renderValidation);
  $("flavor-name").addEventListener("input", (event) => edit((document) => { document.name = event.target.value; }));
  $("grid-rows").addEventListener("change", (event) => resizeGrid(Number(event.target.value), state.document.cluster.cols));
  $("grid-cols").addEventListener("change", (event) => resizeGrid(state.document.cluster.rows, Number(event.target.value)));
  for (const [id, key] of [["memory-banks", "scratchpad_banks"], ["memory-words", "scratchpad_bank_words"],
    ["cluster-id", "cluster_id"], ["lifecycle-timeout", "lifecycle_timeout"]]) {
    $(id).addEventListener("change", (event) => edit((document) => { document.cluster[key] = Number(event.target.value); }));
  }
  $("clock-gating").addEventListener("change", (event) => edit((document) => { document.cluster.clock_gating = event.target.checked; }));
  $("layout-tab").addEventListener("click", () => showView("layout"));
  $("toml-tab").addEventListener("click", () => showView("toml"));
  $("toml-source").addEventListener("input", () => {
    state.tomlDirty = true;
    $("toml-status").textContent = "Unapplied TOML edits";
    $("apply-toml").disabled = false;
    $("discard-toml").hidden = false;
    $("undo-button").disabled = true;
    $("redo-button").disabled = true;
    renderValidation();
  });
  $("apply-toml").addEventListener("click", async () => {
    try { await importToml($("toml-source").value); }
    catch (error) { toast(error.message, true); }
  });
  $("discard-toml").addEventListener("click", () => {
    state.tomlDirty = false;
    state.tomlRevision = -1;
    $("toml-status").textContent = "Architecture source · TOML";
    $("apply-toml").disabled = true;
    $("discard-toml").hidden = true;
    render();
    refreshToml();
  });
  $("undo-button").addEventListener("click", () => undo());
  $("redo-button").addEventListener("click", () => undo(true));
  $("select-button").addEventListener("click", () => { state.brush = null; renderPalette(); renderMode(); });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { state.brush = null; renderPalette(); renderMode(); }
    const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
    if (!typing && (event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "z") {
      event.preventDefault(); undo(event.shiftKey);
    }
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") { event.preventDefault(); saveToml(); }
  });
  $("retry-button").addEventListener("click", bootstrap);
}

async function bootstrap() {
  $("startup-error").hidden = true;
  try {
    const [catalog, history] = await Promise.all([api("/api/catalog"), api("/api/jobs")]);
    if (!catalog.configuration_guidance?.tile_position ||
        !catalog.tile_classes?.every((tile) => tile.guidance)) {
      throw new Error("Restart the local app server (Ctrl+C, then make app) to load " +
        "the updated configuration explanations. Your saved draft will remain available.");
    }
    state.catalog = catalog;
    state.jobs = history.jobs;
    state.document = clone(state.catalog.starter);
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (editableShape(saved) && saved.schema === state.catalog.schema) state.document = saved;
    } catch { /* A damaged local draft never prevents opening the starter. */ }
    state.document.cluster.profile = "Configurable";
    $("memory-banks").replaceChildren(...[1, 2, 4, 8, 16].map((value) => new Option(String(value), value)));
    $("memory-words").replaceChildren(...Array.from({ length: 18 }, (_, bit) => 2 ** bit)
      .map((value) => new Option(String(value), value)));
    $("simulator").replaceChildren(...state.catalog.simulators.map((sim) => new Option(`${sim.id === "icarus" ? "Icarus" : "VCS"}${sim.available ? "" : " (offline)"}`, sim.id)));
    $("simulator").value = state.catalog.simulators.find((sim) => sim.available)?.id || "icarus";
    render();
    scheduleValidation();
    renderJobs();
    schedulePoll();
  } catch (error) {
    $("startup-error-message").textContent = `${error.message} Start the local app server and reload this page.`;
    $("startup-error").hidden = false;
  }
}

bindEvents();
bootstrap();
