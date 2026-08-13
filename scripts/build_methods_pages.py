#!/usr/bin/env python3
"""
Generate the /methods/ appendix pages.

The public-facing method pages are hand-written, plain-language Indonesian
markdown in methods/_content/NN-slug.md — no code, no jargon, the same register
as the rest of the report site. Each generated shell fetches that file at
runtime and renders it with app/site.js, so the content lives in exactly one
place.

The authoritative technical reports stay in reports/NN-slug/README.md (English,
with code, raw data and reproducibility instructions) and are linked — not
embedded — from each page. That keeps the public page readable while keeping
every number traceable for anyone who wants to re-run the work.

Run from the repo root:  python scripts/build_methods_pages.py
Re-run whenever a report is added, renamed, or its title changes.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
METHODS = ROOT / "methods"
CONTENT = METHODS / "_content"

# Reports that intentionally stay out of the public /methods/ appendix. The
# technical write-up remains in reports/ (the evidence base); it is simply not
# published as a public method page.
EXCLUDED = {"18-health-scoring"}

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
    <p class="kicker">Metode · {slug}</p>
    <h1>{title}</h1>
    <p class="lede">{lede}</p>
    <div class="callout"><span class="callout-label">Ringkasan</span>
      <p>{summary}</p>
    </div>
    <div id="md"></div>
    <hr />
    <p class="md-note">Laporan teknis lengkap dari analisis ini (bahasa Inggris,
      dengan data mentah dan cara menjalankan ulang) tersedia di
      <a href="../../reports/{slug}/README.md">reports/{slug}/README.md</a>.
      Daftar kandidat yang <strong>belum diverifikasi</strong> (jika ada) hanya
      ada di sana; lihat <a href="../../about/">kebijakan verifikasi &amp;
      koreksi</a>.</p>
  </main>
  <footer id="site-footer"></footer>
  <script type="module" src="../../app/site.js"></script>
  <script type="module">
    import {{ fetchMarkdown, renderMarkdownInto }} from "../../app/site.js";
    const md = document.getElementById("md");
    try {{
      const text = await fetchMarkdown("../../methods/_content/{slug}.md");
      await renderMarkdownInto(md, text);
    }} catch (e) {{
      md.innerHTML = `<p style="color:#a00">Gagal memuat metode: ${{e.message}}</p>`;
    }}
  </script>
</body>
</html>
"""

# Indonesian public-facing metadata, written by hand. The `title` and `lede`
# head the page; `summary` fills the callout under the lede; `question` is the
# one-line card on /methods/.
ID_TITLE = {
    "01-snapshot-drift": "Angka nol itu nyata, atau hanya belum diisi?",
    "02-zero-inflation": "Hampir semua data kinerja adalah nol",
    "03-population-coverage": "Jangkauan penduduk dan keterpencilan",
    "04-siting-screen": "Layar penapisan lokasi: koperasi mana yang lingkungannya mustahil?",
    "05-road-access": "Jarak ke jalan: seberapa jauh setiap koperasi dari jalan?",
    "06-minimarket-proximity": "Kedekatan dengan minimarket: dibangun di atas ritel yang sudah ada?",
    "07-landuse-polygons": "Penggunaan lahan: di atas kuburan, atau di tengah sawah?",
    "08-exact-geometry": "Geometri yang presisi: jarak sebenarnya, dan koordinat yang mustahil",
    "09-external-corroboration": "Pemeriksaan silang: apakah dashboard adalah angka resmi?",
    "10-coop-clustering": "Penumpukan koperasi: seberapa banyak program ini menumpuk dengan dirinya sendiri?",
    "11-savings-behaviour": "Perilaku menabung: apakah anggota benar-benar menabung?",
    "12-product-mix": "Jenis produk: program ini sebenarnya menjual apa?",
    "13-compliance-npwp-nib": "Kepatuhan NPWP dan NIB: suratnya ada, adakah yang beroperasi?",
    "14-island-comparison": "Perbandingan antarpulau: program ini milik Jawa atau Indonesia?",
    "15-construction-output": "Konstruksi versus hasil",
    "16-rat-compliance": "Kepatuhan RAT: \u201cnol\u201d ternyata salah baca kolom",
    "17-building-proximity": "Jarak ke bangunan: seberapa jauh koperasi dari rumah terdekat?",
    "18-health-scoring": "Indeks kesehatan: apa arti \u201ctidak sehat \u00d738\u201d?",
}

