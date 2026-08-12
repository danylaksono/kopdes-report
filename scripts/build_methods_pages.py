#!/usr/bin/env python3
"""
Generate the /methods/ appendix pages from reports/*/README.md.

The site rule is "generated from reports/*/README.md, never written twice" —
the READMEs are the single source of truth and are rendered client-side by
app/site.js. This script only scaffolds the thin per-report HTML shells (and
the index); it does not copy the content.

Run from the repo root:  python scripts/build_methods_pages.py
Re-run whenever a report is added or its slug/title changes.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
METHODS = ROOT / "methods"

SHELL = """<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title} — Metode</title>
  <link rel="stylesheet" href="../../app/site.css" />
</head>
<body data-root="../../">
  <nav id="site-nav"></nav>
  <main class="wrap">
    <p class="kicker">Metode · lampiran {slug}</p>
    <h1>{title}</h1>
    <p class="lede">Lampiran metode ini ditampilkan langsung dari
      <code>reports/{slug}/README.md</code> — satu sumber kebenaran, tidak
      ditulis dua kali.</p>
    <div id="md"></div>
    <p class="md-note">Laporan metode ditulis dalam bahasa Inggris dan memuat
      tabel data mentah, termasuk nama kandidat yang <strong>belum
      diverifikasi</strong>. Lihat <a href="../../about/">kebijakan verifikasi
      &amp; koreksi</a> sebelum mengutip nama desa/koperasi apa pun.</p>
  </main>
  <footer id="site-footer"></footer>
  <script type="module" src="../../app/site.js"></script>
  <script type="module">
    import {{ fetchMarkdown, renderMarkdownInto }} from "../../app/site.js";
    const md = document.getElementById("md");
    try {{
      const text = await fetchMarkdown("../../reports/{slug}/README.md");
      await renderMarkdownInto(md, text);
    }} catch (e) {{
      md.innerHTML = `<p style="color:#a00">Gagal memuat README: ${{e.message}}</p>`;
    }}
  </script>
</body>
</html>
"""

INDEX_HEAD = """<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Metode — lampiran</title>
  <link rel="stylesheet" href="../app/site.css" />
</head>
<body data-root="../">
  <nav id="site-nav"></nav>
  <main class="wrap">
    <p class="kicker">Lampiran metode</p>
    <h1>Metode: bagaimana setiap angka diperoleh</h1>
    <p class="lede">Setiap klaim di situs ini dapat ditelusuri ke salah satu
      laporan berikut. Tiap laporan adalah satu direktori di
      <code>reports/</code> yang berisi <code>run.py</code> (dapat dijalankan
      ulang), <code>README.md</code> (tulisan analisis), dan CSV hasil yang
      dikomit. Halaman ini <strong>dibuat langsung dari README
      tersebut</strong> — tidak ada salinan kedua.</p>
    <div class="callout"><span class="callout-label">Peringatan</span>
      Laporan metode memuat nama kandidat yang <strong>belum diverifikasi</strong>
      (satu koordinat yang salah dapat menimpa nama desa yang tidak bersalah).
      Halaman naratif di <a href="../findings/">Temuan</a> mengikuti kebijakan
      <em>anonim sampai terverifikasi</em>; lihat <a href="../about/">Tentang</a>.</div>
"""

INDEX_ROW = """    <div class="card">
      <span class="card-kicker">{slug}</span>
      <h3>{title}</h3>
      <p>{question}</p>
      <p><a href="{slug}/">Buka lampiran →</a></p>
    </div>
"""

INDEX_FOOT = """  </main>
  <footer id="site-footer"></footer>
  <script type="module" src="../app/site.js"></script>
</body>
</html>
"""


def report_title(readme: Path) -> str:
    for line in readme.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^#\s+(.+)$", line.strip())
        if m:
            return m.group(1).strip()
    return readme.parent.name


def index_questions() -> dict:
    """slug -> question, read from the Question column of reports/README.md.

    That index table is the authoritative one-line question per report; the
    README bodies rarely phrase it as a standalone sentence.
    """
    q = {}
    readme = REPORTS / "README.md"
    if not readme.exists():
        return q
    for line in readme.read_text(encoding="utf-8").splitlines():
        m = re.match(r"\|\s*\d+\s*\|\s*\[[^]]+\]\(([^)]+)\)\s*\|\s*([^|]+)\|", line)
        if m:
            q[m.group(1).rstrip("/")] = m.group(2).strip()
    return q


def first_question(readme: Path, slug: str) -> str:
    for line in readme.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith("|"):
            continue
        if "?" in s:
            return s[:140]
    return "Lampiran metode untuk " + slug


def main() -> None:
    slugs = sorted(
        p.name for p in REPORTS.iterdir()
        if p.is_dir() and re.fullmatch(r"\d{2}-[a-z0-9-]+", p.name)
    )
    if not slugs:
        sys.exit("no report directories found under reports/")

    METHODS.mkdir(exist_ok=True)
    questions = index_questions()

    rows = []
    for slug in slugs:
        readme = REPORTS / slug / "README.md"
        if not readme.exists():
            print(f"  skipping {slug} (no README.md)")
            continue
        title = report_title(readme)
        out = METHODS / slug / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            SHELL.format(title=title, slug=slug),
            encoding="utf-8",
        )
        question = questions.get(slug) or first_question(readme, slug)
        rows.append((slug, title, question))
        print(f"  wrote {out.relative_to(ROOT)}")

    body = [INDEX_HEAD]
    for slug, title, question in sorted(rows, key=lambda r: r[0]):
        body.append(INDEX_ROW.format(slug=slug, title=title, question=question))
    body.append(INDEX_FOOT)
    (METHODS / "index.html").write_text("\n".join(body), encoding="utf-8")
    print(f"\n  wrote methods/index.html ({len(rows)} reports)")


if __name__ == "__main__":
    main()
