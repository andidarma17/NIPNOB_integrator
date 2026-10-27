# REPORT_SPEC.md — Spesifikasi isi laporan PDF per modul (v0.9.4)

Spesifikasi **konten dan kontrak data** tiap laporan. Gaya visual ada di [`DESIGN.md`](DESIGN.md).
Sumber: `reporting_full.py` (M1, 2, 3, 5, 6), `ai_pdf.py` (M4), `storage.py`.

Konvensi: halaman dihitung pada render sintetis (jumlah nyata bergantung pada data; tabel/grafik dapat melimpah ke halaman `LANJUTAN`).

## 0. Elemen bersama (M1, 2, 3, 5, 6)

| Urutan | Halaman | Fungsi `Report` |
|---|---|---|
| 1 | IKHTISAR DAN HASIL UTAMA | `intro(stats, notes, warning)` → judul laporan (13 pt), tabel indikator, "Metode dan parameter", "Batasan interpretasi" (merah) |
| 2…n−1 | GRAFIK / PETA / REKAP | `figpage` + `bar`/`histogram`/`scatter`/`xy_scatter` atau `start`+`map` atau tabel |
| n | KESIMPULAN DAN TINDAK LANJUT | `footer_recommendations(items, appendix)` → 3 rekomendasi bernomor, "Arsip hasil", "Catatan umum" |

Catatan umum (teks tetap di halaman terakhir): *"Penanda otomatis merupakan indikasi pemeriksaan, bukan bukti hukum atas status bidang atau kewajiban pajak. Konfirmasi menggunakan sumber administrasi resmi."*

Primitif yang tersedia: `text`, `sub`, `table(head, rows, widths, limit=26)`, `bar(labels, series, suffix, horizontal)`, `histogram(values)`, `scatter(values)`, `xy_scatter(pairs, xlabel, ylabel)`, `map(datasets, title, focus)`, `no_data(msg)`.

Setiap peta dilengkapi teks: *"Peta indikatif tanpa peta dasar. Koordinat mengikuti CRS layer; warna menunjukkan kategori QA. Periksa lokasi detail pada layer QGIS."*

---

## 1. Modul 1 — Pemeriksaan kelengkapan → `laporan_modul1.pdf`

**Fungsi:** `report1(folder, b_info, p_info, stats, tables, min_area, max_area)`
`b_info`, `p_info` = `(records, kolom_identitas, kolom_luas)`; `records[i]['a']` = atribut + `id_kosong`, `id_duplikat`, `luas_flag`.

**`stats` (kunci):** `BPN|PBB` + spasi + {`jumlah_record`, `identitas_kosong`, `record_duplikat`, `jumlah_identitas_duplikat`, `record_dengan_atribut_kosong`, `record_luas_bermasalah`, `jumlah_sel_kosong`}.

| Hal. | Judul | Isi | Data sumber | Empty state |
|---|---|---|---|---|
| 1 | Ikhtisar | Tabel indikator (maks 22 baris); metode: ambang luas `min–max m²`, duplikat mengabaikan kosong, luas teks boleh asal numerik; batasan: "luas di luar ambang perlu verifikasi; bukan otomatis salah" | `stats` | — |
| 2 | Grafik 1 – Ringkasan temuan | Bar berkelompok BPN/PBB × {Jumlah record, ID kosong, Record duplikat, Luas bermasalah}; catatan: gunakan jumlah record sebagai pembagi | `stats` | — |
| 3 | Grafik 2 – Jumlah kosong per kolom | Bar horizontal per `BPN - kolom` / `PBB - kolom` | hitung ulang dari `records` | — |
| 4 | Grafik 3 – Persentase kosong per kolom | idem, dalam % | idem | — |
| 5 | Grafik 4 – Histogram luas BPN | 30 bin, batas atas persentil ke-99; keterangan N, P99, jumlah ekstrem disembunyikan | `a[kolom_luas]` > 0 | "Luas numerik positif tidak tersedia." |
| 6 | Grafik 5 – Histogram luas PBB | idem | idem | idem |
| 7 | Grafik 6 – Scatter luas BPN | X = urutan record, Y = log10(luas) | idem | "Tidak ada nilai luas positif." |
| 8 | Grafik 7 – Scatter luas PBB | idem | idem | idem |
| 9 | Grafik 8 – Kategori masalah luas | Bar BPN/PBB × {Kosong/tidak numerik, Nol/negatif, Di bawah ambang, Di atas ambang} | `luas_flag` split `;` | — |
| 10 | Kesimpulan | 3 rekomendasi statis: periksa NIB/NOP kosong/duplikat; lengkapi luas tertulis (jangan ganti dengan luas geometri tanpa bukti); tinjau luas ekstrem (jangan hapus otomatis). Arsip: `rekap_csv.zip`, layer audit | — | — |

