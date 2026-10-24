# DATA_SCHEMA.md — Berkas keluaran, skema CSV, dan kosakata status

## 1. Berkas keluaran per modul

| Modul | Layer spasial | File lain |
|---|---|---|
| 1 | `bpn_audit_atribut`, `pbb_audit_atribut` | `laporan_modul1.pdf`, `rekap_csv.zip` |
| 2 | `bpn_kualitas_spasial`, `pbb_kualitas_spasial` | `laporan_modul2.pdf`, `rekap_csv.zip` |
| 3 | `01_padanan_level1`, `02_bpn_level2`, `03_pbb_level2` | `laporan_modul3.pdf`, `rekap_csv.zip`, `manifest_modul3.json` |
| 3.1 | `01_padanan_level1`, `02_bpn_level2`, `03_pbb_level2` (titik) | `laporan_modul3_1.pdf`, `rekap_csv.zip`, `manifest_modul3_1.json` |
| 4 | — | `model_terpilih.joblib`, `metadata_model.json`, `evaluasi_testing_ai.json`, `laporan_modul4.pdf`, `rekap_csv.zip` |
| 5 | `01_padanan_level1`, `02_bpn_level2`, `03_pbb_level2` | `laporan_modul5.pdf`, `rekap_csv.zip` |
| 6 | — | `verifikasi_studio.csv`, `laporan_modul6.pdf`, `rekap_verifikasi.zip` |

Penamaan: bila file sudah ada, layer baru diberi sufiks `__run2`, `__run3`… (tidak menimpa). CSV memakai UTF-8 **dengan BOM**. Kolom CSV diurutkan alfabet. `rekap_csv.zip` memuat `keterangan = Tidak ada temuan` bila tabel kosong.

## 2. Kolom QA yang ditambahkan (`engine.QA_COLUMNS`)

`geom_kosong, geom_invalid, geom_fixed, overlap, bid_tambah, selisih_luas, persen_selisihL, id_kosong, id_duplikat, luas_flag, level, kode_l2, alasan_l2, calon_n, calon_id, skor_ai, metode_padu, nop_padanan, skor_nama, valid_nama, kekuatan, calon_nama, skor_gabungan`

v0.9.5: Level 1 menambah `skor_nama`, `valid_nama`, `kekuatan` (`overlap_pct` kosong untuk PBB titik); Level 2 menambah `calon_nama`. Layer PBB titik disimpan sebagai MultiPoint.
v0.9.6 (tahap 2): Level 1 dan Level 2 menambah `skor_gabungan` (Level 2: skor kandidat tahap 2 terbaik); padanan tahap 2 bermetode `RULE_NAMA`.
(dibuang saat membaca layer agar QA lama tidak terbawa; `persen_selisihL` bertanda ±, terhadap luas **tertulis**).

## 3. Skema CSV penting

**`pasangan_kandidat.csv` / `skor_kandidat.csv` / `fitur_kandidat.csv`**
`pair_id` (`B%06d_P%06d`), `record_bpn`, `record_pbb`, `NIB`, `NOP`, `irisan_m2`, `overlap_bpn_pct`, `overlap_pbb_pct`, `iou`, `area_bpn_geom`, `area_pbb_geom`, + 18 fitur (lihat `DOMAIN_RULES.md` §3), `x_bpn`, `y_bpn`, `mode_geom` (`POLIGON`/`TITIK`), `titik_di_dalam` (1/0; kosong untuk poligon), `skor_nama`, `valid_nama`; M3 tambah `status` (`LEVEL_1`/`LEVEL_2`), `alasan` (`;`), `kekuatan`, `src_bpn_sha`, `src_pbb_sha`; tahap 2 tambah `skor_spasial`, `skor_gabungan`, `alasan_tahap2`, `metode_padu` (`RULE_NAMA` bila lolos); M5 tambah `skor_ai`, `keputusan_ai`.

**Label operator / GOLD (`verifikasi_studio.csv`, `template_verifikasi_operator.csv`)**
`pair_id, record_bpn, record_pbb, NIB, NOP, label (1|0|kosong), status_verifikasi (DIVERIFIKASI), sumber_verifikasi, operator, catatan, waktu` (+ opsional `wilayah` untuk pengelompokan split, `jenis_data`).

**`gold_labels.csv`**: kandidat + `label`, `label_source` (`GOLD_OPERATOR`, `GOLD_HISTORICAL`, `GOLD_HISTORICAL_GEO`), `sample_weight`, `sumber_verifikasi`, `group_id`.
**`silver_labels.csv`**: `label_source` `SILVER_RULE` (1) / `SILVER_CONTRAST` (0), `sample_weight=0.2`.

