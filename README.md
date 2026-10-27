# NIB–NOP Integrator — plugin QGIS 3 / 4 (beta 0.10.0)

**Status:** implemented, compiled and unit-tested without QGIS; GUI, I/O and geometry processing require end-to-end validation within installed QGIS. **Do not yet use unattended on production land-tax records.**

## Kompatibilitas

Target: QGIS **3.28–3.44** (Qt5) dan **4.0–4.2** (Qt6), dengan metadata `qgisMaximumVersion=4.99`. Versi QGIS 3.0–3.27 tidak ditargetkan. Pengujian langsung lintas versi 3/4 belum dapat dilakukan di lingkungan pembuat paket.

Core (Modul 1–3 dan 6): PyQGIS, Qt/QGIS saja. AI (Modul 4–5): Python packages `numpy`, `scikit-learn`, `joblib`; opsional `xgboost`. Tidak perlu `geopandas`, `shapely`, `reportlab` di lingkungan QGIS.

## Instalasi

1. Jangan mengekstrak ZIP plugin. Buka QGIS → **Plugins → Manage and Install Plugins → Install from ZIP**.
2. Pilih ZIP plugin versi terbaru (`NIBNOP_Integrator_v0.10.0_AI_Independent_Toolbox.zip`).
3. Jika QGIS memberi peringatan *experimental*, aktifkan plugin percobaan dengan kesadaran status beta.
4. **Vector → NIB–NOP Integrator** dan **Processing Toolbox → NIB–NOP Integrator** menyediakan ketujuh tools (Modul 1, 2, 3, 3.1, 4, 5, 6).
5. Buka layer BPN/PBB terlebih dahulu, lalu pilih nama layer dan masing-masing field identitas serta luas melalui dropdown **yang menampilkan semua kolom tanpa filter tipe data**. Default NIB, D_NOP, LUAS, D_LUAS akan dipilih jika ditemukan. Jika nama kolom berbeda, pilih sendiri. Kolom luas bertipe teks boleh dipilih jika nilainya berupa angka; nilai yang tidak dapat dibaca sebagai angka akan ditandai kosong/tidak numerik.
6. Layer BPN harus poligon; layer PBB boleh **poligon atau titik NOP** (lihat "Pembaruan v0.9.5"). Semua layer memakai **CRS proyeksi bermeter**. Bila CRS berbeda, centang transformasi sementara PBB ke CRS BPN.

**AI dependencies:** instal ke Python yang dipakai *QGIS*, bukan sekadar Python/Colab lain. Pada Windows OSGeo4W shell, gunakan interpreter QGIS yang tersedia dan perintah `python -m pip install scikit-learn joblib xgboost` bila kebijakan instalasi mengizinkan. Penting: pada beberapa instalasi OSGeo4W, instalasi paket lewat pip dapat mengganggu paket yang dikelola OSGeo4W; gunakan lingkungan terkelola/OSGeo4W terlebih dahulu. QGIS harus di-restart setelah pemasangan.

## Pembaruan v0.10.0 — formulir Processing dan keluaran terpisah

* **Tata letak:** Modul 1–5 dan 3.1 kini memakai formulir Processing standar di mana pun dibuka (menu **Vector → NIB–NOP Integrator**, Processing Toolbox, Batch, Modeler, `qgis_process`): label di atas dan isian di bawahnya.
* **Keluaran terpisah:** setiap layer spasial punya tujuan sendiri (file `.gpkg`/`.geojson`/`.shp`, file sementara, atau *Skip Output*) dengan kotak *Open output file after running algorithm*. Laporan PDF, `rekap_csv.zip` (serta manifest Modul 3, atau model/metadata Modul 4) bersama dalam satu **Folder hasil** (bawaan `~/NIBNOP_HASIL/modul_<n>`; dapat dilewati). Pilihan *Format layer* dihapus karena format mengikuti ekstensi file.
* **Lewati semua keluaran:** kotak centang `SKIP_OUTPUT` menjalankan perhitungan dan menulis ringkasan ke log tanpa menyimpan file atau memuat layer (uji coba). Pada Modul 4 ini berarti model tidak tersimpan.
* **Kolom bawaan:** NIB, LUAS, D_NOP, D_LUAS dipilih otomatis bila ada; bila tidak, formulir memilih kolom pertama, jadi **periksa kolom luas**. Pemilihan kolom identitas dan luas yang sama ditolak.
* **Modul 6:** panel Verifikasi Studio sekarang berada dalam *scroll area* dan, bila Processing Toolbox terbuka di sisi kanan, digabung sebagai tab dengannya sehingga memakai tinggi penuh jendela. Bagian operator hingga tombol simpan CSV & PDF dapat dijangkau pada layar pendek.
* Jendela lama (`dialogs.ToolDialog`) tetap ada hanya sebagai cadangan bila formulir Processing gagal dibuka dan sebagai sumber metode `run1…run5` yang dipakai bersama.
* **Kompatibilitas:** parameter `OUTPUT_FORMAT` dihapus; keluaran layer kini `OUT_<NAMA>` (mis. `OUT_01_PADANAN_LEVEL1`). Model Graphical Modeler/skrip lama perlu diperbarui.

