# AGENTS.md — kopdes-vis project knowledge base

> For AI agents and new contributors. Read this before doing anything else.

## What this project is

Analysis pipeline for **KDMP** (Koperasi Desa Merah Putih), Indonesia's nationwide village-cooperative program. We have ~83,000 cooperative locations, their financial/operational stats, and are building spatial analytics to investigate claims of misplacement, cannibalization with existing retail, and budget inefficiency.

**Repo**: `danylaksono/kopdes-vis` on GitHub.

## Key documents

| File                       | Purpose                                                                                                                                 |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `analytics-plan.md`        | Full analytical blueprint — modules A–F, hypotheses, external data wishlist                                                             |
| `analytics-plan-review.md` | **Feasibility triage of the above (2026-08-09).** Corrects several load-bearing errors in the plan; read it before acting on any module |
| `reports/README.md`        | Index of completed analyses + the running "what we can and cannot say" list                                                             |
| `README.md`                | Project overview, data layout, how to regenerate data                                                                                   |
| `geo/README.md`            | Boundary shapefile pipeline (download → convert → link to kopdes stats)                                                                 |

## Data inventory

### Primary data (committed in `data/raw/`)

All sourced from SIMKOPDES public API (no auth required). Snapshot date: **2026-08-05**.

| File                                       | Rows   | Key point                                                                                                                                                                                                               |
| ------------------------------------------ | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `kopdes_locations.csv`                     | ~83k   | Every cooperative: id, name, admin hierarchy, lat/lon                                                                                                                                                                   |
| `kopdes_land_assets.csv`                   | ~66k   | Land/building verification status per cooperative                                                                                                                                                                       |
| `kopdes_stats_province.csv`                | 38     | Per-province: transactions, savings, NPWP/NIB, health scores                                                                                                                                                            |
| `kopdes_stats_district.csv`                | ~514   | Same stats at district level                                                                                                                                                                                            |
| `kopdes_stats_subdistrict.csv`             | ~7.2k  | Same stats at subdistrict level                                                                                                                                                                                         |
| `kopdes_stats_village.csv`                 | ~83k   | Same stats at village level (many zeros — most villages have 1 coop with minimal activity)                                                                                                                              |
| `kopdes_national_summary.csv`              | 1      | Headline numbers: **IDR 179.5 billion** (_miliar_, ~USD 11M) total transactions, 1.8M members. **Not trillion** — the old "179.5T" here was wrong by 1000×; externally confirmed in `reports/09-external-corroboration` |
| `kopdes_province_rat_and_construction.csv` | 38     | RAT compliance (**all zeros — major red flag**), construction progress                                                                                                                                                  |
| `kopdes_province_top_products.csv`         | varies | Top products per province (fertilizer, rice, LPG dominate)                                                                                                                                                              |

### Key data quality issues

- **No shared ID** between `kopdes_locations.csv` and `kopdes_land_assets.csv` — joined by exact cooperative name (99.96% match rate, 55 duplicate names)
- **RAT is NOT zero — the old red flag was a field misread.** `total_rat` /
  `total_done_rat` in `kopdes_province_rat_and_construction.csv` come from the
  province `rat_summary` endpoint, which returns zeros on every pull. The real
  RAT channel is **`rat_count`** in `kopdes_stats_province.csv` (~60% of
  cooperatives, 50,174 on 08-05 → 50,200 live 08-13). See `reports/16-rat-compliance`.
  The `rat_count` field is only populated at **province level** — district/
  subdistrict/village walks return 0.
- **All provinces "unhealthy" is an artifact — do not quote it.** `health_score`
  is a constant 30 across all 38 provinces (zero variance); `health_status` is
  "unhealthy" ×38. The real `average_health_index` runs 50–57 but is computed on
  only 37.6% of cooperatives (62.4% never scored), and even among the scored
  91.1% rate "unhealthy". The index tracks data completeness first (ρ=0.85 with
  scored share), RAT/compliance second (ρ=0.80). See `reports/18-health-scoring`.
- **Name-only geo-linking**: stats joined to boundary polygons via fuzzy name matching (difflib, cutoff 0.82), not ID codes. Match rates: provinsi 100%, kabupaten ~97.9%

### External data (not committed, regenerable via scripts)

| File                                  | Size   | Source         | How to get                                    |
| ------------------------------------- | ------ | -------------- | --------------------------------------------- |
| `data/osm/indonesia_roads.gpkg`       | 1.6 GB | Geofabrik PBF  | `python scripts/download_osm.py --roads-only` |
| `data/osm/indonesia_minimarkets.gpkg` | 1.7 MB | Overpass API   | `python scripts/download_osm.py --poi-only`   |
| `geo/output/*.geojson`                | varies | BIG shapefiles | `cd geo && python run_pipeline.py`            |

### The analysis mart (`data/web/kopdes_*.parquet`)

`python scripts/build_analysis_mart.py` joins every per-cooperative table in
`reports/` into one row per cooperative, then rolls it up to kecamatan,
kabupaten and provinsi. **It computes nothing** — if a number here disagrees
with a report, the report is right and the mart is broken.

| File                       | Rows   | Unit                           |
| -------------------------- | ------ | ------------------------------ |
| `kopdes_points.parquet`    | 83,342 | cooperative ≈ desa, 70 columns |
| `kopdes_kecamatan.parquet` | 7,277  | subdistrict                    |
| `kopdes_kabupaten.parquet` | 514    | district                       |
| `kopdes_provinsi.parquet`  | 38     | province (+ health scores)     |

