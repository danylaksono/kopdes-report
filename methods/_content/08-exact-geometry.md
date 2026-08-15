## Pertanyaannya

Lampiran 05 dan 06 mengukur jarak dalam rentang perkiraan. Untuk kalimat tentang desa tertentu, itu tidak cukup. Narasi butuh "jarak ke jalan terdekat 9,7 km", bukan "berada di rentang lebih dari 5 km". Di sini jarak diukur ulang dengan tepat, satu per satu.

## Yang kami temukan

Tiga hal keluar dari pengukuran ini.

**Pertama, <span data-fig="impossible_coords">20</span> koperasi tidak berada di Indonesia.** Ini ditemukan secara tidak sengaja: jarak maksimum ke minimarket keluar 9.349 km, angka yang mustahil untuk desa mana pun di Indonesia. Dari <span data-fig="impossible_coords">20</span> itu, <span data-fig="impossible_coords_signflip">19</span> adalah kesalahan tanda garis lintang: koordinat di selatan khatulistiwa ditulis sebagai utara, sehingga titiknya "terlempar" ke sisi lain planet. Pada potret 9 Agustus, kementerian sudah mengoreksi semuanya. Daftar lengkapnya, dengan koordinat sebelum dan sesudah, ada di `corrected_coordinates_2026-08.csv`.

**Kedua, kelompok tanpa jalan diukur ulang.** Yang tadinya hanya bisa dikatakan "lebih dari 5 km" sekarang punya angka: **median 9,7 km** ke jalan beraspal terdekat, persentil ke-90 sejauh <span data-fig="roadless_p90_km">26,4</span> km, dan yang terjauh <span data-fig="roadless_max_km">185,9</span> km. Sebanyak <span data-fig="roadless_over_25km">587</span> koperasi berjarak lebih dari 25 km. "Tidak ada jalan dalam 5 km" ternyata pernyataan yang terlalu lunak; separuh kelompok ini lebih jauh dari itu.

| Jarak tepat ke jalan beraspal | Koperasi |
| ----------------------------- | -------- |
| 5–10 km                       | <span data-fig="roadless_5_10km">2.467</span>    |
| 10–25 km                      | <span data-fig="roadless_10_25km">1.872</span>    |
| 25–50 km                      | <span data-fig="roadless_25_50km">523</span>      |
| 50–100 km                     | <span data-fig="roadless_50_100km">57</span>       |
| **Lebih dari 100 km**         | **<span data-fig="roadless_over_100km">7</span>**   |

**Ketiga, setiap koperasi kini punya jarak ritel yang pasti.** Jarak median ke minimarket terdekat: 17,3 km.

Pengukuran ini juga mengaudit laporan lama. Jarak jalan pada lampiran 05 akurat (galat median 34 m). Jarak minimarket pada lampiran 06 bias: jaraknya **terlalu besar** sekitar 169 m, artinya 06 meremehkan berapa banyak koperasi yang dekat minimarket. Akan tetapi temuan utama 06, perbandingan dengan lokasi acak, tidak berubah, karena kedua sisi dibandingkan dengan cara yang sama.

| Laporan yang diaudit | Galat median | Akurat dalam satu petak |
| -------------------- | ------------ | ----------------------- |
| 05, jarak jalan      | 34 m         | 92%                     |
| 06, jarak minimarket | +169 m       | 41%                     |

## Yang tidak dapat kami pastikan

Ketelitian punya batas: geometri jalan di OpenStreetMap akurat sekitar 5–15 m, dan jarak di sini sebaiknya dikutip dalam kelipatan 100 m; desimal meter adalah sandiwara. Jarak juga garis lurus, bukan jarak tempuh: 292 km garis lurus di pedalaman Papua bukan perjalanan yang dilakukan siapa pun.