## Pembaruan v0.9.9 — backend AI v0.9.8 + Processing Toolbox

v0.9.9 menggabungkan dua jalur pengembangan: **backend AI v0.9.8** (tiga mode training, Full AI / Hybrid, `ai_matching.py`, impor GOLD yang diperketat) dan **akses Processing Toolbox v0.9.7**.

* **Processing Toolbox → NIB–NOP Integrator** berisi Modul 1, 2, 3, 3.1, 4, 5 dan 6 (id algoritma `nib_nop_integrator:modul_...`, tidak berubah dari v0.9.7).
* **Klik ganda di Toolbox** (sejak v0.10.0: formulir Processing standar; lihat bagian di atas) memakai pilihan v0.9.8 untuk Modul 4 dan 5. Modul 6 membuka panel Verifikasi Studio.
* **Batch process, Graphical Modeler, `processing.run()` dan `qgis_process`** memakai formulir parameter Processing. Untuk Modul 4 tersedia dropdown *Sumber pelatihan* (GOLD Only / SILVER Only / SILVER + GOLD) beserta rekap SILVER (ZIP/CSV), GOLD operator/fitur/historis, radius dan target precision. Untuk Modul 5 tersedia dropdown *Mode prediksi* (Hybrid / Full AI), rekap Modul 3 (ZIP/CSV, wajib untuk Hybrid), model, metadata, skor minimum (bawaan 0,90), margin dan izin Level 1 otomatis (bawaan mati).
* Modul 5 di Toolbox sama seperti di menu: **tidak** ada gerbang aturan Modul 3 (overlap, deviasi luas) dan tidak ada tahap 2 nama; hanya ambang nama COCOK/MIRIP untuk fitur.
* Modul 4 mewajibkan layer BPN/PBB di semua mode (sama seperti dialog v0.9.8).
* Dari v0.9.7 dipertahankan: dropdown layer hanya menampilkan layer vektor sesuai geometri (raster tidak lagi membuat dropdown kolom error). Dari v0.9.8 dipertahankan: penerimaan status `TERVERIFIKASI` pada GOLD, sidik-jari data, dan seluruh perbaikan `ml.py`.
* Pengujian baru `tests/test_processing_spec.py` (tanpa PyQGIS) memastikan setiap widget/`val()` yang dibaca `run1…run5` tersedia di parameter Toolbox, sehingga perubahan dialog di masa depan tidak diam-diam merusak jalur Batch/Modeler.

**Status verifikasi:** kode ter-compile dan seluruh uji tanpa PyQGIS lulus; uji yang memerlukan PyQGIS (`test_processing.py`) dan GUI QGIS belum dijalankan di lingkungan pembuat paket. Lihat `ACCEPTANCE_TEST.md` bagian v0.9.9.

## Pembaruan v0.9.8 — tiga mode training dan Full AI / Hybrid

**Baca bagian ini terlebih dahulu.** Penjelasan v0.9.7 dan versi sebelumnya di bawah hanya riwayat perubahan; pada v0.9.8 Modul 5 **tidak lagi menghitung ulang** keputusan aturan Modul 3.

### Modul 4: pilih sumber belajar