These five files (incl. `mart_manifest.json`) are **committed** — they are the
app's data layer and a Pages deploy 404s without them. Note the `.gitignore`
uses `data/web/*` not `data/web/`: git cannot re-include a file whose parent
directory is excluded, so the negations would silently do nothing.

Things that will bite you:

- **Aggregate measures share names with point measures on purpose**, so one
  glyph spec works at all four levels. Keep it that way when adding columns.
- **`road_class` / `pop_class` / `nn_class`** collapse the reports' bands to four
  ordered classes each (worst first), and the aggregates carry the matching
  `<family>_share_<class>` percentages. The collapse is defined once, in
  `CLASS_COLUMNS`, and the shares are derived from those same expressions —
  re-deriving it in JavaScript is how a grid cell and a kecamatan glyph start
  disagreeing about what "near a road" means. Denominators are non-null counts:
  unmeasured is not a class.
- **`landcover_class` is the same pattern but categorical, not a severity ramp**
  (reports/19): WorldCover labels are folded to compact keys in `CLASS_COLUMNS`
  and the shares have no "worst" end. A new family is picked up everywhere by
  iterating `FAMILIES` (the grid summariser sizes `counts` from
  `fam.classes.length`, and the national baseline iterates the registry) —
  never hardcode a family list. The rail's Penutup Lahan filter builds its
  options from the same `FAMILIES` entry, so filter, glyph and table cannot
  disagree about what a class means.
- **Aggregate economics do not come from the points.** The village link reaches
  79.1% of cooperatives, which carry 88% of national transaction value — summing
  points would be both wrong and biased. Aggregates group straight off the
  deduplicated village file and reconcile exactly with the raw export. The
  script asserts this on every run.
- **Nulls carry meaning**, and `mart_manifest.json` documents it per column. A
  null `km_to_minimarket` is "further than 5 km" (66,846 rows), not "unknown".
- **H3 is `UBIGINT`**, r5–r9, per the roadmap item in `analytics-plan-review.md`.
- Adding a report? Add it to `SOURCES` in the script and to `AGG_MEASURES` if it
  should aggregate. That is the whole extension path.

## Environment & dependencies

- **Python venv**: `d:\personal\github\kopdes\.venv\` (Python 3.13, Windows)
- **Core deps** (for OSM pipeline): `osmium>=4.0`, `geopandas`, `requests`, `tqdm`
- **Full deps**: `scripts/requirements_osm.txt`
- **Node.js**: Used for `scripts/extract_kopdes.mjs` only

Activate venv before running anything:

```powershell
.venv\Scripts\python.exe scripts/download_osm.py --poi-only
```

## How to run the OSM pipeline

### POIs (fast, no PBF needed):

```bash
python scripts/download_osm.py --poi-only
```

Uses Overpass API nodes-only query. Returns ~10,500 convenience store/supermarket nodes in ~35 seconds. Key brands: Indomaret (3,030), Alfamart (2,181), Alfamidi (219), Circle K (242), plus 13 other chains and ~4,500 unbranded stores.

### Roads (slow, needs PBF):

```bash
python scripts/download_osm.py --roads-only
```

Downloads Geofabrik Indonesia PBF (~1.65 GB, cached after first run), then extracts highway-tagged ways via `osmium` Python bindings. Two-pass process: (1) stream to GeoJSONSeq (~19 min), (2) convert to compact GeoPackage (~6 min). Produces ~4.5M road segments at 1.6 GB GPKG.

### Both:

```bash
python scripts/download_osm.py
```

### Skip PBF re-download:

```bash
python scripts/download_osm.py --no-download
```

## Critical lessons learned (OSM data extraction)

### 1. Do NOT use Overpass API for large-area queries

- Nationwide queries for Indonesia (ways + relations) get rejected with 504/connection-reset from all public mirrors
- **What works**: nodes-only queries (`node["shop"="convenience"]`) return in ~35s with 10k results
- For full coverage (including building-outline shops), extract from PBF instead

### 2. Do NOT use pyrosm for large PBF files (>1 GB)

- `pyrosm.OSM()` constructor reads the entire PBF into memory, consuming 5+ GB RAM for a 1.65 GB file
- The earlier POI extraction crashed with `MemoryError`; the road extraction hung at 10+ minutes with 5 GB RAM
- pyrosm is fine for small/medium files (city-level extracts) but not nationwide

### 3. Use osmium Python bindings with streaming for large PBFs

- `osmium.SimpleHandler.apply_file(pbf, locations=True)` is the only approach that worked reliably
- The C++ core handles PBF parsing and node-coordinate resolution efficiently
- Stream features directly to disk (GeoJSONSeq, one JSON object per line) — do NOT accumulate in memory
- Progress: ~4.5M road segments in 19 minutes, memory usage stayed around 4 GB (vs pyrosm's 5+ GB before crashing)

### 4. GeoJSONSeq → GeoPackage conversion is worth the extra step

- GeoJSONSeq is ~2.5 GB for 4.5M features; GPKG is ~1.6 GB (35% smaller)
- GPKG has spatial indexing, is queryable, and loads faster in GIS tools
- The conversion step (`gpd.read_file` + `to_file`) takes ~6 minutes — acceptable for a one-time operation
- Delete the intermediate GeoJSONSeq after conversion to save disk space

### 5. osmium-tool CLI is NOT available on Windows via package managers

- `choco install osmium-tool` — package not found
- `winget search osmium-tool` — no results
- GitHub releases have no pre-built Windows binaries
- The osmium Python bindings (`pip install osmium`) work perfectly as a replacement — no CLI needed

### 6. The `overpass` Python library is buggy/deprecated

- It prepends `[out:json]` and appends `out center;` to queries, causing duplicate-setting errors
- Use `requests.post()` directly with `https://overpass-api.de/api/interpreter` instead — simpler and more reliable
- Always set a proper `User-Agent` header to avoid 406 errors

