# CLAUDE.md — Petunjuk untuk asisten AI pada repo NIB–NOP Integrator

Plugin QGIS (Python, PyQGIS/Qt) untuk memadukan data BPN (NIB) dan PBB (NOP). Baca urutan ini:

1. `PRODUCT.md` — pengguna, nada, prinsip yang tak boleh dilanggar.
2. `DESIGN.md` — desain laporan PDF saat ini, masalah, batasan renderer. **Dokumen utama untuk tugas desain ulang laporan.**
3. `REPORT_SPEC.md` — isi & kontrak data per laporan.
4. `ARCHITECTURE.md`, `MODULES.md`, `DOMAIN_RULES.md`, `DATA_SCHEMA.md` — bila menyentuh logika/data.
5. `STATUS_AND_TESTING.md` — status, utang teknis, uji.

## Aturan kerja

* Bahasa antarmuka & laporan: **Indonesia baku**. Kode/identifier: ikuti yang ada (campur Inggris/Indonesia).
* **Jangan ubah aturan pemaduan, ambang, atau mekanisme AI** (`logic.py`, `engine.determine_levels`, `ml.py`, `evaluation.py`) saat mengerjakan tampilan laporan.
* Pertahankan tanda tangan `report1/2/3/5/6` dan `make_training_report`; pemanggil ada di `dialogs.py` dan `studio.py`.
* PDF dibuat **hanya dengan Qt (`QPdfWriter`/`QPainter`)** bawaan QGIS via `qgis.PyQt`; jangan menambah dependensi (reportlab, matplotlib, WebEngine) di jalur wajib.
* Kompatibel Qt5 **dan** Qt6: gunakan enum berkualifikasi dan `compat.py`.
* Jangan menyajikan angka tak sah sebagai valid (TEST tanpa GOLD → "BELUM DAPAT DINILAI"); Level 2 ≠ salah; "belum pasti" ≠ 0.
* Layer sumber operator tidak boleh dimutasi.
* Ukuran halaman: A4, 120 dpi, area lukis 958×1369 px (terukur Qt 5.15). Font saat ini DejaVu Sans.

## Perintah berguna

```bash
python -m py_compile nibnop_integrator/*.py
python -m unittest discover nibnop_integrator/tests -v
# render laporan tanpa QGIS: lihat reference/render_*.py (PyQt5 + shim qgis.PyQt)
```
