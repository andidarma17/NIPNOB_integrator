# Checklist pengujian langsung QGIS (wajib sebelum operasional)

Paket ini dibuat di lingkungan tanpa runtime QGIS. Status kode `BETA` sampai kasus berikut selesai diuji pada **QGIS 3.44 LTR (Qt5)** dan **QGIS 4.2.3 (Qt6)**.

1. QGIS Plugins → Install from ZIP; enam tools dapat dibuka tanpa traceback dan dropdown layer/field terisi.
2. Modul 1: dua layer awal, hitung record NIB/NOP, kosong/duplikat, luas nol/negatif/outlier; GeoPackage dan PDF dapat dibuka. Bandingkan hasil dengan data manual.
3. Modul 2: siapkan data uji polygon valid, bow-tie invalid, null geometry, overlapping polygons, closed gap dan void tepi; cocokkan `geom_kosong`,`geom_fixed`,`overlap`,`bid_tambah`,`selisih_luas` dan `persen_selisihL`.
4. Modul 3: lakukan koreksi data awal secara manual, buka *dua layer operator baru*, jalankan; pastikan `manifest_modul3.json` dan `pasangan_kandidat.csv` memiliki sidik-jari. 1 calon >50% dan beberapa irisan kecil boleh L1; 2 calon >50% wajib L2; duplikat, luas, relasi 1:1 diperiksa.
5. Modul 4: jalankan silver-only dan cek status PREVIEW_ONLY; ubah file operator dan pastikan checksum menolak silver lama. Masukkan CSV GOLD historis dengan bukti/status, coba RF dan XGBoost jika tersedia, laporkan hasil validasi hanya bila data independen mencukupi.
6. Modul 5: jalankan tanpa model (baseline); dengan model PREVIEW_ONLY + checkbox promosi tetap tidak boleh menambah L1. Dengan model GOLD teruji dan aktivasi ekspisit, uji calon berskor tinggi dan konflik 1:1.
7. Modul 6: pilih kandidat via tabel, klik BPN di peta, zoom dan seleksi bekerja, label 1/0 wajib isi operator dan bukti, CSV langsung tersimpan, ekspor PDF/ZIP, dan CSV dibaca lagi dalam Modul 4.
8. Simpan keluaran sebagai GeoPackage dan GeoJSON; atribut tidak hilang. Shapefile hanya untuk kompatibilitas lama dan cek keterbatasan nama kolom.
9. CRS: layer geografis EPSG:4326 harus ditolak untuk hitungan m²; CRS berbeda tanpa centang reproyeksi harus ditolak; saat centang reproyeksi hasil diproyeksikan ke CRS BPN.
10. Input 1.000–10.000 poligon: catat waktu, konsumsi memori, dan stabilitas UI; audit hasil dibandingkan dengan analisis QGIS/GEOS independen.

**Kriteria penerimaan:** tidak ada crash, seluruh layer PDF/CSV dapat dibaca, perhitungan atribut/spasial benar, tidak terjadi pemaduan salah pada kasus validasi, dan peningkatan Level 1 berbasis AI punya bukti uji terverifikasi.


## Uji regresi patch v0.9.1 — wajib langsung di QGIS

1. Buka Modul 1 dengan `bpn_tm3.geojson` & `pbb_tm3.geojson`; cek default luas `LUAS` dan `D_LUAS`.
2. Buka dropdown, pastikan seluruh field layer tampil dan pemilihan dapat diganti.
3. Ganti ke layer BPN/PBB lain, cek list di-refresh dan default masuk akal.
4. Coba Mod 2, 3, 4, 5 dan 6; cek field luas di masing-masing dialog.
5. Jalankan Modul 1, bandingkan total record BPN 1830, PBB 2031 pada data awal serta jumlah luas kosong BPN 0 dan PBB 1000.
6. Coba area bertipe Double, Integer dan String numerik dari layer contoh.
7. Uji instalasi dan reload plugin pada QGIS 3.x serta 4.x; status belum tersertifikasi tanpa uji ini.


## Pengujian dropdown versi 0.9.2 (semua modul)

1. Buka BPN `bpn_tm3.geojson` dan PBB `pbb_tm3.geojson` lalu buka tool 1.
2. Pastikan `LUAS` dan `D_LUAS` dipilih otomatis serta pilihan kolom menampilkan SEMUA field atribut.
3. Pilih kolom bertipe string/teks yang namanya tidak baku dan pastikan kolom dapat dipilih. Jika isinya bukan angka, hasil QA harus menandai nilai tidak numerik.
4. Ganti layer ke data lain dengan nama kolom luas bukan `LUAS`/`D_LUAS`: dropdown harus memperlihatkan nama kolom baru dan tidak memilih kolom tidak terkait secara otomatis.
5. Jalankan ulang langkah 2–4 di Tools 2, 3, 4, 5 dan panel Tool 6 (termasuk layer historis tool 4).
6. Perhatikan hasil CSV dan PDF tetap dihitung dari field yang **dipilih** operator.

Semua pengecekan dialog interaktif memerlukan QGIS terpasang; pengujian unit otomatis pada lingkungan pembuat paket memakai mock komponen QGIS/Qt.


## Acceptance test khusus laporan PDF versi 0.9.4

1. Modul 1: jalankan layer bpn_tm3, pbb_tm3, pilih kolom `NIB`, `LUAS`, `D_NOP`, `D_LUAS`. Buka `laporan_modul1.pdf`: **delapan grafik** (1–8) harus lengkap, terdapat ringkasan, metode, dan rekomendasi.
2. Modul 2: buka PDF; verifikasi peta overview BPN dan PBB, peta kondisi invalid/fixed, peta detail gap jika ada, tabel overlap dan gap.
3. Modul 3: masukkan layer hasil koreksi operator, lihat tabel Level 1/2, alasan Level 2, chart overlap dan peta; pastikan output GeoJSON/GPKG tidak berubah terhadap versi 0.9.3 untuk input dan parameter identik.
4. Modul 4: cek metrik TRAIN/VALIDATION/TEST untuk kedua model, confusion matrix, ROC/PR/kalibrasi, panduan ambang, dan rekomendasi. Tanpa GOLD, PDF harus menyatakan tidak bisa menilai testing.
5. Modul 5: laporan memuat jumlah L1/L2, grafik skor apabila model diberikan, peta BPN/PBB, kandidat rekomendasi studio dan status model.
6. Modul 6: tandai setidaknya satu pasangan cocok (dengan bukti) dan satu belum pasti; klik ekspor. PDF memuat grafik dan tabel yang sesuai keputusan. Peta tidak ditampilkan jika sumber geometrinya tidak tersedia.
7. Semua modul: `rekap_csv.zip` tetap dihasilkan, tabel rinci tidak disalin seluruhnya ke PDF, tidak ada file PNG wajib di folder hasil; periksa halaman PDF tidak terpotong / teks bertumpuk di QGIS Windows.
8. Ulangi dengan layer tanpa gap, kolom luas teks, tanpa model AI, 0 kasus overlap, dan 0 keputusan studio: PDF harus tetap dapat dibuat dengan keterangan kosong yang jelas.
9. Ulangi QGIS 3.44 LTR dan QGIS 4.x secara terpisah; jika ada kegagalan Qt API, catat traceback lengkap, versi Qt/Python/QGIS, dan tool yang digunakan.