### 7. Geofabrik PBF download is reliable but large

- Indonesia PBF: ~1.65 GB from `https://download.geofabrik.de/asia/indonesia-latest.osm.pbf`
- Use `requests` streaming + `tqdm` progress bar for download feedback
- Cache the PBF in `data/osm/` (gitignored) — don't re-download

## Regenerating kopdes data from SIMKOPDES

```bash
# Python version (recommended):
python scripts/extract_kopdes.py data/raw

# Node.js version:
node scripts/extract_kopdes.mjs

# Rebuild the mart the app reads:
python scripts/build_analysis_mart.py
```

**The committed mart is built from the 08-13 snapshot, not `data/raw`.**
`data/raw` is the 08-05 baseline (83,342 cooperatives); the production parquet
holds 83,379 from `data/snapshots/2026-08-13`. Rebuild with
`$env:KOPDES_RAW='data/snapshots/2026-08-13'` and re-run any affected reports
against the same snapshot first. The manifest's `source_snapshot` string is
hardcoded and says "data/raw" even when the build used a snapshot, so trust the
row count (83,379), not the string. Rebuilding from the default `data/raw`
silently regresses every count on the site.

The extraction scripts discover AES-256-CBC encryption keys at runtime by scraping the SIMKOPDES JS bundle. They make concurrent API calls (concurrency=12) and walk the full admin hierarchy.

## Geo boundary pipeline

```bash
cd geo
pip install -r requirements.txt
python run_pipeline.py
```

Three stages:

1. `download_boundaries.py` — downloads BIG-derived shapefiles from GitHub (~675 MB)
2. `convert_to_geojson.py` — SHP→GeoJSON with Douglas-Peucker simplification
3. `link_kopdes.py` — joins kopdes stats to boundaries via normalized name matching

Outputs go to `geo/output/` (gitignored). Match failures go to `*_unmatched.csv`.

A fourth stage produces the web-ready copies the explorer actually loads:

```bash
python scripts/build_boundaries.py            # all three levels
python scripts/build_boundaries.py provinsi   # just one
```

It strips the merged stats down to `{id, name}`, drops islands too small to
render, simplifies per level, and rounds coordinates — 54 MB of `geo/output/`
becomes 9.7 MB in `data/web/boundaries/`, which **is** committed. Re-run it after
any `geo/run_pipeline.py` run, or the map keeps serving the old shapes.

## Web app — the report site (started 2026-08-12)

Static multi-page site served from the **repo root**, so a plain
`python -m http.server 8000` at the root serves it at `/`. No build step;
dependencies are CDN ES modules. Language: **Bahasa Indonesia** — the narrative
and the methods appendix are both Indonesian; only the technical reports in
`reports/` stay English (they are the reproducible source).

Real directories with `index.html` (works on GitHub Pages, independently
linkable):

| Route                                                    | Role                                                                                                                                                           |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `/` (`index.html`)                                       | The story — image hero + three two-column scrolly chapters + a MapLibre map interlude + verdicts                                                               |
| `/explore/`                                              | The interactive map (`app/explore.js`)                                                                                                                         |
| `/tabel/`                                                | The directory: every cooperative in one searchable, sortable table (`app/tabel.js`)                                                                            |
| `/periksa/`                                              | Self-check: re-run the proximity analyses at a reader-supplied coordinate, in the browser (`app/periksa/`)                                                     |
| `/findings/`, `findings/{remoteness,competition,money}/` | The three acts, in Bahasa Indonesia, **anonymous until verified**                                                                                              |
| `/methods/`, `methods/<nn-slug>/`                        | Methodology appendix — plain-language Indonesian write-ups in `methods/_content/`, rendered client-side; the technical English report is linked from each page |
| `/data/`                                                 | Downloads, provenance, null semantics, snapshot log                                                                                                            |
| `/about/`                                                | Who/why, verification & corrections policy, public corrections log                                                                                             |

Shared shell: `app/site.css` (design system) + `app/site.js` (injects nav +
footer from `data-root`, `marked` markdown renderer, ID-locale number helpers).
The old single-page viewer (`index.html` map + `app/main.js` + `app/style.css`)
is **deleted**, and so are its successors `app/explore.js`, `app/grid-layer.js`
and `app/points-layer.js` — the explorer below replaces all three.

### The home page (`/`) — rebuilt 2026-08-13

The story is its own instrument, in `app/story.css` + `app/story.js` (+ the
map in `app/story-map.js`), separate from `site.css`'s reading pages. Layout:

1. **Hero** — full-bleed photo (`assets/story/hero.jpg`) with a scrim, staggered
   entrance animation, and a stat strip. The hero image URL lives in CSS
   (`story.css`), not inline markup.
