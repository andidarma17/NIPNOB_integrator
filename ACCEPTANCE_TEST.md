# Checklist pengujian langsung QGIS (wajib sebelum operasional)

Paket ini dibuat di lingkungan tanpa runtime QGIS. Status kode `BETA` sampai kasus berikut selesai diuji pada **QGIS 3.44 LTR (Qt5)** dan **QGIS 4.2.3 (Qt6)**.

1. QGIS Plugins → Install from ZIP; enam tools dapat dibuka tanpa traceback dan dropdown layer/field terisi.
2. Modul 1: dua layer awal, hitung record NIB/NOP, kosong/duplikat, luas nol/negatif/outlier; GeoPackage dan PDF dapat dibuka. Bandingkan hasil dengan data manual.
3. Modul 2: siapkan data uji polygon valid, bow-tie invalid, null geometry, overlapping polygons, closed gap dan void tepi; cocokkan `geom_kosong`,`geom_fixed`,`overlap`,`bid_tambah`,`selisih_luas` dan `persen_selisihL`.
4. Modul 3: lakukan koreksi data awal secara manual, buka *dua layer operator baru*, jalankan; pastikan `manifest_modul3.json` dan `pasangan_kandidat.csv` memiliki sidik-jari. 1 calon >50% dan beberapa irisan kecil boleh L1; 2 calon >50% wajib L2; duplikat, luas, relasi 1:1 diperiksa.
5. Modul 4: jalankan silver-only dan cek status PREVIEW_ONLY; ubah file operator dan pastikan checksum menolak silver lama. Masukkan CSV GOLD historis dengan bukti/status, coba RF dan XGBoost jika tersedia, laporkan hasil validasi hanya bila data independen mencukupi.
6. Modul 5 v0.9.8: model + metadata wajib. Jalankan Full AI tanpa hasil Modul 3, lalu Hybrid dengan ZIP rekap Modul 3. Dengan model PREVIEW_ONLY, `05_usulan_ai` tetap terisi tetapi tidak boleh menambah Level 1 otomatis. Dengan model GOLD teruji dan izin eksplisit, uji skor/margin, identitas unik dan konflik 1:1.
7. Modul 6: pilih kandidat via tabel, klik BPN di peta, zoom dan seleksi bekerja, label 1/0 wajib isi operator dan bukti, CSV langsung tersimpan, ekspor PDF/ZIP, dan CSV dibaca lagi dalam Modul 4.
8. Simpan keluaran sebagai GeoPackage dan GeoJSON; atribut tidak hilang. Shapefile hanya untuk kompatibilitas lama dan cek keterbatasan nama kolom.
9. CRS: layer geografis EPSG:4326 harus ditolak untuk hitungan m²; CRS berbeda tanpa centang reproyeksi harus ditolak; saat centang reproyeksi hasil diproyeksikan ke CRS BPN.
10. Input 1.000–10.000 poligon: catat waktu, konsumsi memori, dan stabilitas UI; audit hasil dibandingkan dengan analisis QGIS/GEOS independen.

**Kriteria penerimaan:** tidak ada crash, seluruh layer PDF/CSV dapat dibaca, perhitungan atribut/spasial benar, tidak terjadi pemaduan salah pada kasus validasi, dan peningkatan Level 1 berbasis AI punya bukti uji terverifikasi.

## Uji khusus v0.9.8 (WAJIB sebelum peluncuran)