| Mode | Input wajib | Status tanpa pengujian GOLD independen |
|---|---|---|
| `SILVER_ONLY` | `rekap_csv.zip` dari Modul 3 (atau CSV `pasangan_kandidat.csv`) | `PREVIEW_ONLY`: AI boleh memberi usulan studio, **tidak** membuat Level 1 otomatis |
| `GOLD_ONLY` | CSV GOLD operator, CSV fitur historis, atau BPN/PBB historis + CSV pasangan berlabel | Model dapat menjadi `GOLD_TESTED_REVIEW_REQUIRED` bila pengujian independen memenuhi ambang |
| `SILVER_GOLD` | Keduanya | GOLD untuk validasi/testing; SILVER bobot agregat per kelas dibatasi agar tidak menenggelamkan GOLD |

- Pemilihan sumber adalah dropdown tersendiri di Modul 4. Pilihan yang tidak dipakai diabaikan tanpa menghapus path yang pernah Anda isikan.
- Data BPN/PBB sekarang **tetap wajib** untuk membentuk fitur kandidat dan memeriksa identitas. SILVER harus berasal dari layer yang sama persis dengan hasil Modul 3 (diperiksa melalui sidik-jari data).
- SILVER adalah **weak label**, bukan bukti benar. Model SILVER Only boleh dilatih, tetapi tidak bisa diklaim memiliki precision independen dari GOLD.
- Seluruh mode memerlukan dua kelas label (benar dan salah). Jika SILVER tidak membentuk kedua kelas, tambahkan data pelatihan yang sesuai.
- GOLD dibagi secara spasial ke training/validation/testing bila memenuhi syarat. SILVER dari kelompok GOLD yang ditahan untuk pengujian, atau dengan NIB/NOP yang sama, dikeluarkan dari training. GOLD testing tidak digunakan untuk memilih model.
- `Target precision GOLD` (misalnya 0,80) adalah **target evaluasi precision**, bukan `skor minimum AI`. Pengujian model saat ini menggunakan ambang skor 0,90 dan metadata menyimpannya.

### Modul 5: pilih cara menggunakan model

| Mode | Input | Cara menghasilkan hasil |
|---|---|---|
| **Full AI (`AI_ONLY`)** | Layer BPN dan PBB + `model_terpilih.joblib` + `metadata_model.json` | Skor semua kandidat spasial, menghasilkan usulan AI tanpa aturan Modul 3 |
| **Hybrid (`HYBRID`)** | Semua input Full AI **ditambah** `rekap_csv.zip` hasil Modul 3 | Impor pasangan Level 1 aturan **tanpa menghitung ulang**, lalu prediksi AI terhadap semua kandidat; usulan yang memakai NIB/NOP sudah terpasang tidak digabung otomatis |

**Penting:** overlap, deviasi luas, dan nama merupakan **fitur prediksi**, tidak lagi gerbang aturan yang menolak pasangan AI. Gerbang seleksi AI terbatas pada skor, selisih dengan pesaing, NIB/NOP yang tidak kosong/unik, dan hubungan satu-ke-satu. Radius pencarian tetap membatasi *candidate generation*; pasangan yang berada di luar radius tidak bisa diprediksi.

Untuk mengizinkan pasangan AI menjadi **Level 1 otomatis**, model harus berstatus `GOLD_TESTED_REVIEW_REQUIRED`, centang izin operator, dan `Skor minimum AI` harus **tidak lebih rendah** dari ambang yang telah diuji dalam metadata model. Tanpa seluruh syarat itu, usulan tetap tersedia untuk verifikasi studio pada layer `05_usulan_ai`; tidak dipaksakan menjadi Level 1.

Pada **Hybrid**, input ZIP/CSV Modul 3 harus dari layer BPN/PBB yang **identik** dengan layer Modul 5. Plugin memeriksa sidik-jari BPN dan PBB serta memverifikasi identitas NIB/NOP setiap pasangan Level 1. Gunakan keluaran `rekap_csv.zip` di folder Modul 3, **bukan** ZIP plugin. File `.zip` rekap tidak perlu diekstrak.

Keluaran Modul 5:

1. `01_padanan_level1`: Level 1 aturan (khusus Hybrid) dan Level 1 AI teruji yang diizinkan operator.
2. `02_bpn_level2` dan `03_pbb_level2`: objek yang belum diterima otomatis.
3. `04_rekomendasi_ai_studio`: kandidat terbaik per BPN yang belum dipadukan.
4. `05_usulan_ai`: usulan satu-ke-satu dengan skor dan alasan, **termasuk untuk SILVER Only**; jangan disalahartikan sebagai Level 1 resmi.
5. `06_konflik_ai_rule`: kandidat AI berskor tinggi yang berbenturan dengan pasangan Modul 3 (Hybrid saja).
6. `rekap_csv.zip`, `laporan_modul5.pdf`: skor seluruh kandidat, usulan, tambahan yang benar-benar diterima, konflik, dan alasan seleksi.

Perbandingan tiga mode training sebaiknya memakai BPN/PBB, radius kandidat, dan GOLD pengujian independen **yang sama**, bukan membandingkan jumlah Level 1 semata. Meningkatnya jumlah usulan tidak membuktikan model lebih akurat.

**Keselamatan operasional:** gunakan folder output baru saat uji versi ini. Model SILVER Only dapat menghasilkan banyak prediksi keliru; gunakan verifikasi studio. QGIS GUI tidak tersedia di lingkungan pengembangan paket sehingga uji akhir plugin pada QGIS 3.28+ atau QGIS 4.x masih wajib sebelum operasional.

## Pembaruan 0.9.2 — dropdown atribut

- Diterapkan ke keenam tools (termasuk Verifikasi Studio dan layer historis training).
- Semua nama kolom layer yang terpilih terlihat pada dropdown **kolom identitas** dan **kolom luas tertulis**, tidak ada filter jenis kolom.
- Dropdown memutakhirkan daftar kolom saat operator mengganti layer atau mengganti struktur field layer.
- Kolom umum (BPN `NIB` / `LUAS`, PBB `D_NOP` / `D_LUAS`) terpilih otomatis bila tersedia; jika tidak ada kolom yang dikenali, operator harus memilih secara manual.
- Memilih kolom teks diperbolehkan. **Nilai luas** harus numerik agar dapat dipakai pada kalkulasi; data kosong / tidak numerik diberi flag atau tidak dapat dibandingkan. Penggunaan kolom tanggal atau alamat sebagai luas secara sengaja tetap menghasilkan nilai tidak numerik, bukan hasil luas valid.
- Data dan ambang QA serta aturan Level 1/Level 2 tidak diubah.

**Pembaruan 0.9.3 — Evaluasi AI Modul 4:** Modul 4 kini melaporkan seluruh metrik TRAIN / VALIDATION / TEST (GOLD independen), confusion matrix kedua model, kurva ROC, PR, kalibrasi, feature importance, batas bawah Wilson 95% Precision, panduan interpretasi ambang, dan rekomendasi otomatis. Seluruh gambar langsung masuk ke PDF `laporan_modul4.pdf`. Metrik TEST **tidak dibuat** bila GOLD independen tidak tersedia; laporan menulis BELUM DAPAT DINILAI. `rekap_csv.zip` menambahkan `metrik_train_validation_test.csv`, `feature_importance.csv`, `panduan_ambang_metrik.csv`, `penilaian_per_metrik.csv`, dan `rekomendasi_model.csv`. Model dan parameter aturan Modul 1–3 tidak berubah.

**Memperbarui instalasi:** Nonaktifkan plugin lama di QGIS, gunakan **Plugins > Manage and Install Plugins > Install from ZIP** dengan paket terbaru, lalu restart QGIS. Jika QGIS tidak mengganti file versi lama, hapus instalasi plugin lama lewat manajer plugin sebelum memasang ulang. Jangan hapus atau timpa folder data hasil kerja operator.

## Pembaruan v0.9.7 — GOLD dan transparansi AI