2. **Three two-column scrolly chapters** (Akses / Kompetisi / Anggaran). Each
   is its own `.scrolly` block: text steps left, a sticky `.figure-card`
   right. `story.js` observes each block and swaps the card's hand-built SVG
   chart as steps cross the viewport; bars grow in via a two-frame width
   transition. **The figure is in its own column — the old centred card that
   text scrolled over is gone**, which is what fixed the chart-behind-text bug.
   Chapter photos (`assets/story/akses|kompetisi|anggaran.jpg`) sit between
   chapters with attribution in the caption + `assets/story/CREDITS.md`.
3. **Map interlude** (`#peta`) — a MapLibre map over a compact, committed point
   layer (`data/web/kopdes_story_points.json`, ~2 MB, built by
   `scripts/build_story_points.py`). Loaded **lazily** by `story.js` (dynamic
   `import()` the first time it scrolls within 600px). **Deliberately does NOT
   use duckdb-wasm** — a national overview map is not worth the ~30 MB wasm
   download on the narrative page; the explorer keeps that job. The layer is a
   compact `pts:[[lon,lat,flags]]` + `meta:[[idx,name,province]]` format (not
   GeoJSON — that is ~8 MB of structural overhead for 83 k points). Reuses
   `tintBasemap`/`BASEMAP_BY_ID` from `app/explore/basemaps.js`. Three
   data-grounded filter chips (Terpencil 146 / Tanpa jalan 5.106 / Di luar
   Indonesia 0) whose counts are recomputed from the flags, never hard-coded.
   `scrollZoom: false` so the page keeps scrolling. Popups only show for the
   flagged tail (the only points that carry a name in the layer).
4. **Verdict grid** — three cards, one per claim, each linking to `/findings/`.

Gotchas: the mobile single-column layout reorders the figure FIRST and uses a
low activation band (`rootMargin` in `story.js`) so the active step's text sits
below the sticky figure instead of scrolling under it. `data-root` is empty on
the home page; the story CSS is not shared with sub-pages.

**Data layer (one shared layer for every page — except the home map)**: the
committed parquet files (`data/web/kopdes_points.parquet` etc.) read in-browser
through **duckdb-wasm**. Import map in `explore/index.html` maps
`@duckdb/duckdb-wasm` → `dist/duckdb-browser.mjs` and `apache-arrow@17.0.0/+esm`
(the ESM build imports apache-arrow as a bare specifier; the import map is
required, there is no UMD build). `getJsDelivrBundles()` + `selectBundle()` +
`AsyncDuckDB` is the load path. The old `data/web/points.geojson` (24 MB) and
its builder `scripts/build_points.mjs` are **deleted**; the parquet replaces
both. The home page's map is the deliberate exception: it reads a 2 MB derived
JSON (`data/web/kopdes_story_points.json`, built by
`scripts/build_story_points.py`) with MapLibre circle layers instead, so the
narrative page never pays the ~30 MB wasm download.

**screengrid**: pinned as `https://unpkg.com/screengrid@3.1.1/dist/screengrid.mjs`
(source lives at `D:\Dissertation\screengrid`, npm `screengrid`). Bump the pin in
`app/explore/layers.js` when the library is republished — there is no lockfile.

### The explorer (`app/explore/`, rebuilt 2026-08-12)

Multi-scale multivariate glyph map. Four scales share one glyph specification,
which is the whole design:

| Module        | Role                                                                 |
| ------------- | -------------------------------------------------------------------- |
| `index.js`    | controller: state, layer rebuilds, drill-down, search actions        |
| `measures.js` | **the registry** — scales, sizing, class families, measures, filters |
| `data.js`     | DuckDB session, per-level queries, lazy boundary fetch               |
| `glyph.js`    | cell summaries + canvas drawing for all three glyph modes            |
| `layers.js`   | screengrid layer factories, boundary fill/line, point circles        |
| `basemaps.js` | backdrop registry + the Positron retint                              |
| `search.js`   | in-memory name index over cooperatives and areas                     |
| `ui.js`       | rail, ladder, legend, tooltip, inspector, search, basemap pill       |
| `icons.js`    | inlined Phosphor SVGs (MIT). **Not Lucide** — deliberate choice      |

Chrome lives in `app/explore.css`, not `site.css`: a control rail is a denser
instrument (13 px, tabular numerals) than the 17 px/68ch reading pages.

**Two screengrid render modes, one glyph.** Grid scale uses
`ScreenGridLayerGL.glyphMap` (screen-space cells); the three admin scales use
`ScreenGridLayerGL.featureGlyphs` with `placement: {strategy:'point'}` over the
aggregate anchors. `summarizeCell` (grid members) and `summarizeAnchor` (one
pre-aggregated row) both emit `{count, values, shares}`, and `drawGlyph` never
learns which produced it. Screengrid contract, verified in its source:
`onAfterAggregate` → `cellInfo.customData` for grid cells, `cellInfo.props` for
anchors, `cellInfo.isHovered` in grid mode.

**Every glyph value is a share, and this is load-bearing.** Two reasons that
turned out to be one: `ScreenGridLayerGL.render()` calls `_aggregate()` on every
frame, so a cell summary must be one pass with no sorting; and a grid drawing a
mean beside a kecamatan drawing a median would make the scales incomparable —
which would defeat the point of the ladder. Shares are single counters at grid
level, are exactly the mart's `pct_*` / `*_share_*` columns at admin level, and
fix the legend: 0–100 % everywhere, so nothing rescales as you pan. Medians live
in the click inspector, which runs once and can afford them.