**Layer keluaran (bukan bagian PDF):** `bpn_audit_atribut`, `pbb_audit_atribut`.
**CSV (`rekap_csv.zip`):** `{bpn,pbb}_atribut_kosong.csv`, `_duplikat.csv`, `_luas_bermasalah.csv`, `_per_kolom_kosong.csv`.

---

## 2. Modul 2 — Kualitas spasial → `laporan_modul2.pdf`

**Fungsi:** `report2(folder, b_rows, p_rows, stats, notes, overlap_b, overlap_p, gaps)`

**`stats`:** `{bpn|pbb}_record_awal`, `_record_akhir`, `_geom_kosong`, `_geom_invalid`, `_geom_fixed`, `_overlap`, `_gap_baru`.

| Hal. | Judul | Isi | Empty state |
|---|---|---|---|
| 1 | Ikhtisar | Tabel indikator; catatan: CRS diperiksa, invalid diperbaiki bila mungkin, geometri kosong tidak direkonstruksi, gap = area kosong **tertutup**, overlap ditandai bukan dikoreksi + log. Batasan: *gap baru = kandidat, bukan NIB baru terverifikasi* | — |
| 2 | Grafik 1 – Indikator kualitas spasial | Bar BPN/PBB × {Geometri kosong, invalid, diperbaiki, Bidang overlap, Gap ditambahkan} | — |
| 3 | Peta 1 – Kualitas BPN | Bidang lain (`#b9cad7`), Overlap (`#cb564d`), Gap baru (`#e6a23a`) | "Tidak ada geometri…" |
| 4 | Peta 2 – Kualitas PBB | Bidang lain, Overlap | idem |
| 5 | Peta 3 – Perbaikan geometri | PBB lain vs invalid awal/fixed (`#df9353`) | idem |
| 6 | Peta 4 – Detail gap BPN | Zoom di sekitar gap terluas (margin 9× ukuran gap); teks: "Kandidat gap terbesar: X m²" | "Tidak ada poligon gap baru yang lolos ambang." |
| 7–8 | Rincian overlap dan gap | 3 tabel: overlap internal terbesar BPN (12), PBB (12), gap tertutup (18) — kolom `Record A`, `Record B`, `Luas irisan m2` / `ID`, `Luas m2`, `Ditambah` | tabel kosong (header saja) |
| 9 | Kesimpulan | validasi hasil perbaikan geometri (potensi perubahan batas); telaah konflik overlap vs dokumen resmi; verifikasi gap (tidak otomatis ber-NIB) | — |

**Layer keluaran:** `bpn_kualitas_spasial`, `pbb_kualitas_spasial` (kolom: `geom_kosong`, `geom_invalid`, `geom_fixed`, `overlap`, `bid_tambah`, `selisih_luas`, `persen_selisihL`, `gap_id`).
**CSV:** `{bpn,pbb}_overlap.csv`, `{bpn,pbb}_gap_tertutup.csv`.

---

## 3. Modul 3 — Penentuan level pemaduan berbasis aturan → `laporan_modul3.pdf`

**Fungsi:** `report3(folder, lev1, lev2b, lev2p, pairs, stats, notes, logs, bpn_all, pbb_all, gaps)`

`stats`: `Level 1`, `BPN Level 2`, `PBB Level 2`, `Pasangan beririsan`, `Kandidat > overlap`.
`pairs[i]` (kandidat): `NIB`, `NOP`, `overlap_bpn_pct`, `overlap_pbb_pct`, `kesamaan_luas_tulis`, `status` (LEVEL_1/LEVEL_2), `alasan`, sidik-jari input.

