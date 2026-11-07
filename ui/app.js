// Magic CAD studio. Every figure comes from a JSON endpoint; nothing here invents a result.
"use strict";

const view = document.getElementById("view");
const readAt = document.getElementById("read-at");
const DASH = "—";
const DEFAULT_STEM = "wall_bracket";

// ---- Small DOM and format helpers -------------------------------------------------

function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const missing = (value) => value === null || value === undefined || value === "";
const text = (value) => (missing(value) ? DASH : esc(value));
const label = (key) => esc(String(key).replace(/_/g, " "));

function num(value, digits = 2) {
  if (typeof value !== "number" || !Number.isFinite(value)) return missing(value) ? DASH : esc(value);
  if (Number.isInteger(value)) return String(value);
  const fixed = value.toFixed(digits).replace(/0+$/, "").replace(/\.$/, "");
  return fixed === "-0" ? "0" : fixed;
}

function when(iso) {
  if (!iso) return DASH;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return esc(iso);
  return `${date.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" })} ${date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false })}`;
}

const STATUS_CLASS = {
  PASS: "pass", OK: "pass",
  "NOT RUN": "idle", SKIPPED: "idle",
  NO_DESIGN: "none", NO_RUN: "none", NO_BRIEF: "none", NO_EVALS: "none", NO_LIBRARY: "none",
  FAIL: "fail", ERROR: "fail",
  STALE: "warn", OLDER: "warn", PLACEHOLDER: "warn", UNCALIBRATED: "warn", "NO DATA": "none",
};

function status(word) {
  if (missing(word)) return `<span class="status status--none">${DASH}</span>`;
  const kind = Object.hasOwn(STATUS_CLASS, word) ? STATUS_CLASS[word] : "none";
  return `<span class="status status--${kind}">${esc(word)}</span>`;
}

const passWord = (value) => (value === true ? "PASS" : value === false ? "FAIL" : null);
const yesNo = (value) => (typeof value === "boolean" ? status(passWord(value)) : DASH);

