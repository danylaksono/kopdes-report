## Pertanyaannya

Salah satu tuduhan yang paling sering terdengar adalah koperasi dibangun "di lereng gunung". Itu bisa diukur, dan pertanyaannya sederhana: tanah di bawah tiap koperasi setinggi apa, dan senaik-turun apa?

## Datanya

Kami memakai model ketinggian global **Copernicus GLO-30**, citra ketinggian bumi beresolusi 30 meter, dan membaca nilainya tepat di titik tiap koperasi. Petanya tidak diunduh; hanya beberapa piksel di sekitar tiap titik yang dibaca langsung dari penyimpanan awan.

Untuk tiap titik kami mengambil dua angka: **ketinggian** di titik itu, dan **selisih tinggi tertinggi dengan terendah** dalam radius sekitar 200 meter. Angka kedua itulah ukuran "naik-turun"-nya.

Lampiran 04 sudah melakukan ini lebih dulu, tetapi hanya untuk 2.500 koperasi paling terpencil. Artinya kalimat soal medan hanya bisa berbunyi "dari 2.500 yang paling terpencil", bukan angka nasional. Di sini pengukurannya diperluas ke <span data-fig="coops_total">83.379</span> koperasi, dan seluruhnya berhasil terukur.

## Yang kami temukan

Sebagian besar program ini berdiri di tanah datar dan rendah, sebagaimana mestinya. Median ketinggiannya <span data-fig="median_elevation_m">67</span> meter, dan hampir 45% koperasi berada di bawah 50 meter.

| Ketinggian            | Koperasi | Bagian |
| --------------------- | -------- | ------ |
| 0–50 m                | 37.447   | 44,9%  |
| 50–200 m              | 19.236   | 23,1%  |
| 200–500 m             | 11.193   | 13,4%  |
| 500–1.000 m           | 8.908    | 10,7%  |
| 1.000–2.000 m         | 5.090    | 6,1%   |
| **di atas 2.000 m**   | **<span data-fig="above_2000m_coops">1.505</span>**    | 1,8%   |

Tetapi ekornya nyata: **<span data-fig="steep_coops">12.325</span> koperasi (<span data-fig="steep_pct">14,8%</span>) berdiri di tanah yang naik atau turun lebih dari 60 meter dalam jarak sekitar 200 meter.**

Dan seperti hampir semua temuan ekor lainnya, ini cerita Indonesia timur, kali ini dari sumber yang sama sekali tidak tahu apa-apa soal SIMKOPDES.

| Pulau         | Median ketinggian | Naik-turun tajam |
| ------------- | ----------------- | ---------------- |
| **Papua**     | **533 m**         | **<span data-fig="papua_steep_pct">44,7%</span>**        |
| Nusa Tenggara | 260 m             | 27,9%            |
| Maluku        | 79 m              | 27,4%            |
| Sulawesi      | 66 m              | 23,3%            |
| Sumatra       | 42 m              | 10,4%            |
| Jawa          | 91 m              | <span data-fig="java_steep_pct">6,1%</span>             |
| Kalimantan    | 13 m              | 4,7%             |

Angka nasional ini juga memperbaiki cara membaca lampiran 04. Dari 2.500 koperasi paling terpencil, <span data-fig="shortlist_steep">1.008</span> berada di tanah yang naik-turun tajam, yaitu 40%. Itu **2,7 kali lebih sering** daripada rata-rata nasional yang 14,8%. Wajar, karena daftar 2.500 itu memang disusun berdasarkan keterpencilan, dan di Indonesia keterpencilan dan medan berat berjalan beriringan. Artinya angka 40% itu tidak pernah boleh dibaca sebagai gambaran seluruh program.

## Yang tidak dapat kami pastikan

**Ini bukan kemiringan lereng.** Yang kami hitung adalah selisih tinggi tertinggi dan terendah di sekitar titik, jadi angkanya tidak punya arah dan tidak bisa membedakan tanjakan yang rata dari tanah datar yang tepinya jurang. Sebuah titik di kaki bukit mendapat angka yang sama dengan titik di lerengnya. Karena itu kami menulis "naik-turun lebih dari 60 meter dalam 200 meter", bukan "lereng 30 derajat".

**Tanah terjal bukan berarti sulit dijangkau.** Perbukitan berteras di Jawa curam sekaligus mudah dicapai. Pertanyaan keterjangkauan dijawab lampiran 05, bukan di sini.

**Resolusi 30 meter menghaluskan medan yang sebenarnya**, dan ketinggian diambil dari satu piksel saja. Koperasi yang koordinatnya meleset beberapa puluh meter bisa terbaca di sisi yang salah dari sebuah tebing. Angka per pulau menyerap kesalahan ini; ketinggian satu koperasi jangan dikutip sampai satuan meter.

**Dan yang paling penting**, sama seperti seluruh bab ini: yang terukur adalah tanah di bawah **koordinat yang tercatat**, bukan tanah di bawah bangunannya.
