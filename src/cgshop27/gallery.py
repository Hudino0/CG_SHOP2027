"""A single self-contained HTML page for browsing the instance set.

Images are referenced relatively, so the page and the `renders/` directory
travel together. Everything else -- the catalog table, the per-run objectives --
is embedded as JSON and rendered client-side, which keeps sorting and filtering
instant even for a few hundred instances.
"""

from __future__ import annotations

import json
from pathlib import Path

from .catalog import InstanceStats
from .config import OUT, RENDERS

_TEMPLATE = """<!doctype html>
<meta charset="utf-8">
<title>CG:SHOP 2027 &mdash; instance browser</title>
<style>
  :root {
    color-scheme: light dark;
    --bg: #ffffff; --fg: #17181c; --muted: #6b7280;
    --line: #e3e5ea; --card: #f7f8fa; --accent: #1f77b4;
  }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#14161a; --fg:#e8eaee; --muted:#9aa1ad;
            --line:#2a2e36; --card:#1b1e24; --accent:#5fa8dc; }
  }
  * { box-sizing: border-box; }
  body { margin:0; padding:24px; background:var(--bg); color:var(--fg);
         font:14px/1.5 ui-sans-serif,system-ui,"Segoe UI",sans-serif; }
  h1 { font-size:20px; margin:0 0 4px; }
  .sub { color:var(--muted); margin-bottom:18px; }
  .bar { display:flex; gap:10px; flex-wrap:wrap; align-items:center;
         margin-bottom:16px; }
  input, select { padding:6px 9px; border:1px solid var(--line);
                  border-radius:7px; background:var(--card); color:var(--fg);
                  font:inherit; }
  input[type=search] { min-width:240px; }
  .stats { display:flex; gap:22px; flex-wrap:wrap; margin-bottom:18px;
           padding:12px 16px; background:var(--card); border-radius:10px; }
  .stat b { display:block; font-size:18px; }
  .stat span { color:var(--muted); font-size:12px; }
  .grid { display:grid; gap:14px;
          grid-template-columns:repeat(auto-fill,minmax(340px,1fr)); }
  .card { border:1px solid var(--line); border-radius:10px; overflow:hidden;
          background:var(--card); }
  .card img { width:100%; display:block; background:#fff; cursor:zoom-in; }
  .card .body { padding:9px 12px 12px; }
  .card .uid { font-weight:600; font-family:ui-monospace,monospace;
               font-size:12.5px; word-break:break-all; }
  .kv { display:flex; flex-wrap:wrap; gap:4px 10px; margin-top:6px;
        color:var(--muted); font-size:12px; }
  .kv b { color:var(--fg); font-weight:600; }
  table { border-collapse:collapse; width:100%; font-size:12.5px; }
  th, td { padding:5px 9px; border-bottom:1px solid var(--line);
           text-align:right; white-space:nowrap; }
  th:first-child, td:first-child { text-align:left;
           font-family:ui-monospace,monospace; }
  th { position:sticky; top:0; background:var(--bg); cursor:pointer;
       user-select:none; }
  th:hover { color:var(--accent); }
  .wrap { overflow-x:auto; border:1px solid var(--line); border-radius:10px; }
  .hide { display:none; }
  dialog { border:none; border-radius:10px; padding:0; max-width:95vw;
           background:var(--card); }
  dialog img { display:block; max-width:92vw; max-height:88vh; background:#fff; }
</style>

<h1>CG:SHOP 2027 &mdash; instance browser</h1>
<div class="sub">Multi-Robot Lawn Mowing for Polyominoes &middot; __COUNT__ instances</div>

<div class="stats" id="summary"></div>

<div class="bar">
  <input type="search" id="q" placeholder="filter by uid or family&hellip;">
  <select id="family"></select>
  <select id="cutters"></select>
  <select id="sort"></select>
  <select id="view">
    <option value="grid">gallery</option>
    <option value="table">table</option>
  </select>
  <select id="pic"></select>
</div>

<div class="grid" id="grid"></div>
<div class="wrap hide" id="tablewrap"><table id="table"></table></div>
<dialog id="zoom"><img></dialog>

<script>
const ROWS = __ROWS__;
const RUNS = __RUNS__;          // {run: {uid: {objective, feasible, gap}}}
const IMAGES = __IMAGES__;      // {source: {uid: relative path}}

const NUMERIC = ["number_of_cutters","region_area","region_components",
  "region_width","region_height","bbox_fill","outer_vertices","holes",
  "hole_vertices","cutter_area","cutter_width","cutter_height",
  "cutter_vertices","cutter_cross_section","area_over_cutter","lower_bound"];

for (const row of ROWS)
  for (const [run, byUid] of Object.entries(RUNS)) {
    const v = byUid[row.instance_uid];
    row["obj:" + run] = v && v.feasible ? v.objective : null;
    row["gap:" + run] = v && v.feasible ? v.gap : null;
  }

const runCols = Object.keys(RUNS).flatMap(r => ["obj:" + r, "gap:" + r]);
const COLUMNS = ["instance_uid", "family", ...NUMERIC, ...runCols];

const $ = id => document.getElementById(id);
const fill = (el, opts, label) => {
  el.innerHTML = opts.map(o =>
    '<option value="' + o[0] + '">' + label + o[1] + '</option>').join("");
};

fill($("family"), [["", "all families"],
  ...[...new Set(ROWS.map(r => r.family))].sort().map(f => [f, f])], "");
fill($("cutters"), [["", "any k"],
  ...[...new Set(ROWS.map(r => r.number_of_cutters))]
      .sort((a, b) => a - b).map(k => [k, "k = " + k])], "");
fill($("sort"), COLUMNS.map(c => [c, c]), "sort: ");
fill($("pic"), Object.keys(IMAGES).map(s => [s, s]), "show: ");
$("sort").value = "instance_uid";

let descending = false;

const median = xs => {
  const s = xs.filter(v => v !== null && v !== undefined).sort((a, b) => a - b);
  return s.length ? s[Math.floor(s.length / 2)] : 0;
};
const fmt = v => v === null || v === undefined ? "&mdash;"
  : typeof v === "number" ? v.toLocaleString("en-US") : v;

function selected() {
  const q = $("q").value.trim().toLowerCase();
  const family = $("family").value, k = $("cutters").value;
  const key = $("sort").value;
  const rows = ROWS.filter(r =>
    (!q || r.instance_uid.toLowerCase().includes(q)) &&
    (!family || r.family === family) &&
    (!k || String(r.number_of_cutters) === k));
  rows.sort((a, b) => {
    const x = a[key], y = b[key];
    if (x === y) return a.instance_uid.localeCompare(b.instance_uid);
    if (x === null || x === undefined) return 1;
    if (y === null || y === undefined) return -1;
    return (typeof x === "number" ? x - y : String(x).localeCompare(String(y)))
           * (descending ? -1 : 1);
  });
  return rows;
}

function summary(rows) {
  const sum = f => rows.reduce((t, r) => t + f(r), 0);
  const cards = [
    ["instances", rows.length],
    ["median area", median(rows.map(r => r.region_area))],
    ["max area", Math.max(0, ...rows.map(r => r.region_area))],
    ["cutters k", [...new Set(rows.map(r => r.number_of_cutters))]
        .sort((a, b) => a - b).join(", ") || "-"],
    ["with holes", rows.filter(r => r.holes > 0).length],
    ["total vertices", sum(r => r.outer_vertices + r.hole_vertices)],
  ];
  for (const run of Object.keys(RUNS)) {
    const ok = rows.filter(r => r["obj:" + run] !== null);
    cards.push([run + " feasible", ok.length + " / " + rows.length]);
    if (ok.length) cards.push([run + " median gap",
      median(ok.map(r => r["gap:" + run])).toFixed(2) + "x"]);
  }
  $("summary").innerHTML = cards.map(([label, value]) =>
    '<div class="stat"><b>' + value + '</b><span>' + label + '</span></div>')
    .join("");
}

function drawGrid(rows) {
  const source = IMAGES[$("pic").value] || {};
  $("grid").innerHTML = rows.map(r => {
    const src = source[r.instance_uid];
    const objectives = Object.keys(RUNS).map(run =>
      '<span>' + run + ' <b>' + fmt(r["obj:" + run]) + '</b></span>').join("");
    const image = src
      ? '<img loading="lazy" src="' + src + '" alt="' + r.instance_uid + '">'
      : "";
    return '<div class="card">' + image +
      '<div class="body"><div class="uid">' + r.instance_uid + '</div>' +
      '<div class="kv">' +
        '<span>k <b>' + r.number_of_cutters + '</b></span>' +
        '<span>area <b>' + fmt(r.region_area) + '</b></span>' +
        '<span>holes <b>' + r.holes + '</b></span>' +
        '<span>cutter <b>' + r.cutter_width + '&times;' + r.cutter_height +
          '</b></span>' +
        '<span>LB <b>' + fmt(r.lower_bound) + '</b></span>' +
        objectives +
      '</div></div></div>';
  }).join("");
}

function drawTable(rows) {
  const head = "<tr>" + COLUMNS.map(c =>
    '<th data-c="' + c + '">' + c + '</th>').join("") + "</tr>";
  const body = rows.map(r => "<tr>" + COLUMNS.map(c =>
    "<td>" + fmt(r[c]) + "</td>").join("") + "</tr>").join("");
  $("table").innerHTML = head + body;
  for (const th of $("table").querySelectorAll("th"))
    th.onclick = () => {
      const c = th.dataset.c;
      descending = $("sort").value === c ? !descending : false;
      $("sort").value = c;
      draw();
    };
}

function draw() {
  const rows = selected();
  summary(rows);
  const table = $("view").value === "table";
  $("grid").classList.toggle("hide", table);
  $("tablewrap").classList.toggle("hide", !table);
  if (table) drawTable(rows); else drawGrid(rows);
}

for (const id of ["q", "family", "cutters", "sort", "view", "pic"])
  $(id).addEventListener("input", draw);

$("grid").addEventListener("click", event => {
  if (event.target.tagName !== "IMG") return;
  $("zoom").querySelector("img").src = event.target.src;
  $("zoom").showModal();
});
$("zoom").addEventListener("click", () => $("zoom").close());

draw();
</script>
"""


