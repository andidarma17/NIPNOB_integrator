# DESIGN.md — Desain Laporan PDF NIB–NOP Integrator

> Bagian 1–8 mencatat **baseline v0.9.4 sebelum redesain**, termasuk masalah yang ditemukan.
> Implementasi saat ini memakai token bersama dalam `report_theme.py` untuk kedua renderer aktif
> (`reporting_full.py` dan `ai_pdf.py`). Warna dan layout terkini diringkas di bawah.
> Spesifikasi isi per halaman ada di [`REPORT_SPEC.md`](REPORT_SPEC.md). Konteks produk ada di [`PRODUCT.md`](PRODUCT.md).

---

## Redesain aktif: laporan audit editorial

Mode baca: halaman pertama keenam modul mengikuti tata letak editorial contoh: kesimpulan, batasan interpretasi, hasil terukur, bukti atau contoh record, dan jejak audit. Setiap modul memilih bukti yang sesuai: kolom kosong dan kualitas luas (M1), QA geometri dan overlap terbesar (M2), distribusi Level serta alasan dan contoh pasangan (M3), status GOLD dan hasil TEST (M4), distribusi Level serta kandidat AI (M5), keputusan serta kelengkapan bukti (M6). Modul 1, 2, 4, 5, dan 6 memakai komponen `EditorialPage` bersama; Modul 3 mempertahankan komposisi khusus contoh. Angka selalu berasal dari hasil proses; jumlah input dan jumlah record keluaran diberi nama terpisah bila berbeda. Grafik dan peta berikutnya mengikuti isi data; CSV tetap menjadi rujukan record penuh.

### Sistem visual

| Peran | Token | Aturan |
|---|---|---|
| Struktur | `#1E2250` | Pita atas, judul, header tabel |
| Dataset | BPN `#3A3F9E`, PBB `#A36A00` | PBB memakai arsiran 135° pada peta |
| Level | Level 1 `#0B7285`, Level 2 `#8F7A9E` | Level 2 memakai arsiran 45°; teks `#5E4B70` |
| QA | overlap `#B5173A`, gap `#167FA1`, invalid/fixed `#AA5722`, tanpa pasangan `#AEBBC7` | Gap bergaris putus-putus; invalid/fixed berarsir; lokasi kecil diberi lingkaran |
| Teks dan garis | `#1B1F33`, `#52636F`, `#D5D9E4` | Hierarki tipografi dan grid cetak |

Source Sans 3 Regular/Bold dikemas bersama lisensi OFL. Header memakai pita indigo tipis, bidang abu pucat, nama modul, versi, dan garis pemisah di antara judul dan subjudul dengan jeda baca. Isi memakai kalimat langsung dalam bahasa Indonesia. Status, Level, dan QA tidak dibedakan hanya oleh warna. Tabel menggunakan baris adaptif dan tidak menghilangkan digit NIB/NOP pada tabel bukti penuh. Peta memotong geometri pada bingkai, menampilkan lubang poligon, CRS, skala, koordinat, dan arah utara.

Palet D Indigo–Safron kembali menjadi token aktif berdasarkan acuan visual terbaru. Bagian 1–8 di bawah tetap merupakan riwayat baseline sebelum redesain.

---

## 1. Tujuan dan pembaca laporan

| Aspek | Keterangan |
|---|---|
| Tujuan | Memberi operator bukti ringkas apa yang diperiksa/dihasilkan modul, seberapa bermasalah datanya, dan **apa tindak lanjutnya**. Laporan bukan bukti hukum. |
| Pembaca utama | Operator/analis pertanahan (BPN–PBB), staf teknis pemda/ATR-BPN. Membaca di layar dan/atau mencetak A4. |
| Pembaca sekunder | Supervisor yang mereview hasil sebelum data dipadukan; peneliti yang mengaudit metode. |
| Bahasa | Indonesia (istilah teknis: NIB, NOP, GOLD, SILVER, Level 1/2, overlap, gap, precision, recall…). |
| Nada | Formal-teknis, hati-hati. Selalu ada penafian: hasil otomatis = indikasi pemeriksaan, bukan keputusan administratif. |
| Taruhan | Tinggi: kesalahan menggabungkan NIB–NOP (false positive) berisiko pada data pajak/pertanahan. Desain harus membuat **status, batasan, dan peringatan sulit terlewat**. |

