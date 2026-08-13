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
    <p class="lede">Laporan teknis lengkap dari analisis ini ditulis dalam bahasa
      Inggris demi ketelitian. Ringkasannya dalam bahasa Indonesia ada di bawah.</p>
    <div class="callout"><span class="callout-label">Ringkasan</span>
      <p>{summary}</p>
    </div>
    <h2>Laporan lengkap (Inggris)</h2>
    <div id="md"></div>
    <p class="md-note">Laporan ini memuat tabel data mentah, termasuk nama kandidat
      yang <strong>belum diverifikasi</strong>. Lihat <a href="../../about/">kebijakan
      verifikasi &amp; koreksi</a> sebelum mengutip nama desa/koperasi apa pun.</p>
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
      md.innerHTML = `<p style="color:#a00">Gagal memuat laporan: ${{e.message}}</p>`;
    }}
  </script>
</body>
</html>
"""

# Indonesian plain-language summary per report, written by hand so the public
# page reads like a report, not a machine translation. The English README below
# it remains the authoritative, reproducible source.
ID_SUMMARY = {
    "01-snapshot-drift": (
        "Apakah data SIMKOPDES masih diisi? Kami membandingkan dua cuplikan data "
        "berjarak empat hari. Dari 80.553 desa yang nihil transaksi pada 5 Agustus, "
        "hanya satu yang melaporkan aktivitas pada 9 Agustus. Artinya, angka nol di "
        "sistem ini nyaris tidak berubah dari waktu ke waktu — dan itu menguatkan "
        "dugaan bahwa nol berarti \u201cbelum ada laporan\u201d, bukan sekadar "
        "\u201cbelum sempat diisi\u201d."
    ),
    "02-zero-inflation": (
        "Berapa banyak data kinerja yang benar-benar nol? Ternyata hampir semuanya: "
        "hanya 3,3% desa yang melaporkan transaksi, dan nilainya terkonsentrasi "
        "ekstrem — 100 desa membawa 34,8% dari seluruh nilai nasional. Kolom "
        "administrasi (rekening, NPWP) hampir penuh; kolom aktivitas nyaris kosong."
    ),
    "03-population-coverage": (
        "Siapa yang terjangkau koperasi? Hampir semua orang: 95% penduduk tinggal "
        "dalam 1,4 km dari sebuah koperasi. Tetapi ada ekor yang nyata: 146 koperasi "
        "tanpa penduduk dalam radius 5 km, dan 21,3% koperasi berada di petak 400 "
        "meter yang kosong."
    ),
    "04-siting-screen": (
        "Koperasi mana yang berada di lokasi yang mustahil? Dari 2.500 koperasi "
        "paling terpencil, 2.385 berada di hutan tertutup, 1.008 di lereng curam, dan "
        "384 punya sertifikat lahan \u201cTerverifikasi\u201d. "
        "Catatan penting: cara ini tidak bisa membedakan koperasi yang benar-benar "
        "dibangun di tempat mustahil dari yang koordinatnya salah."
    ),
    "05-road-access": (
        "Berapa jauh koperasi dari jalan? 6,1% koperasi (5.106) "
        "tidak punya jalan beraspal dalam 5 km; 4.294 tidak punya jalan sama sekali. "
        "Angka ini berdasarkan peta OpenStreetMap yang belum lengkap di pedesaan, "
        "jadi merupakan batas bawah."
    ),
    "06-minimarket-proximity": (
        "Apakah koperasi dibangun di atas minimarket? Setelah memperhitungkan bahwa "
        "keduanya sama-sama suka berada di jalan utama daerah ramai, minimarket "
        "sekitar 9,4 poin lebih mungkin punya koperasi dalam 500 m daripada lokasi "
        "acak yang sebanding — tetapi kelebihannya hilang pada jarak 2 km. Kedekatan "
        "ini nyata tapi sedang; bukan bukti kompetisi dagang."
    ),
    "07-landuse-polygons": (
        "Di atas sawah atau kuburan? Koperasi \u201ctercatat\u201d di sawah 2,4 kali "
        "lebih sering dari biasanya (448 kasus dikonfirmasi oleh dua sumber peta "
        "independen). Klaim \u201cdi kuburan\u201d tidak terbukti — hanya 22 kasus. "
        "Penting: \u201ctercatat di\u201d belum tentu \u201cdibangun di\u201d — "
        "koordinatnya bisa saja salah."
    ),
    "08-exact-geometry": (
        "Berapa jauh sebenarnya? Untuk koperasi yang paling terpencil, jarak ke "
        "jalan diukur ulang dengan teliti: separuhnya lebih dari 9,7 km, dan 7 "
        "koperasi lebih dari 100 km. Laporan ini juga menemukan 19 koperasi di luar "
        "Indonesia \u2014 koordinat mustahil \u2014 dan mengoreksi angka laporan 04 "
        "dan 05. Catatan 13-08-2026: pemerintah telah mengoreksi ke-19 koordinat "
        "itu, dan laporan 03\u201308 telah dijalankan ulang pada koordinat terbaru."
    ),
    "09-external-corroboration": (
        "Apakah angka pemerintah cocok dengan angka kami? Nyaris persis: media "
        "melaporkan Rp 179,72 miliar, kami Rp 179,79 miliar. Laporan ini pula yang "
        "meluruskan klaim \u201c179,5 triliun\u201d yang pernah beredar \u2014 termasuk "
        "di catatan perencanaan kami sendiri \u2014 yang benar adalah miliar, "
        "keliru 1000\u00d7."
    ),
    "10-coop-clustering": (
        "Apakah koperasi saling menumpuk? 22,2% koperasi punya koperasi lain dalam "
        "1 km, dan 6,8% berbagi petak 1 km yang sama. Tetapi sebagian besar "
        "\u201cpenumpukan\u201d halus ternyata koordinat ganda (798 koperasi), bukan "
        "bangunan yang bersebelahan. Dan koperasi yang berdekatan tidak berkinerja "
        "lebih buruk."
    ),
    "11-savings-behaviour": (
        "Apakah anggota benar-benar menabung? Hanya 12,5% desa melaporkan simpanan "
        "apa pun — dan di yang ada, uangnya adalah modal awal (sekali setor saat "
        "didirikan), bukan tabungan berjalan: median iuran wajib hanya 0,28\u00d7 "
        "modal pokok."
    ),
    "12-product-mix": (
        "Program ini menjual apa? Lebih dari tiga perempat nilai penjualan yang dilaporkan "
        "adalah beras dan minyak goreng, dengan pupuk sebagai barang utama lainnya. "
        "Koperasi desa ini berperan sebagai toko sembako dan saprotan."
    ),
    "13-compliance-npwp-nib": (
        "Apakah surat-suratnya lengkap? NPWP 97%, NIB 73%. Tetapi uji \u201czombie\u201d "
        "menunjukkan: 69,9% desa memegang izin usaha tanpa transaksi apa pun, "
        "sementara hanya 0,03% yang melaporkan transaksi tanpa izin. Suratnya ada; "
        "bisnisnya tidak."
    ),
    "14-island-comparison": (
        "Program ini milik Jawa atau Indonesia? Jawa punya 30% koperasi tetapi "
        "sekitar 60% nilai transaksi; Papua 8,5% koperasi dan sekitar 0,6% nilai. "
        "Ekor keterpencilan, verifikasi lahan yang minim, dan aktivitas yang senyap — "
        "semuanya tinggal di Indonesia timur."
    ),
    "15-construction-output": (
        "Apakah konstruksi sejalan dengan hasil? Hanya 24% koperasi yang konstruksinya "
        "100% selesai, lebih dari separuh tanpa catatan konstruksi sama sekali. "
        "Kaitan konstruksi\u2013hasil lemah dan tercampur faktor geografi, jadi tidak "
        "bisa dibaca sebagai sebab-akibat."
    ),
    "16-rat-compliance": (
        "Apakah koperasi benar-benar menggelar rapat anggota tahunan (RAT)? Ya \u2014 "
        "60% koperasi tercatat telah melaksanakan RAT per 5 Agustus 2026, tetapi hanya "
        "6% di Papua Pegunungan. Temuan awal yang menyebut \u201cRAT nol di semua "
        "provinsi\u201d keliru karena salah membaca kolom data."
    ),
    "17-building-proximity": (
        "Seberapa jauh koperasi dari rumah terdekat? Dengan data bangunan "
        "OpenStreetMap (44 juta bangunan), sebagian koperasi tidak punya satu pun "
        "bangunan terpetakan dalam 500 m \u2014 tidak ada rumah di sekitarnya. Ini "
        "batas bawah: peta bangunan belum lengkap di pedesaan, jadi tuliskan \u201ctidak "
        "ada rumah terpetakan\u201d, bukan \u201ctidak ada rumah\u201d."
    ),
}

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
      laporan berikut. Tiap laporan bisa dijalankan ulang, ditulis lengkap dalam
      bahasa Inggris demi ketelitian, dan disertai ringkasan bahasa Indonesia.
      Halaman ini dibuat langsung dari laporan aslinya — tidak ada salinan kedua.</p>
    <div class="callout"><span class="callout-label">Perhatian</span>
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
            SHELL.format(
                title=title,
                slug=slug,
                summary=ID_SUMMARY.get(slug, "Ringkasan bahasa Indonesia belum tersedia."),
            ),
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
