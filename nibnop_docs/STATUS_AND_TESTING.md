# STATUS_AND_TESTING.md — Status kematangan, pengujian, dan catatan teknis

## 1. Status

| Aspek | Status |
|---|---|
| Versi | 0.9.4 (beta, `experimental=True`); paket ini adalah **patch lokal "MACOS_PDF_FIX"** (22 Okt 2026) di atas rilis 0.9.4 — versi metadata tidak berubah |
| Target QGIS | 3.28–3.44 (Qt5) dan 4.0–4.2 (Qt6); `qgisMaximumVersion=4.99` |
| Teruji nyata | QGIS-LTR 3.40.5 macOS, Python 3.9.5, Qt 5.15.2: PDF modul 1, 2, 3, 5, 6 (data sintetis), kanvas modul 4, pembuat laporan storage |
| **Belum** teruji | QGIS 4/Qt6; GUI interaktif lintas versi; training AI penuh di QGIS; data besar (1 000–10 000 poligon); Windows |
| Peringatan pengembang | **Jangan dipakai tanpa pengawasan pada data pajak/pertanahan produksi.** Hasil = alat bantu, bukan bukti hukum |

## 2. Hasil pemeriksaan paket ini (sesi ini)

| Pemeriksaan | Hasil |
|---|---|
| Ekstrak ZIP | 25 berkas, 288 KB; tidak ada berkas aneh/biner selain `PANDUAN_PENGGUNA.pdf` |
| `py_compile` semua `.py` | OK |
| Unit test (`test_logic`, `test_evaluation`, `test_fieldwidgets`) | **11 tes lulus** (dijalankan pada salinan, Python 3.13 + scikit-learn) |
| Render PDF headless (PyQt5 5.15.11, data sintetis) | Modul 1, 2, 3, 4, 5, 6 berhasil; font tersemat: DejaVu Sans & Bold |
| Ukuran halaman terukur | 958 × 1369 px @120 dpi (A4, margin Qt ±3,6 mm) |
| Tidak dijalankan | GUI QGIS, algoritma `engine.py` (butuh PyQGIS), training AI end-to-end |

Keterbatasan verifikasi: render memakai geometri palsu sederhana; peta dan angka hanya mengonfirmasi tata letak, bukan kebenaran analisis.

## 3. Catatan teknis / utang yang ditemukan saat membaca kode

| # | Area | Catatan |
|---|---|---|
| T1 | PDF M4 | `complete_report('modul4')` membuat `laporan_modul4.pdf` (gaya legacy) lalu `make_training_report` **menimpanya**; sia-sia dan membingungkan |
| T2 | Dokumentasi | `README.md` merujuk ZIP `…_LAPORAN_LENGKAP.zip`, paket ini bernama `…_MACOS_PDF_FIX.zip` |
| T3 | Metadata | `email`, `homepage`, `tracker`, `repository` masih placeholder (`example.invalid`, `qgis.org`) |
| T4 | Bug visual M4 | Gridline plot gelap (pena MUTED); judul sumbu tabrakan dengan legenda; label confusion matrix menimpa sel (lihat `DESIGN.md` D14) |
| T5 | Dua renderer | `Report` dan `Canvas` menduplikasi util (font, tabel, teks) dengan token berbeda |
| T6 | Font | `DejaVu Sans` hard-coded; fallback tak terkontrol di macOS/Windows |
| T7 | Pembungkus teks | Berbasis jumlah karakter; tabel memotong sel (`..`) |
| T8 | M6 PDF | Tabel keputusan dibatasi 30 baris; kolom operator/waktu/catatan tidak tampil |
| T9 | M3 PDF | Histogram overlap memakai batas bin tetap, padahal ambang dapat diubah |
| T10 | Kinerja | Proses sinkron di UI thread (QGIS bisa "tidak merespons"); gap tanpa batas jumlah (ambang peringatan 2500) dengan progres + Batal; peta PDF menggambar seluruh fitur |
| T11 | Keamanan | `.joblib` = pickle → hanya model tepercaya (sudah diperingatkan di UI & README) |
| T12 | `dialogs.run1/run2/run4` | Variabel `charts` dihitung tetapi tidak dipakai laporan baru (sisa laporan lama) |
| T13 | Peta | Hanya *outer ring*; lubang tak digambar (`# holes not coloured`) |

## 4. Uji penerimaan

Lihat `ACCEPTANCE_TEST.md` (bagian umum + regresi dropdown 0.9.1/0.9.2 + **laporan PDF 0.9.4**). Untuk desain ulang, minimal ulangi poin laporan 1–9, ditambah:

* Cetak A4 hitam-putih: status, seri BPN/PBB, dan peta tetap terbedakan.
* Uji simulasi buta warna (deuteranopia/protanopia) pada peta dan bar.
* Uji ID panjang (NIB 13–17 digit, NOP 18 digit `33.04.xxx…`) tidak terpotong.
* Uji data ekstrem: 0 record, 100 000 record, satu kolom saja, nama kolom sangat panjang, teks non-ASCII (Jawa/Arab/emoji tak boleh merusak render).
* Uji empty state tiap grafik (daftar di `REPORT_SPEC.md`).
* QGIS 3.44 LTR **dan** 4.x terpisah; catat versi Qt/Python dan traceback bila API Qt gagal.

## 5. Cara menjalankan uji unit (tanpa QGIS)

```bash
cd <folder induk nibnop_integrator>
python -m unittest discover nibnop_integrator/tests -v     # README; butuh scikit-learn untuk test_evaluation
```
Catatan: `unittest discover` dari README mengasumsikan `tests` dapat diimpor sebagai paket; bila gagal, jalankan modul tes langsung dengan `PYTHONPATH` ke folder induk.