## 2. Batasan teknis (WAJIB dibaca sebelum mendesain ulang)

1. **Renderer = Qt `QPdfWriter` + `QPainter`** di dalam QGIS. Tidak ada HTML/CSS, matplotlib, reportlab, atau browser engine. Semua elemen digambar imperatif dengan koordinat piksel.
   Konsekuensi: desain dari alat berbasis HTML/CSS harus **diterjemahkan ke token + primitif Qt** (rect, text, line, polygon, ellipse), atau arsitektur renderer diganti (lihat §8).
2. **Resolusi 120 dpi**, A4 portrait. Area lukis nyata (diukur): **958 × 1369 px** = 202,8 × 289,8 mm → margin bawaan Qt ≈ 3,6 mm (10 pt) di tiap sisi. `1 px = 0,6 pt = 0,2117 mm`. Ukuran font diberikan dalam **pt** (`QFont(family, pt)`).
   Nilai margin Qt6/QGIS 4 belum diverifikasi.
3. **Font tunggal: `DejaVu Sans`** (reguler + bold). Tidak ada italic, tidak ada font lain. Pada macOS/Windows DejaVu mungkin tidak terpasang → Qt melakukan fallback tanpa pemberitahuan (laporan uji macOS di `PERBAIKAN_PDF_MACOS.txt`). Jika font diganti, **embed/bundle font di folder plugin** dan muat dengan `QFontDatabase.addApplicationFont`.
4. **Pembungkus teks memakai jumlah karakter** (`textwrap.wrap(width=…)`), bukan metrik font. Mengganti font/ukuran akan menggeser pembungkusan → harus diganti dengan `QFontMetrics`.
5. **Sel tabel dipotong** dengan `[:n-2]+'..'` berdasarkan perkiraan lebar (`lebar/8.4` karakter). Tidak ada wrap multi-baris di tabel.
6. **Peta** digambar dari geometri aktual (hanya *outer ring*, maks. 4000 fitur per layer, simplifikasi tiap 800 titik) **tanpa basemap**, tanpa skala/panah utara/CRS.
7. **Data = hasil eksekusi saat itu.** Laporan harus tetap layak ketika: tidak ada gap, tidak ada model AI, tidak ada GOLD test, 0 overlap, 0 keputusan studio, kolom luas bertipe teks (lihat `ACCEPTANCE_TEST.md` poin 8). Setiap grafik wajib punya *empty state* yang menjelaskan alasan.
8. **Tidak ada PNG terpisah** dan tidak ada dependensi tambahan di lingkungan QGIS. Satu PDF per modul (`laporan_modulN.pdf`).
9. Cetak hitam-putih/fotokopi lazim di lingkungan kerja ini → informasi tidak boleh hanya dibedakan lewat warna.

## 3. Desain saat ini (as-built)

### 3.1 Dua renderer, dua "dialek" visual

| Renderer | Dipakai oleh | Berkas |
|---|---|---|
| `Report` (kelas) | Modul 1, 2, 3, 5, 6 | `reporting_full.py` |
| `Canvas` (kelas) | Modul 4 | `ai_pdf.py` |
| `create_report()` | **Legacy**. Dipanggil `complete_report()` untuk Modul 4 tetapi file hasilnya **ditimpa** oleh `make_training_report()` (nama sama `laporan_modul4.pdf`). Praktis tidak terlihat; abaikan. | `storage.py` |

Kedua renderer aktif **tidak berbagi token**, sehingga warnanya berbeda tipis (lihat 3.2).

### 3.2 Palet warna (as-built)

**Modul 1, 2, 3, 5, 6 — `reporting_full.py`**