Three glyph modes: `profile` (four deficit bars — sepi/jalan/dempet/senyap, one
per report act, taller is always worse), `composition` (stacked column over a
class family), `measure` (one share as a colour ramp).

**`sizeFor` in `glyph.js` is where size encoding is decided, and profile mode is
deliberately exempt.** A varying box makes the same share draw at different
pixel heights in different cells, which destroys the only comparison a profile
glyph supports, and the small end falls below the size where four bars read as
four bars. Profile therefore draws at one `uniformPx` per scale; composition and
measure keep `glyphSize`, scaled to a high percentile of the count rather than
the maximum. Consequence: profile mode encodes nothing about how many
cooperatives a cell holds — the legend says so, and `minzoom` on kabupaten and
kecamatan warns when uniform glyphs overlap, since they no longer thin
themselves out in dense areas the way proportional symbols did.

Measure mode offers an
explicit **"regangkan skala"** toggle, off by default, because several measures
sit in a narrow high band (96.5 % of cooperatives report nothing) where an
absolute ramp shows nothing; the legend prints the moved bounds when it is on.

**View-level controls sit over the canvas** (`#search`, `#basemaps`), not in the
rail: the rail is for what the data says, the canvas for how you look at it.

- **Search** (`search.js`) indexes cooperative names plus the three
  administrative levels, derived from the points already in memory — no extra
  query, and area entries carry the admin id so a hit resolves to the exact
  aggregate row. Picking a cooperative flies to it and turns the point layer on;
  picking an area switches the ladder to that scale and opens its inspector.
- **Basemaps** (`basemaps.js`): Terang (retinted Positron), Detail (Liberty),
  Satelit. Satellite is **Esri World Imagery**, not Google — Google's `mt*.google.com`
  tile endpoints are not licensed for third-party embedding, and shipping them
  in a report that publishes its own provenance is the wrong trade. The licensed
  Google route is their Map Tiles API with a key; it would slot in as another
  registry entry. `dark: true` flips boundary lines to white and cooperative
  dots to yellow-on-charcoal, both invisible over imagery otherwise.

**One size slider, per scale.** `LEVELS[].sizing` drives it: on the grid it sets
`cellSizePixels`, on an administrative scale it sets the glyph itself (there is
no cell). Values are kept per scale so switching away and back does not lose the
adjustment, and `state.sizing` is mutated in place and read on every draw, so
dragging does not rebuild the layer.

**Gotchas that cost time:**

- `cooperative_id` and `admin_id` are BIGINT → JS BigInt → MapLibre throws "Do
  not know how to serialize a BigInt" on any GeoJSON source, and a BigInt is
  never `===` a plain number, which silently breaks search-result matching and
  feature-state keys. `data.js` casts wide integers at the query boundary; keep
  doing that for anything new.
- **`render()` is guarded by a `generation` counter.** It awaits in three places
  (level query, boundary fetch, style swap), so clicking quickly puts two
  renders in flight; without the guard the older one adds its layers into the
  newer one's style and throws on the duplicate layer id. Any new `await` inside
  a render path needs a `if (token !== generation) return;` after it.
- `map.setStyle()` destroys every layer _and_ source, the custom screengrid
  layer included. `setBasemap` resets the bookkeeping (`state.glyphLayer`,
  `clearBoundaryState()`) before rebuilding, or the rebuild updates sources that
  no longer exist.
- `loadLevel` orders `cooperatives ASC` on purpose. `feature-anchors` draws in
  source order with no depth sorting, so descending order lets small glyphs
  overpaint big ones around Java.
- `.field { display: block }` outranks the UA's `[hidden] { display: none }`;
  `app/explore.css` restates it at matching specificity.

**Boundaries**: `data/web/boundaries/{provinsi,kabupaten,kecamatan}.geojson`,
built by `scripts/build_boundaries.py` from `geo/output/`, committed (9.7 MB for
all three). Context fills only — every measure still comes from the parquet via
the admin id. Join coverage is provinsi 38/38, kabupaten 489/514, kecamatan
7 235/7 277; the gaps are the bad SIMKOPDES rows `geo/README.md` documents, and
those areas keep their anchor glyph and simply lose the fill. Kecamatan is 8.4 MB
and fetched lazily.

**/methods/ generation**: `python scripts/build_methods_pages.py` scaffolds
`methods/<nn-slug>/index.html` shells + the index from hand-written Indonesian
metadata in the script. Each shell fetches `methods/_content/<slug>.md` at
runtime and renders it with `marked`. Those content files are plain-language
write-ups in the same register as the narrative; the authoritative technical
report (`reports/<slug>/README.md`, English, with code and raw data) is linked
from each page, never embedded. Charts and diagrams are hand-authored SVGs in
`methods/_figures/`, referenced from the markdown via `../_figures/<name>.svg`.
Reports in `EXCLUDED` (currently `18-health-scoring`) are kept in `reports/` as
evidence but not published as a method page. Re-run the generator when a report
is added, renamed, or its title changes.

**Deployment gotcha**: GitHub Pages runs Jekyll by default, which silently drops
`_`-prefixed directories — `methods/_content/` and `methods/_figures/` 404'd on
the deployed site while working locally. The root `.nojekyll` file (empty, committed)
disables Jekyll; keep it.

### The directory (`/tabel/`)

A browsable table of every cooperative, added 2026-08-13. `app/tabel.js` loads
a lean column set from `kopdes_points.parquet` through the same duckdb-wasm
session (`rows` is exported from `app/explore/data.js`), then searches, filters,
sorts and pages entirely in memory, so the first load is the only network round
trip.

