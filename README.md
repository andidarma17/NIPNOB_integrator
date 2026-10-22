# NIB–NOP Integrator — plugin QGIS 3 / 4 (beta 0.9.4)

**Status:** implemented, compiled and unit-tested without QGIS; GUI, I/O and geometry processing require end-to-end validation within installed QGIS. **Do not yet use unattended on production land-tax records.**

## Kompatibilitas

Target: QGIS **3.28–3.44** (Qt5) dan **4.0–4.2** (Qt6), dengan metadata `qgisMaximumVersion=4.99`. Versi QGIS 3.0–3.27 tidak ditargetkan. Pengujian langsung lintas versi 3/4 belum dapat dilakukan di lingkungan pembuat paket.

Core (Modul 1–3 dan 6): PyQGIS, Qt/QGIS saja. AI (Modul 4–5): Python packages `numpy`, `scikit-learn`, `joblib`; opsional `xgboost`. Tidak perlu `geopandas`, `shapely`, `reportlab` di lingkungan QGIS.

## Instalasi

1. Jangan mengekstrak ZIP plugin. Buka QGIS → **Plugins → Manage and Install Plugins → Install from ZIP**.
2. Pilih `NIBNOP_Integrator_QGIS3_QGIS4_v0.9.4_LAPORAN_LENGKAP.zip`.
3. Jika QGIS memberi peringatan *experimental*, aktifkan plugin percobaan dengan kesadaran status beta.
4. Menu atas atau **Vector → NIB–NOP Integrator** menyediakan enam tools.
5. Buka layer BPN/PBB terlebih dahulu, lalu pilih nama layer dan masing-masing field identitas serta luas melalui dropdown **yang menampilkan semua kolom tanpa filter tipe data**. Default NIB, D_NOP, LUAS, D_LUAS akan dipilih jika ditemukan. Jika nama kolom berbeda, pilih sendiri. Kolom luas bertipe teks boleh dipilih jika nilainya berupa angka; nilai yang tidak dapat dibaca sebagai angka akan ditandai kosong/tidak numerik.
6. Layer harus poligon dan **CRS proyeksi bermeter**. Bila CRS berbeda, centang transformasi sementara PBB ke CRS BPN.

**AI dependencies:** instal ke Python yang dipakai *QGIS*, bukan sekadar Python/Colab lain. Pada Windows OSGeo4W shell, gunakan interpreter QGIS yang tersedia dan perintah `python -m pip install scikit-learn joblib xgboost` bila kebijakan instalasi mengizinkan. Penting: pada beberapa instalasi OSGeo4W, instalasi paket lewat pip dapat mengganggu paket yang dikelola OSGeo4W; gunakan lingkungan terkelola/OSGeo4W terlebih dahulu. QGIS harus di-restart setelah pemasangan.

## Pembaruan 0.9.2 — dropdown atribut

- Diterapkan ke keenam tools (termasuk Verifikasi Studio dan layer historis training).
- Semua nama kolom layer yang terpilih terlihat pada dropdown **kolom identitas** dan **kolom luas tertulis**, tidak ada filter jenis kolom.
- Dropdown memutakhirkan daftar kolom saat operator mengganti layer atau mengganti struktur field layer.
- Kolom umum (BPN `NIB` / `LUAS`, PBB `D_NOP` / `D_LUAS`) terpilih otomatis bila tersedia; jika tidak ada kolom yang dikenali, operator harus memilih secara manual.
- Memilih kolom teks diperbolehkan. **Nilai luas** harus numerik agar dapat dipakai pada kalkulasi; data kosong / tidak numerik diberi flag atau tidak dapat dibandingkan. Penggunaan kolom tanggal atau alamat sebagai luas secara sengaja tetap menghasilkan nilai tidak numerik, bukan hasil luas valid.
- Data dan ambang QA serta aturan Level 1/Level 2 tidak diubah.

**Pembaruan 0.9.3 — Evaluasi AI Modul 4:** Modul 4 kini melaporkan seluruh metrik TRAIN / VALIDATION / TEST (GOLD independen), confusion matrix kedua model, kurva ROC, PR, kalibrasi, feature importance, batas bawah Wilson 95% Precision, panduan interpretasi ambang, dan rekomendasi otomatis. Seluruh gambar langsung masuk ke PDF `laporan_modul4.pdf`. Metrik TEST **tidak dibuat** bila GOLD independen tidak tersedia; laporan menulis BELUM DAPAT DINILAI. `rekap_csv.zip` menambahkan `metrik_train_validation_test.csv`, `feature_importance.csv`, `panduan_ambang_metrik.csv`, `penilaian_per_metrik.csv`, dan `rekomendasi_model.csv`. Model dan parameter aturan Modul 1–3 tidak berubah.

**Memperbarui instalasi:** Nonaktifkan plugin lama di QGIS, gunakan **Plugins > Manage and Install Plugins > Install from ZIP** dengan paket v0.9.4, lalu restart QGIS. Jika QGIS tidak mengganti file versi lama, hapus instalasi plugin lama lewat manajer plugin sebelum memasang ulang. Jangan hapus atau timpa folder data hasil kerja operator.

