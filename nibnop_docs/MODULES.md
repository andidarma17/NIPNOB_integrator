# MODULES.md — Enam tools: input, parameter, proses, keluaran

Semua tool menerima **layer BPN** (poligon) dan **layer PBB** (poligon **atau titik NOP**, v0.9.5), CRS proyeksi **meter**, dengan dropdown layer + **semua field**: kolom identitas (NIB / NOP) dan kolom luas tertulis. Default otomatis: BPN `NIB`/`LUAS`, PBB `D_NOP`/`D_LUAS` (alternatif: `D_NIB, ID_BIDANG`; `NOP, NO_NOP`; `LUAS_TANAH, LUASTANAH, LUAS_TERDAFTAR, LAND_AREA, AREA`).
Opsi umum: *reproyeksikan PBB ke CRS BPN bila CRS berbeda* (jika tidak dicentang dan CRS berbeda → ditolak). CRS geografis (derajat) → ditolak.
Format keluaran layer: GeoPackage (disarankan) / GeoJSON / Shapefile (peringatan nama kolom 10 karakter). Folder bawaan: `~/NIBNOP_HASIL/modul_N`.

---

## Modul 1 — Pemeriksaan kelengkapan

| | |
|---|---|
| Parameter | Luas minimum 5 m², maksimum 10 000 m² |
| Proses | Per layer: hitung record, ID kosong, duplikat, atribut kosong per kolom, luas kosong/non-numerik/nol-negatif/kecil/besar (`luas_flag`) |
| Kolom ditambahkan | `id_kosong`, `id_duplikat`, `luas_flag` |
| Keluaran | `bpn_audit_atribut`, `pbb_audit_atribut`, `laporan_modul1.pdf`, `rekap_csv.zip` |
| Catatan | Luas teks boleh bila numerik (koma desimal diterima); tidak mengubah data |

## Modul 2 — Kualitas spasial & fix geometry

| | |
|---|---|
| Parameter | Minimum luas overlap 0,01 m²; minimum gap 1 m²; centang delineasi gap BPN |
| Proses | Deteksi geometri kosong/invalid; `makeValid` (hanya poligon); overlap internal (irisan > ambang); **gap = lubang tertutup** pada gabungan BPN (maks 2 500; lebih dari itu → error); hitung `selisih_luas` & `persen_selisihL` (geometri vs tertulis) |
| Kolom ditambahkan | `geom_kosong`, `geom_invalid`, `geom_fixed`, `overlap`, `bid_tambah`, `selisih_luas`, `persen_selisihL`, `gap_id` |
| Keluaran | `bpn_kualitas_spasial`, `pbb_kualitas_spasial`, PDF, ZIP (`*_overlap.csv`, `*_gap_tertutup.csv`) |
| Catatan | Gap `bid_tambah=1`, tanpa NIB, **bukan otomatis legal**. Overlap ditandai, tidak dihapus. Setelah ini operator memperbaiki manual lalu menyimpan layer **baru** untuk Modul 3 |

## Modul 3 — Penentuan level pemaduan berbasis aturan

| | |
|---|---|
| Input | **Dua layer hasil koreksi operator** (bukan otomatis dari Modul 2) |
| Parameter | Irisan > **50 %** luas BPN; kesamaan luas tertulis > **90 %**; deviasi luas-geometri maks **50 %**; minimum irisan 0,01 m²; minimum gap 1 m² |
| Proses | Audit spasial ulang → kandidat (irisan > min) → `gate_pair` → Level 1 hanya bila **semua** gerbang lolos dan 1:1; sisanya Level 2 dengan kode alasan |
| Keluaran | `01_padanan_level1` (BPN + atribut PBB berawalan `pbb_`, `nop_padanan`, `metode_padu=RULE`, `overlap_pct`, `kesamaan_pct`), `02_bpn_level2`, `03_pbb_level2` (`level`, `calon_n`, `kode_l2`, `alasan_l2`, `calon_id`), `manifest_modul3.json`, PDF, ZIP |
| Catatan | Kesetaraan tepat pada ambang **tidak lolos** (`>` ketat). Hubungan 1:N dihitung dari calon **di atas ambang**, bukan total irisan kecil |
| Validasi nama (0.9.5) | Kolom nama opsional BPN/PBB → `skor_nama`, `valid_nama`, `kekuatan` (KUAT/SEDANG/LEMAH), `calon_nama`; opsi "Nama TIDAK COCOK → Level 2" (bawaan mati). Ambang nama COCOK 90 %, MIRIP 60 %. PBB berupa titik ditolak → gunakan Modul 3.1 |

## Modul 3.1 — Penentuan level pemaduan PBB titik (NOP) (0.9.5)