- Modul 4 membaca CSV dengan pemisah koma maupun titik koma, dan menerima status verifikasi `DIVERIFIKASI` atau `TERVERIFIKASI`. Kolom sumber/bukti verifikasi tetap wajib diisi.
- GOLD dicocokkan ke kandidat melalui **NIB dan NOP asli** bila unik; `pair_id`/nomor urut dapat digunakan hanya bila identitas tidak bertentangan. NOP yang berubah menjadi notasi ilmiah ditolak, bukan dipaksakan menjadi pasangan lain.
- Saat operator sudah memasukkan GOLD tetapi **nol label yang sah terbaca**, training dihentikan dengan pesan penyebabnya. GOLD yang gagal dipetakan disimpan dalam `gold_ditolak.csv` untuk ditinjau.
- CSV fitur historis harus memuat semua fitur 18/20 sesuai versi model. Angka yang rusak akibat format spreadsheet ditolak dengan pesan jelas.
- Modul 4 melaporkan GOLD positif/negatif, GOLD ditolak, serta jumlah data validasi dan testing. Data SILVER saja tetap menjadi `PREVIEW_ONLY`.
- Modul 5 menghasilkan `04_rekomendasi_ai_studio` (bila ada model dan kandidat) untuk menampilkan kandidat skor AI tanpa mengubah Level 1 aturan. Rincian gerbang promosi ada pada `skor_kandidat.csv` dan `rekap_gerbang_ai.csv`.
- Hasil Level 1 tambahan tetap memerlukan model yang lolos uji GOLD, izin eksplisit operator, dan seluruh gerbang keamanan pasangan. **Kesamaan keluaran Level 1 Modul 3 dan 5 tidak lagi berarti AI tidak dijalankan**: lihat layer rekomendasi dan alasan penolakannya.

**Untuk data Sungai Beliung yang dilampirkan:** gunakan `gold_operator_terpetakan.csv` dari ZIP GOLD yang telah direkonsiliasi, bukan CSV asli yang NOP-nya berubah menjadi notasi ilmiah. Pilih sebagai **CSV label operator pada layer yang dipilih**, bersama kedua SHP sumber penuh yang sesuai. File ini mencatat deklarasi verifikasi manual pengguna, bukan bukti administratif independen. Uji prediksi dan verifikasi lanjutan tetap wajib sebelum mengesahkan pemaduan.

## Pembaruan v0.9.6 - Pemadanan tahap 2 (buffer + skor nama)

Pada Modul 3, 3.1 dan 5, bila kolom nama BPN dan PBB dipilih, centang *"Tahap 2: cari ulang padanan Level 2 dalam buffer dengan skor nama"*:

1. **Tahap 1** — aturan yang sudah ada dijalankan apa adanya, menghasilkan Level 1 dan Level 2.
2. **Tahap 2** — rekaman Level 2 (kecuali NIB/NOP kosong atau duplikat) dicari ulang kandidatnya dalam **buffer** di sekitar bidang BPN (bawaan **5 m**; Modul 3.1 memakai toleransi titik). Tiap kandidat dinilai:
   * `skor_nama` (0–100), `skor_spasial` (100 bila beririsan / titik di dalam bidang, turun linear sampai 0 di tepi buffer), dan kesamaan luas tertulis;
   * `skor_gabungan` = 0,60·nama + 0,25·spasial + 0,15·luas (bobot dapat diubah).
3. Kandidat menjadi **Level 1** dengan `metode_padu=RULE_NAMA` bila skor gabungan ≥ 80, skor nama ≥ 60, unggul ≥ 10 poin dari kandidat ke-2 di sisi BPN maupun PBB, dan pasangan 1:1. Semua ambang dapat diubah di dialog.

Rekaman yang tetap Level 2 mendapat kolom `skor_gabungan` (kandidat terbaik) untuk prioritas verifikasi studio. Detail per kandidat (`skor_spasial`, `skor_gabungan`, `alasan_tahap2`) ada di `pasangan_kandidat.csv`. Lihat `nibnop_docs/DOMAIN_RULES.md` §1c.

**Gap tertutup BPN (Modul 2, 3, 3.1):**

