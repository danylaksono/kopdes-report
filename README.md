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
index.html         the story (scrollytelling), served from the repo root
explore/           the interactive map
app/               shared shell (site.css, site.js) + story.js
app/explore/       the map's modules; app/explore.css is its chrome
data/raw/          kopdes_*.csv  -  raw SIMKOPDES export (committed; source of truth)
data/web/          the parquet mart + simplified boundaries (committed)
scripts/           extractor, mart builder, boundary builder
geo/               boundary-shapefile download/convert/join pipeline (see geo/README.md)
```

`geo/raw/`, `geo/geojson/` and `geo/output/` are gitignored - they're
regenerated from `data/raw/` by the scripts below and run into the hundreds of
MB. `data/web/` is gitignored *except* for the files the deployed app fetches:
the four parquet tables, `mart_manifest.json`, and `boundaries/*.geojson`.

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

**3. Rebuild the map's boundary layer** from what step 2 produced (fast, no
download - it simplifies `geo/output/` down to something a browser can fetch):

```bash
python scripts/build_boundaries.py
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
| `data/web/kopdes_points.parquet` | 83,342 | one cooperative ≈ one desa — **70 columns** |
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

Static site served from the repo root, no build step - MapLibre GL JS,
[screengrid](https://github.com/danylaksono/screengrid) and DuckDB-wasm from a
CDN, reading the committed parquet directly:

```bash
python -m http.server 8000
# open http://localhost:8000  (story)  or  /explore/  (map)
```

### The map (`/explore/`)

**Four scales of the same 83,342 cooperatives**, picked from the ladder in the
left rail, which shows what each one costs you: 83.342 points → 7.273 kecamatan
→ 514 kabupaten → 38 provinsi.

- **Kisi dinamis** - screen-space cells via screengrid, fixed pixel size
  (slider), re-binned on every pan and zoom.
- **Kecamatan / Kabupaten / Provinsi** - one glyph per area, drawn at the
  *median position of its member cooperatives*, not the polygon centroid, which
  can sit offshore. Simplified boundaries render underneath as context.

**Three ways to encode a cell**, all of them shares of cooperatives so the four
scales stay comparable:

- **Profil** - four bars, one per question the report asks: sekitarnya sepi,
  jauh dari jalan, berdempetan, tidak melaporkan transaksi. Taller is always
  worse, so a tall glyph is an area in trouble on several fronts.
- **Komposisi** - a stacked column showing how the area's cooperatives divide
  across a class family (distance to road, population nearby, distance to the
  nearest other cooperative).
- **Ukuran** - one measure as a colour ramp, fixed at 0-100% so the colours do
  not change meaning as you pan. Several measures sit in a narrow band near one
  end, so there is an explicit "regangkan skala" toggle; the legend prints the
  bounds whenever it is on.

**Profil draws every glyph at the same size**, on purpose. Sizing it by count
would put the same share at different pixel heights in different cells, which is
precisely the comparison the mode exists to support - and the smallest cells
would fall below the size where four bars still read as four bars. The count is
in the inspector instead. Komposisi and Ukuran do scale with count, where it
costs nothing: proportions are scale-invariant, and colour leaves size free.
There the area is scaled to a high percentile rather than the maximum, because
scaling to Java's peak flattens everywhere else.

**Titik koperasi** overlays the raw coordinates on any scale; filters apply to the grid
and the points, never to the pre-computed admin aggregates (the rail says so
when they are inert). Clicking any glyph opens an inspector with the full
profile against the national figure, the medians the glyph deliberately does not
encode, and a button to drop one rung down the ladder in that area.

**Search** (top-left, over the map) covers all 83,342 cooperative names and every
kecamatan, kabupaten and provinsi. Picking an area switches the ladder to that
scale and opens it; picking a cooperative flies to it, turns the point layer on
and marks it - which paired with the satellite basemap is how you check whether
a coordinate lands on anything.

**Basemaps** (bottom-left, over the map): _Terang_ is
[OpenFreeMap](https://openfreemap.org) Positron retinted to the report's
palette, _Detail_ is OpenFreeMap Liberty, and _Satelit_ is
[Esri World Imagery](https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9).

> Satellite imagery is Esri rather than Google on purpose: Google's `mt*.google.com`
> tile endpoints are not licensed for embedding in another site. If you have a
> Google Maps Platform key, their Map Tiles API is the licensed route and drops
> into `app/explore/basemaps.js` as one more entry.

Icons are [Phosphor](https://phosphoricons.com) (MIT), inlined.

## Known data-quality caveats

- `kopdes_stats_*.csv` uses SIMKOPDES's own internal ids
  (`province_id`/`district_id`/`subdistrict_id`/`village_id`), not
  BPS/Kemendagri codes - see [geo/README.md](geo/README.md) for why the
  boundary join goes through name-matching instead.
- A small number of source rows have wrong province/district pairings or
  bogus coordinates baked into the SIMKOPDES export itself (e.g. a district
  named "Fukuoka" filed under province "PAPUA").
  [Report 08](reports/08-exact-geometry/) identifies the 19 coordinates that
  fall outside Indonesia and flags them as `coordinate_suspect` in the mart;
  the map filters them out by default but lets you show them. The geo pipeline
  logs unmatched rows to `geo/output/<level>_unmatched.csv`.
- `kopdes_land_assets.csv` has no cooperative id either - it's joined to
  `kopdes_locations.csv` by exact cooperative name, which misses ~0.04% of
  land-asset rows (26 of 65,921 unique names) and, for the 55 duplicate names
  in that file, keeps whichever row appears last.
