# Pemeriksaan redesain laporan PDF

## Koreksi jarak dan peta QA (23 Oktober 2026)

- Garis pemisah header kini berada di antara judul dan subjudul dengan jarak yang terbaca pada keenam modul. Legenda grafik proporsi atribut Modul 1 tidak lagi berhimpitan dengan judul grafik kolom kosong berikutnya.
- Peta Modul 2 membedakan kandidat gap (biru, tepi putus-putus) dari geometri invalid/fixed PBB (jingga, arsiran). Lingkaran penunjuk lokasi membantu menemukan poligon kecil; keterangan menyatakan bahwa ukuran lingkaran bukan luas bidang.

## Penyelarasan keenam modul (23 Oktober 2026)

- Halaman pertama Modul 1, 2, 4, 5, dan 6 kini memakai `EditorialPage`: kolom label kiri, kesimpulan dan batasan yang terlihat, tabel bukti ringkas, bar berlabel, serta jejak audit. Modul 3 tetap mengikuti komposisi referensi yang sudah disetujui. Kategori Level, dataset, dan status memakai peran warna berbeda.
- Contoh PDF Modul 1–5 dirender dari data `NIBNOP_HASIL` yang tersedia. Modul 4 memang tidak memiliki GOLD TEST independen, sehingga contoh menyatakan **BELUM DAPAT DINILAI** dan tidak menampilkan angka evaluasi TEST buatan. Karena belum ada hasil Modul 6 yang disediakan, contoh Modul 6 memakai identitas rekaan dan diberi label **DATA SINTETIS** pada setiap halaman.
- Halaman pertama keenam contoh diperiksa pada A4. Isi rinci berikutnya tetap dirender oleh generator yang sama; contoh lengkap ada di `output/pdf/laporan_modul{1..5}_contoh_redesain.pdf` dan `output/pdf/laporan_modul6_contoh_sintetis.pdf` pada workspace ini.

## Iterasi acuan report editorial (23 Oktober 2026)

- Halaman pertama Modul 1, 2, 4, 5, dan 6 kini memakai urutan **Kesimpulan → Batasan interpretasi → Hasil utama/evaluasi → Tindak lanjut → Parameter dan jejak audit**. Modul 3 menambah distribusi kategori, frekuensi alasan Level 2, dan enam contoh kandidat, sesuai struktur contoh pengguna.
- Modul 3 menggunakan bidang BPN keluaran sebagai penyebut kategori. Contoh data memiliki 1.830 bidang input dan 1.831 record keluaran; kedua angka ditulis terpisah pada halaman pertama. Level 2 dengan calon beririsan dipisahkan dari bidang tanpa calon.
- Palet aktif kembali ke Indigo–Safron: struktur `#1E2250`, BPN `#3A3F9E`, PBB `#A36A00`, Level 1 `#0B7285`, Level 2 `#8F7A9E`. Warna dilengkapi simbol/arsiran dan teks.
- Render QGIS 3.40.5 berhasil untuk keenam modul (Modul 1–3 pada data tersedia; Modul 4–6 pada fixture sintetis). Halaman pertama seluruh modul diperiksa secara visual. Sebelas uji `unittest` dan dua pemeriksaan kontras palet lulus.
- Contoh Modul 3 memakai nama layer, CRS, ambang, dan sha256 input sebenarnya. Operator ditulis “tidak tercatat” karena tidak tersedia pada fixture; tidak dibuat-buat.

Acuan: `TODO_REDESIGN.md`. Laporan yang ditinjau adalah hasil render QGIS 3.40.5/macOS dari `NIBNOP_HASIL`, ditambah kasus tanpa record dan ID 18 digit. Perubahan ini adalah implementasi laporan yang dapat dipakai; status di bawah membedakan yang sudah diuji dari yang masih perlu diuji pada lingkungan lain.

## Sudah diterapkan dan diperiksa