* Jumlah gap tidak lagi menghentikan proses: melebihi *ambang peringatan* (bawaan 2 500 gap ≥ luas minimum) hanya memunculkan peringatan di log dan PDF.
* Gap disimpan sebagai layer kandidat tersendiri (Modul 2: `bpn_kandidat_gap`; Modul 3/3.1: `04_kandidat_gap`) dengan `luas_m2` dan `status_periksa` (`LAYAK_PERIKSA` / `DI_BAWAH_MINIMUM`); gap tidak lagi ditambahkan ke layer BPN.
* Modul 3/3.1 memadukan **bidang BPN sumber**. Centang *"Sertakan kandidat gap BPN sebagai petunjuk"* untuk menyimpan layer gap dan menandai PBB Level 2 di atas gap (`PBB_DI_ATAS_GAP`, `calon_gap`); gap tidak ikut keunikan 1:1, jadi tidak memicu `MULTI_NIB`.
* Laporan memisahkan: gap terdeteksi, memenuhi luas minimum, diproses, dan status pemeriksaan (`LENGKAP` / `TIDAK LENGKAP`).
* Jendela progres dengan tombol **Batal**. Batal saat tahap gap menghentikan pemeriksaan gap (status TIDAK LENGKAP) dan modul tetap selesai; batal di tahap lain menghentikan modul tanpa menulis keluaran. Penggabungan poligon untuk mencari gap adalah satu langkah yang tidak dapat disela; Batal berlaku sesudahnya.

**Nama di Modul 4 dan 5:**

* **Modul 4** — kolom nama BPN/PBB opsional. Bila dipilih, model dilatih dengan fitur nama (`skor_nama`, `nama_tidak_dinilai`; versi fitur `QGIS_PLUGIN_V2`, 20 fitur). Centang *"Sertakan padanan tahap 2 (RULE_NAMA) dari CSV Modul 3 sebagai silver"* untuk memakai padanan tahap 2 sebagai label silver dengan bobot sendiri (bawaan 0,1; silver aturan 0,2).
* **Modul 5** — tahap 2 yang sama tersedia sebelum promosi AI (aturan → tahap 2 → AI). Model berfitur nama wajib dijalankan dengan kolom nama; model lama (V1) tetap dapat dipakai.

## Pembaruan v0.9.5 - Modul 3.1 (PBB titik NOP) dan validasi nama

Dalam praktik, data NOP sering hanya tersedia sebagai **titik**. Pemaduan berbasis aturan kini dipisah:

* **Modul 3** — tetap seperti semula untuk **PBB poligon** (aturan overlap/luas tidak berubah), ditambah validasi nama opsional. Bila layer PBB berupa titik, Modul 3 menolak dan mengarahkan ke Modul 3.1.
* **Modul 3.1** — khusus **PBB titik NOP** (Point/MultiPoint), dengan aturan di bawah. Keluaran di `~/NIBNOP_HASIL/modul_3_1`: layer `01/02/03`, `laporan_modul3_1.pdf`, `rekap_csv.zip`, `manifest_modul3_1.json`.

Modul 1, 2, 4, 5 dan 6 menerima PBB poligon maupun titik; layer BPN tetap poligon. Modul 5 memakai baseline Modul 3 untuk PBB poligon dan Modul 3.1 untuk PBB titik.

**Aturan Modul 3.1 (PBB titik):**

* Gerbang overlap diganti: calon memenuhi syarat spasial bila **titik NOP berada di dalam bidang BPN**. Titik di luar bidang sampai *Toleransi titik* (bawaan 5 m) tetap dicatat sebagai calon, tetapi menjadi Level 2 dengan alasan `TITIK_DI_LUAR_BIDANG`.
* Gerbang lain tetap: identitas kosong/duplikat, keunikan 1:1 (dua titik dalam satu bidang → `MULTI_NOP`; titik di dua bidang yang bertumpuk → `MULTI_NIB`), kesamaan luas tertulis BPN–PBB > 90 %, dan deviasi luas. Karena titik tidak punya luas, deviasi luas PBB dihitung **luas tertulis PBB terhadap luas geometri BPN** yang memuat titik.
* Bidang BPN tanpa titik → `TIDAK_ADA_TITIK`; titik di luar semua bidang → `TITIK_DI_LUAR_SEMUA_BIDANG`.
* Modul 2: "overlap" PBB titik berarti **titik berimpit** (jarak ≤ 0,01 m); perbaikan geometri dan selisih luas geometri tidak berlaku untuk titik.

**Validasi nama (opsional, Modul 3, 3.1, 4, 5, 6)** — pilih kolom nama pemegang hak (BPN, mis. `NAMA`) dan nama wajib pajak (PBB, mis. `NM_WP`), atau biarkan `(tidak digunakan)`:

