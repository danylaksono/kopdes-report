## Pertanyaannya

Apakah koperasi dibangun di atas minimarket yang sudah ada? Ini bagian dari tuduhan bahwa program "mengkanibal" ritel yang ada.

## Datanya: dua kelemahan yang harus diakui lebih dulu

Sumbernya dua kali tidak sempurna, dan kami mengatakannya lebih dulu. Pertama, data "minimarket" sebenarnya campuran: 28% di antaranya supermarket dan department store, bukan minimarket yang bersaing dengan koperasi desa; kami pisahkan dulu. Kedua, peta ini sangat tidak lengkap di pedesaan dan berat di kota: dari gerai Indomaret resmi, hanya sekitar 14% yang terpetakan; Alfamart sekitar 11%.

Artinya semua angka "seberapa dekat" di sini adalah **batas bawah**: kenyataannya pasti lebih besar. Karena itu kami menulis "setidaknya", bukan "hanya".

## Yang kami temukan

Setidaknya 2,5% koperasi (2.068) berada dalam sekitar 500 m dari minimarket yang terpetakan, dan setidaknya 19,8% dalam 5 km.

| Dalam jarak | Koperasi (minimal) | Bagian (minimal) |
| ----------- | ------------------ | ---------------- |
| ±500 m      | 2.068              | 2,5%             |
| ±1 km       | 4.150              | 5,0%             |
| ±2 km       | 7.425              | 8,9%             |
| ±5 km       | 16.505             | 19,8%            |

Arah sebaliknya lebih menarik. 78,3% minimarket yang terpetakan punya koperasi dalam 1 km. Tapi ini saja belum membuktikan apa-apa: koperasi ada satu per desa dan menjangkau 95% penduduk, jadi titik mana pun yang berpenduduk hampir pasti punya koperasi di dekatnya.

Untuk menguji, kami membandingkan dengan lokasi acak yang "masuk akal": di jalan utama di daerah ramai, tempat ritel memang biasa berdiri.

Ada satu jebakan di langkah ini. Menaruh titik acak "di daerah berpenduduk" saja tidak cukup, karena minimarket tidak berdiri di sembarang daerah berpenduduk: mereka berdiri di yang paling ramai. Diukur, petak minimarket berisi median <span data-fig="mm_median_pop">3.786</span> orang, sedangkan titik acak yang hanya dituntut "di jalan dan ada penduduknya" jatuh di median <span data-fig="road_null_median_pop">2.374</span> orang. Karena koperasi lebih rapat di tempat yang ramai, selisih kepadatan itu sendiri sudah menghasilkan "kedekatan" yang bukan kedekatan.

Karena itu kepadatannya kami samakan: titik acak diambil sehingga sebaran jumlah penduduknya sama persis dengan sebaran di petak minimarket. Hasilnya: **minimarket sekitar <span data-fig="minimarket_excess_pp">6,7</span> poin persentase lebih mungkin punya koperasi dalam 500 m daripada lokasi acak yang sama ramainya**, dan kelebihannya menyusut cepat mengikuti jarak, praktis habis pada 5 km.

| Dalam  | Minimarket | Acak, sama ramai | Kelebihan     | Pembanding longgar |
| ------ | ---------- | ---------------- | ------------- | ------------------ |
| ±500 m | 43,8%      | 37,1%            | **+<span data-fig="minimarket_excess_pp">6,7</span> poin** | +<span data-fig="minimarket_excess_road_pp">9,6</span> poin       |
| ±1 km  | 78,3%      | 74,6%            | +<span data-fig="minimarket_excess_1km_pp">3,7</span> poin     | +7,5 poin       |
| ±2 km  | 95,7%      | 94,2%            | +<span data-fig="minimarket_excess_2km_pp">1,5</span> poin     | +2,8 poin       |
| ±5 km  | 99,6%      | 99,4%            | +<span data-fig="minimarket_excess_5km_pp">0,2</span> poin     | +0,2 poin       |

Titik acak itu diundi, jadi angkanya bergeser sedikit tiap pengundian. Angka ±500 m dan ±1 km di atas adalah rata-rata 40 kali undian; untuk ±500 m rentang 95%-nya <span data-fig="minimarket_excess_lo">5,7</span> sampai <span data-fig="minimarket_excess_hi">7,7</span> poin. Dua baris terbawah berasal dari satu undian saja.

Cara kerja ini setara dengan uji **kasus-kontrol** yang lazim dipakai di epidemiologi: minimarket berperan sebagai "kasus", titik acak sebagai "kontrol", dan keramaian disamakan lebih dulu supaya tidak ikut terhitung. Nama baku tiap langkahnya, beserta rujukannya, kami catat di laporan teknisnya.

## Yang tidak dapat kami pastikan

Kedekatan bukan persaingan. Ini membuktikan koperasi dan minimarket sering berdekatan; itu syarat untuk bersaing, bukan bukti persaingan itu sendiri.

Yang benar-benar tergeser koperasi desa biasanya warung atau toko kelontong, dan data publik nyaris tidak memetakannya (hanya 858 di seluruh Indonesia, padahal jumlahnya jutaan). Jadi tuduhan kanibalisasi, dalam arti perdagangan, sebagian besar tidak bisa diuji dengan data ini. Kami hanya mengukur satu irisan yang terlihat: ritel modern bermerek.
