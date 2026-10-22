# DOMAIN_RULES.md — Aturan bisnis, ambang, dan glosarium

Sumber: `logic.py`, `engine.py`, `ml.py`, `evaluation.py`, `README.md`. Semua ambang dapat diubah operator kecuali yang tertulis tetap di kode.

## 1. Aturan pemaduan Level 1 (`logic.gate_pair`)

Sebuah pasangan (BPN *i*, PBB *j*) menjadi **Level 1** hanya bila **tidak ada** satupun alasan berikut (semua alasan dilaporkan, bukan hanya yang pertama):

| Kode alasan | Kondisi gagal |
|---|---|
| `NIB_KOSONG` / `NOP_KOSONG` | Identitas kosong |
| `NIB_DUPLIKAT` / `NOP_DUPLIKAT` | Nilai identitas muncul > 1 kali di layer |
| `LUAS_BPN_TIDAK_SESUAI` | Deviasi luas tertulis vs geometri BPN > `max_dev` (50 %) atau tak bisa dihitung |
| `LUAS_PBB_TIDAK_SESUAI` | idem untuk PBB |
| `LUAS_TERTULIS_TIDAK_SAMA` | Kesamaan luas tertulis ≤ `min_sim` (90 %) atau tak bisa dihitung |
| `OVERLAP_KURANG` | Irisan / luas BPN ≤ `min_overlap` (50 %) |
| `MULTI_NOP` / `TANPA_NOP` | BPN punya ≠ 1 calon PBB di atas ambang |
| `MULTI_NIB` / `TANPA_NIB` | PBB punya ≠ 1 calon BPN di atas ambang |
| `TIDAK_ADA_IRISAN` | (record Level 2) tanpa kandidat beririsan |

Rumus: `deviasi % = 100·|tertulis − luas_geom| / luas_geom`; `kesamaan % = 100·min(a,b)/max(a,b)`; `overlap_bpn % = 100·irisan/luas_BPN`.
Ambang sama (`50.0 %` tepat) **tidak lolos**. Irisan kecil-kecil tidak otomatis menggugurkan bila hanya satu calon di atas ambang; dua calon di atas ambang **wajib** Level 2.

**Level 2** = butuh verifikasi studio. *Bukan* pasangan salah dan *bukan* label negatif.

## 2. Label untuk AI

| Jenis | Sumber | Bobot | Syarat sah |
|---|---|---|---|
| **GOLD** | Operator (Modul 6/CSV) | 1,0 | `label ∈ {0,1}` (atau `level=LEVEL 1` + diverifikasi), `status_verifikasi=DIVERIFIKASI`, `sumber_verifikasi` terisi, bukan `SINTETIS/SYNTHETIC/DEMO`, bukan teks "data sintetis / synthetic sample / model demo" |
| **SILVER** | Hasil aturan Modul 3 (positif) + kontras (negatif: overlap < 20 % kedua arah & IoU < 0,10 terhadap pasangan yang sudah diterima) | 0,2 | Hanya untuk fit, **tidak** untuk evaluasi |
| Tidak pasti | Level 2 / `belum pasti` | — | Tidak pernah menjadi 0 |

## 3. Fitur model (18; `engine.FEATURE_NAMES`, versi `QGIS_PLUGIN_V1`)

`overlap_bpn_pct, overlap_pbb_pct, iou, kesamaan_luas_geom, kesamaan_luas_tulis, deviasi_luas_bpn, deviasi_luas_pbb, jarak_centroid, jarak_geometri, kesamaan_bentuk, bpn_luas_kosong, pbb_luas_kosong, bpn_invalid, pbb_invalid, bpn_internal_overlap, pbb_internal_overlap, jumlah_calon_radius_bpn, jumlah_calon_radius_pbb`.
Fitur turunan label atau keputusan Modul 3 tidak boleh dipakai sebagai prediktor.

## 4. Evaluasi model (`evaluation.py`) — panduan kebijakan, bukan standar ilmiah/hukum

| Metrik | Panduan |
|---|---|
| Precision | ≥ 99 % pada GOLD test; batas bawah Wilson CI95 ≥ 95 % |
| Recall | ≥ 80 % |
| F1 | ≥ 90 % (bukan satu-satunya ukuran) |
| Accuracy | > baseline kelas mayoritas |
| ROC-AUC | ≥ 0,90; 0,50 ≈ acak |
| Average Precision | ≫ prevalensi positif |
| Brier | < baseline `prevalensi·(1−prevalensi)` |
| Jumlah GOLD | ≥ 50 prediksi positif; dua kelas; lintas kelompok spasial |
| Tidak dipakai | R², MAE, RMSE (tugas klasifikasi) |

Verdict operasional (`operational_assessment`): `BELUM DAPAT DINILAI` → `BELUM LAYAK` → `PERLU PERBAIKAN / VERIFIKASI TAMBAHAN` → `LAYAK MASUK PENINJAUAN OPERASIONAL - belum otomatis disetujui` (precision ≥ target, CI95 ≥ 95 %, recall ≥ 80 %, ≥ 50 prediksi positif). **Tidak ada status "disetujui otomatis".**

## 4b. Status model (`logic.model_status` / `ml.train_model`)

`NO_MODEL` (Modul 5 tanpa model) · `PREVIEW_ONLY` (default) · `GOLD_TESTED_REVIEW_REQUIRED` (satu-satunya yang boleh menambah Level 1, bila checkbox promosi aktif) · (`ELIGIBLE_REVIEW` di `logic.model_status`, fungsi pembantu).

## 5. Glosarium

| Istilah | Arti |
|---|---|
| NIB | Nomor Identifikasi Bidang tanah (BPN) |
| NOP | Nomor Objek Pajak PBB |
| BPN / PBB | Badan Pertanahan Nasional / Pajak Bumi dan Bangunan |
| Bidang | Satu poligon persil |
| Overlap | Irisan antar poligon; *internal* (dalam satu layer) vs *antar-sumber* (BPN×PBB) |
| Gap | Lubang tertutup pada gabungan poligon BPN; kandidat bidang tambahan |
| Fix geometry | `makeValid` pada poligon invalid |
| IoU | Irisan / gabungan luas |
| Studio | Verifikasi manual pasangan di peta |
| FP / FN | False positive (pasangan salah diterima — risiko utama) / false negative |
| Wilson CI | Selang kepercayaan binomial untuk Precision |
| Drift | Perubahan distribusi data yang menurunkan kinerja model |
