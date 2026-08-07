# AGENTS.md — kopdes-vis project knowledge base

> For AI agents and new contributors. Read this before doing anything else.

## What this project is

Analysis pipeline for **KDMP** (Koperasi Desa Merah Putih), Indonesia's nationwide village-cooperative program. We have ~83,000 cooperative locations, their financial/operational stats, and are building spatial analytics to investigate claims of misplacement, cannibalization with existing retail, and budget inefficiency.

**Repo**: `danylaksono/kopdes-vis` on GitHub.

## Key documents

| File | Purpose |
|---|---|
| `analytics-plan.md` | Full analytical blueprint — modules A–F, hypotheses, external data wishlist |
| `README.md` | Project overview, data layout, how to regenerate data |
| `geo/README.md` | Boundary shapefile pipeline (download → convert → link to kopdes stats) |

## Data inventory

### Primary data (committed in `data/raw/`)

All sourced from SIMKOPDES public API (no auth required). Snapshot date: **2026-08-05**.

| File | Rows | Key point |
|---|---|---|
| `kopdes_locations.csv` | ~83k | Every cooperative: id, name, admin hierarchy, lat/lon |
| `kopdes_land_assets.csv` | ~66k | Land/building verification status per cooperative |
| `kopdes_stats_province.csv` | 38 | Per-province: transactions, savings, NPWP/NIB, health scores |
| `kopdes_stats_district.csv` | ~514 | Same stats at district level |
| `kopdes_stats_subdistrict.csv` | ~7.2k | Same stats at subdistrict level |
| `kopdes_stats_village.csv` | ~83k | Same stats at village level (many zeros — most villages have 1 coop with minimal activity) |
| `kopdes_national_summary.csv` | 1 | Headline numbers: IDR 179.5T total transactions, 1.8M members |
| `kopdes_province_rat_and_construction.csv` | 38 | RAT compliance (**all zeros — major red flag**), construction progress |
| `kopdes_province_top_products.csv` | varies | Top products per province (fertilizer, rice, LPG dominate) |

### Key data quality issues

- **No shared ID** between `kopdes_locations.csv` and `kopdes_land_assets.csv` — joined by exact cooperative name (99.96% match rate, 55 duplicate names)
- **RAT = 0 everywhere**: `total_rat` and `total_done_rat` are zero for all 38 provinces — either data not collected, or genuine non-compliance
- **All provinces "unhealthy"**: health scores clustered 51–57, likely driven by zero RAT
- **Name-only geo-linking**: stats joined to boundary polygons via fuzzy name matching (difflib, cutoff 0.82), not ID codes. Match rates: provinsi 100%, kabupaten ~97.9%

### External data (not committed, regenerable via scripts)

| File | Size | Source | How to get |
|---|---|---|---|
| `data/osm/indonesia_roads.gpkg` | 1.6 GB | Geofabrik PBF | `python scripts/download_osm.py --roads-only` |
| `data/osm/indonesia_minimarkets.gpkg` | 1.7 MB | Overpass API | `python scripts/download_osm.py --poi-only` |
| `geo/output/*.geojson` | varies | BIG shapefiles | `cd geo && python run_pipeline.py` |
| `web/data/points.geojson` | varies | kopdes locations | `python scripts/build_points.mjs` |

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

## Web viewer

Static MapLibre GL map at `web/index.html`. Loads `web/data/points.geojson` (regenerated by `scripts/build_points.mjs`). Open `web/index.html` directly in a browser.

## Git notes

- `data/raw/*.csv` is committed (source of truth, small files)
- `data/osm/`, `geo/raw/`, `geo/geojson/`, `geo/output/`, `web/data/` are gitignored (large, regenerable)
- `.venv/` is gitignored
- The `.gitignore` is organized by section with comments explaining how to rebuild each ignored path
