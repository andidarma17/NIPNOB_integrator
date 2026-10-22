# Pemeriksaan redesain laporan PDF

Acuan: `TODO_REDESIGN.md`. Laporan yang ditinjau adalah hasil render QGIS 3.40.5/macOS dari `NIBNOP_HASIL`, ditambah kasus tanpa record dan ID 18 digit. Perubahan ini adalah implementasi laporan yang dapat dipakai; status di bawah membedakan yang sudah diuji dari yang masih perlu diuji pada lingkungan lain.

## Sudah diterapkan dan diperiksa

- Semua modul memakai token warna, Source Sans 3 terkemas, running head, teks berbasis `QFontMetrics`, serta callout **Catatan/Peringatan** yang sama. Renderer PDF lama di `storage.py` dihapus.
- Modul 1: temuan awal berbasis persentase record, kolom kosong nonnol digabung dan diurutkan, histogram BPN/PBB memakai sumbu sama, serta plot luas tertulis vs geometri. Contoh turun menjadi **4 halaman**.
- Modul 3: alasan Level 2 dibaca sebagai frasa manusiawi; ambang overlap dan kesamaan luas pada grafik berasal dari parameter operator; peta PBB membedakan tanpa pasangan, Level 2, dan Level 1. Contoh turun menjadi **6 halaman** setelah penghapusan penafian berulang.
- Peta: geometri dipotong pada bingkai, lubang poligon dipertahankan, kategori nol tidak ada di legenda, dan CRS, arah utara, koordinat ekstrem, serta skala grafis dicantumkan.
- Modul 4 tanpa GOLD test menampilkan **BELUM DAPAT DINILAI** pada halaman pertama. TRAIN tetap diberi label diagnostik. Referensi PR dan garis diagonal kalibrasi tampil bila data TEST tersedia.
- Modul 5 mencatat gerbang promosi untuk tiap kandidat ke `skor_kandidat.csv` (model, skor, ID unik, overlap, deviasi, margin, pesaing, dan ketersediaan). Tabel PDF memperlihatkan ringkasan gerbang kandidat teratas.
- Modul 6 memuat semua keputusan dengan operator, waktu, sumber bukti, dan ID lengkap. Uji PDF dengan ID 18 digit menghasilkan dua kemunculan ID utuh pada ekstraksi teks.
- Kasus kosong Modul 1 dan 3 menghasilkan satu halaman ringkasan tanpa grafik nol. Sebelas uji logika yang tersedia lulus.

## Batas verifikasi saat ini

- Footer sudah memuat nomor halaman, waktu WIB, versi, dan hash input bila tersedia. **Total halaman X/N belum dicetak** karena `QPdfWriter` menggambar halaman secara berurutan; ini membutuhkan pass render kedua atau pascaproses PDF yang tidak boleh menjadi dependensi baru plugin tanpa pengujian lintas QGIS.
- Peta mengasumsikan CRS proyeksi meter untuk skala grafis. CRS geografis perlu penanganan skala geodesik tersendiri.
- Simulasi deuteranopia, protanopia, dan tritanopia serta uji cetak fisik belum dijalankan. Palet memisahkan BPN/PBB terutama lewat luminans dan memakai bentuk/teks selain warna.
- QGIS 4/Qt6, Windows, Linux, dan beban 100 ribu record belum tersedia untuk uji langsung. Kode enum Qt5/Qt6 disiapkan, tetapi belum dianggap terverifikasi.
- Inset peta ekstrem dan glosarium lampiran masih terbuka. Detail tabel kasus Modul 2 mempertahankan halaman lanjutan agar ID dan bukti tidak dipotong.
