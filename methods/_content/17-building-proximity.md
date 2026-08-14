> **Koreksi 14 Agustus 2026.** Versi sebelumnya halaman ini menyebut 62,6%
> koperasi tidak punya satu pun bangunan terpetakan dalam sekitar 5 km. Angka
> itu **salah** dan kami tarik. Angka yang benar adalah **1,19%**. Dua sebabnya
> kami uraikan di bawah. Rinciannya ada di
> [catatan koreksi](../../about/).

## Pertanyaannya

Seberapa jauh koperasi dari rumah terdekat? Peta populasi (lampiran 03) mengukur penduduk dalam petak 400 meter; itu agregat, bukan rumah. Di sini kami mengukur hal yang harfiah: jarak ke bangunan terdekat yang terpetakan.

## Yang kami temukan

**44,4% koperasi berdiri tepat di atas petak yang berisi bangunan terpetakan, dan tiga perempatnya (75,2%) punya bangunan terpetakan dalam jarak sekitar 260 meter.** Hanya 1,19% yang tidak punya satu pun bangunan terpetakan dalam sekitar 5 km.

Artinya jelas dan harus dikatakan terus terang: **tuduhan bahwa koperasi dibangun jauh dari permukiman tidak terbukti secara nasional dalam ukuran ini.** Sebagian besar koperasi berdiri di tengah bangunan.

| Jarak ke bangunan terdekat        | Koperasi   | Bagian     |
| --------------------------------- | ---------- | ---------- |
| Di atas petak bangunan (&lt;70 m) | 36.985     | 44,36%     |
| &lt; ±260 m                       | 25.699     | 30,82%     |
| &lt; ±530 m                       | 7.555      | 9,06%      |
| &lt; ±1 km                        | 5.745      | 6,89%      |
| &lt; ±2 km                        | 3.587      | 4,30%      |
| &lt; ±5 km                        | 2.817      | 3,38%      |
| **&gt; ±5 km / tak ditemukan**    | **991**    | **1,19%**  |

## Yang tersisa, dan justru lebih kuat

Yang tersisa adalah ekor kecil, dan di situlah temuan sesungguhnya berada. **128 koperasi sekaligus: tidak punya rumah terpetakan dalam 1 km, tidak punya penduduk dalam 5 km menurut peta satelit, dan tidak punya jalan yang bisa dilalui kendaraan dalam 5 km.** Tiga sumber yang sama sekali berbeda menunjuk kelompok yang sama.

Seratus dua puluh delapan koperasi jauh lebih sedikit daripada 52 ribu. Tapi angka 128 itu bertahan diperiksa dari tiga arah, sementara angka 62,6% tidak bertahan diperiksa dari satu arah pun. Itulah sebabnya angka inilah yang kami pakai.

## Kenapa angka lamanya salah

Ada dua sebab yang saling menumpuk, dan keduanya kami temukan saat membangun halaman [Periksa mandiri](../../periksa/), yang menghitung ulang ukuran ini langsung di peramban dan hasilnya tidak cocok dengan tabel yang kami terbitkan.

**Pertama, ada kekeliruan dalam program kami.** Pencarian jarak mengembalikan cincin ke berapa pun ia berhenti, bilangan bulat mana saja dari 0 sampai 38, sedangkan tabel pita hanya menamai enam di antaranya. Koperasi yang bangunan terdekatnya jatuh di cincin yang tidak bernama (1, 3, 5, 6, 7, 9 sampai 14, 16 sampai 37) tidak menemukan pasangannya di tabel, lalu tersapu masuk ke kelompok "tidak ditemukan". Lampiran 05 tidak pernah memakai cara itu dan tidak ikut salah.

**Kedua, peta bangunan yang kami pakai terlalu kosong di pedesaan.** Versi lama memakai jejak bangunan OpenStreetMap saja, sekitar 43,9 juta bangunan. Versi ini memakai gabungan Google, Microsoft dan OpenStreetMap: **137,1 juta bangunan** untuk Indonesia. Bangunan hasil pengenalan citra satelit justru rapat di tempat yang jarang dipetakan sukarelawan, yaitu pedesaan.

Kekeliruan program menyumbang sekitar tiga perempat dari kesalahan, sisanya dari sumber data:

| Versi                                | Di atas petak bangunan | Tanpa bangunan dalam ±5 km |
| ------------------------------------ | ---------------------- | -------------------------- |
| Terbit 13 Agustus (keliru, OSM)      | 23,2%                  | **62,6%**                  |
| Kekeliruan diperbaiki, tetap OSM     | 23,2%                  | 14,88%                     |
| Diperbaiki + peta gabungan (kini)    | **44,36%**             | **1,19%**                  |

## Yang tidak bisa kami katakan

Peta bangunan tetap tidak pernah lengkap, bahkan dengan 137 juta jejak. Bangunan di bawah tajuk pohon dan bangunan kecil non-permanen tetap bisa terlewat. "Tidak ada bangunan dalam X" tetap batas bawah: artinya "tidak ada rumah **terpetakan**", selalu.

Jaraknya juga rentang perkiraan, bukan metrik pasti, sama seperti pita jalan di lampiran 05. Dan peta gabungan ini bukan satu tahun perekaman: Google, Microsoft dan OpenStreetMap punya waktu rekam masing-masing, jadi bacalah sebagai "pernah ada bangunan terpetakan di sini", bukan "hari ini ada bangunan berdiri di sini".