## Pembaruan v0.9.4 - Laporan PDF lengkap untuk enam tools

- **Modul 1:** delapan grafik lengkap dalam PDF: perbandingan temuan, jumlah atribut kosong, persen atribut kosong, histogram luas BPN/PBB, scatter luas BPN/PBB, dan kategori masalah luas. Setiap grafik diberi judul/keterangan, diproses ulang pada layer dan nama field yang operator pilih.
- **Modul 2:** ringkasan QA spasial, peta indikatif overlap BPN, peta overlap PBB, peta geometri invalid/fixed, serta peta perbesaran kandidat gap BPN bila ada. Tabel overlap/gap utama dan rekomendasi tersedia di PDF.
- **Modul 3:** histogram kandidat overlap, grafik alasan Level 2, sebaran perbandingan overlap/kesamaan luas, peta Level 1/2, contoh kandidat, dan tindak lanjut. Memakai file BARU hasil koreksi operator, bukan cache QA Modul 1/2.
- **Modul 4:** tetap menggunakan laporan AI lengkap v0.9.3 (TRAIN / VALIDATION / TEST GOLD, confusion matrix, ROC, PR, Brier, ambang/rekomendasi); tidak ada nilai testing palsu bila GOLD belum ada.
- **Modul 5:** hasil level aturan dan tambahan AI, distribusi skor AI (jika model diisi), peta tingkat pemaduan, tabel rekomendasi studio, dan status model.
- **Modul 6:** ringkasan verifikasi GOLD, grafik keputusan, peta indikatif lokasi pasangan yang diperiksa jika layer masih tersedia, tabel keputusan dan tindak lanjut.
- **PDF tunggal per modul:** nama `laporan_modul1.pdf` hingga `laporan_modul5.pdf`; Modul 6 memakai `laporan_modul6.pdf`. Rekap detail tetap dalam ZIP CSV. Tidak ada keharusan membuka PNG terpisah.
- **Menu plugin:** tepat `3. Penentuan level pemaduan berbasis aturan` dan `4. Training AI`.
- Perubahan ini **tidak** mengubah aturan penentuan NIB-NOP Level 1/2, input perbaikan operator pada Modul 3, atau mekanisme AI dari v0.9.3.

**Penting:** Peta PDF adalah visualisasi indikatif berdasarkan koordinat layer sumber; bukan peta pendaftaran tanah berskala resmi. Untuk pemeriksaan batas, operator tetap harus membuka layer hasil di kanvas QGIS. Fitur output yang tidak tersedia (misalnya gap tidak ditemukan atau skor AI belum ada) diberi penjelasan, bukan dibuat-buat. Laporkan bug tampilan ke pengembang dengan screenshot serta pesan pada QGIS Python console. Kompatibilitas Qt5/Qt6 telah diupayakan tetapi belum teruji langsung dalam instalasi QGIS karena runtime QGIS tidak tersedia di lingkungan pengembangan.

## Enam tools

| Tool | Input utama | Output |
|---|---|---|
| 1. Kelengkapan | Dua layer awal, dropdown NIB/NOP dan luas, batas luas | Dua layer QA, PDF + ZIP CSV |
| 2. Spasial | Dua layer awal, overlap area minimum, gap minimum | Dua layer QA geometri, PDF + ZIP CSV |
| 3. Pemaduan aturan | **Dua layer hasil koreksi manual operator** (bukan otomatis dari Modul 2); parameter 50/90/50 bisa diubah | Padanan L1, BPN L2, PBB L2, CSV pasangan + sidik jari input, PDF |
| 4. Training hybrid | Layer operator + CSV kandidat Modul 3 (silver) opsional; CSV fitur GOLD dan/atau layer historis + CSV verifikasi opsional | Model joblib, metadata JSON, rekap CSV+PDF |
| 5. Inference | Layer operator dan model/metadata Modul 4 | Tiga GeoJSON/GPKG/SHP Level 1 dan 2, CSV skor + PDF |
| 6. Verifikasi studio | Dua layer aktif + CSV pasangan kandidat opsional | Label manual per-pasangan, CSV langsung, ZIP+PDF rekap |

### Perbedaan input dan fitur

**Modul 3 HARUS dijalankan ulang setelah operator memperbaiki GeoJSON**. Plugin membuang penanda QA lama dan menghitung ulang geometri/atribut; modul 3 menghasilkan CSV `pasangan_kandidat.csv` di dalam ZIP dan file `manifest_modul3.json` di folder hasil. Saat modul 4 menerima silver dari CSV Modul 3, hash kedua layer diperiksa dan ketidakcocokan ditolak.

**Modul 4:** silver labels adalah tebakan aturan dan **tidak** diklaim benar. Level 2 tidak menjadi label negatif. Untuk GOLD gunakan CSV berisi `pair_id` atau `record_bpn`/`record_pbb` atau `NIB`/`NOP`, `label` (0/1), `status_verifikasi=DIVERIFIKASI`, `sumber_verifikasi`, opsional `wilayah`. Bisa pula CSV fitur lengkap yang mengandung 18 fitur (lihat `engine.FEATURE_NAMES`) dan kolom label/verifikasi, atau layer historis BPN dan PBB berikut tabel pasangan berlabel. Untuk validasi yang bagus, data GOLD harus mencakup area/kelompok independen. **Data Level 2 tanpa label eksplisit 0 adalah belum pasti, bukan negatif.**

