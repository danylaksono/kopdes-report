## Pertanyaannya

Dua tuduhan yang tidak bisa dilihat analisis lain: "dibangun di tanah kuburan" dan "dibangun di tengah sawah". Yang pertama tidak memiliki kelas di peta satelit, jadi kami pakai peta buatan sukarelawan (OpenStreetMap) yang memang memetakan kuburan. Yang kedua ditangani dengan cara baru, tanpa ukuran keterpencilan, jadi koperasi di sawah yang dekat desa tetap terlihat.

## Caranya dan pembandingnya

Kami menandai semua <span data-fig="coops_total">83.379</span> titik koperasi, lalu menghitung apakah titik itu jatuh di dalam poligon sawah atau poligon kuburan. Angka mentah tidak berarti tanpa pembanding: kami menjalankan cara yang sama persis pada titik "pusat desa" yang dipetakan sukarelawan OpenStreetMap sendiri, posisi yang oleh para pemeta (tanpa kepentingan dalam argumen ini) dianggap tempat yang wajar untuk institusi desa.

## Yang kami temukan

Tuduhan sawah bertahan. **Koperasi jatuh di dalam poligon sawah 2,4 kali lebih sering daripada pusat desa biasa** (2,65% berbanding <span data-fig="village_node_farmland_pct">1,10%</span>). Lalu kami saring lebih ketat untuk menyingkirkan artefak: hanya yang berada 100 meter atau lebih dari tepi sawah, dengan penduduk di sekitarnya, dan bukan poligon gambar kasar yang merangkum seluruh dataran. Tersisa <span data-fig="farmland_candidates">538</span> kandidat, dan **448 di antaranya dikonfirmasi oleh peta satelit kedua yang berdiri sendiri (ESA WorldCover)** sebagai lahan pertanian.

| Di dalam…       | KDMP              | Titik pusat desa |
| --------------- | ----------------- | ---------------- |
| Poligon sawah   | **2,65%** (<span data-fig="in_farmland_coops">2.209</span>) | <span data-fig="village_node_farmland_pct">1,10%</span> (832)      |
| Poligon kuburan | 0,026% (22)       | <span data-fig="village_node_cemetery_pct">0,022%</span> (17)      |

Dua sumber independen sepakat: 448 koperasi tercatat di lahan pertanian, jauh dari tepi, di desa yang berpenduduk. Dua ratus sembilan di antaranya membawa status lahan resmi "Terverifikasi".

| Tahap penyaringan                  | Koperasi |
| ---------------------------------- | -------- |
| Di dalam poligon sawah             | <span data-fig="in_farmland_coops">2.209</span>    |
| ≥100 m dari tepi, ada penduduk     | 1.027    |
| Bukan poligon kasar seluas dataran | <span data-fig="farmland_candidates">538</span>      |
| Dikonfirmasi peta satelit kedua    | **448**  |

Tuduhan kuburan tidak bertahan. Hanya 22 koperasi yang jatuh di dalam kuburan terpetakan, laju yang tidak bisa dibedakan dari pusat desa biasa. Sebagian besar adalah efek tepi (kantor kelurahan di sebelah tembok kuburan), dan 16 dari 22 berada di kota besar, tempat kuburan umum memang sebesar blok kota.

## Yang tidak dapat kami pastikan

Ini poin yang paling penting. **Titik di sawah belum tentu bangunan di sawah.** Jika koordinat SIMKOPDES sebenarnya titik pusat desa, maka desa yang sebagian besar sawah otomatis menghasilkan titik di tengah sawah, dan itu akan lebih sering "jatuh" di sawah daripada pusat desa biasa, persis seperti yang kami ukur. Uji jalan condong ke arah yang mencemaskan: kandidat ini lebih jarang dekat jalan daripada koperasi sebanding, bukan lebih sering.

Karena itu kalimat yang bisa didukung adalah "**tercatat di** lokasi di dalam sawah", bukan "dibangun di sawah". Jika kementerian menjawab bahwa koordinatnya salah, itu cerita yang berbeda, tetapi tidak lebih kecil: itu berarti registrinya tidak tahu di mana koperasinya berada.