* Setelah kandidat NIB–NOP terbentuk, nama keduanya dibandingkan (`skor_nama` 0–100) setelah normalisasi gelar/sapaan (H., Hj., Drs., S.H., Alm., Ny., …), ejaan lama (OE→U, DJ→J, TJ→C), varian Muhammad, dan urutan kata. Status `valid_nama`: **COCOK** (≥ 90 %), **MIRIP** (≥ 60 %), **TIDAK_COCOK**, atau **TIDAK_DINILAI** (nama kosong / kolom tidak dipilih).
* Setiap pasangan Level 1 diberi **`kekuatan`**:

  | PBB | Nama COCOK | Nama MIRIP / tidak dinilai | Nama TIDAK COCOK |
  |---|---|---|---|
  | Titik | KUAT | SEDANG | LEMAH |
  | Poligon | KUAT | KUAT | SEDANG |

* Secara bawaan nama **hanya menambah kekuatan**, tidak menggugurkan Level 1 (nama dapat berbeda sah karena jual beli, waris, alias). Centang *"Nama TIDAK COCOK menurunkan pasangan ke Level 2"* untuk menjadikannya gerbang (`NAMA_TIDAK_COCOK`).
* Layer Level 2 mendapat kolom `calon_nama`: calon pasangan yang namanya COCOK, sebagai petunjuk verifikasi studio.
* Modul 6 menampilkan posisi titik (di dalam / di luar + jarak) dan status nama di tabel kandidat.

**AI (Modul 4–5)**: kandidat titik memakai 18 fitur yang sama dengan pengisian khusus titik (lihat `nibnop_docs/DOMAIN_RULES.md`). Model mencatat `mode_geometri_pbb`; model poligon tidak dapat dipakai untuk data titik dan sebaliknya, dan data latih tidak boleh mencampur keduanya. Nama tidak dipakai sebagai fitur model.

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

## Tujuh tools (Modul 3.1 = PBB titik)

| Tool | Input utama | Output |
|---|---|---|
| 1. Kelengkapan | Dua layer awal, dropdown NIB/NOP dan luas, batas luas | Dua layer QA, PDF + ZIP CSV |
| 2. Spasial | Dua layer awal, overlap area minimum, gap minimum | Dua layer QA geometri, PDF + ZIP CSV |
| 3. Pemaduan aturan | **Dua layer hasil koreksi manual operator** (bukan otomatis dari Modul 2); parameter 50/90/50 bisa diubah | Padanan L1, BPN L2, PBB L2, CSV pasangan + sidik jari input, PDF |
| 3.1 Pemaduan PBB titik | Layer BPN poligon + layer PBB **titik NOP** hasil koreksi; kolom nama opsional; toleransi titik 5 m | Padanan L1 (+ `valid_nama`, `kekuatan`), BPN L2, PBB L2 (titik), CSV pasangan, PDF |
| 4. Training AI tiga mode | Layer BPN/PBB + SILVER, GOLD atau keduanya | Model joblib, metadata JSON, rekap CSV+PDF |
| 5. Full AI / Hybrid | Layer BPN/PBB dan model/metadata; rekap Modul 3 tambahan khusus Hybrid | Level 1/2, usulan AI, konflik, skor CSV + PDF |
| 6. Verifikasi studio | Dua layer aktif + CSV pasangan kandidat opsional | Label manual per-pasangan, CSV langsung, ZIP+PDF rekap |

### Perbedaan input dan fitur

**Modul 3 HARUS dijalankan ulang setelah operator memperbaiki GeoJSON**. Plugin membuang penanda QA lama dan menghitung ulang geometri/atribut; modul 3 menghasilkan CSV `pasangan_kandidat.csv` di dalam ZIP dan file `manifest_modul3.json` di folder hasil. Saat modul 4 menerima silver dari CSV Modul 3, hash kedua layer diperiksa dan ketidakcocokan ditolak.