- **No table library.** Sorting, filtering and pagination are plain JS over an
  in-memory array. TanStack was considered and rejected: it is headless in
  vanilla, so every `<tr>` and all CSS is yours anyway, and 83k rows in memory
  need no virtualization once pagination caps the rendered rows.
- **One encoding everywhere.** Badge colours and the road filter derive from
  `FAMILIES` in `app/explore/measures.js`, so the table agrees with the map
  about what a band means. `COLS` in `tabel.js` is the single column registry.
- **Population sparkline** is a nested bar (cell 400 m, 1.4 km, 5.1 km)
  normalised to the 99th percentile of catchment (`popP99`), the same
  high-percentile rule the glyphs use. Three blues, deliberately not any
  family ramp.
- **Peta column** opens Google Maps at the coordinate (`@lat,lon,250m/data=!3m1!1e3`,
  the same `imagery_url` format the mart and the explorer use) in a new tab; the
  raw coordinates live in the link's tooltip. "Perlu dicek" rows keep the
  warning badge above the link.
- **Penutup Lahan column** shows the ESA WorldCover 10 m (2021) class at the
  recorded coordinate (`land_cover` / `land_cover_code` in the mart, from
  `reports/19-land-cover`), with two OSM overrides from report 07: a mapped
  cemetery shows "Pemakaman", a point ≥100 m inside a non-coarse farmland
  polygon shows "Lahan pertanian". The tooltip states the source; the class is
  a satellite pixel, not the building footprint.
- **"Lebar penuh" toggle** (toolbar button, sets `body.tabel-wide`) breaks the
  table out of the 1080 px measure: `.tabel-bleed` spans `100vw` and `#grid`
  stretches to fill it (`width: 100%`, so it fills wide monitors; content and
  `min-width: 1080px` still cap it on narrower ones).
- **Nulls carry meaning in the cells**: "> 5 km" for a never-found road or
  minimarket, "Tidak terhubung" for a village with no transaction record,
  "Belum melaporkan" (never "tidak aktif") for a linked village reporting
  zero. The "—" cells are the standing no-data placeholder.
- The road filter's `over_5km` count is exactly the 5.106 headline from
  `reports/05`, which is the cheap correctness check.
- The page pays the duckdb-wasm download like the explorer; the story page
  deliberately does not.

### The self-check (`/periksa/`, added 2026-08-14)

"Periksa mandiri". Answers the objection the whole report inherits: every
coordinate comes from SIMKOPDES, which says its own map positions are
representative visualisations per area rather than precise locations. A reader
picks a cooperative, drops a pin where the building actually stands, and the
same five analyses are re-run at that point **in the browser**. The output is
the delta between the two readings.

| Module                    | Role                                                         |
| ------------------------- | ------------------------------------------------------------ |
| `app/periksa/index.js`    | state, map, picker, map tools, orchestration                 |
| `app/periksa/analysis.js` | the five measures at one coordinate (the engine)             |
| `app/periksa/layers.js`   | overlays: search disk, road/building cells, population, KDMP |
| `app/periksa/ruler.js`    | click-to-measure                                             |
| `app/periksa/ui.js`       | two-column comparison, verdict, sources, report link         |
| `app/periksa.css`         | page styles (a reading page with one instrument in it)       |

**This is why the H3 layout was worth keeping.** H3 ids sort hierarchically, so
every r10 descendant of an r7 parent is one contiguous range of the uint64 id
space. `scripts/build_cell_indexes.py` sorts each index by `h3`, writes 20k-row
row groups, and adds a coarse parent column `p` (r7 for the r10 indexes, r5 for
the r8 population grid). A 5 km k-ring query then asks for the ~21 parents that
cover the disk, and Parquet row-group statistics prune it to a couple of groups.
**Measured: 59 KB median, 220 KB p90, 1 MB worst case out of a 13 MB file.** A
full five-measure analysis costs roughly 150 KB of range requests. Sorting also
shrinks the files (delta encoding on near-consecutive uint64s): the road index
went 34 MB → 13.3 MB with the parent column included.

Committed to `data/web/cells/` (30.9 MB total, gitignore has the negations):
`road_r10.parquet`, `building_r10.parquet`, `pop_r8.parquet`,
`minimarket.parquet`, `cells_manifest.json`.

Things that will bite you:

- **`rows()` casts wide integers to plain JS numbers**, which is lossy above
  2^53, and every H3 id is far above it. The queries select
  `lower(to_hex(h3))` and join on the hex string, which is h3-js's own native
  representation. Never let a cell id become a Number.
- **One query per measure, not one per ring.** The reports expand rings in a
  loop; translating that directly would put up to 38 network round trips inside
  a single click. The whole 5 km disk is fetched once and the minimum ring index
  is taken in JS via `gridDiskDistances`.
- **Both coordinates are recomputed by the same function.** The page could read
  the official-coordinate figures out of `kopdes_points.parquet`, but then any
  difference in method would surface as a difference in the answer and the
  delta would be measuring our own inconsistency.
- **`python -m http.server` does not serve Range requests**, so duckdb-wasm logs
  "fall back to full HTTP read" and downloads each index whole. Local timings
  are meaningless; GitHub Pages serves ranges. Budget ~30 s per analysis locally
  and do not "fix" it.
