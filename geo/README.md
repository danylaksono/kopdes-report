# kopdes geo pipeline

Links the SIMKOPDES stats exports (`../data/raw/kopdes_stats_*.csv`) to Indonesia
administrative boundary polygons, at all four levels: province, kabupaten/kota,
kecamatan, and desa/kelurahan.

## Why this exists

`kopdes_stats_*.csv` carries SIMKOPDES's own internal database ids
(`province_id`, `district_id`, `subdistrict_id`, `village_id`) - not BPS or
Kemendagri administrative codes. There's no id you can join on. Every join in
this pipeline goes through **normalized names** instead.

Boundary source: [Alf-Anas/batas-administrasi-indonesia](https://github.com/Alf-Anas/batas-administrasi-indonesia),
BIG-derived shapefiles at 1:10.000 scale, split into `.7z` parts on GitHub.

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
# whole pipeline, all four levels (~675MB download, one-time)
python run_pipeline.py

# just one or two levels
python run_pipeline.py provinsi kab_kota

# re-run stages individually (e.g. after editing name_utils.py)
python download_boundaries.py kel_desa
python convert_to_geojson.py kel_desa
python link_kopdes.py kel_desa
```

Downloaded archives and extracted shapefiles are cached under `raw/` -
`download_boundaries.py` skips a level if it's already downloaded/extracted.
`convert_to_geojson.py` and `link_kopdes.py` always re-run so changes to
simplification tolerance or name normalization take effect on the next run.

## Pipeline stages

1. **`download_boundaries.py`** - pulls the split `.7z` shapefile parts per
   level from GitHub, reassembles, extracts to `raw/<level>/extracted/`.
2. **`convert_to_geojson.py`** - reads each `.shp` with `pyshp`, simplifies
   geometry with `shapely` (Douglas-Peucker, topology-preserving - the raw
   1:10.000 data is ~100x too detailed for this use and produces
   multi-hundred-MB files), and writes `geojson/<level>.geojson` with a
   `name_norm` property (and parent `..._norm` properties) added to every
   feature.
3. **`link_kopdes.py`** - loads `kopdes_stats_<level>.csv`, normalizes its
   province/district/subdistrict/village name columns the same way, and joins
   on the normalized name path. Two-tier matching:
   - exact match on the full normalized name path
   - if the *parent* path matches exactly but the finest-level name doesn't,
     fuzzy-match (difflib, cutoff 0.82) against candidates sharing that exact
     parent only - never matches across the wrong district/subdistrict.

   Output: `output/<level>.geojson` (every boundary feature, kopdes columns
   merged in where matched) and `output/<level>_unmatched.csv` (kopdes rows
   that found no geometry, with a `_reason` column).

## Known match gaps

Last full run: provinsi 100%, kab_kota 97.9%. The kab_kota leftovers are
**not** name-matching failures - they're bad data in SIMKOPDES itself (e.g.
district `Akaiwa`/`Fukuoka` filed under province `PAPUA`, `KAB. MAPPI` filed
under `PAPUA` instead of `PAPUA SELATAN`). Check `output/<level>_unmatched.csv`
after each run before assuming a gap is fixable here.

If a future kopdes export introduces new name variants, extend
`name_utils.py`'s `_WORD_ALIASES` / `_ALIASES` rather than loosening
`FUZZY_CUTOFF` in `link_kopdes.py` - a lower cutoff risks matching the wrong
district instead of just leaving a row unmatched.

## Files

| File | Purpose |
|---|---|
| `name_utils.py` | shared name normalization (prefixes, abbreviations, accents) |
| `download_boundaries.py` | fetch + extract shapefiles |
| `convert_to_geojson.py` | SHP -> simplified GeoJSON |
| `link_kopdes.py` | name-match join + unmatched report |
| `run_pipeline.py` | runs all three stages for the requested levels |
| `raw/` | downloaded archives + extracted shapefiles (gitignore-able) |
| `geojson/` | converted, simplified boundaries (no kopdes data yet) |
| `output/` | final joined GeoJSON + unmatched-row reports |
