# kopdes

Investigasi data atas **Koperasi Desa/Kelurahan Merah Putih**, beserta seluruh
alur data dan peta interaktifnya. Sumber datanya
[SIMKOPDES](https://simkopdes.go.id) dengan API publik dari kementerian sendiri.

Repositori ini memuat tiga hal sekaligus: **laporannya** (situs statis di akar
repo), **bukti di baliknya** (`reports/`, satu direktori per analisis, bisa
dijalankan ulang), dan **data mentahnya** (`data/raw/`, ikut di-commit).

> Catatan bahasa: laporan publik dan berkas ini berbahasa Indonesia. Laporan
> teknis di `reports/` sengaja tetap berbahasa Inggris, karena itu berkas kerja
> yang harus bisa dibaca dan diuji siapa pun yang mengulang analisisnya.

## Laporannya

Situs disajikan langsung dari tiap laporan, dan sengaja dibuat statis tanpa framework.

| Halaman                    | Isi                                                                      |
| -------------------------- | ------------------------------------------------------------------------ |
| [`index.html`](index.html) | Cerita utama, _storytelling_, ringkasan seluruh temuan                   |
| [`findings/`](findings/)   | Tiga bab temuan, lebih dalam, dengan tabel dan gambarnya                 |
| [`explore/`](explore/)     | Peta interaktif: 83.379 koperasi, empat skala, tiga cara pewarnaan       |
| [`periksa/`](periksa/)     | Hitung ulang analisisnya di satu koordinat yang pembaca tentukan sendiri |
| [`tabel/`](tabel/)         | Tabel lengkap, bisa dicari dan diurutkan                                 |
| [`methods/`](methods/)     | Lampiran metode, bahasa Indonesia, satu halaman per analisis             |
| [`data/`](data/)           | Unduhan, asal-usul data, dan catatan potret harian                       |
| [`about/`](about/)         | Siapa, kenapa, dan **log koreksi** publik                                |

### Tiga tuduhan yang diuji

Setiap bab menjawab satu tuduhan publik, dan menyebut vonisnya apa adanya,
termasuk ketika tuduhannya tidak terbukti.

| Bab                                                   | Tuduhan                                      | Vonis singkat                                                                      |
| ----------------------------------------------------- | -------------------------------------------- | ---------------------------------------------------------------------------------- |
| [1 · Akses & penempatan](findings/remoteness/)        | "Dibangun di tempat yang tak terjangkau"     | Tidak terbukti massal (95% penduduk dalam 1,4 km), tetapi ekornya nyata            |
| [2 · Kompetisi & kanibalisasi](findings/competition/) | "Dibangun menimpa minimarket yang sudah ada" | Kedekatannya nyata tapi sedang (6,7 poin); kompetisi dagang tidak terbukti         |
| [3 · Anggaran & output](findings/money/)              | "Boros, uang keluar tanpa hasil"             | "Tidak ada hasil" terbukti; "boros" tidak bisa diuji, sisi biaya tidak ada di data |

## Buktinya: 20 analisis di `reports/`

Setiap direktori berisi `run.py` (bisa dijalankan ulang), `README.md` (tulisan
lengkapnya, bahasa Inggris) dan CSV hasilnya yang ikut di-commit, sehingga
temuannya tetap ada tanpa perlu menjalankan ulang apa pun. Indeks lengkap
beserta status tiap laporan ada di **[`reports/README.md`](reports/README.md)**,
termasuk daftar "apa yang bisa dan tidak bisa kami katakan".

#### Dasar seluruh investigasi

| #                                                               | Pertanyaan                                                   |
| --------------------------------------------------------------- | ------------------------------------------------------------ |
| [01 snapshot-drift](reports/01-snapshot-drift/)                 | Apakah angka nol itu nyata, atau datanya memang belum diisi? |
| [02 zero-inflation](reports/02-zero-inflation/)                 | Berapa banyak data kinerja yang sebenarnya nol?              |
| [09 external-corroboration](reports/09-external-corroboration/) | Apakah angka publik kementerian cocok dengan dashboardnya?   |

#### Bab 1 · akses dan penempatan

| #                                                         | Pertanyaan                                                           |
| --------------------------------------------------------- | -------------------------------------------------------------------- |
| [03 population-coverage](reports/03-population-coverage/) | Siapa yang terjangkau, dan koperasi mana yang tidak dekat siapa pun? |
| [04 siting-screen](reports/04-siting-screen/)             | Koperasi mana yang lingkungannya mustahil?                           |
| [05 road-access](reports/05-road-access/)                 | Seberapa jauh tiap koperasi dari jalan?                              |
| [07 landuse-polygons](reports/07-landuse-polygons/)       | Di atas kuburan? Di tengah sawah?                                    |
| [08 exact-geometry](reports/08-exact-geometry/)           | Berapa jauh sebenarnya, dan apakah koordinatnya mungkin?             |
| [17 building-proximity](reports/17-building-proximity/)   | Seberapa jauh koperasi dari bangunan terdekat?                       |
| [19 land-cover](reports/19-land-cover/)                   | Tiap koperasi berdiri di atas penutup lahan apa?                     |
| [20 terrain](reports/20-terrain/)                         | Seberapa tinggi dan seberapa terjal tanah di bawah tiap koperasi?    |

#### Bab 2 · kompetisi dan kanibalisasi

| #                                                           | Pertanyaan                                                    |
| ----------------------------------------------------------- | ------------------------------------------------------------- |
| [06 minimarket-proximity](reports/06-minimarket-proximity/) | Apakah koperasi dibangun menimpa ritel modern yang sudah ada? |
| [10 coop-clustering](reports/10-coop-clustering/)           | Apakah koperasi menumpuk satu sama lain, dan merugikan?       |
| [12 product-mix](reports/12-product-mix/)                   | Program ini sebenarnya menjual apa?                           |

#### Bab 3 · anggaran dan output

| #                                                         | Pertanyaan                                                                  |
| --------------------------------------------------------- | --------------------------------------------------------------------------- |
| [11 savings-behaviour](reports/11-savings-behaviour/)     | Anggota benar-benar menabung, atau rekeningnya tidur?                       |
| [13 compliance-npwp-nib](reports/13-compliance-npwp-nib/) | Suratnya nyata, dan adakah yang beroperasi dengan surat itu?                |
| [14 island-comparison](reports/14-island-comparison/)     | Program ini milik Jawa atau milik Indonesia?                                |
| [15 construction-output](reports/15-construction-output/) | Apakah konstruksi sejalan dengan hasil?                                     |
| [16 rat-compliance](reports/16-rat-compliance/)           | Apakah koperasi menggelar rapat anggota tahunan?                            |
| [18 health-scoring](reports/18-health-scoring/)           | Indeks kesehatan kementerian itu sebenarnya bilang apa? (tidak diterbitkan) |

### Setiap angka yang terbit bisa dicek

`scripts/verify_published_figures.py` menghitung ulang **setiap angka utama yang
muncul di situs** dari data yang di-commit, lalu membandingkannya dengan teks
yang tertulis di halaman. Ini bukan formalitas: sebuah kekeliruan pemberian pita
jarak pernah menerbitkan 62,6% ketika angka sebenarnya 1,19%, dan lolos karena
tidak ada yang membandingkan kalimatnya dengan datanya.

```bash
python scripts/verify_published_figures.py           # periksa saja
python scripts/verify_published_figures.py --emit    # sekaligus tulis data/web/figures.json
```

Halaman menuliskan angkanya lewat `<span data-fig="kunci">6,7</span>`, dan
`app/site.js` mengganti isinya dari `figures.json` saat halaman dimuat. Teks yang
tertulis di berkas HTML tetap harus benar, karena itulah yang dilihat pembaca
tanpa JavaScript dan yang terlihat di `git diff`; skrip di atas gagal kalau
keduanya tidak cocok. Pemeriksa lain:

```bash
python scripts/check_links.py       # tautan internal
python scripts/check_emdashes.py    # tanda pisah panjang di teks publik
```

## Mengambil datanya

Cuma butuh datanya, bukan alur kerjanya? `data/raw/*.csv` ikut di-commit di repo
ini, jadi cukup klon dan semuanya sudah ada:

```bash
git clone <url-repo-ini>
```

Atau ambil satu berkas tanpa mengklon: buka di GitHub lalu pakai tombol "Raw"
(atau `raw.githubusercontent.com/<pemilik>/<repo>/main/data/raw/<berkas>.csv`).

| Berkas                                                                              | Isinya                                                                       |
| ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| `kopdes_locations.csv`                                                              | setiap koperasi: id, nama, provinsi/kabupaten/kecamatan, lintang/bujur       |
| `kopdes_land_assets.csv`                                                            | lahan/bangunan hasil survei per koperasi, termasuk `status` verifikasinya    |
| `kopdes_stats_province.csv` / `_district.csv` / `_subdistrict.csv` / `_village.csv` | statistik agregat (rekening, transaksi, simpanan, dll) di tiap tingkat admin |
| `kopdes_national_summary.csv`                                                       | angka utama nasional                                                         |
| `kopdes_province_rat_and_construction.csv`                                          | status rapat anggota tahunan (RAT) dan kemajuan bangunan per provinsi        |
| `kopdes_province_top_products.csv`                                                  | produk terlaris per provinsi                                                 |

CSV di repo ini adalah potret dari kapan pun terakhir dibuat ulang (cek
`git log -- data/raw` untuk tanggalnya). Kalau ingin tarikan segar langsung dari
SIMKOPDES:

```bash
python scripts/extract_kopdes.py data/raw
```

Skrip itu memanggil API publik (tanpa autentikasi) dan menimpa berkasnya.

### Potret bertanggal

`data/snapshots/<tanggal>/` menyimpan tarikan bertanggal. **CSV-nya tidak
di-commit** (28 MB sekali tarik), tetapi `_manifest.json`-nya di-commit: berisi
hash SHA-256 tiap berkas, dan itulah satu-satunya catatan asal-usul untuk potret
yang tidak bisa ditarik ulang, karena API hanya melayani keadaan terkini.

Beberapa laporan dijalankan terhadap potret 13 Agustus, bukan terhadap
`data/raw` yang bertanggal 5 Agustus. Tiap direktori laporan mencatatnya sendiri
di `_source.json`, dan README-nya menyebut perintah untuk mengulangnya:

```bash
KOPDES_RAW=data/snapshots/2026-08-13 python reports/02-zero-inflation/run.py
```

Menjalankan tanpa `KOPDES_RAW` membaca ekspor 5 Agustus, dan angkanya akan
berbeda. Itu bukan kerusakan, itu memang potret yang berbeda.

## Susunan direktori

```
index.html         cerita utama (bergulir), disajikan dari akar repo
findings/          tiga bab temuan
methods/           lampiran metode; isinya di methods/_content/*.md
explore/           peta interaktif
periksa/           pemeriksa satu koordinat
app/               kerangka bersama (site.css, site.js) + story.js
app/explore/       modul peta; app/explore.css chrome-nya
reports/           20 analisis: run.py + README.md + CSV hasilnya
data/raw/          kopdes_*.csv, ekspor mentah SIMKOPDES (di-commit)
data/web/          mart parquet + batas wilayah sederhana + figures.json (di-commit)
scripts/           ekstraktor, pembangun mart, pembangun batas, pemeriksa angka
geo/               alur unduh/konversi/gabung batas wilayah (lihat geo/README.md)
```

`geo/raw/`, `geo/geojson/` dan `geo/output/` diabaikan git, karena dibuat ulang
dari `data/raw/` dan ukurannya ratusan MB. `data/web/` juga diabaikan _kecuali_
berkas yang memang diambil aplikasi saat dibuka: empat tabel parquet,
`mart_manifest.json`, `figures.json`, dan `boundaries/*.geojson`.

## Membuat ulang datanya

**1. Segarkan ekspor SIMKOPDES** (memanggil API langsung, aman diulang):

```bash
python scripts/extract_kopdes.py data/raw
```

**2. Bangun ulang poligon batas wilayah yang tergabung dengan statistik**
(sekali unduh ~675 MB, setelah itu tersimpan; lihat [geo/README.md](geo/README.md)
untuk cara kerja penggabungan berbasis nama dan celah yang diketahui):

```bash
pip install -r geo/requirements.txt
python geo/run_pipeline.py
```

**3. Bangun ulang lapisan batas untuk peta** dari hasil langkah 2 (cepat, tanpa
unduhan; hanya menyederhanakan `geo/output/` sampai cukup ringan untuk peramban):

```bash
python scripts/build_boundaries.py
```

## Mart analisis (yang dibaca aplikasi)

Setiap analisis di `reports/` menghasilkan tabelnya sendiri per koperasi.
Aplikasi butuh semuanya dalam satu baris, jadi
`scripts/build_analysis_mart.py` menggabungkan semuanya dan menulis empat berkas
parquet: ukuran yang sama pada empat tingkat agregasi, sehingga satu spesifikasi
visualisasi bekerja di semua tingkat zoom.

```bash
python scripts/build_analysis_mart.py
```

| Berkas                              | Baris  | Satuan                                  |
| ----------------------------------- | ------ | --------------------------------------- |
| `data/web/kopdes_points.parquet`    | 83.379 | satu koperasi ≈ satu desa, **81 kolom** |
| `data/web/kopdes_kecamatan.parquet` | 7.277  | kecamatan                               |
| `data/web/kopdes_kabupaten.parquet` | 514    | kabupaten/kota                          |
| `data/web/kopdes_provinsi.parquet`  | 38     | provinsi                                |

Keempatnya (plus `mart_manifest.json`) **ikut di-commit**, sekitar 7 MB, cukup
kecil untuk disajikan GitHub Pages, tidak seperti `points.geojson` 25 MB yang
digantikannya. Sisa isi `data/web/` tetap diabaikan git.

**Mart ini tidak menghitung apa pun.** Kalau angka di sini berbeda dengan angka
di laporannya, yang benar laporannya dan mart-nya rusak.

Tiap titik membawa id sel H3 pada r5 sampai r9 sebagai `UBIGINT`, sehingga
aplikasi bisa membin ulang di resolusi mana pun tanpa menghitung lagi dari
lintang/bujur (pakai `h3_h3_to_string()` untuk bentuk heksadesimalnya). Tiap
baris agregat membawa `anchor_lat`/`anchor_lon`, yaitu posisi median
anggotanya, dan itulah yang dipakai penggambar ketika yang digambar bukan titik.
Tetap saring `anchor_lat is not null` sebelum memetakan, sebagai pengaman.

**Baca `mart_manifest.json` sebelum memetakan kolom apa pun.** Berkas itu
mencatat skema, cakupan penggabungan, dan yang terpenting, **arti null di tiap
kolom**. Beberapa null justru membawa temuannya, bukan menandai data hilang:
`km_to_minimarket` yang null berarti "tidak ada minimarket dalam 5 km" (66.874
koperasi), bukan "tidak diketahui", dan menggambarnya sebagai data hilang
membalik hasil [laporan 06](reports/06-minimarket-proximity/).

Satu penggabungan bersifat lossy dan manifest menerbitkan angkanya: id
administratif terselesaikan untuk **seluruh** 83.379 koperasi, sedangkan
ekonomi tingkat desa perlu dua lompatan lewat berkas aset lahan dan hanya
mencapai **79,1%**. Karena itu ekonomi agregat _tidak_ berasal dari titik, tetapi
dikelompokkan langsung dari berkas desa yang lengkap dan cocok persis dengan
ekspor mentahnya. **Jangan pernah menjumlahkan ekonomi tingkat titik untuk
mendapat total wilayah; baca tabel agregatnya.**

## Aplikasinya

Situs statis dari akar repo, tanpa build. MapLibre GL JS,
[screengrid](https://github.com/danylaksono/screengrid) dan DuckDB-wasm dari CDN,
membaca parquet yang di-commit secara langsung:

```bash
python -m http.server 8000
# buka http://localhost:8000  (cerita)  atau  /explore/  (peta)
```

### Petanya (`/explore/`)

**Empat skala untuk 83.379 koperasi yang sama**, dipilih dari tangga di rel
kiri, yang sekaligus menunjukkan ongkos tiap pilihan: 83.379 titik → 7.277
kecamatan → 514 kabupaten → 38 provinsi.

- **Kisi dinamis**: sel dalam ruang layar lewat screengrid, ukuran piksel tetap
  (penggeser), dibin ulang tiap kali digeser dan di-zoom.
- **Kecamatan / Kabupaten / Provinsi**: satu glif per wilayah, digambar di
  _posisi median koperasi anggotanya_, bukan centroid poligon, yang bisa jatuh
  di laut. Batas wilayah sederhana digambar di bawahnya sebagai konteks.

**Tiga cara mewarnai sel**, semuanya berupa proporsi koperasi supaya keempat
skala tetap sebanding:

- **Profil**: empat batang, satu per pertanyaan yang diajukan laporan ini:
  sekitarnya sepi, jauh dari jalan, berdempetan, tidak melaporkan transaksi.
  Makin tinggi selalu berarti makin buruk, jadi glif yang tinggi adalah wilayah
  yang bermasalah di beberapa sisi sekaligus.
- **Komposisi**: kolom bertumpuk yang menunjukkan bagaimana koperasi di wilayah
  itu terbagi dalam satu keluarga kelas (jarak ke jalan, penduduk di sekitar,
  jarak ke koperasi terdekat).
- **Ukuran**: satu ukuran sebagai gradasi warna, dipatok 0 sampai 100% supaya
  arti warnanya tidak berubah saat peta digeser. Beberapa ukuran menumpuk di
  pita sempit di salah satu ujung, jadi ada tombol "regangkan skala"; legendanya
  mencetak batas nilainya setiap kali tombol itu aktif.

**Profil menggambar setiap glif dengan ukuran yang sama**, dan itu disengaja.
Mengukur glif berdasarkan jumlah koperasi akan membuat proporsi yang sama tampil
setinggi berbeda di sel yang berbeda, padahal justru perbandingan itulah yang
ingin didukung mode ini. Sel terkecil juga akan jatuh di bawah ukuran ketika
empat batang masih terbaca sebagai empat batang. Jumlahnya ada di inspektur.
Komposisi dan Ukuran memang ikut membesar mengikuti jumlah, karena di sana tidak
ada ongkosnya: proporsi tidak bergantung skala, dan warna membebaskan ukuran.
Di sana luas glif dipatok ke persentil tinggi, bukan ke nilai maksimum, karena
memakai puncak Jawa akan memipihkan seluruh wilayah lain.

**Titik koperasi** menumpangkan koordinat mentah di atas skala mana pun. Filter
berlaku untuk kisi dan titik, tidak pernah untuk agregat administratif yang
sudah dihitung sebelumnya (rel kiri mengatakannya ketika filter itu tidak
berlaku). Mengklik glif mana pun membuka inspektur berisi profil lengkap
dibanding angka nasional, median yang sengaja tidak dikodekan glifnya, dan
tombol untuk turun satu anak tangga di wilayah itu.

**Pencarian** (kiri atas, di atas peta) mencakup seluruh 83.379 nama koperasi
serta semua kecamatan, kabupaten dan provinsi. Memilih wilayah akan memindahkan
tangga ke skala itu dan membukanya; memilih koperasi akan terbang ke sana,
menyalakan lapisan titik dan menandainya, yang bila dipasangkan dengan peta
satelit adalah cara memeriksa apakah sebuah koordinat benar-benar jatuh di atas
sesuatu.

**Peta dasar** (kiri bawah, di atas peta): _Terang_ adalah
[OpenFreeMap](https://openfreemap.org) Positron yang diwarnai ulang mengikuti
palet laporan, _Detail_ adalah OpenFreeMap Liberty, dan _Satelit_ adalah
[Esri World Imagery](https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9).

> Citra satelitnya memakai Esri, bukan Google, dan itu disengaja: endpoint ubin
> `mt*.google.com` milik Google tidak dilisensikan untuk ditanam di situs lain.
> Kalau Anda punya kunci Google Maps Platform, Map Tiles API mereka adalah jalur
> resminya dan tinggal ditambahkan sebagai satu entri lagi di
> `app/explore/basemaps.js`.

Ikonnya [Phosphor](https://phosphoricons.com) (MIT), ditanam langsung.

## Catatan mutu data yang perlu diketahui

- `kopdes_stats_*.csv` memakai id internal SIMKOPDES sendiri
  (`province_id`/`district_id`/`subdistrict_id`/`village_id`), bukan kode
  BPS/Kemendagri. Lihat [geo/README.md](geo/README.md) untuk alasan penggabungan
  batas wilayah dilakukan lewat pencocokan nama.
- Sejumlah kecil baris sumber punya pasangan provinsi/kabupaten yang keliru atau
  koordinat yang mustahil, dan itu memang sudah begitu di ekspor SIMKOPDES-nya
  (misalnya kabupaten bernama "Fukuoka" terdaftar di provinsi "PAPUA").
  [Laporan 08](reports/08-exact-geometry/) mencatat **20 koordinat** yang jatuh
  di luar Indonesia pada ekspor 5 Agustus dan menandainya `coordinate_suspect` di
  mart; peta menyembunyikannya secara bawaan tetapi bisa dimunculkan. Kementerian
  sudah mengoreksi kedua puluhnya pada potret 9 Agustus, dan catatan sebelum
  sesudahnya ada di
  [`corrected_coordinates_2026-08.csv`](reports/08-exact-geometry/corrected_coordinates_2026-08.csv).
  Alur geo mencatat baris yang tidak cocok ke `geo/output/<tingkat>_unmatched.csv`.
- `kopdes_land_assets.csv` juga tidak punya id koperasi, jadi digabungkan ke
  `kopdes_locations.csv` lewat nama koperasi yang persis sama. Cara itu meleset
  sekitar 0,04% baris aset lahan (26 dari 65.921 nama unik) dan, untuk 55 nama
  ganda di berkas itu, mengambil baris yang muncul terakhir.
- **Nol berarti "belum melaporkan", bukan "tidak aktif".** Ini pembatas
  terpenting di seluruh investigasi, dan berlaku untuk setiap kolom kegiatan.
  Lihat [laporan 01](reports/01-snapshot-drift/) dan
  [laporan 02](reports/02-zero-inflation/).
- **Tidak ada di OpenStreetMap bukan berarti tidak ada di dunia nyata.** Setiap
  jarak yang diturunkan dari OSM adalah batas atas, dan setiap kedekatan adalah
  batas bawah. Peta ritel yang kami pakai hanya memuat sekitar 14% gerai
  Indomaret dan 11% Alfamart, dan di sebagian Papua tidak memuat satu pun.