| Token | Hex | Peran saat ini |
|---|---|---|
| NAVY | `#123b58` | Pita atas, judul halaman, sub-judul, header tabel |
| BLUE | `#236d9f` | Seri data 1 (**BPN**), histogram/scatter, label modul di header |
| ORANGE | `#d58b43` | Seri data 2 (**PBB**) |
| GREEN | `#267c68` | Seri 3; peta: BPN Level 1, BPN diverifikasi |
| RED | `#bf5550` | Seri 4; teks peringatan "Batasan interpretasi"; "Visualisasi tidak tersedia" |
| INK | `#243642` | Teks isi |
| MUTED | `#5c707e` | Teks sekunder, footer, label sumbu, keterangan |
| LIGHT | `#edf4f8` | Pita header halaman, zebra baris tabel |
| GRID | `#d4e1e9` | Garis grid, bingkai, garis pemisah |

Warna peta (hex literal di pemanggilan `report2/3/5/6`):

| Konteks | Hex |
|---|---|
| Latar kanvas peta | `#f8fafb` (bingkai GRID) |
| Bidang lain BPN (M2) / PBB lain (M2 peta 3) | `#b9cad7` / `#d7e3eb` |
| Overlap | `#cb564d` |
| Gap baru / kandidat gap | `#e6a23a` |
| Invalid awal / fixed (PBB) | `#df9353` |
| Bidang sekitar gap (zoom) | `#dce6ed` |
| Level 2 (M3, M5) | `#d7e1e8` / `#d7e2e9` |
| Level 1 (M3 / M5) | `#328b73` / `#308671` |
| BPN diverifikasi (M6) | `#267c68` |
| PBB diverifikasi (M6) | `#d58b43` |
| Isi poligon | warna seri, **alpha 90/255**; tepi alpha 180, lebar pena 1,1 |

**Modul 4 — `ai_pdf.py`** (nilai berbeda dari di atas)

| Token | Hex | Peran |
|---|---|---|
| NAVY | `#163b5b` | Pita atas 13 px, judul, header tabel |
| INK | `#222d38` | Teks |
| MUTED | `#64748b` | Subjudul, footer, label sumbu |
| BLUE | `#2376b7` | Model 1 (RandomForest), bar feature importance |
| ORANGE | `#dc8135` | Model 2 (XGBoost) |
| PALE | `#eff5f9` | Zebra tabel, kotak catatan biasa |
| BORDER | `#d7e2ed` | Garis & bingkai |
| RED | `#ae3e3e` | Teks kotak peringatan |
| (inline) | `#fff6eb` | Latar kotak peringatan (*caution*) |
| (inline) | `#e3f0f6` / `#ffe9df` | Sel diagonal benar (TP/TN) / salah (FP/FN) pada confusion matrix |
| (inline) | `#98a6b4` | Garis baseline PR |

**Legacy `storage.py`:** `#123B62`, `#4b5563` (tidak terlihat; lihat 3.1).

### 3.3 Tipografi (as-built)

Satu keluarga: **DejaVu Sans**. Hierarki:

| Elemen | Modul 1/2/3/5/6 | Modul 4 |
|---|---|---|
| Judul halaman | 17 pt bold NAVY, dipotong 67 karakter, y=122 px | 19 pt bold NAVY |
| Subjudul halaman | 9 pt INK | 9 pt MUTED |
| Label modul (pita) | 10 pt bold BLUE, huruf kapital `NIB-NOP INTEGRATOR \| MODUL N` | — (tidak ada; footer saja) |
| Judul seksi (`sub`) | 12 pt bold NAVY | 12 pt bold NAVY |
| Isi | 10 pt INK, leading 23 px | 9 pt INK, leading 20 px |
| Isi kecil / metode | 9 pt, leading 21 px | — |
| Header tabel | 9 pt bold putih di NAVY | 8–9 pt bold putih di NAVY |
| Sel tabel | 9 pt, baris 31 px | 8–9 pt, baris 30–40 px |
| Label sumbu / nilai batang | 8 pt MUTED / INK | 8 pt |
| Legenda | 9 pt | 8 pt |
| Keterangan grafik | 9 pt MUTED | 9 pt |
| Peringatan | 9 pt RED | 9 pt RED di kotak `#fff6eb` |
| Footer | 9 pt MUTED | 8 pt MUTED |
| Angka confusion matrix | — | 11 pt bold |

