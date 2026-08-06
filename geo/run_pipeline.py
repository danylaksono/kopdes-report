#!/usr/bin/env python3
"""
run_pipeline.py

One-shot entry point for the whole geo pipeline: download boundaries ->
convert to simplified GeoJSON -> join kopdes stats. Re-running is cheap:
each stage skips work it already did (see download_boundaries.py's
size/existence checks) except convert/link, which always re-run so edits to
name_utils.py or SIMPLIFY_TOLERANCE take effect.

Usage: python run_pipeline.py [level ...]
       (levels: provinsi kab_kota kecamatan kel_desa; default: all four)
"""

import sys

import convert_to_geojson
import download_boundaries
import link_kopdes


def main():
    levels = [a.lower() for a in sys.argv[1:]] or list(download_boundaries.LEVELS.keys())

    for key in levels:
        archive = download_boundaries.download_parts(key, download_boundaries.LEVELS[key])
        download_boundaries.extract(key, archive)

    for key in levels:
        convert_to_geojson.convert(key, convert_to_geojson.LEVELS[key])

    for key in levels:
        link_kopdes.link(key, link_kopdes.LEVELS[key])


if __name__ == "__main__":
    main()