def _relative(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def collect_images(base: Path = OUT) -> dict[str, dict[str, str]]:
    """Every rendered PNG, grouped by what produced it."""
    sources: dict[str, dict[str, str]] = {}
    instances = RENDERS / "instances"
    if instances.is_dir():
        found = {png.stem: _relative(png, base) for png in sorted(instances.glob("*.png"))}
        if found:
            sources["instance"] = found
    solutions = RENDERS / "solutions"
    if solutions.is_dir():
        for run_dir in sorted(p for p in solutions.iterdir() if p.is_dir()):
            found = {
                png.stem: _relative(png, base) for png in sorted(run_dir.glob("*.png"))
            }
            if found:
                sources[f"solution: {run_dir.name}"] = found
    return sources or {"instance": {}}


def build(
    stats: list[InstanceStats],
    runs: dict[str, dict[str, dict]] | None = None,
    *,
    target: Path | None = None,
) -> Path:
    target = target or OUT / "gallery.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    rows = [s.as_row() | {"cutter_center": list(s.cutter_center)} for s in stats]
    html = (
        _TEMPLATE.replace("__COUNT__", str(len(rows)))
        .replace("__ROWS__", json.dumps(rows))
        .replace("__RUNS__", json.dumps(runs or {}))
        .replace("__IMAGES__", json.dumps(collect_images(target.parent)))
    )
    target.write_text(html, encoding="utf-8")
    return target