| Hal. | Judul | Isi | Empty state |
|---|---|---|---|
| 1 | Ikhtisar | Indikator; metode: input wajib layer **hasil perbaikan operator**, pemeriksaan dihitung ulang, ambang overlap `x%` terhadap luas BPN, 1 NIB/NOP = 1 padanan, ambang kesamaan luas. Batasan: **Level 2 bukan pasangan salah** | — |
| 2 | Grafik 1 – Distribusi level | Bar {Level 1, BPN Level 2, PBB Level 2} | — |
| 3 | Grafik 2 – Alasan Level 2 | Bar horizontal frekuensi kode alasan (maks 16) | "Tidak ada kategori." |
| 4 | Grafik 3 – Seleksi berdasarkan overlap | Histogram batas tetap `0-20-40-50-60-80-100 %`; catatan: ambang aktual mengikuti parameter operator | — |
| 5 | Grafik 4 – Overlap vs kesamaan luas | Scatter XY 0–100 | "Data numerik berpasangan tidak tersedia." |
| 6 | Peta 1 – Level BPN | BPN Level 2 (`#d7e1e8`) vs Level 1 (`#328b73`) | — |
| 7 | Peta 2 – Level PBB | PBB Level 2 (satu warna) | — |
| 8 | Rekap pasangan | Tabel 20 pasangan overlap BPN terbesar: `NIB`, `NOP`, `Overlap BPN %`, `Overlap PBB %` | — |
| 9 | Kesimpulan | periksa hubungan 1:N/N:1; prioritaskan atribut kosong & kesamaan luas; gunakan output studio sebagai data label (Level 2 ≠ label 0) | — |

**Kode alasan Level 2** (`logic.gate_pair`): `NIB_KOSONG`, `NOP_KOSONG`, `NIB_DUPLIKAT`, `NOP_DUPLIKAT`, `LUAS_BPN_TIDAK_SESUAI`, `LUAS_PBB_TIDAK_SESUAI`, `LUAS_TERTULIS_TIDAK_SAMA`, `OVERLAP_KURANG`, `MULTI_NOP`, `TANPA_NOP`, `MULTI_NIB`, `TANPA_NIB`, `TIDAK_ADA_IRISAN`.
Kode ini muncul mentah di grafik → pertimbangkan label manusiawi.

**Layer keluaran:** `01_padanan_level1`, `02_bpn_level2`, `03_pbb_level2`. **File:** `manifest_modul3.json` (sha256 kedua layer). **CSV:** `pasangan_kandidat.csv`, `overlap_bpn.csv`, `overlap_pbb.csv`, `kandidat_gap.csv`, `alasan_level2.csv`.

---

## 4. Modul 4 — Training AI → `laporan_modul4.pdf` (renderer `ai_pdf.Canvas`)

**Fungsi:** `make_training_report(output_dir, evaldata, notes=None, summary=None)`
`evaldata` = isi `evaluasi_testing_ai.json`.

| Hal. | Judul (Title Case) | Isi |
|---|---|---|
| 1 | Laporan Evaluasi Training AI | Kotak **STATUS** (`status_operasional`; kotak *caution* bila GOLD test tak ada); tabel Ringkasan proses (model terpilih, jumlah GOLD/SILVER/FIT/Validasi/Testing, ambang 0,9, target precision 99%); "Cara membaca laporan"; catatan: R²/MAE/RMSE tidak dipakai |
| 2 | Metrik model | Per model (RandomForest, XGBoost bila terpasang): tabel TRAIN/VALIDATION/TEST × n, Precision, Recall, F1, Accuracy, ROC-AUC, AP; baris TEST: prediksi positif, FP, FN, Brier vs baseline, CI95 bawah. Tanpa TEST → kotak peringatan |
| 3 | Penilaian Otomatis per Metrik | Tabel `Metrik / Hasil TEST / Patokan operator / Interpretasi` (8 metrik); kotak peringatan. Tanpa GOLD → "BELUM DAPAT DINILAI" |
| 4 | Confusion Matrix (GOLD testing) | 2×2 per model + FP/FN + legenda TP/TN/FP/FN. Tanpa TEST → catatan |
| 5 | Kurva ROC dan Precision-Recall | 2 plot 370 px; PR dengan garis baseline = prevalensi. **Hanya jika TEST ada** |
| 6 | Kalibrasi dan fitur penting | Plot kalibrasi + 10 bar feature importance. **Hanya jika TEST ada** |
| 7 | Panduan interpretasi metrik | 8 butir dari `evaluation.threshold_guidance()` (Precision ≥99% & CI95 ≥95%; Recall ≥80%; F1 ≥90%; Accuracy > baseline mayoritas; ROC-AUC ≥0,90; AP ≫ prevalensi; Brier < baseline; jumlah GOLD ≥50 prediksi positif) |
| 8 | Rekomendasi Tindak Lanjut | Daftar dinamis `recommendations()`, "Pembatasan dan tindakan operator" (`catatan`), kotak kesimpulan |

**Output lain:** `model_terpilih.joblib`, `metadata_model.json`, `evaluasi_testing_ai.json`; CSV: `fitur_kandidat`, `silver_labels`, `gold_labels`, `template_verifikasi_operator`, `metrik_train_validation_test`, `feature_importance`, `panduan_ambang_metrik`, `penilaian_per_metrik`, `rekomendasi_model`.