Tidak ada: angka tabular/monospace untuk NIB–NOP, skala tipografi modular, atau rata kanan untuk angka.

### 3.4 Layout halaman (modul 1/2/3/5/6)

```
y=0    ┌──────────────────────────────────────────┐
       │ ▇▇▇ pita NAVY 15 px (3,2 mm) ▇▇▇▇▇▇▇▇▇▇▇ │
y=15   │ pita LIGHT 60 px (12,7 mm)               │
y=48   │  NIB-NOP INTEGRATOR | MODUL N  (BLUE 10b)│
y=122  │  JUDUL HALAMAN (17 pt bold NAVY)         │
       │  subjudul 9 pt                           │
       │  ───────── garis GRID ───────────        │
       │                                          │
       │  konten (margin kiri/kanan 62 px =13 mm) │
       │  lebar konten 834 px = 176,6 mm          │
y=h-108│  ← batas bawah konten                    │
y=h-42 │  Laporan otomatis | dd-mm-yyyy HH:MM  Halaman N
       └──────────────────────────────────────────┘
```

* Satu grafik/peta **per halaman**; area grafik ±590–665 px tinggi dari 1369 → sisa halaman kosong (lihat §4).
* Halaman 1 = "IKHTISAR DAN HASIL UTAMA": tabel 2-kolom indikator (64%/36%), "Metode dan parameter" (butir `- `), "Batasan interpretasi" (merah).
* Halaman terakhir = "KESIMPULAN DAN TINDAK LANJUT": 3 rekomendasi bernomor (judul 12 pt bold + isi 10 pt), "Arsip hasil", "Catatan umum".
* Halaman lanjutan memakai judul `LANJUTAN - <judul laporan>`.
* Modul 4: tanpa pita LIGHT; hanya pita NAVY 13 px; footer `NIB-NOP Integrator | Modul 4 - Training AI` + `Hal. N`; judul memakai Title Case, bukan KAPITAL.

### 3.5 Komponen grafik yang ada

| Komponen | Dipakai di | Catatan implementasi |
|---|---|---|
| Bar berkelompok vertikal (maks. 4 seri) | M1 G1/G8; M2 G1; M3 G1/G3; M5 G1/G2; M6 G1 | Seri: BLUE, ORANGE, GREEN, RED (berurutan). Label nilai di atas batang 8 pt. Sumbu Y 5 gridline, label 1 desimal (`230.0`, `57.5`) bahkan untuk hitungan bulat. |
| Bar horizontal | M1 G2/G3; M3 G2 | Label kolom dipotong 34 karakter; tidak diurutkan; nilai 0 tetap digambar. |
| Histogram 30 bin | M1 G4/G5 | Batas atas = persentil ke-99; ekor ekstrem dibuang dan dicatat di keterangan. Tick X 6 titik tanpa pembulatan "cantik". |
| Scatter log-Y | M1 G6/G7 | X = urutan record (bukan informasi bermakna), titik 1,9 px. |
| Scatter XY (maks. 12 000 titik) | M3 G4 | X overlap BPN %, Y kesamaan luas %. Tanpa garis ambang. |
| Peta indikatif | M2 ×4, M3 ×2, M5 ×2, M6 ×1 | Lihat batasan #6. Legenda kotak 12 px, 3 kolom. |
| Tabel zebra | semua | Lihat batasan #5; `limit` 18–30 baris + catatan "data lengkap di rekap_csv.zip". |
| Kotak catatan | M4 | Latar PALE / `#fff6eb`. |
| Confusion matrix 2×2 | M4 | Blok 64 px; TP/TN `#e3f0f6`, FP/FN `#ffe9df`. |
| Kurva ROC/PR/kalibrasi (polyline 2,6 px) | M4 | Dua seri: BLUE (model 1), ORANGE (model 2). |
| Bar feature importance (10 baris) | M4 | Bar BLUE, nilai 3 desimal. |

