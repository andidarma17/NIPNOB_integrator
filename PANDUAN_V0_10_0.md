# Panduan singkat NIB–NOP Integrator v0.10.0

## Instalasi dan persiapan

1. QGIS → Plugins → Manage and Install Plugins → Install from ZIP → pilih `NIBNOP_Integrator_v0.10.0_AI_Independent_Toolbox.zip`. Jangan ekstrak ZIP plugin.
2. Buka layer BPN dan PBB yang sudah dikoreksi operator. Pastikan CRS kedua layer proyeksi **meter**. Jika CRS berbeda, aktifkan reproyeksi sementara PBB.
3. Pilih kolom NIB, NOP, **luas tertulis BPN** dan **luas bumi PBB** yang benar. Pada data Sungai Beliung contoh, `LUAS BUMI` lebih sesuai untuk pengujian daripada `d_luas`; verifikasi nilai sumber tetap diperlukan.
4. Gunakan folder output berbeda untuk tiap percobaan agar hasil sebelumnya tidak tertimpa.

## Menjalankan modul dan mengatur keluaran

Modul 1–5 dibuka dari **Vector → NIB–NOP Integrator** atau **Processing Toolbox → NIB–NOP Integrator** dan tampil sebagai formulir Processing yang sama. Pilih layer lalu kolomnya (NIB, LUAS, D_NOP, D_LUAS terpilih otomatis bila ada; **periksa kolom luas**), atur parameter, lalu keluaran:

- **Folder hasil** — laporan PDF dan `rekap_csv.zip` (Modul 3: juga `manifest_modul3.json`; Modul 4: juga model `.joblib` dan metadata). Bawaan `~/NIBNOP_HASIL/modul_<n>`.
- **Output layer …** — satu tujuan per layer spasial. Pilih file (`.gpkg` disarankan, `.geojson`, `.shp`), biarkan kosong untuk file sementara, atau *Skip Output* dari tombol "…". Centang *Open output file after running algorithm* agar layer dimuat.
- **Lewati semua keluaran** — hanya menghitung dan menampilkan ringkasan di log (uji coba). Jangan dipakai untuk Modul 4 bila model perlu disimpan.
- **Modul 4:** pilih *Sumber pelatihan* (GOLD Only / SILVER Only / SILVER + GOLD) dan isi hanya berkas yang relevan. Layer BPN/PBB tetap wajib.
- **Modul 5:** pilih *Mode prediksi*; Hybrid memerlukan *Rekap Modul 3*. Model `.joblib` dan metadata `.json` selalu berpasangan. Izin Level 1 otomatis bawaannya mati.
- **Modul 6** membuka panel Verifikasi Studio yang dapat di-scroll; bila Toolbox terbuka, panel muncul sebagai tab di sebelahnya.

## Modul 3 — Rule-based (opsional untuk Full AI)

- Masukkan BPN/PBB yang sudah dikoreksi dan jalankan Modul 3 (atau 3.1 jika PBB titik).
- Simpan `rekap_csv.zip` beserta hasil dan `manifest_modul3.json` pada folder output.
- Gunakan ZIP ini sebagai sumber SILVER pada Modul 4 atau hasil aturan untuk Hybrid pada Modul 5.

## Modul 4 — Training AI

Pilih **satu** dari tiga mode:

| Mode | Wajib diisi |
|---|---|
| SILVER Only | `rekap_csv.zip` hasil Modul 3, dari data BPN/PBB yang sama persis |
| GOLD Only | GOLD operator berlabel atau data historis BPN/PBB + CSV verifikasi |
| SILVER + GOLD | Kedua kelompok di atas |

Masukkan layer BPN/PBB terbaru untuk ekstraksi fitur. Jika memakai nama sebagai fitur, pilih kolom nama pada **kedua** layer. Untuk GOLD historis, gunakan skema nama yang konsisten. Atur radius kandidat dan target precision. Klik **Jalankan Modul 4**.

Hasil utama:

- `model_terpilih.joblib` dan `metadata_model.json`: **harus selalu digunakan berpasangan** pada Modul 5.
- `laporan_modul4.pdf`: ringkasan metode, ukuran training, validation, testing, precision, recall, dan risiko.
- `rekap_csv.zip`: fitur, label, hasil evaluasi, GOLD gagal dipetakan, dan rekomendasi.