ID_LEDE = {
    "01-snapshot-drift": (
        "Apakah 97% angka nol itu berarti program ini mati, atau hanya belum "
        "diisi? Jawabannya menentukan hampir semua temuan lain di situs ini."
    ),
    "02-zero-inflation": (
        "Hampir semua data kinerja dalam sistem ini adalah nol. Berapa banyak "
        "yang benar-benar terisi, dan apa artinya untuk angka yang boleh kita kutip."
    ),
    "03-population-coverage": (
        "Siapa yang terjangkau program ini? Hasilnya membelah dua: jangkauan "
        "sangat baik, tetapi ekornya nyata."
    ),
    "04-siting-screen": (
        "Koperasi mana yang lingkungannya mustahil? Kami mengurutkan 83 ribu "
        "koperasi dari yang paling sepi, lalu memeriksa ketinggian, kemiringan, "
        "dan penutup lahannya."
    ),
    "05-road-access": (
        "Seberapa jauh koperasi dari jalan? Kami mengukur jarak setiap koperasi "
        "ke jalan terdekat di peta nasional \u2014 dan memisahkan jalan beraspal "
        "dari jalan tanah."
    ),
    "06-minimarket-proximity": (
        "Apakah koperasi dibangun di atas minimarket yang sudah ada? Datanya "
        "tidak sempurna, jadi kami katakan kelemahannya lebih dulu \u2014 lalu "
        "mengujinya dengan lokasi acak yang sebanding."
    ),
    "07-landuse-polygons": (
        "Dua tuduhan yang tak terlihat analisis lain: di tanah kuburan dan di "
        "tengah sawah. Keduanya diuji dengan peta \u2014 dan hasilnya berlawanan arah."
    ),
    "08-exact-geometry": (
        "Jarak yang diukur ulang satu per satu, dan sebuah temuan yang tidak "
        "disengaja: 19 koperasi ternyata tidak berada di Indonesia."
    ),
    "09-external-corroboration": (
        "Angka resmi pemerintah cocok dengan dashboardnya \u2014 sampai selisih "
        "0,04%. Bantahan \u201cwebsitenya belum diperbarui\u201d runtuh."
    ),
    "10-coop-clustering": (
        "Apakah koperasi menumpuk dengan koperasi lain? Kami mengukur jarak "
        "sebenarnya, dan menemukan: hampir menyambung, bukan menumpuk."
    ),
    "11-savings-behaviour": (
        "Apakah anggota benar-benar menabung? Simpanan dibagi menjadi modal "
        "sekali dan iuran berkala \u2014 dan perbandingan keduanya bercerita."
    ),
    "12-product-mix": (
        "Program ini sebenarnya menjual apa? Komposisinya sederhana dan "
        "konsisten: sembako dan pupuk."
    ),
    "13-compliance-npwp-nib": (
        "Uji zombie: surat-suratnya nyaris lengkap, tetapi adakah yang "
        "beroperasi dengan surat itu?"
    ),
    "14-island-comparison": (
        "Program ini milik Jawa atau Indonesia? Dari ekonomi sampai penempatan, "
        "jawabannya konsisten."
    ),
    "15-construction-output": (
        "Apakah konstruksi sejalan dengan hasil? Dua fakta struktural perlu "
        "dinyatakan \u2014 dan kami menahan diri dari klaim sebab-akibat."
    ),
    "16-rat-compliance": (
        "Sebuah koreksi: \u201cRAT nol di semua provinsi\u201d ternyata salah baca "
        "kolom. Angka sebenarnya: 60%."
    ),
    "17-building-proximity": (
        "Seberapa jauh koperasi dari rumah terdekat? Kami mengukur hal yang "
        "harfiah \u2014 dan menahan diri untuk tidak membaca \u201ctidak "
        "terpetakan\u201d sebagai \u201ctidak ada\u201d."
    ),
    "18-health-scoring": (
        "Apa arti \u201ctidak sehat \u00d738\u201d? Ternyata kolomnya konstan. "
        "Indeks yang sebenarnya bercerita lain."
    ),
}

ID_SUMMARY = {
    "01-snapshot-drift": (
        "Apakah data SIMKOPDES masih diisi? Kami membandingkan dua cuplikan data "
        "berjarak empat hari. Dari 80.553 desa yang nihil transaksi pada 5 Agustus, "
        "hanya satu yang melaporkan aktivitas pada 9 Agustus. Sistem ini tidak "
        "sedang aktif diisi. (Pada 13 Agustus, 209 desa baru mulai melaporkan "
        "\u2014 jadi bacaan ini hanya berlaku untuk jendela itu.)"
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
        "Apakah koperasi dibangun di atas minimarket? Setelah memperhitungkan "
        "bahwa keduanya sama-sama suka berada di jalan utama daerah ramai, "
        "minimarket sekitar 9,6 poin lebih mungkin punya koperasi dalam 500 m "
        "daripada lokasi acak yang sebanding \u2014 tetapi kelebihannya hilang pada "
        "jarak 2 km. Kedekatan ini nyata tapi sedang; bukan bukti persaingan dagang."
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
        "jalan diukur ulang dengan teliti: separuhnya lebih dari 9,7 km, dan 16 "
        "koperasi lebih dari 100 km. Laporan ini juga menemukan 19 koperasi di "
        "luar Indonesia \u2014 koordinat mustahil \u2014 dan mengoreksi angka "
        "laporan 04 dan 05. Catatan 13-08-2026: pemerintah telah mengoreksi "
        "ke-19 koordinat itu."
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
        "OpenStreetMap (44 juta bangunan), 62,6% koperasi tidak punya satu pun "
        "bangunan terpetakan dalam 5 km. Ini batas bawah: peta bangunan belum "
        "lengkap di pedesaan, jadi tuliskan \u201ctidak ada rumah terpetakan\u201d, "
        "bukan \u201ctidak ada rumah\u201d."
    ),
    "18-health-scoring": (
        "Apa arti \u201cindeks kesehatan\u201d koperasi? Label \u201ctidak sehat di semua "
        "provinsi\u201d adalah artefak: kolomnya konstan (30) di 38 provinsi, jadi tidak "
        "boleh dikutip. Indeks sungguhan (50\u201357) hanya dihitung untuk 38% "
        "koperasi \u2014 62% tidak pernah dinilai \u2014 dan di antara yang dinilai, 91% "
        "tetap \u201ctidak sehat\u201d. Indeks ini lebih mencerminkan kelengkapan data "
        "dan kepatuhan administrasi daripada kesehatan yang independen."
    ),
}