- Semua modul memakai token warna, Source Sans 3 terkemas, running head, teks berbasis `QFontMetrics`, serta callout **Catatan/Peringatan** yang sama. Renderer PDF lama di `storage.py` dihapus.
- Modul 1: temuan awal berbasis persentase record, kolom kosong nonnol digabung dan diurutkan, histogram BPN/PBB memakai sumbu sama, serta plot luas tertulis vs geometri. Contoh turun menjadi **4 halaman**.
- Modul 3: alasan Level 2 dibaca sebagai frasa manusiawi; ambang overlap dan kesamaan luas pada grafik berasal dari parameter operator; peta PBB membedakan tanpa pasangan, Level 2, dan Level 1. Contoh turun menjadi **6 halaman** setelah penghapusan penafian berulang.
- Peta: geometri dipotong pada bingkai, lubang poligon dipertahankan, kategori nol tidak ada di legenda, dan CRS, arah utara, koordinat ekstrem, serta skala grafis dicantumkan.
- Modul 4 tanpa GOLD test menampilkan **BELUM DAPAT DINILAI** pada halaman pertama. TRAIN tetap diberi label diagnostik. Referensi PR dan garis diagonal kalibrasi tampil bila data TEST tersedia.
- Modul 5 mencatat gerbang promosi untuk tiap kandidat ke `skor_kandidat.csv` (model, skor, ID unik, overlap, deviasi, margin, pesaing, dan ketersediaan). Tabel PDF memperlihatkan ringkasan gerbang kandidat teratas.
- Modul 6 memuat semua keputusan dengan operator, waktu, sumber bukti, dan ID lengkap. Uji PDF dengan ID 18 digit menghasilkan dua kemunculan ID utuh pada ekstraksi teks.
- Kasus kosong Modul 1 dan 3 menghasilkan satu halaman ringkasan tanpa grafik nol. Tiga belas uji logika dan kontras lulus. Uji sintetis 100 ribu record Modul 1 selesai; nama kolom panjang tetap utuh pada ekstraksi PDF.
- `palette_review.png` memperlihatkan warna normal, simulasi protanopia, deuteranopia, tritanopia, dan abu-abu. BPN dan PBB tetap berbeda luminans; Level 2 dan tanpa pasangan dibantu arsiran/label. Kontras terukur: teks isi/putih 14,9:1; teks sekunder/putih 8,15:1; teks Level 2/isian 7,36:1; peringatan 7,14:1; putih/navy tabel 10,7:1. Simulasi memakai matriks prahitung Machado severity 1 dan bersifat perkiraan layar ([metode](https://colour.readthedocs.io/en/develop/_modules/colour/blindness/machado2009.html), [riset](https://pubmed.ncbi.nlm.nih.gov/19834201/)).

## Batas verifikasi saat ini

- Footer sudah memuat nomor halaman, waktu WIB, versi, dan hash input bila tersedia. **Total halaman X/N belum dicetak** karena `QPdfWriter` menggambar halaman secara berurutan; ini membutuhkan pass render kedua atau pascaproses PDF yang tidak boleh menjadi dependensi baru plugin tanpa pengujian lintas QGIS.
- Peta mengasumsikan CRS proyeksi meter untuk skala grafis. CRS geografis perlu penanganan skala geodesik tersendiri.
- Simulasi layar sudah dibuat; **uji cetak fisik** dan pembacaan oleh pengguna dengan gangguan persepsi warna belum dijalankan. Simulasi tidak menggantikan uji pengguna.
- QGIS 4/Qt6, Windows, Linux, dan beban 100 ribu geometri nyata belum tersedia untuk uji langsung. Kode enum Qt5/Qt6 disiapkan, tetapi belum dianggap terverifikasi.
- Inset peta ekstrem masih terbuka; istilah ringkas sudah tercantum pada halaman ringkasan modul utama. Detail tabel kasus Modul 2 mempertahankan halaman lanjutan agar ID dan bukti tidak dipotong.