**Catatan:** SILVER Only tetap menghasilkan model tetapi belum mendapat pengesahan dari GOLD pengujian independen. Perhatikan pula bahwa target precision 80% berbeda dari skor AI 0,80; model saat ini dievaluasi pada skor 0,90.

## Modul 5 — Prediksi AI

Pilih **Full AI** jika ingin menguji kemampuan AI secara mandiri:

1. Pilih layer BPN/PBB.
2. Pilih **Full AI: prediksi tanpa aturan Modul 3**.
3. Pilih `model_terpilih.joblib` dan `metadata_model.json`.
4. Atur radius, skor minimum (disarankan awal 0,90), dan selisih skor kandidat (awal 0,15).
5. Tanpa izin Level 1 otomatis, hasil prediksi yang lolos seleksi tersimpan di **`05_usulan_ai`** dan tetap membutuhkan verifikasi studio.

Pilih **Hybrid** untuk menggabungkan hasil aturan dan AI:

1. Input BPN/PBB, model, dan metadata sama seperti Full AI.
2. Pilih **Hybrid: hasil Modul 3 + tambahan AI**.
3. Masukkan `rekap_csv.zip` dari Modul 3 pada kotak **Rekap Modul 3 (Hybrid)**.
4. Plugin memeriksa sidik-jari data. Jika tidak cocok, gunakan sumber layer yang sama atau ulangi Modul 3.
5. Pasangan aturan dipertahankan; AI menilai kandidat secara independen. Konflik hasil masuk `06_konflik_ai_rule` untuk studio.

**Kapan mencentang izin Level 1 otomatis?** Hanya untuk model `GOLD_TESTED_REVIEW_REQUIRED`, skor minimum sekurangnya sebesar ambang yang diuji dalam metadata, dan setelah kebijakan verifikasi organisasi disepakati. Jangan mengaktifkan ini hanya untuk membuat jumlah Level 1 bertambah.

### Cara membaca output

| Output | Artinya |
|---|---|
| `01_padanan_level1` | Pasangan yang benar-benar diterima otomatis; dalam Full AI dapat kosong jika model belum lolos GOLD atau izin tidak dicentang |
| `02_bpn_level2`, `03_pbb_level2` | Objek yang belum memiliki pasangan otomatis |
| `04_rekomendasi_ai_studio` | Kandidat terbaik per BPN yang belum otomatis dipadukan |
| `05_usulan_ai` | **Usulan**, bukan keputusan resmi; bisa ada meskipun Level 1 AI = 0 |
| `06_konflik_ai_rule` | Kandidat AI yang menggunakan NIB/NOP yang sudah dipakai aturan (Hybrid) |
| `rekap_csv.zip` | Seluruh skor dan alasan kandidat diterima/ditolak |
| `laporan_modul5.pdf` | Ringkasan tingkat pemaduan, usulan AI, konflik, dan peringatan |

## Perbandingan enam percobaan

Jalankan training tiga kali: SILVER Only, GOLD Only, SILVER + GOLD (folder berbeda). Untuk masing-masing model, jalankan Modul 5 dua kali: Full AI dan Hybrid. Gunakan **layer, kolom luas, radius, skor, margin, dan kelompok GOLD pengujian yang sama**. Bandingkan:

- Precision dan recall pada GOLD independen (bukan jumlah pasangan saja).
- Jumlah usulan AI, Level 1 AI yang benar-benar diterima, dan konflik NIB/NOP.
- Persentase usulan yang diverifikasi benar oleh operator.

## Batasan

- Pengujian program independen dari QGIS telah dilakukan, tetapi **GUI/ekspor layer di QGIS belum diuji langsung** pada komputer pembuat paket. Mulai dengan subset kecil dan cek PDF, seluruh GeoPackage, serta record contoh.
- `joblib` memuat objek Python: gunakan hanya model yang dibuat/dipercaya sendiri.
- GOLD dari area yang sangat kecil tidak membuktikan kemampuan generalisasi ke kelurahan lain. Tingkatkan variasi GOLD dan verifikasi hasil studio sebelum penggunaan operasional.
