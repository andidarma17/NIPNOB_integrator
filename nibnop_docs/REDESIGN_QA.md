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
- Kasus kosong Modul 1 dan 3 menghasilkan satu halaman ringkasan tanpa grafik nol. Tiga belas uji logika dan kontras lulus. Uji sintetis 100 ribu record Modul 1 selesai; nama kolom panjang tetap utuh pada ekstraksi PDF.
- `palette_review.png` memperlihatkan warna normal, simulasi protanopia, deuteranopia, tritanopia, dan abu-abu. BPN dan PBB tetap berbeda luminans; Level 2 dan tanpa pasangan dibantu arsiran/label. Kontras terukur: teks isi/putih 14,9:1; teks sekunder/putih 8,15:1; teks Level 2/isian 7,36:1; peringatan 7,14:1; putih/navy tabel 10,7:1. Simulasi memakai matriks prahitung Machado severity 1 dan bersifat perkiraan layar ([metode](https://colour.readthedocs.io/en/develop/_modules/colour/blindness/machado2009.html), [riset](https://pubmed.ncbi.nlm.nih.gov/19834201/)).

## Batas verifikasi saat ini

- Footer sudah memuat nomor halaman, waktu WIB, versi, dan hash input bila tersedia. **Total halaman X/N belum dicetak** karena `QPdfWriter` menggambar halaman secara berurutan; ini membutuhkan pass render kedua atau pascaproses PDF yang tidak boleh menjadi dependensi baru plugin tanpa pengujian lintas QGIS.
- Peta mengasumsikan CRS proyeksi meter untuk skala grafis. CRS geografis perlu penanganan skala geodesik tersendiri.
- Simulasi layar sudah dibuat; **uji cetak fisik** dan pembacaan oleh pengguna dengan gangguan persepsi warna belum dijalankan. Simulasi tidak menggantikan uji pengguna.
- QGIS 4/Qt6, Windows, Linux, dan beban 100 ribu geometri nyata belum tersedia untuk uji langsung. Kode enum Qt5/Qt6 disiapkan, tetapi belum dianggap terverifikasi.
- Inset peta ekstrem masih terbuka; istilah ringkas sudah tercantum pada halaman ringkasan modul utama. Detail tabel kasus Modul 2 mempertahankan halaman lanjutan agar ID dan bukti tidak dipotong.
