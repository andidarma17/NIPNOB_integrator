# ARCHITECTURE.md — Arsitektur plugin NIB–NOP Integrator v0.9.4

## 1. Struktur paket

```
nibnop_integrator/                 ≈ 3.150 baris (Python) + dokumen
├── __init__.py                    classFactory → NibNopPlugin
├── metadata.txt                   QGIS min 3.28 / max 4.99, experimental=True, kategori Vector
├── plugin.py          (46)        Menu "NIB–NOP Integrator" + Vector menu, 6 aksi; modul 6 = QDockWidget
├── dialogs.py        (456)        ToolDialog untuk Modul 1–5 (UI + orkestrasi run1…run5)
├── studio.py         (263)        VerificationDock (Modul 6, dock kanan, klik peta)
├── fieldwidgets.py   (104)        LayerFieldComboBox: dropdown SEMUA field + default (NIB/LUAS, D_NOP/D_LUAS)
├── engine.py         (385)        Algoritma native PyQGIS: baca, fix geometri, overlap, gap, kandidat, level
├── logic.py           (83)        Aturan murni tanpa QGIS (gate_pair, label GOLD, status model) — unit-testable
├── ml.py             (302)        Label GOLD/SILVER, split berkelompok spasial, training, predict
├── evaluation.py     (168)        Metrik, Wilson CI, panduan ambang, rekomendasi (tanpa QGIS; butuh sklearn)
├── storage.py        (127)        Simpan layer (GPKG/GeoJSON/SHP), ZIP CSV, PDF legacy
├── reporting_full.py (520)        Laporan PDF M1, 2, 3, 5, 6  ← desain ulang di sini
├── ai_pdf.py         (262)        Laporan PDF M4              ← desain ulang di sini
├── compat.py          (41)        Shim Qt5/Qt6 (QVariant/QMetaType, QAction, set_pdf_a4)
├── tests/                         test_logic, test_evaluation, test_fieldwidgets (tanpa QGIS)
├── README.md, ACCEPTANCE_TEST.md, PERUBAHAN_V0_9_{2,3,4}.txt, PERBAIKAN_PDF_MACOS.txt
├── PANDUAN_PENGGUNA.pdf (3 hlm, ReportLab/Lato)
└── contoh_label_operator.csv      Contoh CSV GOLD (bertanda SINTETIS → ditolak otomatis)
```

## 2. Lapisan

```
 UI              plugin.py ─► dialogs.ToolDialog (M1–5)      studio.VerificationDock (M6)
                         └── fieldwidgets.LayerFieldComboBox
 Orkestrasi      dialogs.run1..run5            studio.export
 Domain/Algoritma engine.py (PyQGIS)  ─ logic.py (murni) ─ ml.py + evaluation.py (sklearn)
 Keluaran        storage.py (layer, ZIP CSV)  reporting_full.py / ai_pdf.py (PDF via Qt)
 Kompat          compat.py (Qt5/Qt6, QGIS 3/4)
```

Prinsip: layer sumber operator **tidak pernah dimutasi**. Semua perhitungan pada salinan `records` (`{'idx','fid','a':atribut,'geom':QgsGeometry}`); `idx` 1-basis stabil selama satu eksekusi.

## 3. Alur data antarmodul

```
 BPN + PBB (poligon, CRS meter)
   │
   ├─► M1 audit atribut ──────────► laporan_modul1.pdf, *_audit_atribut, rekap_csv.zip
   ├─► M2 fix+overlap+gap ────────► laporan_modul2.pdf, *_kualitas_spasial
   │        │ (operator MEMPERBAIKI manual di QGIS → layer BARU)
   │        ▼
   ├─► M3 aturan Level 1/2 ───────► 01/02/03 layer, pasangan_kandidat.csv (+sha256), manifest_modul3.json, PDF
   │        │ silver (opsional, hash dicek)
   │        ▼
   ├─► M6 studio (label manual) ──► verifikasi_studio.csv  (GOLD: label 1/0 + bukti)
   │        ▼
   ├─► M4 training ───────────────► model_terpilih.joblib, metadata_model.json, evaluasi_testing_ai.json, PDF
   │        ▼
   └─► M5 inference ──────────────► 01/02/03 layer (+ skor_ai), skor_kandidat.csv, PDF
```

* Modul 3 **harus dijalankan ulang** pada layer hasil perbaikan operator; ia membuang penanda QA lama (`QA_COLUMNS`) dan menghitung ulang.
* Modul 4 menolak CSV silver bila `src_bpn_sha`/`src_pbb_sha` tidak cocok dengan layer sekarang (`layer_fingerprint` = SHA-256 CRS+field+ID+WKB+atribut).
* Modul 5 memuat `.joblib` (pickle) → **hanya dari sumber tepercaya**.

## 4. Pemetaan fungsi pembuat laporan → dialog

| Modul | Dipanggil dari | Fungsi laporan | Berkas |
|---|---|---|---|
| 1 | `dialogs.run1` | `reporting_full.report1` | `laporan_modul1.pdf` |
| 2 | `dialogs.run2` | `report2` | `laporan_modul2.pdf` |
| 3 | `dialogs.run3` | `report3` | `laporan_modul3.pdf` |
| 4 | `dialogs.run4` | `ai_pdf.make_training_report` (setelah `storage.complete_report` yang membuat PDF legacy lalu **ditimpa**) | `laporan_modul4.pdf` |
| 5 | `dialogs.run5` | `report5` | `laporan_modul5.pdf` |
| 6 | `studio.export` | `report6` | `laporan_modul6.pdf`, `rekap_verifikasi.zip` |

Kontrak parameter: [`REPORT_SPEC.md`](REPORT_SPEC.md).

## 5. Ketergantungan

| Lapisan | Dependensi |
|---|---|
| Modul 1–3, 6 + semua PDF | PyQGIS, Qt (`qgis.PyQt`) saja. Tak perlu geopandas/shapely/reportlab/matplotlib |
| Modul 4–5 | `numpy`, `scikit-learn`, `joblib`; opsional `xgboost` (dipasang di Python **yang dipakai QGIS**) |
| Uji unit | `unittest`; `test_evaluation` butuh scikit-learn |

## 6. Kompatibilitas QGIS 3 / 4 (`compat.py`)

* `QgsField` tipe: `QVariant` (< 3.38) vs `QMetaType.Type` (≥ 3.38/4).
* `QAction`: `QtGui` (Qt6) vs `QtWidgets` (Qt5).
* PDF A4: `pageLayout().setPageSize(QPageSize(...))` + `setPageLayout` — perbaikan error `setPageSize … QPageSize` pada Qt 5.15 (`PERBAIKAN_PDF_MACOS.txt`).
* Enum Qt6 berkualifikasi (`Qt.ItemDataRole.UserRole`, `QPageSize.PageSizeId.A4`).
* Belum diuji langsung pada QGIS 4/Qt6.

## 7. Titik ekstensi untuk desain ulang laporan

* Semua pembuatan PDF terpusat di `Report`, `Canvas` → ganti implementasi tanpa mengubah tanda tangan `reportN`.
* Pilihan renderer (QPainter vs QTextDocument vs WebEngine): lihat `DESIGN.md` §8.
* Jangan ubah isi `stats`/`tables`/`records` dari `dialogs.py` kecuali diperlukan; itu juga isi `rekap_csv.zip`.
* Simpan token di satu modul (mis. `report_theme.py`) yang diimpor oleh kedua renderer.