**Aturan konten yang tidak boleh dilanggar desain:** tanpa GOLD independen, **jangan** tampilkan angka TEST; angka TRAIN tidak boleh disajikan sebagai kinerja.

---

## 5. Modul 5 — Inference AI dan Level 1/2 → `laporan_modul5.pdf`

**Fungsi:** `report5(folder, lev1, lev2b, lev2p, pairs, scores, extras, stats, notes, model_meta, logs)`
`stats`: `Level 1`, `Level 1 baru dari AI`, `BPN Level 2`, `PBB Level 2`, `Status AI`, `Kandidat AI berskor`.

| Hal. | Judul | Isi | Empty state |
|---|---|---|---|
| 1 | Ikhtisar | Indikator; catatan: baseline Modul 3 dipertahankan, AI tanpa GOLD = rekomendasi studio saja, ambang skor & selisih, 1 NIB : 1 NOP. Batasan: skor tinggi ≠ bukti kecocokan administratif | — |
| 2 | Grafik 1 – Hasil klasifikasi | Bar {Level 1 aturan, Level 1 baru AI, BPN L2, PBB L2} | — |
| 3 | Grafik 2 – Distribusi skor AI | Histogram 10 bin 0–1 | "Model belum dipilih atau skor AI tidak tersedia." |
| 4 | Peta 1 – Level 1 dan BPN studio | L2 vs L1 | — |
| 5 | Peta 2 – PBB studio | PBB L2 | — |
| 6 | Daftar rekomendasi inference | Tabel 25 skor tertinggi: `NIB`, `NOP`, `Skor`, `Keputusan` (`DITERIMA_LEVEL1` / `REKOMENDASI_STUDIO`); "Status pengujian model": `algorithm`, `status`, `precision`, `model_version`, `test_data_source` | — |
| 7 | Kesimpulan | pertahankan 1:1; periksa skor & pesaing dekat; evaluasi GOLD independen | — |

**Gerbang promosi AI → Level 1** (`dialogs.run5`): status model `GOLD_TESTED_REVIEW_REQUIRED` + checkbox promosi + skor ≥ `confidence` + margin vs pesaing ≥ `margin` + ID unik + bebas overlap internal + deviasi luas ≤ ambang + tak ada pesaing ≥ confidence. Laporan idealnya menunjukkan **gerbang mana yang gagal** per kandidat (belum ada).

**Layer keluaran:** `01_padanan_level1`, `02_bpn_level2`, `03_pbb_level2`. **CSV:** `skor_kandidat.csv`, `pasangan_rule.csv`, `tambahan_ai.csv`.

---

## 6. Modul 6 — Verifikasi studio → `laporan_modul6.pdf` (+ `rekap_verifikasi.zip`)

Dipicu tombol Ekspor di dock (`studio.py`).
**Fungsi:** `report6(folder, decisions, candidates, bpn_rows=None, pbb_rows=None, notes=None)`
`decisions[i]`: `pair_id`, `record_bpn`, `record_pbb`, `NIB`, `NOP`, `label` (`'1'`/`'0'`/kosong), `status_verifikasi`, `sumber_verifikasi`, `operator`, `catatan`, `waktu`.

| Hal. | Judul | Isi | Empty state |
|---|---|---|---|
| 1 | Ikhtisar | Indikator: Kandidat tersedia, Keputusan tercatat, Cocok (GOLD+), Tidak cocok (GOLD−), Belum pasti. Batasan: Level 2/belum pasti ≠ label 0 | — |
| 2 | Grafik 1 – Status keputusan studio | Bar {Cocok (1), Tidak cocok (0), Belum pasti} | — |
| 3 | Peta – Pasangan yang diverifikasi | BPN diverifikasi (`#267c68`), PBB diverifikasi (`#d58b43`) | "Layer sumber tidak tersedia saat PDF diekspor." |
| 4 | Tabel keputusan operator | `NIB`, `NOP`, `Label`, `Sumber bukti` — **maks. 30 baris**; kolom operator/waktu/catatan **tidak tampil** | — |
| 5 | Kesimpulan | lengkapi bukti; prioritaskan pasangan meragukan; masukkan ke Modul 4 (jangan jadikan "belum pasti" negatif) | — |

Peringatan kebijakan: label 1/0 mensyaratkan identitas operator + sumber bukti; contoh data bertanda `SINTETIS/DEMO` ditolak sebagai GOLD.