const runFolder = (path) => path.replace(/^runs\//, "").replace(/\/report\.json$/, "");
const gateStatus = (gates, name) => ((gates || []).find((g) => g.name === name) || {}).status;

// What a PASS covered, so it is never read as more than the harness checked.
function scopeNote(run) {
  if (!run) return "";
  const gates = run.gates || [];
  const named = (test) => gates.filter(test).map((g) => String(g.name || "unnamed gate").replace(/^\d+\s+/, "").toLowerCase()).join(", ");
  const failed = named((g) => g.status === "FAIL" || g.status === "ERROR");
  const skipped = named((g) => g.status === "NOT RUN" || g.status === "SKIPPED");
  const parts = [`${esc(run.mode || "unknown")} mode`];
  if (failed) parts.push(`${esc(failed)} failed`);
  if (skipped) parts.push(`${esc(skipped)} not run`);
  if (gates.length && !failed && !skipped) parts.push("all gates run");
  if (!gates.length) parts.push("no gates recorded");
  return parts.join(", ");
}

// A fallback run must carry its own staleness, or it reads as current evidence.
function fullRunNote(full, stem, shownPath) {
  if (!full) return "No run-mode pass is on disk.";
  const folder = runFolder(full.path);
  const name = full.path === shownPath ? `<span class="path">${esc(folder)}</span>` : `<a class="path" href="#/design/${esc(stem)}/${esc(folder)}">${esc(folder)}</a>`;
  const stale = full.changed_since && full.changed_since.length
    ? ` ${status("STALE")} <span class="path">${esc(full.changed_since.join(", "))}</span> changed after it.` : "";
  return `Last full run: ${name}, <span class="num">${when(full.modified)}</span>.${stale}`;
}

// Everything a gate pass does not establish. Absence is data.
function notChecked(prints, unverified) {
  const u = unverified || {};
  const flag = (on, word, yes, no) => (on === true ? [status(word), yes] : on === false ? [status("OK"), no] : [status("NO DATA"), "CLAUDE.md could not be read."]);
  return table("What the gates do not cover", [{ title: "Evidence" }, { title: "State" }, { title: "Meaning" }], [
    ["Design critique", status("NO DATA"), "No reviewer verdict is wired into this studio. A gate pass is not a design verdict."],
    ["Slicer check", status("NO DATA"), "No slicer result is wired in. The printability gate is geometry only."],
    ["Printed parts", `<span class="num">${num(prints)}</span>`, `Logged in <span class="path">prints/</span>.${prints ? "" : " Nothing has been proven on a printer."}`],
    ["Clearances", ...flag(u.clearances_uncalibrated, "UNCALIBRATED", "CLAUDE.md marks them as not yet calibrated on a real print.", "CLAUDE.md no longer marks them as uncalibrated.")],
  ]);
}

function titleBlock(rows) {
  const cells = rows.filter(Boolean).map(([term, value]) => `<div><dt>${esc(term)}</dt><dd>${value}</dd></div>`);
  return `<dl class="title-block">${cells.join("")}</dl>`;
}

function table(caption, headers, rows, opts = {}) {
  const head = headers.map((h) => `<th scope="col"${h.cls ? ` class="${h.cls}"` : ""}>${esc(h.title)}</th>`).join("");
  const body = rows.map((row) => `<tr>${row.map((cell, i) => {
    const cls = headers[i].cls ? ` class="${headers[i].cls}"` : "";
    return i === 0 && !opts.noRowHeader ? `<th scope="row"${cls}>${cell}</th>` : `<td${cls}>${cell}</td>`;
  }).join("")}</tr>`).join("");
  const name = esc(caption);
  return `<div class="table-scroll${opts.narrow ? " table-scroll--narrow" : ""}" data-label="${name}"><table>
    <caption${opts.showCaption ? "" : ' class="visually-hidden"'}>${name}</caption>
    <thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

// ---- Data -------------------------------------------------------------------------

async function fetchJson(url) {
  const response = await fetch(url, { cache: "no-store" });
  let data = null;
  try { data = await response.json(); } catch { data = null; }
  if (response.ok) return { ok: true, data };
  if (response.status === 404 && data) return { ok: false, absent: true, data };
  const failure = new Error(data && data.message ? data.message : `${url} answered ${response.status}.`);
  failure.fromServer = true;
  throw failure;
}

// Only a table that really overflows becomes a focusable scroll region.
function syncScrollRegions() {
  view.querySelectorAll(".table-scroll").forEach((box) => {
    if (box.scrollWidth > box.clientWidth + 1) {
      box.setAttribute("role", "region");
      box.setAttribute("aria-label", box.dataset.label);
      box.setAttribute("tabindex", "0");
    } else {
      box.removeAttribute("role");
      box.removeAttribute("aria-label");
      box.removeAttribute("tabindex");
    }
  });
}

function absentState(heading, data, extra = "") {
  return `<h1 tabindex="-1">${esc(heading)}</h1>
    <p class="lead">${status(data.status)}</p>
    <p class="note">${text(data.message)}</p>${extra}`;
}

// ---- Overview ---------------------------------------------------------------------

function evalFigures(summary) {
  const rate = summary && summary.pass_rate;
  const coverage = summary && summary.coverage;
  return `<dl class="figures">
    <div><dt>Eval pass rate</dt><dd class="value">${text(rate && rate.text)}</dd>
      <dd class="meaning">Of the briefs that have a design, how many pass.</dd></div>
    <div><dt>Eval coverage</dt><dd class="value">${text(coverage && coverage.text)}</dd>
      <dd class="meaning">Of all eval briefs, how many have a design at all.</dd></div>
  </dl>`;
}

function renderOverview(data) {
  const evals = data.latest_eval;
  const run = data.latest_run;
  const designRows = data.designs.map((d) => {
    const latest = d.latest_run;
    const links = [
      d.has_design ? `<a href="#/design/${esc(d.stem)}">Report</a>` : null,
      d.has_brief || d.has_eval_brief ? `<a href="#/brief/${esc(d.stem)}">Brief</a>` : null,
    ].filter(Boolean).join(" · ");
    return [
      `<span class="name">${esc(d.stem)}</span>`,
      status(d.status) + (latest && latest.changed_since.length ? ` ${status("STALE")}` : ""),
      status(d.eval_status) + (d.eval_status === "PASS" && evals && evals.sweep_skipped ? ` <span class="status-note">${esc(evals.summary.mode)}, sweep not run</span>` : ""),
      latest ? scopeNote(latest) : DASH,
      latest ? `<span class="path">${esc(runFolder(latest.path))}</span>` : DASH,
      latest ? `<span class="num">${when(latest.modified)}</span>` : DASH,
      links || DASH,
    ];
  });
  const noFullRun = data.designs.filter((d) => d.has_design && !d.last_full_run).map((d) => d.stem);
  const fullRuns = data.designs.filter((d) => d.last_full_run).map((d) =>
    `<span class="name">${esc(d.stem)}</span>: ${fullRunNote(d.last_full_run, d.stem, null)}`);

  const gates = run ? run.gates.map((g) => [esc(g.name), status(g.status)]) : [];

  view.innerHTML = `
    <h1 tabindex="-1">Studio overview</h1>
    <h2>Evals</h2>
    ${evalFigures(evals && evals.summary)}
    ${evals ? `<p class="note">${esc(evals.summary.mode || "Unknown")} mode eval, <span class="num">${when(evals.generated_at)}</span>, from <span class="path">${esc(evals.source.path)}</span>.</p>` : `<p class="note">No eval report on disk.</p>`}
    ${evals && evals.sweep_skipped ? `<p class="warning">${status("NOT RUN")} This eval skipped the sweep, so its pass rate says nothing about parametric behaviour.${evals.last_full ? ` ${lastFullEval(evals.last_full)}` : " No full eval is on disk."}</p>` : ""}

    <h2>Designs</h2>
    ${table("Designs and eval briefs", [
      { title: "Design" }, { title: "Latest run" }, { title: "Eval" }, { title: "Scope of that run" },
      { title: "Run folder", cls: "wide-only" }, { title: "Run time", cls: "wide-only" }, { title: "Open" },
    ], designRows)}
    ${fullRuns.map((line) => `<p class="note">${line}</p>`).join("")}
    ${noFullRun.length ? `<p class="warning">${status("NOT RUN")} No run-mode pass on disk for <span class="name">${esc(noFullRun.join(", "))}</span>. CLAUDE.md requires one before a design counts as verified.</p>` : ""}

    <h2>Latest run gates</h2>
    ${run ? `${titleBlock([
      ["Design", esc(run.design)], ["Mode", text(run.mode)], ["Source", esc(run.path)], ["Modified", when(run.modified)],
    ])}
    ${table("Gates of the latest run", [{ title: "Gate" }, { title: "Status" }], gates, { narrow: true })}` : `<p class="note">${status("NO_RUN")} No <span class="path">runs/*/report.json</span> on disk.</p>`}

    <h2>Printer profile</h2>
    ${titleBlock([
      ["Printer", esc(data.printer.name)],
      ["Build volume", `${data.printer.build_volume_mm.map(num).join(" × ")} mm`],
      ["Nozzle", `${num(data.printer.nozzle_mm)} mm`],
      ["Materials", Object.keys(data.printer.materials).map(esc).join(", ")],
    ])}
    <p class="note">Material fit clearances are starting values and have not been calibrated on a real print. Choose the material for a project in Studio.</p>
    <h2>Not covered by the gates</h2>
    ${notChecked(data.prints_logged, data.unverified)}`;
}

function lastFullEval(full) {
  const sweeps = (full.briefs || []).map((b) => `<span class="name">${esc(b.name)}</span> sweep ${num(b.parametric.passed)}/${num(b.parametric.total)}`).join(", ");
  return `The last full eval, <span class="path">${esc(full.path)}</span> from <span class="num">${when(full.generated_at)}</span>, read pass rate <span class="num">${text(full.summary.pass_rate && full.summary.pass_rate.text)}</span> and coverage <span class="num">${text(full.summary.coverage && full.summary.coverage.text)}</span>${sweeps ? `, with ${sweeps}` : ""}.`;
}

// ---- Design -----------------------------------------------------------------------

const VIEW_NAMES = {
  iso: "Isometric view", front: "Front view", top: "Top view", side: "Side view", section: "Section view",
};

function gauge(delta, tolerance, passed) {
  if (typeof delta !== "number" || !tolerance) return DASH;
  const position = Math.max(0, Math.min(100, 50 + (delta / tolerance) * 50));
  return `<span class="gauge" aria-hidden="true"><span class="gauge__end"></span><span class="gauge__end"></span>
    <span class="gauge__zero"></span><span class="gauge__mark${passed ? "" : " gauge__mark--out"}" style="left:${position}%"></span></span>`;
}

function renderGallery(data) {
  const files = data._render_files || [];
  if (!files.length) return `<p class="note">${status(gateStatus(data.gates, "4 Renders") || "NOT RUN")} This run has no renders.</p>`;
  const bbox = data.geometry && data.geometry.bbox ? Object.values(data.geometry.bbox)[0] : null;
  const size = Array.isArray(bbox) ? `, ${bbox.map((v) => num(v)).join(" by ")} millimetres overall` : "";
  const figures = files.map((f) => {
    const title = VIEW_NAMES[f.view] || f.view;
    if (!f.url) return `<figure><div class="missing">No file</div><figcaption>${esc(title)}: file missing</figcaption></figure>`;
    const alt = `${title} of ${data._stem}${size}. QA render from the reloaded STL with a flat z-buffer. Opens full size.`;
    return `<figure><a href="${esc(f.url)}"><img src="${esc(f.url)}" alt="${esc(alt)}" loading="lazy" width="920" height="920"></a><figcaption>${esc(title)}</figcaption></figure>`;
  });
  return `<div class="renders">${figures.join("")}</div>
    <p class="note">Flat z-buffer QA renders from the reloaded STL. They are an engineering check, not a finish preview.</p>`;
}

function renderSweep(sweep, gateWord) {
  if (!sweep) return `<p class="note">${status(gateWord || "NOT RUN")} This report has no sweep.</p>`;
  const dead = sweep.dead_params || [];
  const failed = (sweep.rows || []).filter((row) => !row.pass);
  const rows = [
    ["Samples passed", `${num(sweep.passed)} of ${num(sweep.total)}`],
    ["Printable samples", `${num(sweep.printable_passed)} of ${num(sweep.total)}`],
    ["Required pass share", typeof sweep.required_share === "number" ? `${num(sweep.required_share * 100)} %` : DASH],
    ["Dead parameters", dead.length ? esc(dead.join(", ")) : "none"],
    ["Worst support risk", `${num(sweep.max_support_risk_pct, 1)} %`],
    ["Worst brief overhang", `${num(sweep.max_overhang_brief_pct, 1)} %`],
  ];
  const failing = failed.length
    ? `<h3>Failing samples</h3>${table("Failing sweep samples", [{ title: "Sample" }, { title: "Problems" }],
      failed.map((row) => [`<span class="name">${esc(row.label)}</span>`, esc((row.problems || []).join("; ")) || DASH]))}`
    : "";
  return table("Sweep summary", [{ title: "Measure" }, { title: "Result", cls: "n" }], rows, { narrow: true }) + failing;
}

function wireJumps() {
  view.querySelectorAll("[data-jump]").forEach((link) => link.addEventListener("click", (event) => {
    event.preventDefault();  // an in-page jump, not a route change
    const target = document.getElementById(link.dataset.jump);
    target.scrollIntoView();
    target.focus({ preventScroll: true });
  }));
}

function renderDesign(data) {
  const stem = data._stem;
  const gates = (data.gates || []).map((g) => [esc(g.name), status(g.status), g.detail && g.detail !== "-" ? `<span class="num">${esc(g.detail)}</span>` : DASH]);
  const tolerance = data._tolerance_mm;
  const dims = ((data.geometry && data.geometry.dimensions) || []).map((d) => [
    `<span class="name">${esc(d.name)}</span>`,
    // Three decimals: the gate compares against ±0.1, so 0.104 must not read as 0.1.
    num(d.spec, 3), num(d.measured, 3), num(d.delta, 3),
    gauge(d.delta, tolerance, d.pass),
    status(passWord(d.pass)),
  ]);
  const params = Object.entries(data.params || {}).map(([key, value]) => [`<span class="name">${esc(key)}</span>`, num(value)]);
  const shownPath = data._source.path;
  const runRows = (data._runs || []).map((r) => [
    r.path === shownPath ? `<span class="path">${esc(r.folder)}</span> (shown)` : `<a class="path" href="#/design/${esc(stem)}/${esc(r.folder)}">${esc(r.folder)}</a>`,
    text(r.mode),
    status(passWord(r.pass)),
    scopeNote(r),
    `<span class="num">${when(r.modified)}</span>`,
  ]);
  const notFull = gateStatus(data.gates, "5 Exports") === "NOT RUN" || gateStatus(data.gates, "Sweep") === "NOT RUN";
  const changed = data._changed_since || [];

  view.innerHTML = `
    <h1 tabindex="-1">Design: <span class="name">${esc(stem)}</span></h1>
    ${titleBlock([
      ["Harness result", status(passWord(data.pass))],
      ["Scope", scopeNote({ mode: data._mode, gates: data.gates })],
      ["Source", esc(data._source.path)],
      ["Modified", when(data._source.modified)],
    ])}
    <p class="note">A harness pass means the gates passed. It is not a design verdict; <a href="#/design/${esc(stem)}" data-jump="not-covered">see what the gates do not cover</a>.</p>
    ${data._is_newest ? "" : `<p class="warning">${status("OLDER")} This is an older run, not the newest. <a href="#/design/${esc(stem)}">Go to the newest run</a>.</p>`}
    ${changed.length ? `<p class="warning">${status("STALE")} Changed after this run, so these results may not describe them: <span class="path">${esc(changed.join(", "))}</span>.</p>` : ""}
    ${notFull ? `<p class="warning">${status("NOT RUN")} This ${text(data._mode)} mode run did not complete every gate, so it does not meet the project's definition of verified. ${fullRunNote(data._last_full_run, stem, shownPath)}</p>` : ""}

    <h2>Gates</h2>
    ${table("Gate checklist", [{ title: "Gate" }, { title: "Status" }, { title: "Detail" }], gates)}

    <h2>Dimensions</h2>
    ${dims.length ? table("Brief target against measured dimension", [
      { title: "Dimension" }, { title: "Brief target", cls: "n" }, { title: "Measured", cls: "n" }, { title: "Delta", cls: "n" },
      { title: tolerance ? `Delta within ±${tolerance}` : "Tolerance", cls: "gauge-cell" }, { title: "Result" },
    ], dims) + `<p class="note">Lengths in mm, hole counts unitless, measured on the reloaded STEP.</p>` : `<p class="note">${DASH} This report has no dimensions.</p>`}

    <h2>Sweep</h2>
    ${renderSweep(data.sweep, gateStatus(data.gates, "Sweep"))}

    <h2>Parameters</h2>
    ${params.length ? table("Parameters used in this run", [{ title: "Parameter" }, { title: "Value", cls: "n" }], params, { narrow: true }) : `<p class="note">${DASH} This report has no parameters.</p>`}
    <p class="note">Units, ranges, and intent are on the <a href="#/brief/${esc(stem)}">brief</a>.</p>

    <h2>Renders</h2>
    ${renderGallery(data)}

    <h2>Run history</h2>
    ${table("Runs of this design, newest first", [{ title: "Run folder" }, { title: "Mode" }, { title: "Result" }, { title: "Scope", cls: "wide-only" }, { title: "Modified" }], runRows)}

    <h2 id="not-covered" tabindex="-1">Not covered by the gates</h2>
    ${notChecked(data._prints_logged, data._unverified)}`;
  wireJumps();
}

// ---- Brief ------------------------------------------------------------------------

function sliderStep(min, max) {
  return 10 ** (Math.floor(Math.log10(max - min)) - 1);
}

function paramControl(key, raw) {
  const p = raw && typeof raw === "object" ? raw : { value: raw };
  const ranged = typeof p.value === "number" && typeof p.min === "number" && typeof p.max === "number" && p.max > p.min;
  const unit = p.unit ? esc(p.unit) : "";
  if (!ranged) {
    return `<div class="param"><span class="name">${esc(key)}</span><span></span>
      <span class="param__value">${num(p.value)} ${unit}</span>
      <p class="param__intent">${text(p.intent)} No range in the brief, so no slider.</p></div>`;
  }
  const origin = (p.value - p.min) / (p.max - p.min);
  const id = `param-${esc(key)}`;
  return `<div class="param">
    <label for="${id}">${esc(key)}</label>
    <div class="range">
      <span class="range__line"></span>
      <span class="range__tick" style="--at:0"></span><span class="range__tick" style="--at:1"></span>
      <span class="range__tick range__tick--origin" style="--at:${origin}"></span>
      <input type="range" id="${id}" data-key="${esc(key)}" data-origin="${p.value}" data-unit="${unit}"
        min="${p.min}" max="${p.max}" step="${sliderStep(p.min, p.max)}" value="${p.value}"
        aria-describedby="${id}-intent draft-note" aria-valuetext="${num(p.value)} ${unit}">
      <span class="range__ends"><span>${num(p.min)}</span><span>${num(p.max)}</span></span>
    </div>
    <output class="param__value" for="${id}" id="${id}-out" aria-live="off"><span>${num(p.value)}</span> ${unit}</output>
    <p class="param__intent" id="${id}-intent">${text(p.intent)}</p>
  </div>`;
}

function hardDimensionRows(brief) {
  const measures = brief.measures || {};
  return Object.entries(brief.hard_dimensions || {}).map(([key, value]) => {
    const m = measures[key];
    const how = m ? Object.entries(m).map(([k, v]) => `${label(k)} ${esc(v)}`).join(", ") : DASH;
    return [`<span class="name">${esc(key)}</span>`, num(value), `<span class="name">${how}</span>`];
  });
}

const bulletList = (items) => (items && items.length
  ? `<ul class="plain-list">${items.map((item) => `<li>${esc(item)}</li>`).join("")}</ul>`
  : `<p class="note">${DASH}</p>`);

function renderBrief(brief) {
  const stem = brief._stem;
  const params = Object.entries(brief.params || {});
  const anyRange = params.some(([, p]) => p && typeof p.value === "number" && typeof p.min === "number" && typeof p.max === "number");
  const check = `.venv/bin/python magic.py check designs/${esc(stem)}.py --brief ${esc(brief._source.path)}`;
  const others = (window.__stems || []).filter((s) => s !== stem);

  view.innerHTML = `
    <h1 tabindex="-1">Brief: <span class="name">${esc(stem)}</span></h1>
    ${titleBlock([
      ["Source", esc(brief._source.path)],
      ["Modified", when(brief._source.modified)],
      ["Design", brief._has_design ? `<a href="#/design/${esc(stem)}">designs/${esc(stem)}.py</a>` : status("NO_DESIGN")],
    ])}
    ${others.length ? `<p class="note">Other briefs: ${others.map((s) => `<a href="#/brief/${esc(s)}" class="name">${esc(s)}</a>`).join(" · ")}</p>` : ""}

    <h2>Function</h2>
    <p class="prose">${text(brief.function)}</p>

    <h2>Hard dimensions</h2>
    ${table("Hard dimensions and how the harness measures each", [{ title: "Dimension" }, { title: "Target", cls: "n" }, { title: "Measured by" }], hardDimensionRows(brief))}
    <p class="note">Lengths in mm, hole counts unitless. The harness measures each one on the reloaded STEP.</p>

    <h2>Interfaces</h2>
    ${bulletList(brief.interfaces)}

    <h2>Soft preferences</h2>
    ${bulletList(brief.soft_preferences)}

    <h2>Assumptions</h2>
    ${bulletList(brief.assumptions)}

    <h2>Parameters</h2>
    <div class="draft-bar">
      <p id="draft-note"><span class="draft-label">DRAFT</span>These sliders only move on this page. They do not rebuild the design, change the brief, or alter any result. Rebuild wiring lands in a later phase.</p>
      <p id="moved-count" class="draft-bar__count" aria-live="polite">No values moved.</p>
    </div>
    <div class="params">${params.map(([key, p]) => paramControl(key, p)).join("") || `<p class="note">${DASH} This brief has no parameters.</p>`}</div>
    <div class="actions">
      ${anyRange ? `<button type="button" class="button" id="reset-params" disabled>Reset to brief values</button>` : ""}
      <button type="button" class="button" disabled aria-describedby="run-check-why">Run check</button>
      <p id="run-check-why">Run check is disabled until rebuild wiring lands in a later phase. ${brief._has_design ? `Until then, use <code>${check}</code>.` : `There is also no <span class="path">designs/${esc(stem)}.py</span> to check yet.`}</p>
    </div>`;

  wireSliders();
}

function wireSliders() {
  const sliders = [...view.querySelectorAll('input[type="range"]')];
  const reset = document.getElementById("reset-params");
  const paint = (slider) => {
    const value = Number(slider.value);
    const shown = num(value);
    const moved = Math.abs(value - Number(slider.dataset.origin)) > 1e-9;
    const out = document.getElementById(`${slider.id}-out`);
    out.innerHTML = `<span${moved ? ' class="moved"' : ""}>${shown}</span> ${esc(slider.dataset.unit)}${moved ? ' <span class="moved">not applied</span>' : ""}`;
    slider.setAttribute("aria-valuetext", `${shown} ${slider.dataset.unit}${moved ? ", moved from the brief value, not applied" : ""}`);
  };
  const syncReset = () => {
    const moved = sliders.filter((s) => Math.abs(Number(s.value) - Number(s.dataset.origin)) > 1e-9).length;
    if (reset) reset.disabled = moved === 0;
    const count = document.getElementById("moved-count");
    if (count) count.textContent = moved ? `${moved} moved, none applied.` : "No values moved.";
  };
  sliders.forEach((slider) => slider.addEventListener("input", () => { paint(slider); syncReset(); }));
  if (reset) {
    reset.addEventListener("click", () => {
      sliders.forEach((slider) => { slider.value = slider.dataset.origin; paint(slider); });
      syncReset();
      if (sliders[0]) sliders[0].focus();
    });
  }
}

// ---- Evals ------------------------------------------------------------------------

function renderEvals(data) {
  const summary = data.summary || {};
  const quick = (data.briefs || []).some((b) => gateStatus(b.gates, "Sweep") === "NOT RUN");
  const full = data._last_full_eval;
  const parametric = (b) => {
    if (b.parametric && typeof b.parametric === "object") return `${status(b.parametric.passed === b.parametric.total ? "PASS" : "FAIL")} <span class="num">${num(b.parametric.passed)}/${num(b.parametric.total)}</span>`;
    if (typeof b.parametric === "boolean") return yesNo(b.parametric);
    return gateStatus(b.gates, "Sweep") ? status(gateStatus(b.gates, "Sweep")) : DASH;
  };
  const rows = (data.briefs || []).map((b) => {
    const dims = b.dimensional ? `${num(b.dimensional.passed)}/${num(b.dimensional.total)}` : DASH;
    return [
      `<a class="name" href="#/brief/${esc(b.name)}">${esc(b.name)}</a>`,
      status(b.status),
      yesNo(b.runs),
      `<span class="num">${dims}</span>`,
      yesNo(b.printable),
      parametric(b),
      missing(b.seconds) ? DASH : num(b.seconds, 1),
      text(b.reason),
    ];
  });

  view.innerHTML = `
    <h1 tabindex="-1">Evals</h1>
    ${titleBlock([
      ["Mode", text(summary.mode)],
      ["Source", esc(data._source.path)],
      ["Generated", when(data.generated_at)],
      ["Exit code", text(summary.exit_code)],
      ["Eval runs on disk", text(data._eval_runs_on_disk)],
    ])}
    ${evalFigures(summary)}
    ${table("Eval counts", [{ title: "Passed", cls: "n" }, { title: "Failed", cls: "n" }, { title: "Errored", cls: "n" }, { title: "No design", cls: "n" }],
      [[num(summary.passed), num(summary.failed), num(summary.errored), num(summary.no_design)]], { noRowHeader: true, narrow: true })}
    ${quick ? `<p class="warning">${status("NOT RUN")} This ${text(summary.mode)} eval skipped the sweep and kept no exports, so a PASS below does not cover parametric behaviour.${full ? ` ${lastFullEval(full)}` : " No full eval is on disk."}</p>` : ""}

    <h2>Per brief</h2>
    ${table("Per-brief eval results", [
      { title: "Brief" }, { title: "Status" }, { title: "Runs" }, { title: "Dimensions", cls: "n" },
      { title: "Printable" }, { title: "Parametric" }, { title: "Seconds", cls: "n" }, { title: "Reason" },
    ], rows)}`;
}

// ---- Library ----------------------------------------------------------------------

function libraryCategory(name, parts) {
  const entries = Object.entries(parts || {});
  const columns = [...new Set(entries.flatMap(([, part]) => Object.keys(part || {})))];
  const headers = [{ title: "Part" }, ...columns.map((c) => {
    const numeric = entries.some(([, part]) => typeof (part || {})[c] === "number");
    return { title: c.replace(/_/g, " "), cls: numeric ? "n" : "" };
  })];
  const rows = entries.map(([id, part]) => [
    `<span class="name">${esc(id)}</span>`,
    ...columns.map((c) => (part ? num(part[c]) : DASH)),
  ]);
  return `<h2>${label(name).replace(/^./, (c) => c.toUpperCase())}</h2>${table(`${label(name)} dimensions`, headers, rows)}`;
}

function renderLibrary(data, announce = false) {
  const categories = Object.entries(data).filter(([key]) => !key.startsWith("_"));
  view.innerHTML = `
    <h1 tabindex="-1">Standard parts</h1>
    ${titleBlock([["Standard parts source", esc(data._source.path)], ["Modified", when(data._source.modified)], ["Categories", String(categories.length)]])}
    ${data._notes ? `<p class="note catalogue-notes">${esc(data._notes)}</p>` : ""}
    ${categories.map(([name, parts]) => libraryCategory(name, parts)).join("")}
    <h2>Purchased components</h2>
    <p class="note">Catalogue sources: ${(data._catalogue_sources || []).map((source) => `<span class="path">${esc(source)}</span>`).join(", ")}</p>
    <p id="catalogue-loaded" role="status" tabindex="-1">${announce ? (data._project ? `Showing catalogue for ${esc(data._project)}.` : "Showing the shared catalogue.") : ""}</p>
    <form id="catalogue-project-form">
      <label for="catalogue-project">Project folder</label>
      <input id="catalogue-project" name="project" type="text" value="${esc(data._project || "")}" placeholder="/path/to/project" autocomplete="off">
      <button type="submit" class="button">Show project catalogue</button>
      <p class="note">Enter a Magic CAD project folder to include its measured components. Leave blank for the shared catalogue.</p>
      <p id="catalogue-error" role="alert"></p>
    </form>
    ${(data._components || []).map((component) => `
      <h3>${esc(component.name)}</h3>
      <p class="catalogue-notes">${esc(component.notes || "")}</p>
      <p>Catalogue file: <span class="path">${esc(component._catalogue_file?.path || "Unknown")}</span> · Modified ${when(component._catalogue_file?.modified)}</p>
      <p>Source: ${/^https:\/\//.test(component.source || "") ? `<a href="${esc(component.source)}">Manufacturer drawing</a>` : esc(component.source || "Not provided")}</p>
      ${table(`${component.name} dimensions`, [{ title: "Dimension" }, { title: "mm", cls: "n" }, { title: "Evidence" }],
        Object.entries(component.dimensions).map(([name, dimension]) => [esc(label(name)), num(dimension.value), esc(dimension.provenance)]))}
    `).join("") || "<p>No purchased components are available.</p>"}`;
  const form = document.getElementById("catalogue-project-form");
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const project = document.getElementById("catalogue-project").value.trim();
    const error = document.getElementById("catalogue-error");
    const button = form.querySelector("button");
    button.disabled = true;
    error.textContent = "";
    try {
      const result = await fetchJson(`/api/library${project ? `?project=${encodeURIComponent(project)}` : ""}`);
      if (!form.isConnected) return;
      if (result.ok) {
        renderLibrary(result.data, true);
        document.getElementById("catalogue-loaded").focus();
      }
      else error.textContent = result.data.message || "Could not read this project catalogue.";
    } catch {
      if (form.isConnected) error.textContent = "Could not read the catalogue. Check that Mission Control is running.";
    } finally {
      button.disabled = false;
    }
  });
}

// ---- Router -----------------------------------------------------------------------

const ROUTES = {
  overview: { nav: "overview", title: () => "Overview", url: () => "/api/overview", render: renderOverview, heading: "Studio overview" },
  design: { nav: "design", title: (s) => `Design ${s}`, url: (s, run) => `/api/design/${encodeURIComponent(s)}${run ? `?run=${encodeURIComponent(run)}` : ""}`, render: renderDesign, heading: "Design", stem: true },
  brief: { nav: "brief", title: (s) => `Brief ${s}`, url: (s) => `/api/brief/${encodeURIComponent(s)}`, render: renderBrief, heading: "Brief", stem: true },
  evals: { nav: "evals", title: () => "Evals", url: () => "/api/evals", render: renderEvals, heading: "Evals" },
  library: { nav: "library", title: () => "Library", url: () => "/api/library", render: renderLibrary, heading: "Standard parts" },
};

let currentLoad = 0;
let assemblyModule = null;
let studioModule = null;  // Three.js is 1.3 MB: Mission Control never pays for it

function setSurface(surface) {
  document.documentElement.dataset.surface = surface;
  document.querySelector('meta[name="theme-color"]').content = surface === "studio" ? "#ece9e3" : "#0c1116";
}

async function showStudio(stem, ticket) {
  setSurface("studio");
  studioModule ??= import("/studio.js");
  try {
    const studio = await studioModule;
    if (ticket === currentLoad) await studio.enter(stem);
  } catch (error) {
    studioModule = null;  // a failed import is cached by the promise, so the next visit must retry
    document.getElementById("st-absent").textContent = `The 3D studio could not load: ${error.message}. Mission control still works.`;
    document.getElementById("st-absent").hidden = false;
  }
}

function leaveStudio() {
  setSurface("control");
  studioModule?.then((studio) => studio.leave()).catch(() => {});
}

function parseRoute() {
  const [, name = "studio", stem, run] = location.hash.match(/^#\/([^/]+)(?:\/([^/]+))?(?:\/([^/]+))?/) || [];
  if (name === "studio") return { studio: true, stem: stem ? decodeURIComponent(stem) : null };
  if (name === "assembly") return { assembly: true };
  const route = Object.hasOwn(ROUTES, name) ? ROUTES[name] : null;
  if (!route) return { route: null, name };
  return { route, stem: route.stem ? decodeURIComponent(stem || DEFAULT_STEM) : null, run: run ? decodeURIComponent(run) : null };
}

function setNav(active) {
  document.querySelectorAll("[data-nav]").forEach((link) => {
    if (link.dataset.nav === active) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  });
}

function showLoading(route) {
  view.setAttribute("aria-busy", "true");
  view.innerHTML = `<h1>${esc(route.heading)}</h1><div aria-hidden="true"><span class="skeleton"></span><span class="skeleton"></span><span class="skeleton"></span></div>`;
}

function connectionError(error) {
  view.innerHTML = `<h1 tabindex="-1">Could not read project data</h1>
    <p class="lead">${esc(error.message)}</p>
    <p class="note">${error.fromServer
    ? "The server is running but could not answer this request. Check the file or address it names."
    : "Check that the server is running from the project root: <code>.venv/bin/python ui/server.py</code>"}</p>
    <div class="actions"><button type="button" class="button" id="retry">Try again</button></div>`;
  document.getElementById("retry").addEventListener("click", () => load({ focus: true }));
}

async function load({ focus = false } = {}) {
  const ticket = ++currentLoad;
  let parsed;
  try {
    parsed = parseRoute();
  } catch {
    parsed = { route: null, name: null };
  }
  const { route, stem, run, name } = parsed;
  assemblyModule?.then((module) => module.leave()).catch(() => {});
  if (parsed.studio) return showStudio(stem, ticket);
  leaveStudio();
  if (parsed.assembly) {
    setNav("assembly");
    document.title = "Assembly · Magic CAD";
    view.setAttribute("aria-busy", "true");
    view.innerHTML = "<h1>Assembly</h1><p>Loading the model…</p>";
    try {
      assemblyModule ??= import("/assembly.js");
      const module = await assemblyModule;
      if (ticket === currentLoad) await module.enter(view, () => ticket === currentLoad);
    } catch (error) {
      if (ticket === currentLoad) connectionError(error);
    }
    if (ticket === currentLoad) view.removeAttribute("aria-busy");
    return;
  }
  if (!route) {
    setNav(null);
    view.removeAttribute("aria-busy");
    view.innerHTML = `<h1 tabindex="-1">${name ? `No view called ${esc(name)}` : "No view at this address"}</h1><p class="note"><a href="#/overview">Go to the overview</a></p>`;
    readAt.textContent = "";
    view.querySelector("h1").focus();
    return;
  }
  setNav(route.nav);
  document.title = `${route.title(stem)} · Magic CAD studio`;
  showLoading(route);
  try {
    const result = await fetchJson(route.url(stem, run));
    if (route.nav === "brief" && !window.__stems) {
      const list = await fetchJson("/api/overview");
      window.__stems = list.ok ? list.data.designs.filter((d) => d.has_brief || d.has_eval_brief).map((d) => d.stem) : [];
    }
    if (ticket !== currentLoad) return;
    if (result.ok) route.render(result.data);
    else {
      const backToBrief = route.nav === "design" ? `<p class="note"><a href="#/brief/${esc(stem)}">Read the ${esc(stem)} brief</a></p>` : "";
      view.innerHTML = absentState(stem ? `${route.heading}: ${stem}` : route.heading, result.data, backToBrief);
    }
    readAt.textContent = `Files read ${new Date().toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false })}`;
  } catch (error) {
    if (ticket !== currentLoad) return;
    if (!error.fromServer && !(error instanceof TypeError && /fetch/i.test(error.message))) {
      error.fromServer = true;  // a render fault on data the server did return
      error.message = `This view could not be drawn from the data on disk: ${error.message}`;
    }
    connectionError(error);
    readAt.textContent = "Last read failed";
  }
  view.removeAttribute("aria-busy");
  syncScrollRegions();
  if (focus) {
    const heading = view.querySelector("h1");
    if (heading) heading.focus({ preventScroll: true });
    window.scrollTo(0, 0);
  }
}

window.addEventListener("hashchange", () => {
  if (location.hash.startsWith("#/") || !location.hash) load({ focus: true });
});
window.addEventListener("resize", syncScrollRegions);
document.querySelector(".skip").addEventListener("click", (event) => {
  event.preventDefault();  // #view is not a route, so it must not reach the router
  view.focus();
});
document.getElementById("reload").addEventListener("click", () => { window.__stems = null; load(); });
load();
