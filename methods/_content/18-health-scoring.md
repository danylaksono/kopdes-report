## Pertanyaannya

Apa sebenarnya arti label "tidak sehat" pada indeks kesehatan kementerian? Catatan lama kami menyimpan satu baris: "semua 38 provinsi tidak sehat", dengan dugaan "didorong RAT nol". Lampiran 16 (RAT ternyata 60%) memaksa kami memeriksa ulang.

## Yang kami temukan

Label "tidak sehat ×38" adalah artefak. Kolom `health_score` bernilai **konstan 30 di semua 38 provinsi** — tanpa variasi sama sekali. Anda tidak bisa membandingkan provinsi pada kolom yang konstan; siapa pun yang mengutip "semua provinsi tidak sehat" mengutip angka tempat, bukan pengukuran.

Indeks yang sebenarnya dihitung dashboard adalah `average_health_index`: **50–57, rata-rata 53,2.** Tapi ada fakta yang lebih besar: **hanya 37,6% koperasi yang pernah dinilai (31.354 dari 83.379) — 62,4% tidak pernah dinilai sama sekali.** Cakupannya sangat timpang: DKI Jakarta menilai 79,1% koperasinya; Papua Pegunungan hanya 0,7% (16 dari 2.387). Dan di antara yang dinilai, 91,1% tetap "tidak sehat".

Yang paling erat mengikuti indeks bukanlah kesehatan, melainkan **berapa banyak koperasi yang dinilai** (korelasi 0,85), lalu kepatuhan dan simpanan (korelasi sekitar 0,80). RAT yang ternyata 60% tidak "menyelamatkan" provinsi ke status sehat: indeks didominasi kelengkapan data. Bacaan yang bisa dipertahankan: indeks kesehatan lebih banyak mencerminkan kelengkapan data dan formalitas administrasi daripada penilaian kesehatan yang independen.

## Yang tidak bisa kami katakan

Rumus indeksnya tidak diungkap API, jadi "apa yang mengikuti indeks" adalah korelasi, bukan rubrik. Dan kami tidak tahu mengapa 62% tidak pernah dinilai — terlalu baru, atau tidak punya data keuangan sama sekali. Karena itu kami tidak memublikasikan "semua 38 provinsi tidak sehat"; yang bisa ditulis hanyalah: indeks mencakup 38% koperasi, dan di antara yang tercakup 91% tidak sehat — dengan catatan bahwa skornya didominasi siapa yang melapor, bukan ukuran kesehatan yang berdiri sendiri.