1. **Modul 4 SILVER Only:** pilih ZIP Modul 3 tanpa GOLD. Pastikan training menghasilkan `.joblib`, metadata `training_mode=SILVER_ONLY`, `n_gold=0`, status `PREVIEW_ONLY` dan PDF tidak mengklaim ada testing independen.
2. **Modul 4 GOLD Only:** pilih GOLD terverifikasi tanpa SILVER. Pastikan `n_silver=0`, pembagian GOLD spasial, dan metrik validasi/testing jika jumlah grup mencukupi.
3. **Modul 4 SILVER + GOLD:** pilih kedua sumber dan cek metadata `training_mode=SILVER_GOLD`, bobot efektif SILVER serta ketiadaan kebocoran GOLD holdout dari SILVER dengan NIB/NOP atau tile yang sama.
4. **Input gagal:** pilih SILVER dari BPN/PBB versi berbeda; training harus berhenti dengan pesan fingerprint tidak sesuai. Coba GOLD yang semuanya gagal dipetakan; proses harus berhenti dan melaporkan alasan.
5. **Modul 5 Full AI:** tanpa input Modul 3, pilih model GOLD Only dan skor 0,90, margin 0,15; pastikan seluruh kandidat diberi skor, `05_usulan_ai` dapat dibuka, dan `01_padanan_level1` tidak memuat pasangan aturan.
6. **Modul 5 Hybrid:** masukkan ZIP Modul 3 dari layer identik; tanpa izin Level 1 AI, jumlah/pasangan aturan sama persis dengan Modul 3. Tidak boleh ada perhitungan ulang hasil rule.
7. **Geometri berbeda:** ubah sedikit saja geometri/atribut BPN/PBB lalu masukkan ZIP Modul 3 lama; Hybrid wajib menolak karena fingerprint berbeda.
8. **Konflik:** siapkan AI yang menyarankan NOP yang sudah digunakan pasangan Modul 3; jangan gabungkan otomatis. Periksa `06_konflik_ai_rule` dan CSV konflik.
9. **AI tanpa gerbang aturan:** buat contoh pasangan dengan deviasi luas >50%, overlap <50%, tetapi memiliki skor model tinggi. Modul 5 tidak boleh menolaknya semata-mata karena dua kondisi itu; tetap wajib lolos skor, margin, NIB/NOP unik, dan 1:1.
10. **SILVER Only prediksi:** aktifkan checkbox promosi dengan model PREVIEW_ONLY; `05_usulan_ai` terisi bila ada calon layak, tetapi Level 1 otomatis harus tetap 0 pada Full AI.
11. **Ambang GOLD:** model teruji pada skor 0,90 + opsi promosi aktif + skor Modul 5 0,80 harus ditolak dengan pesan alasan yang jelas.
12. **Data besar dan output kosong:** uji 10.000+ bidang, tidak ada kandidat AI, tidak ada Level 1, dan PBB titik. Periksa 01–06, PDF, ZIP, memori, dan jumlah record. Ulangi pada QGIS 3.x dan QGIS 4.x.

**Batas pengujian otomatis:** 48 pengujian Python lulus (6 dilewati karena PyQGIS tidak tersedia). Itu belum menggantikan seluruh uji GUI di atas.


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


## Acceptance test Modul 3.1 (PBB titik) dan validasi nama versi 0.9.5

1. Buat layer PBB titik (mis. *Centroids* dari PBB poligon, lalu geser sebagian titik ke luar bidang 1–4 m dan beberapa > 5 m). Modul 1 dan 2 harus berjalan tanpa galat; Modul 2 menyimpan `pbb_kualitas_spasial` sebagai titik.
2. Modul 3 dengan PBB titik harus menolak dan mengarahkan ke Modul 3.1; Modul 3.1 dengan PBB poligon juga menolak. Modul 3.1 dengan PBB titik tanpa kolom nama: Level 1 hanya untuk titik di dalam bidang dengan satu titik per bidang; `kekuatan = SEDANG`; titik di luar bidang ≤ 5 m beralasan `TITIK_DI_LUAR_BIDANG`, > 5 m `TITIK_DI_LUAR_SEMUA_BIDANG`; bidang tanpa titik `TIDAK_ADA_TITIK`. `03_pbb_level2` bertipe titik.
3. Ulangi Modul 3.1 dengan kolom nama (mis. `NAMA` dan `NM_WP`): pasangan nama sama → `KUAT`; nama berbeda → `LEMAH` dan tetap Level 1. Centang "Nama TIDAK COCOK menurunkan pasangan ke Level 2": pasangan itu pindah ke Level 2 dengan `NAMA_TIDAK_COCOK`.
4. Dua titik dalam satu bidang dengan satu nama cocok → keduanya Level 2 `MULTI_NOP`, kolom `calon_nama` berisi NOP bernama cocok.
5. Pilih kolom nama hanya di salah satu layer → dialog menolak dengan pesan jelas.
6. Modul 3 (poligon) dengan kolom nama `(tidak digunakan)`: jumlah Level 1/2 identik dengan v0.9.4 untuk input dan parameter sama.
7. Modul 4 pada data titik lalu Modul 5 pada data poligon dengan model tersebut → ditolak (mode geometri berbeda).
8. Modul 6 dengan PBB titik: tabel menampilkan "Di dalam bidang" / "Di luar (x m)" dan status nama; memilih baris menyorot bidang BPN dan titik PBB.
9. Hasil Modul 3.1 tersimpan di `modul_3_1/` dengan `laporan_modul3_1.pdf` dan `manifest_modul3_1.json`; menu QGIS menampilkan entri "3.1" di antara Modul 3 dan 4.

