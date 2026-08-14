# Cartogram source for the Kisi Provinsi scale

`indonesia_grid.csv` is the Indonesia grid cartogram layout that ships with the
[geo-morpher](https://github.com/danylaksono/geomorpher) example data, copied
verbatim from `danylaksono/geomorpher` → `data/indonesia/indonesia-grid.csv`
on 2026-08-14.

It assigns each of the 38 provinces to a grid cell by **BPS province code**
(columns `ID,Provinsi,Initials,row,col`). The lettered Papua codes (`91-A` …
`92-B`) matter: the plain `91`/`92` are the pre-split codes and collapse six
provinces into two.

This file is the layout _source_. `scripts/build_province_cartogram.py` re-keys
it to SIMKOPDES `province_id` (via a name join against
`data/web/boundaries/provinsi.geojson`) and writes
`data/web/cartogram/provinsi_grid.csv`, which is what the explorer actually
loads.