## 4. Temuan masalah desain (diverifikasi dari render)

Prioritas: **P1** = memengaruhi kebenaran/keterbacaan keputusan; **P2** = kualitas profesional; **P3** = poles.

### Komunikasi dan hierarki
| # | P | Temuan |
|---|---|---|
| D1 | P1 | **Tidak ada ringkasan eksekutif.** Halaman 1 berupa tabel polos dengan kunci mentah (`BPN jumlah_record`, `BPN record_luas_bermasalah`) — *snake_case* bocor ke UI. Tidak ada angka kunci besar, tidak ada verdict "apa yang harus saya lakukan sekarang". |
| D2 | P1 | **Status & peringatan tidak diberi bobot visual.** Status model (`PREVIEW_ONLY`, `GOLD_TESTED_REVIEW_REQUIRED`), verdict (`BELUM DAPAT DINILAI`, `LAYAK MASUK PENINJAUAN OPERASIONAL…`), dan label metrik (`DI BAWAH TARGET`, `MEMADAI`, `TAMBAH GOLD`…) dicetak sebagai teks biasa di tabel. Penafian "bukan bukti hukum" hanya di halaman terakhir, 9 pt abu-abu. |
| D3 | P2 | Halaman 1 ±80% kosong; tiap grafik sendirian di halaman penuh dengan ±40% ruang kosong di bawahnya. Laporan Modul 1 = 10 halaman untuk informasi yang muat ±3–4. |
| D4 | P2 | Judul halaman generik ("IKHTISAR DAN HASIL UTAMA", "GRAFIK 2 – …") — mendeskripsikan *jenis* konten, bukan **temuan**. Tidak ada judul-sebagai-kesimpulan. |
| D5 | P2 | Tidak ada halaman sampul / blok identitas: nama layer input, kolom yang dipilih, parameter ambang, CRS, versi plugin, jumlah fitur, hash/sidik-jari input (Modul 3 sudah punya `sha256`), nama operator. Footer hanya cap waktu. Laporan tidak dapat diaudit/direproduksi dari PDF-nya saja. |
| D6 | P2 | Daftar rekomendasi (Modul 1/2/3/5/6) statis dan tidak terhubung ke temuan angka halaman sebelumnya; tidak diprioritaskan (urutan = urutan kode). |

