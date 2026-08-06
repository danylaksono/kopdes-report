"""
name_utils.py

Shared name-normalization helpers for matching Indonesian administrative
names between the SIMKOPDES export (kopdes_stats_*.csv, which uses SIMKOPDES's
own internal ids, not BPS/Kemendagri codes) and the BIG boundary shapefiles
(which use plain names, e.g. "Kabupaten Aceh Barat" / "KAB. ACEH BARAT").

Both sides get pushed through normalize_name() before comparison so that
casing, punctuation, and administrative-unit prefixes ("KAB.", "KOTA",
"KEC.", "DESA", "KELURAHAN", ...) stop being sources of mismatch.
"""

import re
import unicodedata

_PREFIXES = {
    "district": ["KABUPATEN", "KAB", "KOTA ADMINISTRASI", "KOTA", "KOTAMADYA"],
    "subdistrict": ["KECAMATAN", "KEC", "DISTRIK"],
    "village": ["KELURAHAN", "KEL", "DESA", "NAGARI", "GAMPONG", "KAMPUNG", "PEKON", "NEGERI"],
}

_ALIASES = {
    # a few well-known province naming variants that show up across sources
    "DAERAH ISTIMEWA YOGYAKARTA": "DI YOGYAKARTA",
    "DIY": "DI YOGYAKARTA",
    "DKI JAKARTA": "DKI JAKARTA",
    "PROVINSI DKI JAKARTA": "DKI JAKARTA",
    "PROVINSI DI YOGYAKARTA": "DI YOGYAKARTA",
    # known typo in the BIG kecamatan shapefile itself (Kab. Aceh Barat) -
    # every village under it fails the parent-path match without this
    "JOHAN PAHWALAN": "JOHAN PAHLAWAN",
}

# word-level expansions applied token-by-token after prefix stripping - covers
# common abbreviations that show up in kopdes district names but not in the
# BIG shapefile's spelled-out names (e.g. "KAB. OKU TIMUR" vs "Ogan Komering
# Ulu Timur"). Scoped to 'district' to avoid collateral matches elsewhere.
_WORD_ALIASES = {
    "district": {
        "OKU": "OGAN KOMERING ULU",
        "OKI": "OGAN KOMERING ILIR",
        "KEP": "KEPULAUAN",
        "ADM": "ADMINISTRASI",
    },
}


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def normalize_name(raw: str, kind: str | None = None) -> str:
    """kind: None | 'district' | 'subdistrict' | 'village' - strips the matching
    administrative-unit prefix token(s) if present, in addition to generic cleanup."""
    if raw is None:
        return ""
    s = _strip_accents(str(raw)).upper()
    s = s.replace(".", " ").replace("-", " ").replace("'", "")
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    word_aliases = _WORD_ALIASES.get(kind)
    if word_aliases:
        s = " ".join(word_aliases.get(tok, tok) for tok in s.split(" "))

    if kind in _PREFIXES:
        for prefix in _PREFIXES[kind]:
            if s.startswith(prefix + " "):
                s = s[len(prefix) + 1:]
                break

    return _ALIASES.get(s, s)


def dedupe_key(*parts: str) -> tuple:
    return tuple(parts)