- The verdict deliberately does not say a correction is an improvement. It
  reports **band crossings**, because the report publishes bands and only a band
  change alters a published classification. An earlier draft counted measures
  that "membaik", which asserted that a cooperative further from a minimarket is
  a better cooperative: an argument the report makes with evidence elsewhere and
  that this page has not earned.
- Nothing is submitted automatically. The coordinate round-trips through the URL
  hash, and the report link opens a **prefilled GitHub issue** the reader
  chooses to send. Keep that distinction in the copy: the callout says nothing
  leaves the browser without a button press, which is only true while no code
  posts anything on its own.

**The overlays and the ruler** (added 2026-08-14):

- **The overlays cost no extra request.** `analysis.js` used to discard the
  cells after taking the minimum ring; it now returns them, and `layers.js`
  turns ids into boundaries with `cellToBoundary`. Only cells **inside the
  disk** are drawn: the query fetches whole r7 parents and returns a ragged
  surplus, and drawing it would show a search area we did not use.
- **The basemap is a raster style, so there are no glyphs and no sprite.** A
  `symbol` layer renders nothing at all. Fills, lines and circles only; the
  ruler's running total is a DOM marker.
- Fill opacities are low and deliberately unequal (road 0.10, building 0.20,
  population data-driven 0.10–0.42). Road cells blanket a village almost
  completely, so a fill heavy enough to see one cell makes a solid sheet of the
  whole neighbourhood. The outlines do the work.
- **The tool panel is anchored bottom-left.** The site nav is sticky at a higher
  z-index, so anything in the top ~56 px of the map is covered by it once the
  map's top edge scrolls past; the other corners hold the zoom control and the
  attribution.
- **The ruler and the pin share the map's click event.** `index.js` returns
  early from its click handler while `ruler.isActive()`, or every measurement
  would silently rewrite the analysis. Escape and double-click end a
  measurement and **keep** the line; the button reflects state via `onChange`
  rather than setting it, because the ruler can also end itself.
- `redraw()` must notify through `notify()`, not its own listener loop. It had
  one, it omitted `active`, and the button label lied for the whole measurement.
- The busy veil covers the comparison table and has a real background. Dimming
  alone was tried and is not enough: a reader can still pick numbers off the
  previous point, which is the entire failure it exists to prevent.

- every `*.html` in `/`, `/explore/`, `/findings/`, `/methods/`, `/data/`, `/about/`
- `methods/_content/**/*.md` (the runtime-rendered method prose) and
  `methods/_figures/**/*.svg`
- user-facing string literals in `app/**/*.js` (tooltips, hints, inspector text)
- the method metadata inside `scripts/build_methods_pages.py` (it generates the
  `methods/*/index.html` shells)

**When one of these files is modified**, rewrite every sentence containing an
em-dash so the em-dash is gone — split the clause, use a colon or parentheses,
or restart the sentence. Do not leave existing em-dashes in place while editing
other parts of the file.

Detector (lists file, line and containing sentence; exits non-zero when any are
found, so it can gate a pre-commit hook or CI):

```bash
python scripts/check_emdashes.py           # pages only
python scripts/check_emdashes.py --code    # also check JS UI strings
python scripts/check_emdashes.py --report  # reporting mode, never exits non-zero
```

Deliberate non-prose uses that stay: `—` as a "no data" cell/placeholder (e.g.
`<td class="num">—</td>` in `findings/remoteness/index.html`, the rail `—` in
`app/explore/ui.js`). The detector still lists them; they are not sentences and
are not paraphrased.

## The deliverable: an investigative report, not an academic paper

**Decided 2026-08-09. This supersedes the earlier plan to write this up as a
conference paper.**

The output is a **public-facing investigative report** — an independent piece in
the vein of Mongabay or bandungbergerak.id (reference the team gave:
`https://bandungbergerak.id/londo-ireng-di-pohon-keluarga-prabowo`). Concretely:

- **Interactive, scrollytelling** — narrative drives the visuals, not the other
  way round. The reader scrolls; the map and charts respond.
- **Grounded in scientific principles** — every claim traceable to a reproducible
  analysis, nulls and caveats intact behind the scenes.
- **Written for the general public.** This is the hardest constraint and the one
  most likely to be violated by default. See the tone rules below.
- **Tables, figures and interactive maps**, with **screengrid** as a primary
  visualisation vehicle (see the Web app section).

### Tone rules (the default register here is too technical)

- Lead with the human claim, then the evidence. Never open a section with a
  method.
- No unexplained jargon: "H3 cell", "k-ring", "null model", "zero-inflated",
  "lower bound" all need a plain-language gloss on first use or replacement.
  Prefer "we compared it against 10,000 random spots that look just as
  plausible" over "population-weighted null model".
- Numbers need a referent. "IDR 2.43 million per cooperative" means nothing;
  "about USD 145 — one month of groceries — for the entire lifetime of a
  cooperative" lands.
- Uncertainty is stated in sentences, not hedged into invisibility. "We can't
  tell whether these zeros mean no business or no paperwork" is honest and
  readable; "the outcome variable is unidentifiable between states" is neither.
- Keep the rigour, move it. Methods, caveats and null models belong in a linked
  methodology section, not in the narrative flow.

### What does and does not change

- **`reports/` does not change.** It remains the evidence base and must stay
  rigorous and reproducible — it becomes the report's linked methodology
  appendix, which is the standard pattern for this genre (Reuters Graphics,
  Mongabay, Bellingcat all do this).