| | |
|---|---|
| Input | Layer BPN poligon + layer PBB **titik** (Point/MultiPoint) hasil koreksi operator; kolom nama opsional |
| Parameter | Kesamaan luas tertulis > **90 %**; deviasi luas maks **50 %**; toleransi titik di luar bidang **5 m**; minimum overlap internal BPN 0,01 m²; minimum gap 1 m²; nama COCOK 90 % / MIRIP 60 %; opsi "Nama TIDAK COCOK → Level 2" |
| Proses | Audit ulang (BPN: fix, overlap, gap; PBB: titik berimpit) → kandidat titik-bidang → gerbang identitas, keunikan 1:1, luas, **titik di dalam bidang** (menggantikan overlap) → validasi nama → kekuatan |
| Keluaran | `01_padanan_level1` (bidang BPN + atribut PBB, `overlap_pct` kosong), `02_bpn_level2`, `03_pbb_level2` (titik), `manifest_modul3_1.json`, `laporan_modul3_1.pdf`, ZIP (`pasangan_kandidat.csv`, `titik_berimpit_pbb.csv`, …) |
| Catatan | Deviasi luas PBB = luas tertulis PBB vs luas geometri BPN. Titik di luar bidang hanya calon Level 2 (`TITIK_DI_LUAR_BIDANG`). Bidang tanpa titik `TIDAK_ADA_TITIK`; titik jauh dari semua bidang `TITIK_DI_LUAR_SEMUA_BIDANG`. Padanan titik tanpa nama cocok berkekuatan paling tinggi SEDANG |

## Modul 4 — Training AI

| | |
|---|---|
| Input | Layer operator; CSV kandidat Modul 3 (silver, opsional, hash dicek); CSV fitur historis GOLD; CSV label operator; atau layer historis + CSV pasangan berlabel |
| Parameter | Radius kandidat 15 m; target precision 0,99 |
| Proses | Bangun kandidat (18 fitur); label **GOLD** (verifikasi manusia + bukti) dan **SILVER** (aturan; bobot 0,2); split GOLD berkelompok spasial (`GroupShuffleSplit`, tile 250 m / kolom `wilayah`) → train/validation/test; RandomForest (+ XGBoost bila ada); pilih model hanya dari **validation**; ambang prediksi 0,90 |
| Syarat split | GOLD ≥ 100, tiap kelas ≥ 20, ≥ 5 kelompok; selain itu **tanpa TEST** → "BELUM DAPAT DINILAI" |
| Status model | `GOLD_TESTED_REVIEW_REQUIRED` bila TEST precision ≥ target, ≥ 10 prediksi positif, validation ada, GOLD ≥ 100; selain itu `PREVIEW_ONLY` |
| Keluaran | `model_terpilih.joblib`, `metadata_model.json`, `evaluasi_testing_ai.json`, PDF, ZIP (9 CSV) |
| Catatan | Label Level 2 tanpa label eksplisit **bukan** negatif. Data bertanda SINTETIS/DEMO ditolak |

## Modul 5 — Inference AI dan Level 1/2

| | |
|---|---|
| Input | Layer operator; opsional model `.joblib` + metadata `.json` dari Modul 4 |
| Parameter | Aturan Modul 3 (50/90/50) + radius 15 m; skor minimum 0,95; selisih skor vs kandidat ke-2 0,15; checkbox "izinkan tambahan Level 1 berbasis AI" (default mati) |
| Proses | Baseline aturan (Modul 3) dipertahankan; skor AI semua kandidat; promosi ke Level 1 **hanya** bila status `GOLD_TESTED_REVIEW_REQUIRED` + checkbox + semua gerbang (skor, margin, ID unik, tanpa overlap, deviasi luas, tanpa pesaing kuat) |
| Keluaran | `01_padanan_level1` (`metode_padu=AI_VERIFIED` untuk tambahan, `skor_ai`), `02_bpn_level2`, `03_pbb_level2`, PDF, ZIP (`skor_kandidat.csv`, `pasangan_rule.csv`, `tambahan_ai.csv`) |
| Catatan | Tanpa model → hanya baseline. Model silver-only → hanya prioritas verifikasi |

## Modul 6 — Verifikasi Studio interaktif

| | |
|---|---|
| UI | Dock kanan: pilih layer & kolom, CSV kandidat (opsional) atau radius cari 15 m, tabel kandidat (200/halaman), klik bidang BPN di peta, zoom & sorot pasangan |
| Aksi | **Cocok (1)** / **Tidak cocok (0)** / **Belum pasti** + nama operator, sumber bukti, catatan; label 1/0 mewajibkan operator + bukti |
| Penyimpanan | `verifikasi_studio.csv` ditulis setiap keputusan (UTF-8 BOM) |
| Ekspor | `laporan_modul6.pdf`, `rekap_verifikasi.zip` |
| Catatan | Urutan record layer harus sama dengan saat CSV Modul 3/3.1/5 dibuat; CSV hasil dipakai Modul 4 sebagai GOLD |