**Modul 4:** silver labels adalah tebakan aturan dan **tidak** diklaim benar. Level 2 tidak menjadi label negatif. Untuk GOLD gunakan CSV berisi `pair_id` atau `record_bpn`/`record_pbb` atau `NIB`/`NOP`, `label` (0/1), `status_verifikasi=DIVERIFIKASI`, `sumber_verifikasi`, opsional `wilayah`. Bisa pula CSV fitur lengkap yang mengandung 18 fitur (lihat `engine.FEATURE_NAMES`) dan kolom label/verifikasi, atau layer historis BPN dan PBB berikut tabel pasangan berlabel. Untuk validasi yang bagus, data GOLD harus mencakup area/kelompok independen. **Data Level 2 tanpa label eksplisit 0 adalah belum pasti, bukan negatif.**

**Modul 5 (sejak v0.9.8):** selalu memerlukan model. Full AI memprediksi secara independen, Hybrid mengimpor baseline Modul 3 dari ZIP/CSV dengan pemeriksaan sidik-jari. SILVER Only menghasilkan usulan untuk studio; penambahan Level 1 otomatis memerlukan GOLD teruji, izin operator, batas skor evaluasi, keunikan identitas, margin skor, dan 1:1. Tidak ada gerbang deviasi luas atau overlap Modul 3 dalam keputusan AI. Model `.joblib` hanya boleh dimuat dari sumber terpercaya (format pickle dapat menjalankan kode Python saat dimuat).

**Modul 6:** tabel pasangan dipaginasi 200 baris; klik baris atau gunakan tombol klik bidang BPN di peta untuk menyorot calon pasangan dan memperbesar peta. Operator mengisi nama, sumber bukti, catatan, lalu klik **Cocok**, **Tidak cocok**, atau **Belum pasti**. CSV keputusan disimpan setiap kali menekan tombol. Masukkan CSV hasil ini ke Modul 4 untuk menambah data GOLD (pastikan layer sama). Jika memilih CSV dari Modul 3/5, urutan record dalam layer harus tetap sama dengan ketika CSV dibuat.

## Pilihan penyimpanan

- **GeoPackage (.gpkg)**: rekomendasi utama karena mempertahankan nama kolom yang panjang.
- **GeoJSON (.geojson)**: pertukaran data; gunakan CRS dan tipe atribut dengan cermat.
- **Shapefile (.shp)**: kompatibilitas lama; **nama kolom dibatasi ~10 karakter** dan nama bisa dipotong/bertabrakan. Hindari terutama untuk output Level 1 dengan banyak field.
- Tiap modul: `laporan_modulX.pdf` berisi ringkasan, tabel, seluruh visualisasi utama, interpretasi, dan rekomendasi; `rekap_csv.zip` berisi semua rekap. Tool 4 juga menghasilkan `.joblib` dan `.json` karena kedua berkas diperlukan untuk inference (bukan laporan).

## Batasan dan QA yang perlu dilakukan

1. Semua luas dihitung dari CRS proyeksi **meter**; periksa kecocokan datum/zone EPSG. Selisih luas tertulis memakai nilai absolut, sedangkan kolom `persen_selisihL` bertanda (+/-) terhadap **luas tertulis**.
2. Gap hanya lubang tertutup dalam gabungan poligon BPN, bukan area luar. Sejak 0.9.6 gap disimpan di layer kandidat tersendiri (`bpn_kandidat_gap` / `04_kandidat_gap`) tanpa NIB dan **tidak** otomatis dianggap legal; pemaduan Modul 3 memakai bidang BPN sumber.
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
- `ai_matching.py` pemilihan mode, impor baseline Modul 3, dan penentuan usulan AI independen (dapat diuji tanpa QGIS)
- `storage.py` export layer/ZIP CSV/laporan PDF Qt
- `compat.py` dukungan PyQt/Qt5 dan Qt6


## Patch v0.9.1 — Pilihan kolom luas tertulis

- Memperbaiki dropdown luas BPN dan PBB kosong pada Modul 1–5 dan Verifikasi Studio.
- Semua field dari layer terpilih ditampilkan, termasuk Double/Integer dan numerik yang disimpan sebagai teks.
- Kolom umum `LUAS` pada BPN dan `D_LUAS` pada PBB dipilih otomatis jika tersedia.
- Pergantian layer menyegarkan dropdown; tidak ada perubahan algoritma pemaduan, hasil audit, atau data asli.
- Tutup seluruh dialog, nonaktifkan plugin lama, pasang ZIP v0.9.1, lalu restart QGIS untuk memuat kode baru.
