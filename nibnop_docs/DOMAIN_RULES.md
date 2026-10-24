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

### 1b. Modul 3.1 (PBB titik) dan validasi nama (v0.9.5)

Modul 3.1 dipakai bila layer PBB bertipe titik (`engine.point_mode`); Modul 3 menolak PBB titik. Aturan:

| Kode alasan | Kondisi gagal |
|---|---|
| `TITIK_DI_LUAR_BIDANG` | Titik NOP tidak berada di dalam/pada batas bidang BPN (menggantikan `OVERLAP_KURANG`); calon dibuat bila jarak ≤ `point_tol` (5 m) |
| `MULTI_NOP` / `MULTI_NIB` | > 1 titik di dalam satu bidang / titik di dalam > 1 bidang |
| `LUAS_PBB_TIDAK_SESUAI` | Deviasi luas tertulis PBB **terhadap luas geometri BPN** > `max_dev` |
| `TIDAK_ADA_TITIK` | (BPN Level 2) tidak ada titik di dalam/dekat bidang |
| `TITIK_DI_LUAR_SEMUA_BIDANG` | (PBB Level 2) titik tidak berada di/dekat bidang mana pun |

Validasi nama (opsional, `logic.name_similarity` / `name_status`): `valid_nama` = `COCOK` (≥ `name_match` 90 %), `MIRIP` (≥ `name_partial` 60 %), `TIDAK_COCOK`, `TIDAK_DINILAI`. Gerbang `NAMA_TIDAK_COCOK` hanya aktif bila `require_name` dicentang; `TIDAK_DINILAI` tidak pernah menggugurkan. `kekuatan` Level 1 (`logic.match_strength`): titik — COCOK→KUAT, MIRIP/TIDAK_DINILAI→SEDANG, TIDAK_COCOK→LEMAH; poligon — TIDAK_COCOK→SEDANG, lainnya KUAT.

Pengisian fitur untuk kandidat titik: `overlap_bpn_pct = overlap_pbb_pct = 100` (di dalam) atau `0`; `iou = 0`; `kesamaan_luas_geom` = luas tertulis PBB vs luas geometri BPN; `deviasi_luas_pbb` = luas tertulis PBB vs luas geometri BPN; `jarak_centroid` = centroid BPN → titik; `jarak_geometri` = jarak titik ke bidang (0 bila di dalam); `kesamaan_bentuk` kosong (diimputasi). Model mencatat `mode_geometri_pbb` (`POLIGON`/`TITIK`).

### 1c. Tahap 2 — buffer + skor gabungan nama (v0.9.6, Modul 3, 3.1 & 5)

Opsional (`opts['name_stage']`, checkbox *"Tahap 2: cari ulang padanan Level 2…"*), hanya bila kolom nama BPN dan PBB dipilih. Dijalankan **setelah** tahap 1 (aturan §1/§1b) di `engine.name_stage`; hasil tahap 1 tidak diubah.

1. Peserta: rekaman BPN/PBB yang **belum** Level 1 di tahap 1, dengan NIB/NOP terisi dan unik (`logic.STAGE2_BLOCKED`: `NIB_KOSONG`, `NOP_KOSONG`, `NIB_DUPLIKAT`, `NOP_DUPLIKAT` tidak pernah diselamatkan nama).
2. Kandidat: PBB yang beririsan/berada di dalam bidang BPN atau berjarak ≤ `stage2_buffer` (Modul 3 bawaan 5 m; Modul 3.1 memakai `point_tol`). Kandidat baru (tanpa irisan) ditambahkan ke `pasangan_kandidat.csv` dengan alasan `TIDAK_ADA_IRISAN` / `TITIK_DI_LUAR_BIDANG`.
3. Skor (`logic.spatial_score`, `logic.combined_score`):
   * `skor_spasial` = 100 bila beririsan / titik di dalam bidang, selain itu `100·(1 − jarak/buffer)`;
   * `skor_gabungan` = (`w_name`·`skor_nama` + `w_spatial`·`skor_spasial` + `w_area`·`kesamaan_luas_tulis`) / Σbobot; bawaan 0,60 / 0,25 / 0,15. Luas tak terbaca → 0. Nama tak dinilai → tanpa skor (tidak bisa lolos).
