# AGENTS.md — kopdes-vis project knowledge base

> For AI agents and new contributors. Read this before doing anything else.

## What this project is

Analysis pipeline for **KDMP** (Koperasi Desa Merah Putih), Indonesia's nationwide village-cooperative program. We have ~83,000 cooperative locations, their financial/operational stats, and are building spatial analytics to investigate claims of misplacement, cannibalization with existing retail, and budget inefficiency.

**Repo**: `danylaksono/kopdes-vis` on GitHub.

## Key documents

| File                | Purpose                                                                     |
| ------------------- | --------------------------------------------------------------------------- |
| `analytics-plan.md` | Full analytical blueprint — modules A–F, hypotheses, external data wishlist |
| `analytics-plan-review.md` | **Feasibility triage of the above (2026-08-09).** Corrects several load-bearing errors in the plan; read it before acting on any module |
| `reports/README.md` | Index of completed analyses + the running "what we can and cannot say" list |
| `README.md`         | Project overview, data layout, how to regenerate data                       |
| `geo/README.md`     | Boundary shapefile pipeline (download → convert → link to kopdes stats)     |

## Data inventory

### Primary data (committed in `data/raw/`)

All sourced from SIMKOPDES public API (no auth required). Snapshot date: **2026-08-05**.

| File                                       | Rows   | Key point                                                                                  |
| ------------------------------------------ | ------ | ------------------------------------------------------------------------------------------ |
| `kopdes_locations.csv`                     | ~83k   | Every cooperative: id, name, admin hierarchy, lat/lon                                      |
| `kopdes_land_assets.csv`                   | ~66k   | Land/building verification status per cooperative                                          |
| `kopdes_stats_province.csv`                | 38     | Per-province: transactions, savings, NPWP/NIB, health scores                               |
| `kopdes_stats_district.csv`                | ~514   | Same stats at district level                                                               |
| `kopdes_stats_subdistrict.csv`             | ~7.2k  | Same stats at subdistrict level                                                            |
| `kopdes_stats_village.csv`                 | ~83k   | Same stats at village level (many zeros — most villages have 1 coop with minimal activity) |
| `kopdes_national_summary.csv`              | 1      | Headline numbers: IDR 179.5T total transactions, 1.8M members                              |
| `kopdes_province_rat_and_construction.csv` | 38     | RAT compliance (**all zeros — major red flag**), construction progress                     |
| `kopdes_province_top_products.csv`         | varies | Top products per province (fertilizer, rice, LPG dominate)                                 |

### Key data quality issues

- **No shared ID** between `kopdes_locations.csv` and `kopdes_land_assets.csv` — joined by exact cooperative name (99.96% match rate, 55 duplicate names)
- **RAT = 0 everywhere**: `total_rat` and `total_done_rat` are zero for all 38 provinces — either data not collected, or genuine non-compliance
- **All provinces "unhealthy"**: health scores clustered 51–57, likely driven by zero RAT
- **Name-only geo-linking**: stats joined to boundary polygons via fuzzy name matching (difflib, cutoff 0.82), not ID codes. Match rates: provinsi 100%, kabupaten ~97.9%

### External data (not committed, regenerable via scripts)

| File                                  | Size   | Source           | How to get                                    |
| ------------------------------------- | ------ | ---------------- | --------------------------------------------- |
| `data/osm/indonesia_roads.gpkg`       | 1.6 GB | Geofabrik PBF    | `python scripts/download_osm.py --roads-only` |
| `data/osm/indonesia_minimarkets.gpkg` | 1.7 MB | Overpass API     | `python scripts/download_osm.py --poi-only`   |
| `geo/output/*.geojson`                | varies | BIG shapefiles   | `cd geo && python run_pipeline.py`            |
| `data/web/points.geojson`             | varies | kopdes locations | `node scripts/build_points.mjs`               |

## Environment & dependencies