## Uji khusus v0.9.9 — Processing Toolbox (WAJIB sebelum peluncuran)

1. **Registrasi:** Processing Toolbox menampilkan grup *NIB–NOP Integrator* dengan 7 algoritma; plugin dapat di-unload dan di-load ulang tanpa duplikasi provider. Jalankan `python -m unittest nibnop_integrator.tests.test_processing -v` di Python QGIS (PyQGIS diperlukan).
2. **Klik ganda Modul 4 dan 5 di Toolbox:** jendela yang muncul sama dengan menu Vektor, termasuk dropdown *Sumber pelatihan* dan *Mode prediksi*. Bila dialog tidak tertanam benar di Toolbox pada versi QGIS Anda, laporkan versi QGIS-nya; menu Vektor tetap berfungsi.
3. **Batch / Modeler Modul 4:** jalankan masing-masing mode (GOLD Only, SILVER Only, SILVER + GOLD) dengan data yang sama seperti uji v0.9.8 nomor 1–3; `metadata_model.json` harus memuat `training_mode` yang benar dan hasilnya sama dengan jalur menu.
4. **Batch / Modeler Modul 5:** jalankan Full AI dan Hybrid (dengan `rekap_csv.zip` Modul 3). Bandingkan `01_padanan_level1`, `05_usulan_ai`, `06_konflik_ai_rule` dan `rekap_csv.zip` dengan jalur menu; harus identik. Hybrid tanpa rekap Modul 3 harus gagal dengan pesan yang jelas.
5. **`qgis_process`:** `qgis_process run nib_nop_integrator:modul_5_inference_ai -- ...` berjalan tanpa jendela dan menulis ke `OUTPUT_FOLDER`.
6. **Log:** catatan Modul 4/5 (jumlah GOLD diterima/ditolak, mode, jumlah usulan AI) muncul di panel log Processing.
7. **Layer raster terbuka di proyek:** dropdown layer di dialog tidak menampilkan raster dan tidak ada traceback.

## Uji khusus v0.10.0 — formulir dan keluaran (WAJIB sebelum peluncuran)

1. **Formulir:** Vector → NIB–NOP Integrator → tiap Modul 1–5/3.1 membuka formulir Processing dengan label di atas isian; sama dengan klik ganda di Toolbox. Pada Modul 1, kolom NIB/LUAS/D_NOP/D_LUAS terpilih otomatis bila ada.
2. **Keluaran terpisah (Modul 3):** isi tiap tujuan berbeda (`.gpkg`, `.geojson`, file sementara) dan satu *Skip Output*; hanya yang tidak dilewati tertulis dan, bila *Open output file* dicentang, dimuat ke proyek. `laporan_modul3.pdf`, `rekap_csv.zip`, `manifest_modul3.json` berada di Folder hasil.
3. **Folder hasil dikosongkan / Skip:** PDF dan ZIP tidak tersimpan, ada peringatan di log, layer tetap tertulis.
4. **Lewati semua keluaran:** tidak ada file baru dan tidak ada layer dimuat; ringkasan tampil di log. Pada Modul 4 ada peringatan bahwa model tidak tersimpan.
5. **Modul 4/5:** Modul 4 menulis `model_terpilih.joblib`, `metadata_model.json`, PDF dan ZIP ke Folder hasil; Modul 5 membaca keduanya dan menulis `01…06` ke tujuan masing-masing (06 hanya mode Hybrid).
6. **Shapefile:** tujuan `.shp` memunculkan peringatan pemotongan nama kolom; tujuan basis data ditolak dengan pesan jelas.
7. **Kolom salah:** memilih kolom yang sama untuk identitas dan luas ditolak sebelum dijalankan.
8. **Modul 6:** dengan Processing Toolbox terbuka di kanan, panel muncul sebagai tab di Toolbox; kecilkan tinggi jendela QGIS dan pastikan scroll mencapai Operator, Sumber verifikasi, tombol Cocok/Tidak cocok dan *Simpan CSV & PDF Rekap Verifikasi*.
9. **Batch:** *Run as Batch Process* pada Modul 1 dengan dua baris menghasilkan keluaran terpisah per baris.
