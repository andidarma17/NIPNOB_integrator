# TODO_REDESIGN.md — Daftar perbaikan tampilan laporan PDF

Sumber: render branch `report-palette-indigo-safron-20261022` (data sintetis; Modul 1, 3, 4 dilihat langsung) dan pembacaan kode. Poin Modul 2, 5, 6 perlu dicek ulang di render.
Prioritas: **P1** wajib sebelum dianggap redesain · **P2** kualitas profesional · **P3** poles.
Konteks: `DESIGN.md` (baseline & masalah), `PRODUCT.md` (prinsip), `REPORT_SPEC.md` (isi halaman).

**Urutan kerja yang disarankan:** A1–A4, F1–F4, B1 → C dan D → sisanya.

## A. Struktur dan alur dokumen
- [ ] **A1 P1** Lembar ringkasan satu halaman: verdict satu kalimat, 3–4 angka besar dengan pembanding, tiga tindakan berurutan prioritas, batasan interpretasi yang terlihat.
- [ ] **A2 P1** Pindahkan tabel indikator 8–22 baris ke lampiran.
- [ ] **A3 P1** Padatkan: dua grafik per halaman. Target Modul 1 ≈ 4 halaman (kini 10), Modul 3 ≈ 5–6 (kini 9).
- [ ] **A4 P1** Hapus halaman tanpa isi (mis. "Jumlah kosong per kolom" berisi 0 semua); ganti satu kalimat di ringkasan.
- [ ] **A5 P2** Blok dasar pemeriksaan: layer BPN/PBB, kolom NIB/NOP/luas, CRS, ambang (50/90/50), versi plugin, sidik-jari input, operator.
- [ ] **A6 P2** Penomoran temuan (T1, T2…) dirujuk silang ke tindakan akhir.
- [ ] **A7 P2** Tindakan akhir terkait angka, hanya yang relevan, urut dampak; bila tak ada temuan tulis "tidak ada tindakan".
- [ ] **A8 P2** Lampiran: tabel penuh, daftar kandidat, glosarium singkat.
- [ ] **A9 P3** Halaman sampul/identitas kecil untuk laporan yang diserahkan ke supervisor.

## B. Rangka halaman
- [ ] **B1 P1** Hapus pita navy + band tint + label kapital di tiap halaman; ganti satu running head tipis (modul, versi, hash input).
- [ ] **B2 P2** Footer: halaman X dari N, nama layer, tanggal-waktu dengan zona (WIB).
- [ ] **B3 P2** Margin dan grid kolom konsisten; satu ritme spasi (mis. 4/8/16/24 pt).
- [ ] **B4 P3** Pastikan area lukis (958×1369 px) tidak memotong elemen tepi di Qt6.

## C. Warna
- [ ] **C1 P1** Maksimal 3 hue aktif: identitas data, status keputusan, peringatan; sisanya luminans, garis tepi, label.
- [ ] **C2 P1** Hilangkan kerumunan ungu (BPN 276°, Level 2 311°, Invalid 313°, RandomForest 338°).
- [ ] **C3 P1** Pisahkan pasangan hampir kembar: Gap vs PBB (dE 0,06; 0,04 deuteranopia), Invalid vs RandomForest (0,08), Level 1 vs XGBoost (0,07).
- [ ] **C4 P1** Level 2 netral dengan kontras teks ≥ 4,5:1 (kini 3,86:1); bukan "error", bukan hue baru.
- [ ] **C5 P1** BPN vs PBB dibedakan terutama lewat luminans agar terbaca di fotokopi hitam-putih.
- [ ] **C6 P2** Uji semua pasangan: deuteranopia, protanopia, tritanopia, skala abu-abu; simpan hasil.
- [ ] **C7 P2** Satu sumber token (`report_theme.py`) peran → warna; tanpa hex literal di pemanggil.
- [ ] **C8 P2** Teks kecil di latar berwarna ≥ 4,5:1 (callout, badge, header tabel).
- [ ] **C9 P3** Latar halaman putih murni kecuali ada alasan kuat.

## D. Tipografi
- [ ] **D1 P1** Kemas satu keluarga font (OFL) di plugin via `QFontDatabase.addApplicationFont`.
- [ ] **D2 P1** Skala: angka kunci 28–36 pt, judul-temuan 18–20 pt, seksi 12–13 pt, isi 10 pt, label ≥ 9 pt (tidak ada 8 pt).
- [ ] **D3 P2** Mono/angka tabular untuk NIB, NOP, kolom angka; ID tak boleh terpotong tanpa tanda jelas.
- [ ] **D4 P2** Kolom numerik rata kanan, satuan di header (m², %).
- [ ] **D5 P2** Variasi bobot dan ukuran judul.
- [ ] **D6 P3** `m²` bukan `m2`; satukan bahasa label ("Split", "Pred 0", "Real 1", "Hal." vs "Halaman").
- [ ] **D7 P3** Kurangi kapital penuh; sentence case untuk judul.