### Data-viz
| # | P | Temuan |
|---|---|---|
| D7 | P1 | **Pasangan warna GREEN `#267c68` vs RED `#bf5550` memiliki luminans hampir sama (kontras 1,11:1)** → tak terbedakan untuk buta warna merah-hijau & saat dicetak hitam-putih. Keduanya dipakai berdampingan sebagai seri 3/4 dan di peta (Level 1 hijau vs overlap merah). |
| D8 | P2 | ORANGE `#d58b43` / `#dc8135` di atas putih hanya **2,76–2,9:1** — di bawah ambang 3:1 untuk objek grafis (WCAG 1.4.11). Berlaku untuk seri PBB, bar PBB, kurva model 2. |
| D9 | P2 | Sumbu: hitungan bulat berlabel `57.5`, `230.0`; tick histogram tidak "cantik" (`110, 221, 331`). Tidak ada judul sumbu pada bar chart; satuan hanya di keterangan. |
| D10 | P2 | Bar horizontal (kelengkapan per kolom, alasan Level 2) tidak diurutkan menurun; nilai 0 memakan baris; label dipotong. Tidak ada pemisahan BPN/PBB selain awalan teks `BPN - …`. |
| D11 | P2 | Scatter log-Y memakai **urutan record sebagai sumbu X** — nyaris tak berinformasi; sumbu Y berlabel `log10` (1.4–2.9) bukan m². Tak ada garis ambang `min/max` yang jadi parameter modul. |
| D12 | P2 | Scatter Modul 3 tidak menandai ambang overlap & kesamaan (50 % / 90 %), padahal itu gerbang keputusan Level 1/2. Histogram overlap memakai batas bin tetap `0-20-40-50-60-80-100` walau ambang bisa diubah operator. |
| D13 | P2 | **Peta:** tanpa panah utara, bar skala, CRS, atau ekstrem koordinat; hanya *outer ring*; bidang netral (`#d7e1e8`) kontras 1,27:1 terhadap latar peta → nyaris tak terlihat; tak ada hitungan per kategori di legenda; peta Level 2 "PBB terpilih & studio" kurang bermakna (satu warna). |
| D14 | P2 | **Modul 4 – bug render:** gridline plot ROC/PR/kalibrasi berwarna gelap (pena MUTED, bukan BORDER); judul sumbu X bertabrakan dengan legenda; label "Real 0/Real 1" menimpa sel confusion matrix; kurva dua model tumpang-tindih tanpa pembeda gaya garis. |
| D15 | P3 | Dua seri warna saja (BLUE/ORANGE) dipakai sebagai identitas BPN/PBB **sekaligus** model 1/model 2 (M4) → makna warna berubah antar modul. |

### Sistem & aksesibilitas
| # | P | Temuan |
|---|---|---|
| D16 | P2 | Dua palet berbeda untuk produk yang sama (M4 vs lainnya) dan token hanya sebagai variabel modul Python, bukan sumber tunggal. |
| D17 | P2 | Kontras teks: RED `#bf5550` di putih 4,54:1 (lulus tipis), **di `#fff6eb` 4,24:1 (gagal AA untuk teks 9 pt)**; MUTED `#64748b` di PALE 4,33:1 (gagal). Teks peringatan 9 pt merah adalah teks terpenting, tapi paling kecil. |
| D18 | P2 | Tabel: angka rata kiri, NIB/NOP tanpa font monospace/angka tabular, tanpa satuan di header (m², %), `..` pemotongan membuat ID ambigu. Pemotongan ID adalah masalah **kebenaran**, bukan sekadar estetika. |
| D19 | P3 | Ukuran teks terkecil 8 pt (label sumbu, M4) – batas keterbacaan cetak; teks isi 9–10 pt. |
| D20 | P3 | Tipografi: `m2` bukan `m²`; tanggal `dd-mm-yyyy` tanpa zona waktu; label KAPITAL berlebihan; bahasa campur ("Split", "Pred 0", "Real 1", "Hal." vs "Halaman"). |
| D21 | P3 | `PANDUAN_PENGGUNA.pdf` memakai **Lato** + ReportLab (identitas visual berbeda dari laporan modul yang memakai DejaVu Sans). |
| D22 | P3 | Tidak ada dukungan mode gelap — memang tidak relevan untuk PDF; hanya untuk pratinjau layar. |

## 5. Peran semantik yang perlu didefinisikan ulang

Desain ulang sebaiknya menetapkan token **berdasarkan peran**, bukan nama warna:

| Peran | Dipakai untuk |
|---|---|
| Identitas dataset: **BPN**, **PBB** | Seri bar/histogram, peta (dua warna kategorikal yang konsisten **di semua modul**) |
| Identitas model (M4): RandomForest, XGBoost | Pembeda dari BPN/PBB; sebaiknya bukan hue yang sama |
| **Level 1** (pasangan otomatis lolos) | Peta, bar, badge |
| **Level 2** (butuh studio; *bukan* "salah") | Peta, bar, badge — **jangan** memakai nada "error" |
| **Cocok / Tidak cocok / Belum pasti** (M6) | Label GOLD 1 / 0 / belum pasti; "belum pasti" ≠ negatif |
| Masalah QA: **overlap**, **gap**, **invalid/fixed**, **duplikat**, **kosong** | Peta + bar kategori masalah |
| Status kesiapan: **baik / perlu perhatian / tidak memadai / belum dapat dinilai** | Label metrik M4, status model M5, badge halaman 1 |
| Peringatan / batasan interpretasi | Kotak callout konsisten (bukan sekadar teks merah) |
| Netral: latar, grid, bingkai, bidang tak bermasalah di peta | Sekunder, tidak boleh berebut perhatian |
| Ambang / baseline (garis referensi) | Garis 50 %, 90 %, prevalensi, y=x |

