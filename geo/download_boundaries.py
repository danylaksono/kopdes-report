#!/usr/bin/env python3
"""
download_boundaries.py

Downloads Indonesia administrative boundary shapefiles (Provinsi, Kab_Kota,
Kecamatan, Kel_Desa) from the Alf-Anas/batas-administrasi-indonesia GitHub
repo, reassembles the split .7z archives, and extracts the .shp/.dbf/.shx/.prj
files into geo/raw/<level>/.

Source: https://github.com/Alf-Anas/batas-administrasi-indonesia (BIG-derived,
skala 1:10.000). Re-run any time to refresh: already-downloaded archive parts
and already-extracted levels are skipped.

Usage: python download_boundaries.py [level ...]
       (levels: provinsi kab_kota kecamatan kel_desa; default: all four)
"""

import sys
from pathlib import Path

import py7zr
import requests

REPO = "Alf-Anas/batas-administrasi-indonesia"
API = f"https://api.github.com/repos/{REPO}/contents"

LEVELS = {
    "provinsi": "Provinsi",
    "kab_kota": "Kab_Kota",
    "kecamatan": "Kecamatan",
    "kel_desa": "Kel_Desa",
}

ROOT = Path(__file__).parent
RAW_DIR = ROOT / "raw"


def log(*args):
    print("[download]", *args, flush=True)


def list_parts(folder: str):
    resp = requests.get(f"{API}/{folder}", timeout=30)
    resp.raise_for_status()
    entries = [e for e in resp.json() if e["name"].endswith((".7z", *_part_suffixes()))]
    entries.sort(key=lambda e: e["name"])
    return entries


def _part_suffixes():
    return tuple(f".7z.{i:03d}" for i in range(1, 30))


def download_parts(level_key: str, folder: str) -> Path:
    level_dir = RAW_DIR / level_key
    parts_dir = level_dir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    entries = list_parts(folder)
    if not entries:
        raise RuntimeError(f"No .7z parts found for {folder} - repo layout may have changed")

    local_paths = []
    for e in entries:
        dest = parts_dir / e["name"]
        local_paths.append(dest)
        if dest.exists() and dest.stat().st_size == e["size"]:
            log(f"{level_key}: {e['name']} already downloaded, skipping")
            continue
        log(f"{level_key}: downloading {e['name']} ({e['size'] / 1e6:.1f} MB)")
        with requests.get(e["download_url"], stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)

    combined = level_dir / f"{level_key}.7z"
    if not combined.exists() or combined.stat().st_size != sum(p.stat().st_size for p in local_paths):
        log(f"{level_key}: reassembling {len(local_paths)} parts")
        with open(combined, "wb") as out:
            for p in local_paths:
                out.write(p.read_bytes())
    return combined


def extract(level_key: str, archive: Path) -> Path:
    extract_dir = RAW_DIR / level_key / "extracted"
    shp_files = list(extract_dir.rglob("*.shp")) if extract_dir.exists() else []
    if shp_files:
        log(f"{level_key}: already extracted ({len(shp_files)} .shp files), skipping")
        return extract_dir

    log(f"{level_key}: extracting {archive.name}")
    extract_dir.mkdir(parents=True, exist_ok=True)
    with py7zr.SevenZipFile(archive, mode="r") as z:
        z.extractall(path=extract_dir)
    return extract_dir


def main():
    requested = [a.lower() for a in sys.argv[1:]] or list(LEVELS.keys())
    for key in requested:
        if key not in LEVELS:
            log(f"unknown level '{key}', skipping (valid: {', '.join(LEVELS)})")
            continue
        folder = LEVELS[key]
        archive = download_parts(key, folder)
        extract(key, archive)
    log("done")


if __name__ == "__main__":
    main()