- **Python venv**: `d:\personal\github\kopdes\.venv\` (Python 3.13, Windows)
- **Core deps** (for OSM pipeline): `osmium>=4.0`, `geopandas`, `requests`, `tqdm`
- **Full deps**: `scripts/requirements_osm.txt`
- **Node.js**: Used for `scripts/build_points.mjs` and `scripts/extract_kopdes.mjs`

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

# Build web map points:
node scripts/build_points.mjs
```

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

## Web app

Static MapLibre GL app served from the **repo root** (`index.html` + `app/`), so a plain `python -m http.server 8000` at the root serves it at `/`. No build step; dependencies are CDN ES modules.

| File                 | Role                                                                                     |
| -------------------- | ---------------------------------------------------------------------------------------- |
| `index.html`         | Shell: map container, control panel, legend, tooltip                                     |
| `app/main.js`        | Loads `data/web/points.geojson`, switches views, renders legend/tooltip                  |
| `app/points-layer.js`| Clustered per-cooperative circles, colored by verification status                        |
| `app/grid-layer.js`  | screengrid screen-space aggregation (rect + hex), colour ramp                            |
| `app/style.css`      | All styling                                                                              |

**screengrid**: pinned as `https://unpkg.com/screengrid@3.1.1/dist/screengrid.mjs` (source lives at `D:\Dissertation\screengrid`, npm `screengrid`). Bump the pin in `app/grid-layer.js` when the library is republished — there is no lockfile.

Grid cells currently encode **count of cooperatives only** (`getWeight: () => 1`, `aggregationFunction: 'sum'`). Attribute glyphs are deliberately deferred; they attach via `getWeight`/`onDrawCell`/`enableGlyphs` in `app/grid-layer.js`.

Normalization is screengrid's default `max-local`, i.e. **view-relative** — the same count maps to different colours at different viewports. The legend prints the current max to keep that honest. If cross-view comparison ever matters, switch to `max-global` with a fixed `normalizationContext.globalMax`.

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
- Numbers need a referent. "IDR 2.15 million per cooperative" means nothing;
  "about USD 130 — one month of groceries — for the entire lifetime of a
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

| Route | Role |
|---|---|
| `/` | **The story.** Scrollytelling, linear, the summarised findings. Links inline to everything below. |
| `/explore/` | **The interactive map.** Full screengrid explorer — layer switching, filters, per-cell inspection. The reader's own investigation. |
| `/findings/` | Index of the detailed write-ups |
| `/findings/remoteness/`, `/competition/`, `/money/` | One page per act, in depth, with the tables and figures the story only gestures at |
| `/methods/`, `/methods/<nn-slug>/` | Methodology appendix — one page per `reports/` entry |
| `/data/` | Downloads, provenance, the snapshot log |
| `/about/` | Who, why, and the corrections policy |

Design decisions:

- **Real directories with `index.html`, not a hash router.** Works on GitHub
  Pages as-is, gives clean URLs, keeps each page independently linkable — which
  matters when other outlets cite a specific finding.
- **`/methods/` pages must be generated from `reports/*/README.md`, never
  written twice.** Single source of truth. Rendering the markdown client-side
  keeps the no-build-step property; a build step is the alternative if the
  render quality isn't good enough.
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

- **Language**: Bahasa Indonesia, English, or both? Audience and reach depend on
  it, and it affects every string in the app.
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
analyses live in that file's **Backlog** section (currently: land-use
point-in-polygon, exact-geometry refinement, external corroboration of the
transaction figures).

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
  yet reported" (see `reports/01-snapshot-drift`). Write "has not *reported* any
  transaction", never "is inactive", until a snapshot series settles it.

## Git notes

- `data/raw/*.csv` is committed (source of truth, small files)
- `data/osm/`, `geo/raw/`, `geo/geojson/`, `geo/output/`, `web/data/` are gitignored (large, regenerable)
- `.venv/` is gitignored
- The `.gitignore` is organized by section with comments explaining how to rebuild each ignored path