4. Lolos (`logic.select_stage2`) bila **semua**: `skor_gabungan ≥ stage2_min` (80), `skor_nama ≥ stage2_min_name` (60), kandidat terbaik bagi BPN **dan** PBB-nya, unggul ≥ `stage2_margin` (10 poin) dari kandidat ke-2 di kedua sisi. Alasan gagal di `alasan_tahap2`: `NAMA_TIDAK_DINILAI`, `SKOR_GABUNGAN_KURANG`, `SKOR_NAMA_KURANG`, `BUKAN_KANDIDAT_TERBAIK`, `SELISIH_SKOR_KURANG`.
5. Pasangan lolos → Level 1 dengan `metode_padu=RULE_NAMA`, `kekuatan` dinilai seperti titik (COCOK→KUAT, MIRIP→SEDANG). Rekaman Level 2 tersisa mendapat `skor_gabungan` kandidat terbaiknya sebagai prioritas studio.
6. Modul 5 menjalankan tahap 2 yang sama pada baseline aturannya (urutan: aturan → tahap 2 → promosi AI pada sisa); buffer Modul 5 punya parameter sendiri (bawaan 5 m).
7. Modul 4: pasangan `RULE_NAMA` dari CSV Modul 3 hanya menjadi SILVER bila dicentang, sebagai `SILVER_RULE_NAMA` dengan bobot sendiri (bawaan 0,1; SILVER aturan tetap 0,2).

**Level 2** = butuh verifikasi studio. *Bukan* pasangan salah dan *bukan* label negatif.

## 2. Label untuk AI

| Jenis | Sumber | Bobot | Syarat sah |
|---|---|---|---|
| **GOLD** | Operator (Modul 6/CSV) | 1,0 | `label ∈ {0,1}` (atau `level=LEVEL 1` + diverifikasi), `status_verifikasi=DIVERIFIKASI`, `sumber_verifikasi` terisi, bukan `SINTETIS/SYNTHETIC/DEMO`, bukan teks "data sintetis / synthetic sample / model demo" |
| **SILVER** | Hasil aturan Modul 3 (positif) + kontras (negatif: overlap < 20 % kedua arah & IoU < 0,10 terhadap pasangan yang sudah diterima) | 0,2 | Hanya untuk fit, **tidak** untuk evaluasi |
| **SILVER_RULE_NAMA** | Padanan tahap 2 Modul 3 (`metode_padu=RULE_NAMA`), opsional | bawaan 0,1 | Sama dengan SILVER |
| Tidak pasti | Level 2 / `belum pasti` | — | Tidak pernah menjadi 0 |

## 3. Fitur model (`engine.FEATURE_VERSIONS`)

* `QGIS_PLUGIN_V1` — 18 fitur (`engine.FEATURE_NAMES`), dipakai bila Modul 4 tanpa kolom nama.
* `QGIS_PLUGIN_V2` (v0.9.6) — 18 fitur + `skor_nama` (kosong → diimputasi median) dan `nama_tidak_dinilai` (1/0), dipakai bila Modul 4 diberi kolom nama BPN dan PBB. Model V2 di Modul 5 wajib diberi kolom nama; model V1 tetap dapat dipakai.

Fitur V1:

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
| Titik NOP | Lokasi objek pajak PBB tanpa poligon bidang |
| Validasi nama | Kesamaan nama pemegang hak (BPN) dan wajib pajak (PBB) sebagai penguat padanan |
| Overlap | Irisan antar poligon; *internal* (dalam satu layer) vs *antar-sumber* (BPN×PBB) |
| Gap | Lubang tertutup pada gabungan poligon BPN; kandidat bidang tambahan |
| Fix geometry | `makeValid` pada poligon invalid |
| IoU | Irisan / gabungan luas |
| Studio | Verifikasi manual pasangan di peta |
| FP / FN | False positive (pasangan salah diterima — risiko utama) / false negative |
| Wilson CI | Selang kepercayaan binomial untuk Precision |
| Drift | Perubahan distribusi data yang menurunkan kinerja model |