ID_QUESTION = {
    "01-snapshot-drift": "Apakah data SIMKOPDES masih diisi? Apakah nol hanya sementara?",
    "02-zero-inflation": "Berapa banyak data kinerja yang benar-benar nol?",
    "03-population-coverage": "Siapa yang terjangkau koperasi, dan koperasi mana yang dekat dengan siapa pun?",
    "04-siting-screen": "Koperasi mana yang berada di lokasi yang mustahil?",
    "05-road-access": "Seberapa jauh setiap koperasi dari jalan?",
    "06-minimarket-proximity": "Apakah koperasi dibangun di atas minimarket yang sudah ada?",
    "07-landuse-polygons": "Di atas kuburan atau di tengah sawah?",
    "08-exact-geometry": "Berapa jauh sebenarnya? Apakah koordinatnya masuk akal?",
    "09-external-corroboration": "Apakah angka resmi pemerintah sama dengan angka di dashboard?",
    "10-coop-clustering": "Seberapa banyak program ini menumpuk dengan dirinya sendiri?",
    "11-savings-behaviour": "Apakah anggota benar-benar menabung, atau rekeningnya tidur?",
    "12-product-mix": "Program ini sebenarnya menjual apa?",
    "13-compliance-npwp-nib": "Apakah surat-suratnya nyata, dan adakah yang beroperasi dengan surat itu?",
    "14-island-comparison": "Program ini milik Jawa atau Indonesia?",
    "15-construction-output": "Apakah konstruksi sejalan dengan hasil?",
    "16-rat-compliance": "Apakah koperasi benar-benar menggelar RAT?",
    "17-building-proximity": "Seberapa jauh koperasi dari rumah terdekat?",
    "18-health-scoring": "Apa sebenarnya arti \u201ctidak sehat\u201d pada indeks kesehatan?",
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
    <p class="lede">Setiap klaim di situs ini bisa ditelusuri ke salah satu
      halaman di bawah. Tiap halaman menjelaskan dalam bahasa sederhana: dari
      mana datanya, bagaimana kami mengolahnya, apa yang kami temukan — dan apa
      yang tidak bisa kami katakan. Laporan teknis lengkap (bahasa Inggris,
      dengan data mentah dan cara menjalankan ulang) ditautkan di tiap halaman
      bagi siapa pun yang ingin memeriksa pekerjaan kami.</p>
    <div class="callout"><span class="callout-label">Perhatian</span>
      Sebagian laporan memuat kandidat yang <strong>belum diverifikasi</strong>
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


def main() -> None:
    slugs = sorted(
        p.name for p in REPORTS.iterdir()
        if p.is_dir() and re.fullmatch(r"\d{2}-[a-z0-9-]+", p.name)
    )
    if not slugs:
        sys.exit("no report directories found under reports/")

    CONTENT.mkdir(exist_ok=True)
    METHODS.mkdir(exist_ok=True)

    rows = []
    for slug in slugs:
        if slug in EXCLUDED:
            print(f"  skipped {slug} (excluded from public methods)")
            continue
        readme = REPORTS / slug / "README.md"
        if not readme.exists():
            print(f"  skipping {slug} (no README.md)")
            continue
        title = ID_TITLE.get(slug) or report_title(readme)
        lede = ID_LEDE.get(slug, "")
        summary = ID_SUMMARY.get(slug, "Ringkasan bahasa Indonesia belum tersedia.")
        question = ID_QUESTION.get(slug, title)

        content = CONTENT / f"{slug}.md"
        if content.exists():
            print(f"  content: {content.relative_to(ROOT)}")
        else:
            print(f"  warning: no {content.relative_to(ROOT)} — page will be thin")

        out = METHODS / slug / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            SHELL.format(
                title=title,
                slug=slug,
                lede=lede,
                summary=summary,
            ),
            encoding="utf-8",
        )
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
