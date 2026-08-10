# kopdes

Data pipeline and map viewer for **Koperasi Desa/Kelurahan Merah Putih**
(village/urban cooperatives), sourced from [SIMKOPDES](https://simkopdes.go.id).

## Getting the data

Just here for the data, not the pipeline? `data/raw/*.csv` is committed to
this repo - clone it and you have everything:

```bash
git clone <this-repo-url>
```

Or grab a single file without cloning: open it on GitHub and use the "Raw"
button (or `raw.githubusercontent.com/<owner>/<repo>/main/data/raw/<file>.csv`).

| File | What's in it |
|---|---|
| `kopdes_locations.csv` | every cooperative: id, name, province/district/subdistrict, lat/lon |
| `kopdes_land_assets.csv` | surveyed land/building per cooperative, incl. verification `status` |
| `kopdes_stats_province.csv` / `_district.csv` / `_subdistrict.csv` / `_village.csv` | roll-up stats (accounts, transactions, savings, ...) at each admin level |
| `kopdes_national_summary.csv` | headline national metrics |
| `kopdes_province_rat_and_construction.csv` | annual-meeting (RAT) and building-progress status by province |
| `kopdes_province_top_products.csv` | top traded products by province |

The CSVs in the repo are a snapshot from whenever they were last regenerated
(check `git log -- data/raw` for the date). If you want a fresh pull straight
from SIMKOPDES instead of that snapshot:

```bash
python scripts/extract_kopdes.py data/raw
```

It hits the live public API (no auth) and overwrites the files in place.

## Layout

```
index.html    the visual-analytics app (served from the repo root)
app/          its JS/CSS modules
data/raw/     kopdes_*.csv  -  raw SIMKOPDES export (committed; source of truth)
data/web/     points.geojson  -  generated app data
scripts/      extractor + web-data generator scripts
geo/          boundary-shapefile download/convert/join pipeline (see geo/README.md)
```

`geo/raw/`, `geo/geojson/`, `geo/output/`, and `data/web/` are gitignored -
they're all regenerated from `data/raw/` by the scripts below, and the
boundary-level ones run into the hundreds of MB.

## Regenerating the data

**1. Refresh the SIMKOPDES export** (hits the live API; safe to re-run anytime):

```bash
python scripts/extract_kopdes.py data/raw
```

**2. Rebuild administrative boundary polygons joined to the stats** (one-time
~675MB download, cached after that - see [geo/README.md](geo/README.md) for
how the name-matching join works and its known gaps):

```bash
pip install -r geo/requirements.txt
python geo/run_pipeline.py
```

**3. Rebuild the point layer for the app** (fast, no download):

```bash
node scripts/build_points.mjs
```

## The analysis mart (what the app reads)

Every analysis in `reports/` produces its own per-cooperative table. The app
needs them on one row, so `scripts/build_analysis_mart.py` joins all of them and
writes four parquet files — the same measures at four levels of aggregation, so
one visualisation spec works at every zoom:

```bash
python scripts/build_analysis_mart.py
```

| File | Rows | Unit |
|---|---|---|
| `data/web/kopdes_points.parquet` | 83,342 | one cooperative ≈ one desa — **63 columns** |
| `data/web/kopdes_kecamatan.parquet` | 7,277 | subdistrict |
| `data/web/kopdes_kabupaten.parquet` | 514 | district |
| `data/web/kopdes_provinsi.parquet` | 38 | province |

These four (and `mart_manifest.json`) are **committed** — ~7 MB total, small
enough to serve from GitHub Pages, unlike the 25 MB `points.geojson` they
replace. Everything else in `data/web/` stays gitignored.

Each point carries H3 cell ids at r5–r9 as `UBIGINT`, so the app can re-bin at
any resolution without recomputing from lat/lon (`h3_h3_to_string()` for the hex
form). Each aggregate row carries `anchor_lat`/`anchor_lon` — the median position
of its members — which is what a renderer binds a feature to when it is not
drawing points. Filter on `anchor_lat is not null`: 4 kecamatan have villages in
the statistics but no name-matched cooperative.

**Read `mart_manifest.json` before encoding anything.** It records the schema,
join coverage, and — most importantly — what a null *means* per column. Several
nulls carry the finding rather than marking absence: a null `km_to_minimarket`
means "no minimarket within 5 km" (66,846 cooperatives), not "unknown", and
rendering it as missing data inverts the result of
[report 06](reports/06-minimarket-proximity/).

Two joins are lossy and the manifest publishes both rates: admin ids resolve for
**99.95%** of cooperatives by subdistrict name, while village-level economics
need a two-hop join through the land-asset file and reach **79.1%**. Aggregate
economics therefore do *not* come from the points — they are grouped straight off
the complete village file and reconcile exactly with the raw export. **Never sum
point economics for a regional total; read the aggregate table.**

## The app

Static site served from the repo root, no build step - MapLibre GL JS and
[screengrid](https://github.com/danylaksono/screengrid) from a CDN plus one
generated GeoJSON file:

```bash
node scripts/build_points.mjs        # if data/web/points.geojson doesn't exist yet
python -m http.server 8000
# open http://localhost:8000
```

Three views over the same 83k cooperatives, switchable from the panel top-right:

- **Screen grid** (default) and **screen hex** - screen-space density
  aggregation via screengrid. Cells are a fixed pixel size (slider, 16-120px),
  so the grid re-bins on every pan/zoom and always shows density at the
  resolution you're actually looking at. Cell value is a plain count of
  cooperatives; hover for the number. Colour is √-scaled (counts are wildly
  skewed between Java and the outer islands) and rescales to the current
  viewport, so read the legend, not the hue, across views.
- **Points (clustered)** - every cooperative as a circle, colored by
  land-asset verification status (green = Terverifikasi, amber = any other
  known status, gray = no land-asset record at all). That status is joined
  from `kopdes_land_assets.csv` by exact cooperative name in
  `scripts/build_points.mjs` (99.96% match rate - see that script's header
  comment); click a point for its raw status string.

Only position is used by the grid views so far - per-cell attribute encoding
(glyphs) hangs off `getWeight`/`onDrawCell` in [app/grid-layer.js](app/grid-layer.js)
when we get to it.

Basemap is [OpenFreeMap](https://openfreemap.org) (free, no API key). Next
step: bring in the joined boundary GeoJSON from `geo/output/` for choropleths
at any admin level.

## Known data-quality caveats

- `kopdes_stats_*.csv` uses SIMKOPDES's own internal ids
  (`province_id`/`district_id`/`subdistrict_id`/`village_id`), not
  BPS/Kemendagri codes - see [geo/README.md](geo/README.md) for why the
  boundary join goes through name-matching instead.
- A small number of source rows have wrong province/district pairings or
  bogus coordinates baked into the SIMKOPDES export itself (e.g. a district
  named "Fukuoka" filed under province "PAPUA"). `scripts/build_points.mjs`
  drops points outside Indonesia's bounding box and logs how many; the geo
  pipeline logs unmatched rows to `geo/output/<level>_unmatched.csv`.
- `kopdes_land_assets.csv` has no cooperative id either - it's joined to
  `kopdes_locations.csv` by exact cooperative name, which misses ~0.04% of
  land-asset rows (26 of 65,921 unique names) and, for the 55 duplicate names
  in that file, keeps whichever row appears last.