Kosakata status yang **sudah ada di kode** dan harus tetap dapat ditampilkan (lihat `DATA_SCHEMA.md` §Status):
`PREVIEW_ONLY`, `GOLD_TESTED_REVIEW_REQUIRED`, `NO_MODEL`, `LAYAK MASUK PENINJAUAN OPERASIONAL`, `PERLU PERBAIKAN / VERIFIKASI TAMBAHAN`, `BELUM LAYAK`, `BELUM DAPAT DINILAI`, `TARGET TERCAPAI`, `SAMPEL BELUM KUAT`, `DI BAWAH TARGET`, `MEMADAI`, `TAMBAH GOLD`, `PERLU PERBAIKAN`, `LEBIH BAIK BASELINE`, `DI ATAS BASELINE`, `DITERIMA_LEVEL1`, `REKOMENDASI_STUDIO`.

## 6. Catatan desain per modul

Isi halaman rinci: [`REPORT_SPEC.md`](REPORT_SPEC.md). Di sini: **apa yang harus ditekankan**.

| Modul | Pertanyaan operator yang harus dijawab di halaman 1 | Elemen yang paling layak diperkuat |
|---|---|---|
| **1 Kelengkapan** | "Seberapa bersih atribut BPN vs PBB, dan kolom mana yang harus diperbaiki dulu?" | Perbandingan BPN vs PBB berdampingan, persen (bukan hanya hitungan) — jumlah record berbeda (contoh uji 1830 vs 2031). Urutkan kolom kosong menurun. Garis ambang luas di histogram. Delapan grafik bisa dipadatkan (grafik 2+3 = satu; 4+5 dan 6+7 berdampingan). |
| **2 Spasial** | "Berapa geometri bermasalah, di mana, dan apa yang sudah otomatis diperbaiki?" | Peta sebagai tokoh utama; badge perubahan geometri (invalid → fixed); peringatan bahwa **gap ≠ NIB baru**; peta zoom gap dengan skala. |
| **3 Pemaduan aturan** | "Berapa pasangan lolos Level 1, mengapa sisanya Level 2, dan apa dampak ambang?" | Corong/stack Level 1 vs Level 2 + alasan; scatter dengan garis ambang yang dipakai **aktual**; tabel kandidat dengan ID tidak terpotong; panel parameter (50/90/50) dan sidik-jari input; tekankan "Level 2 ≠ salah". |
| **4 Training AI** | "Apakah model layak dipakai? Berapa false positive?" | Verdict + status di paling atas (tanpa GOLD → **BELUM DAPAT DINILAI**, jangan tampilkan angka seolah valid); tabel penilaian metrik berwarna status; confusion matrix + FP disorot; kurva PR di atas ROC (data tak seimbang); CI Wilson. Perbaiki bug D14. |
| **5 Inference** | "Berapa Level 1 baru dari AI, seberapa yakin, dan apakah AI *diizinkan* menambah Level 1?" | Status model & gerbang promosi (checkbox, GOLD teruji) sebagai banner; histogram skor dengan garis `skor_min` & `margin`; daftar kandidat dengan skor + pesaing terdekat. |
| **6 Verifikasi studio** | "Apa yang sudah diputuskan, oleh siapa, dengan bukti apa?" | Jejak audit: operator, waktu, sumber bukti; tiga status label; peta pasangan yang diverifikasi; tabel keputusan lengkap (saat ini dibatasi 30 baris) — halaman ini adalah **catatan resmi**, bukan sekadar ringkasan. |