- **The web app at the repo root becomes the report itself**, not a data viewer.
  The current three-view map is a component of it, not the product.
- The narrative should be organised around the three public claims (remoteness,
  cannibalisation, budget-vs-output), and must report the honest verdict on each
  — including that the coverage claim does **not** hold (see
  `reports/README.md`'s "what we can and cannot say"). A report that only
  confirms is not an investigation.

### Site architecture: a site, not a page

One scrollytelling page cannot carry this much material. It is the **summary
layer**; the detail has to live somewhere navigable. Proposed structure —
four levels of progressive disclosure, each one click deeper, which is the
Reuters Graphics / Mongabay pattern:

| Route                                               | Role                                                                                                                               |
| --------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------- |
| `/`                                                 | **The story.** Scrollytelling, linear, the summarised findings. Links inline to everything below.                                  |
| `/explore/`                                         | **The interactive map.** Full screengrid explorer — layer switching, filters, per-cell inspection. The reader's own investigation. |
| `/findings/`                                        | Index of the detailed write-ups                                                                                                    |
| `/findings/remoteness/`, `/competition/`, `/money/` | One page per act, in depth, with the tables and figures the story only gestures at                                                 |
| `/methods/`, `/methods/<nn-slug>/`                  | Methodology appendix — one page per published `reports/` entry (`18-health-scoring` stays unpublished)                             |
| `/data/`                                            | Downloads, provenance, the snapshot log                                                                                            |
| `/about/`                                           | Who, why, and the corrections policy                                                                                               |

Design decisions:

- **Real directories with `index.html`, not a hash router.** Works on GitHub
  Pages as-is, gives clean URLs, keeps each page independently linkable — which
  matters when other outlets cite a specific finding.
- **`/methods/` pages are plain-language Indonesian, written once in
  `methods/_content/`.** The technical English reports stay in `reports/` as the
  reproducible source and are linked, not embedded — the public page reads like
  the report, the appendix stays auditable.
- **One shared data layer** across all pages: the same parquet files and
  DuckDB-wasm setup, so the story and the explorer use one screengrid component
  configured differently, not two implementations.
- **A public corrections log** in `/about/`. For an independent investigative
  report this is a credibility requirement, not a nicety.

Note the parquet migration solves the deployment problem that blocked GitHub
Pages: the old `points.geojson` was 25 MB and gitignored, so a Pages deploy
would 404 on its data. Population is 3.0 MB as parquet and the cooperative
table is of the same order, which is small enough to commit outright.

### Open questions to settle before building

- **Language**: Bahasa Indonesia — settled 2026-08-13. The narrative and the
  methods appendix are both Indonesian; the technical reports stay English as
  the reproducible source.
- **Naming individual cooperatives**: the siting candidates in
  `reports/04-siting-screen/` are nameable village institutions. A wrong
  coordinate would unfairly tar a specific desa. Set a verification bar
  (imagery + boundary check, ideally local confirmation) before any name is
  published.

## Reports (standing requirement)

**Any analysis must land in `reports/` — no exceptions, no throwaway scripts.**
One directory per question: `reports/NN-slug/` containing `run.py` (runnable
from the repo root, writes only into its own directory), `README.md` (the
write-up), and the output CSVs (committed, so findings survive without a
re-run). Shared helpers live in `reports/_lib/`. Deps in
`reports/requirements.txt`.

When you finish an analysis, also update the **"What we can and cannot say
right now"** section of `reports/README.md`. That list is the project's single
source of truth for which claims are currently supportable. Agreed-but-unbuilt
analyses live in that file's **Backlog** section (currently: exact-geometry
refinement, external corroboration of the transaction figures).

**Performance note for OSM work**: filter on the C++ side
(`osmium.FileProcessor(...).with_filter(osmium.filter.KeyFilter(...))`, 36 s over
the 1.73 GB Indonesia PBF). Iterating tags in a Python `SimpleHandler` callback
fires once per object across ~250M nodes — that ran for 92 minutes without
finishing.

Two hard rules that fall out of the data being live:

- **Never regenerate `data/raw/` in place.** It is the 2026-08-05 baseline for
  `reports/01-snapshot-drift`; overwriting it destroys the evidence that answers
  the "not entered yet" rebuttal. New pulls go to `data/snapshots/YYYY-MM-DD/`
  via `python scripts/extract_kopdes.py data/snapshots/$(date +%F)`, which writes
  a `_manifest.json` alongside them.
- **Snapshot CSVs stay out of git** (~28 MB per pull); the project publishes
  figures as HTML pages and hands over raw snapshots on request. `.gitignore`
  drops `data/snapshots/**/*.csv` but keeps every `_manifest.json`, because a
  SIMKOPDES snapshot cannot be re-fetched and those SHA-256 hashes are the only
  provenance record. **Back the local snapshots up outside the working tree** —
  lose them and the central finding is unverifiable by anyone.
- **A zero in the performance data is ambiguous** between "no activity" and "not
  yet reported" (see `reports/01-snapshot-drift`). Write "has not _reported_ any
  transaction", never "is inactive", until a snapshot series settles it.

## Git notes

- `data/raw/*.csv` is committed (source of truth, small files)
- `data/osm/`, `geo/raw/`, `geo/geojson/`, `geo/output/`, `web/data/` are gitignored (large, regenerable)
- `.venv/` is gitignored
- The `.gitignore` is organized by section with comments explaining how to rebuild each ignored path