## E. Komponen
- [ ] **E1 P1** Callout dua jenis saja (catatan, peringatan) dengan label teks; hapus lima varian dan glyph ✓ ▲ ✕ ? !.
- [ ] **E2 P1** Status/metrik (`PREVIEW_ONLY`, `BELUM DAPAT DINILAI`, `DI BAWAH TARGET`) sebagai label manusiawi dengan penanda bentuk, bukan kode mentah/hanya warna.
- [ ] **E3 P2** Tabel dengan wrap multi-baris (bukan `..`), tinggi baris adaptif, header berulang saat lanjut.
- [ ] **E4 P2** Badge status kecil di tabel (Keputusan di M5, Label di M6).
- [ ] **E5 P2** Kotak angka kunci (KPI) dengan pembanding BPN vs PBB, tanpa dekorasi tambahan.
- [ ] **E6 P3** Penanda kategori berupa bentuk vektor sederhana (persegi, belah ketupat, lingkaran, silang).

## F. Grafik
- [ ] **F1 P1** Normalkan Grafik 1 Modul 1 ke % dari jumlah record (kini total 200 dan defect 1–8 satu sumbu).
- [ ] **F2 P1** Gabungkan "Jumlah kosong" + "Persentase kosong" jadi satu plot terurut menurun, hanya kolom bernilai kosong.
- [ ] **F3 P1** Hapus scatter sumbu-X urutan record; ganti luas tertulis vs luas geometri dengan garis ambang.
- [ ] **F4 P1** Hapus arsir dari bar/histogram; arsir hanya untuk peta bila perlu.
- [ ] **F5 P2** Histogram BPN dan PBB bersanding, sumbu bersama, garis ambang min/maks luas.
- [ ] **F6 P2** Modul 3: garis ambang aktual (50 % overlap, 90 % kesamaan) menggantikan bin tetap `0-20-40-50-60-80-100`.
- [ ] **F7 P2** Sumbu: angka bulat untuk hitungan, tick "cantik", judul sumbu + satuan.
- [ ] **F8 P2** Label langsung pada seri/bar, bukan legenda terpisah.
- [ ] **F9 P2** Label manusiawi untuk kode alasan Level 2 (`OVERLAP_KURANG`, `MULTI_NOP`, …).
- [ ] **F10 P2** Modul 4: perbaiki gridline gelap, judul sumbu tabrakan legenda, label "Real 0/1" menimpa sel, kurva dua model tumpang tindih (gaya garis berbeda).
- [ ] **F11 P2** Modul 4: garis referensi jelas (baseline PR = prevalensi, diagonal y=x di kalibrasi).
- [ ] **F12 P3** Anotasi satu kalimat pada grafik utama.

## G. Peta
- [ ] **G1 P1** Pastikan CRS diteruskan ke semua laporan (di render uji muncul "CRS peta: tidak tercatat" karena argumen `crs` tak dikirim); uji di data nyata.
- [ ] **G2 P1** Hapus kategori kosong dari legenda ("PBB Level 1 (0)").
- [ ] **G3 P2** Panah utara dan ekstrem koordinat; cek keterbacaan skala di ukuran cetak.
- [ ] **G4 P2** Gambar lubang poligon (kini hanya *outer ring*).
- [ ] **G5 P2** Kontras bidang netral terhadap latar peta cukup, tepi jelas.
- [ ] **G6 P2** Peta Level 2 PBB: bedakan "tidak ada pasangan" dari "perlu studio" dengan label.
- [ ] **G7 P3** Inset ekstrem untuk peta zoom gap Modul 2.

## H. Kejujuran data dan empty state
- [ ] **H1 P1** Tanpa GOLD test: **BELUM DAPAT DINILAI** sebagai verdict utama di halaman 1 Modul 4; tidak ada halaman metrik kosong.
- [ ] **H2 P1** Tiap grafik punya empty state yang menjelaskan alasan (tidak ada gap/model, 0 overlap, 0 keputusan).
- [ ] **H3 P2** Modul 5: tampilkan gerbang promosi AI per kandidat (skor, margin, ID unik, overlap, deviasi).
- [ ] **H4 P2** Modul 6: semua keputusan (bukan maks. 30 baris) dengan operator, waktu, sumber bukti.
- [ ] **H5 P2** Tampilkan Wilson CI95 dan jumlah sampel di dekat Precision.

## I. Implementasi
- [ ] **I1 P1** Satukan `Report` dan `Canvas` ke satu kerangka (token, tabel, teks, callout).
- [ ] **I2 P1** Hapus PDF legacy `storage.create_report` yang ditimpa untuk Modul 4.
- [ ] **I3 P2** Pembungkus teks memakai `QFontMetrics` di semua tempat.
- [ ] **I4 P2** Uji Qt5 dan Qt6, QGIS 3.44 LTR dan 4.x, Windows/macOS/Linux.
- [ ] **I5 P2** Uji ekstrem: 0 record, 100 ribu record, nama kolom sangat panjang, teks non-ASCII, ID 13–18 digit.
- [ ] **I6 P3** Simpan render referensi tiap rilis dan bandingkan untuk regresi visual.

## J. Proses
1. `shape` dengan `PRODUCT.md`: putuskan struktur (A, B) **sebelum** memilih palet.
2. Pilih palet (C), uji simulasi buta warna dan cetak hitam-putih.
3. `critique` dan `audit` pada hasil render PDF, bukan pada kode; tinjau tiap halaman di ukuran cetak.
4. Jalankan `ACCEPTANCE_TEST.md` (laporan 0.9.4) + uji cetak hitam-putih, buta warna, ID panjang.