**Modul 1**: `*_atribut_kosong.csv` (`record, id, kolom_kosong`), `*_duplikat.csv` (`record, id, jumlah`), `*_luas_bermasalah.csv` (`record, id, luas, masalah`), `*_per_kolom_kosong.csv` (`nama_kolom, jumlah_kosong, persentase`).
**Modul 2**: `*_overlap.csv` (`record_a, record_b, luas_irisan_m2`), `*_gap_tertutup.csv` (`gap_id, luas_m2, ditambahkan`).
**Modul 4**: `metrik_train_validation_test.csv` (`algoritma, split, status_acuan, n, positif, …, precision, recall, f1, …`), `feature_importance.csv` (`algoritma, fitur, importance`), `panduan_ambang_metrik.csv` (`nama, panduan, alasan`), `penilaian_per_metrik.csv` (`metrik, nilai, patokan, interpretasi`), `rekomendasi_model.csv` (`urutan, rekomendasi`).

## 4. `evaluasi_testing_ai.json` (masukan `make_training_report`)

```
judul, jenis="BINARY_CLASSIFICATION", evaluasi_gold_tersedia (bool), model_terpilih,
metode_pemilihan, ambang_prediksi (0.90), target_precision_usulan,
jumlah_silver, jumlah_gold, jumlah_fit, jumlah_validasi, jumlah_testing,
status_operasional, rekomendasi[str], penilaian_per_metrik[{metrik,nilai,patokan,interpretasi}],
models{ <algoritma>: { split{TRAIN|VALIDATION|TEST: metrik}, feature_importance[{fitur,importance}] } },
catatan[str]
```
Metrik per split: `n, positif, negatif, prevalensi, threshold, tp, tn, fp, fn, confusion_matrix[[tn,fp],[fn,tp]], prediksi_positif, precision, precision_ci95_bawah, recall, f1, accuracy, balanced_accuracy, specificity, accuracy_baseline_kelas_mayoritas, brier, brier_baseline_prevalensi, auc_roc, average_precision, status_acuan`; hanya TEST: `kurva{roc{x,y}, pr{x,y}, kalibrasi{x,y}}` (≤101 titik; kalibrasi 8 bin kuantil).
`status_acuan`: `GOLD_INDEPENDEN` (VALIDATION/TEST) atau `TRAIN_CAMPURAN_GOLD_SILVER_TIDAK_INDEPENDEN`.

## 5. `metadata_model.json`

`status, feature_version="QGIS_PLUGIN_V1", features[18], mode_geometri_pbb (POLIGON|TITIK; tidak ada = POLIGON), algorithm, n_silver, n_gold, n_training, n_validation, n_testing, target_precision, holdout{…}, threshold, evaluation_file, note`.

## 6. Kosakata status & label (untuk desain — harus bisa ditampilkan)

| Konteks | Nilai |
|---|---|
| Level pasangan | `LEVEL_1`, `LEVEL_2`; metode: `RULE`, `RULE_NAMA` (tahap 2), `AI_VERIFIED` |
| Keputusan AI (M5) | `DITERIMA_LEVEL1`, `REKOMENDASI_STUDIO` |
| Status model | `NO_MODEL`, `PREVIEW_ONLY`, `GOLD_TESTED_REVIEW_REQUIRED` |
| Verdict operasional (M4) | `BELUM DAPAT DINILAI`, `BELUM LAYAK`, `PERLU PERBAIKAN / VERIFIKASI TAMBAHAN`, `LAYAK MASUK PENINJAUAN OPERASIONAL` |
| Interpretasi metrik (M4) | `TARGET TERCAPAI`, `SAMPEL BELUM KUAT`, `DI BAWAH TARGET`, `MEMADAI`, `TAMBAH GOLD`, `PERLU PERBAIKAN`, `LEBIH BAIK BASELINE`, `DI ATAS BASELINE` |
| Keputusan studio (M6) | `1` Cocok, `0` Tidak cocok, kosong = Belum pasti |
| Flag luas (M1) | `LUAS_KOSONG_ATAU_NONNUMERIK`, `LUAS_NOL_NEGATIF`, `LUAS_KECIL`, `LUAS_BESAR` |
| Alasan Level 2 (M3) | lihat `DOMAIN_RULES.md` §1 |
| Kandidat gap | `bid_tambah=1`, `gap_id=GAPnnnnn` |
| Validasi nama | `COCOK`, `MIRIP`, `TIDAK_COCOK`, `TIDAK_DINILAI` |
| Kekuatan Level 1 | `KUAT`, `SEDANG`, `LEMAH` |
| Mode geometri PBB | `POLIGON`, `TITIK` |

Kode mentah (UPPER_SNAKE) saat ini bocor ke PDF; desain ulang perlu **label manusiawi** + pemetaan kode→label.
