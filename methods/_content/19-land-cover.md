## Pertanyaannya

Setiap koperasi punya titik koordinat, dan setiap titik koordinat punya satu
nilai dalam peta tutupan lahan. Analisis lain baru menilai penutup lahan untuk
beberapa ribu koperasi yang paling mencurigakan. Laporan ini melakukannya
untuk seluruh 83.379 koperasi, sehingga tabel direktori bisa menunjukkan
kelas penutup lahan satu per satu, bukan sekadar bendera peringkat.

## Dari mana datanya

Dari ESA WorldCover, peta tutupan lahan global beresolusi 10 meter yang
disusun dari citra satelit tahun 2021. Untuk setiap koordinat koperasi kami
mengambil nilai piksel di titik itu, lalu mengelompokkannya ke kelas: hutan,
semak belukar, padang rumput, lahan pertanian, pemukiman, tanah terbuka,
perairan, rawa, dan mangrove. Kami juga memakai peta OpenStreetMap untuk dua
kasus yang lebih spesifik: koperasi di dalam poligon pemakaman dan yang jauh
di dalam poligon lahan pertanian.

## Yang kami temukan

Sebagian besar koordinat koperasi, sekitar 61%, berada pada piksel berkelas
hutan. Sekitar 17,5% pada pemukiman, dan 12,6% pada lahan pertanian.

## Yang tidak dapat kami pastikan

Dua hal. Pertama, kelas ini adalah nilai piksel 10 meter di titik koordinat,
bukan jejak bangunan koperasi. Titik koordinat sebagian besar adalah pusat
desa, dan piksel di sekitar pemukiman sering terklasifikasi sebagai hutan.
"Hutan" di tabel tidak berarti koperasi berdiri di hutan, dan "Pemukiman"
tidak berarti ada bangunan di sana. Kedua, peta ini dari tahun 2021, sementara
koordinat dicatat tahun 2026. Penutup lahan bisa berubah dalam lima tahun.

Untuk kasus spesifik, peta OpenStreetMap lebih tegas: koperasi yang tercatat
di dalam poligon pemakaman ditandai "Pemakaman", dan yang berada 100 meter
atau lebih di dalam poligon lahan pertanian ditandai "Lahan pertanian". Tabel
memberi tahu sumber setiap nilai lewat keterangan (tooltip).