**Modul 5:** tanpa model dapat menjalankan aturan baseline; dengan silver-only hanya memberikan skor prioritas verifikasi. Tambahan Level 1 melalui AI **dibatasi** pada model dengan GOLD teruji, persetujuan eksplisit, keunikan ID, bebas overlap internal, deviasi luas di bawah ambang, dan margin skor kandidat. Model `.joblib` hanya boleh dimuat dari sumber terpercaya (format pickle bisa menjalankan kode Python saat dimuat).

**Modul 6:** tabel pasangan dipaginasi 200 baris; klik baris atau gunakan tombol klik bidang BPN di peta untuk menyorot calon pasangan dan memperbesar peta. Operator mengisi nama, sumber bukti, catatan, lalu klik **Cocok**, **Tidak cocok**, atau **Belum pasti**. CSV keputusan disimpan setiap kali menekan tombol. Masukkan CSV hasil ini ke Modul 4 untuk menambah data GOLD (pastikan layer sama). Jika memilih CSV dari Modul 3/5, urutan record dalam layer harus tetap sama dengan ketika CSV dibuat.

## Pilihan penyimpanan

- **GeoPackage (.gpkg)**: rekomendasi utama karena mempertahankan nama kolom yang panjang.
- **GeoJSON (.geojson)**: pertukaran data; gunakan CRS dan tipe atribut dengan cermat.
- **Shapefile (.shp)**: kompatibilitas lama; **nama kolom dibatasi ~10 karakter** dan nama bisa dipotong/bertabrakan. Hindari terutama untuk output Level 1 dengan banyak field.
- Tiap modul: `laporan_modulX.pdf` berisi ringkasan, tabel, seluruh visualisasi utama, interpretasi, dan rekomendasi; `rekap_csv.zip` berisi semua rekap. Tool 4 juga menghasilkan `.joblib` dan `.json` karena kedua berkas diperlukan untuk inference (bukan laporan).

## Batasan dan QA yang perlu dilakukan

1. Semua luas dihitung dari CRS proyeksi **meter**; periksa kecocokan datum/zone EPSG. Selisih luas tertulis memakai nilai absolut, sedangkan kolom `persen_selisihL` bertanda (+/-) terhadap **luas tertulis**.
2. Gap hanya lubang tertutup dalam gabungan poligon BPN, bukan area luar. Bidang gap baru `bid_tambah=1` tanpa NIB dan **tidak** otomatis dianggap legal.
3. Overlap antar-bidang sumber ditandai, **tidak** dihapus sepihak. Luas iris > ambang minimum dianggap overlap. Ambang 50% untuk pasangan dihitung dari **luas BPN**. `50.0%` tepat tidak lolos bila kriteria `>50%`.
4. Interpretasi hubungan satu-ke-banyak menggunakan jumlah **calon di atas ambang**, bukan total irisan kecil. Kedua belah pihak harus tepat satu calon.
5. Model AI merupakan alat bantu, **bukan bukti hukum**. Harus diuji dengan sampel pasangan nyata independen untuk menaksir false match.
6. Runtime QGIS/Qt belum tersedia di lingkungan pengembangan. Wajib lakukan *acceptance test* pada QGIS 3.44 LTR dan 4.2 sebelum pemakaian organisasi.
7. Proses besar berjalan sinkron dalam dialog; saat layer sangat besar QGIS bisa berhenti merespons sementara. Uji dahulu pada subset kecil.

## Paket pengujian

`python -m unittest discover nibnop_integrator/tests -v` menjalankan unit test logika aturan dan GOLD/Level 2 tanpa QGIS. Uji AI (scikit-learn) tersendiri dilakukan dengan stub agar tidak memerlukan runtime QGIS; bukan bukti uji integrasi QGIS.

## File teknis

- `plugin.py` menu 6 tools
- `dialogs.py` tools 1–5
- `studio.py` tool 6
- `engine.py` algoritma spasial native QGIS
- `logic.py` aturan murni (unit-testable)
- `ml.py` data GOLD/SILVER, training dan inference
- `storage.py` export layer/ZIP CSV/laporan PDF Qt
- `compat.py` dukungan PyQt/Qt5 dan Qt6


## Patch v0.9.1 — Pilihan kolom luas tertulis

- Memperbaiki dropdown luas BPN dan PBB kosong pada Modul 1–5 dan Verifikasi Studio.
- Semua field dari layer terpilih ditampilkan, termasuk Double/Integer dan numerik yang disimpan sebagai teks.
- Kolom umum `LUAS` pada BPN dan `D_LUAS` pada PBB dipilih otomatis jika tersedia.
- Pergantian layer menyegarkan dropdown; tidak ada perubahan algoritma pemaduan, hasil audit, atau data asli.
- Tutup seluruh dialog, nonaktifkan plugin lama, pasang ZIP v0.9.1, lalu restart QGIS untuk memuat kode baru.