## 7. Prinsip arah desain (usulan, untuk dipertimbangkan alat desain)

Ini **usulan**, bukan keputusan — silakan diubah oleh proses desain ulang.

1. **Judul = temuan.** ("12% bidang BPN tak punya luas numerik", bukan "Grafik 3").
2. **Satu halaman ringkasan** yang dapat dibaca berdiri sendiri: status, 3–5 angka kunci, tindak lanjut teratas, batasan.
3. **Padatkan.** Dua grafik kecil per halaman bila memungkinkan; target Modul 1 ≤ 5 halaman.
4. **Status bukan hanya warna:** ikon/bentuk/teks + warna; lulus cetak hitam-putih.
5. **Peringatan sebagai komponen kelas satu** (callout), tidak lebih kecil dari teks isi.
6. **ID dan angka tabular**: NIB/NOP monospace/tabular, tidak pernah dipotong tanpa tanda jelas; angka rata kanan dengan satuan di header.
7. **Peta dengan konteks minimum**: skala, panah utara, CRS, jumlah per kategori, ekstrem.
8. **Satu sistem token** untuk seluruh modul (termasuk M4) dan untuk `PANDUAN_PENGGUNA.pdf`.
9. **Jujur terhadap ketiadaan data**: empty state informatif, tak pernah grafik kosong atau angka palsu (aturan produk, lihat `PRODUCT.md`).

## 8. Jalur implementasi setelah desain ulang

| Opsi | Cara | Kelebihan | Risiko |
|---|---|---|---|
| A. Tetap `QPainter` | Terjemahkan desain ke token + helper (kartu, badge, callout, tabel ber-`QFontMetrics`) di satu modul `report_theme.py`; satukan `Report` dan `Canvas` | Tanpa dependensi baru; sudah teruji di QGIS 3.40 / macOS | Kerja manual; HTML/CSS tidak langsung dapat dipakai |
| B. `QTextDocument` (HTML/CSS2 subset) → `QPdfWriter` / `QPrinter` | Susun laporan sebagai HTML sederhana + gambar grafik (`QImage`/SVG) | Tata letak teks/tabel otomatis, wrap benar | Subset CSS terbatas (tanpa flex/grid); kontrol *page break* terbatas; perlu uji Qt5 & Qt6 |
| C. `QWebEnginePage.printToPdf` | HTML/CSS penuh | Fidelitas desain tertinggi | WebEngine **tidak selalu tersedia** di QGIS (khususnya macOS/OSGeo4W); berat; hindari sebagai satu-satunya jalur |

Apa pun opsinya: pertahankan **fungsi publik** `report1/2/3/5/6(...)` dan `make_training_report(...)` (tanda tangan di `REPORT_SPEC.md`) agar `dialogs.py`/`studio.py` tidak berubah, dan jalankan ulang `ACCEPTANCE_TEST.md` bagian "laporan PDF versi 0.9.4" di QGIS 3.x **dan** 4.x.

## 9. Referensi visual kondisi saat ini

Render headless dengan data **sintetis** (hanya untuk melihat tata letak; angka tak bermakna):

| Berkas | Isi |
|---|---|
| `reference/current_modul1.png` | 10 halaman Modul 1 |
| `reference/current_modul2.png` | 9 halaman Modul 2 |
| `reference/current_modul3.png` | 9 halaman Modul 3 (Grafik 2 kosong akibat data sintetis, bukan bug desain) |
| `reference/current_modul4.png` | 8 halaman Modul 4 (dua model dibuat identik → kurva menumpuk) |
| `reference/current_modul5.png` | 7 halaman Modul 5 |
| `reference/current_modul6.png` | 5 halaman Modul 6 |

Render ulang: `reference/render_modul_1_2_3_5_6.py`, `render_modul_4.py`, `render_reports.py` (butuh `pip install PyQt5`; memakai shim `qgis.PyQt` → PyQt5).
