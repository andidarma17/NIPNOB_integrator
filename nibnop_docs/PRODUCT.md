# PRODUCT.md — Konteks produk NIB–NOP Integrator

Dokumen konteks untuk perancang/AI (mis. Impeccable): **siapa penggunanya, apa tujuannya, nada, dan hal yang tidak boleh dilakukan.**
Turunan dari `README.md`, `PANDUAN_PENGGUNA.pdf`, `metadata.txt` dan kode plugin. Bagian bertanda *(asumsi)* adalah inferensi dan perlu dikonfirmasi pemilik produk.

## Apa ini

Plugin **QGIS 3.28–3.44 / 4.x** (v0.9.4, *beta/experimental*) untuk **mengaudit dan memadukan data bidang tanah BPN (NIB, sertipikat/persil) dengan objek pajak PBB (NOP)** melalui enam tools berurutan:

1. Pemeriksaan kelengkapan atribut
2. Kualitas spasial & perbaikan geometri
3. Penentuan level pemaduan berbasis aturan (Level 1 otomatis / Level 2 studio)
4. Training AI (RandomForest/XGBoost; label GOLD/SILVER)
5. Inference AI → Level 1/2
6. Verifikasi studio interaktif di peta (pelabelan manusia)

Setiap tool menghasilkan **layer spasial, `rekap_csv.zip`, dan satu laporan PDF** (`laporan_modulN.pdf`). Laporan PDF adalah fokus desain ulang.

## Pengguna

| Persona | Kebutuhan terhadap laporan |
|---|---|
| **Operator/analis pemaduan** (utama) | Tahu hasil modul sekali lihat, tahu apa yang harus diperbaiki/diverifikasi berikutnya, tidak salah menafsirkan "Level 2" atau skor AI |
| **Supervisor / penanggung jawab data** | Menyetujui atau menolak lanjut ke modul berikutnya; butuh jejak audit (parameter, input, operator, bukti) |
| **Pengembang / peneliti / auditor** | Mereproduksi hasil; memeriksa metrik model (Precision, CI95, FP) |
| Konteks pakai *(asumsi)* | Kantor pertanahan/pemda di Indonesia; layar desktop, sering dicetak A4 hitam-putih; penutur bahasa Indonesia; pengguna QGIS menengah |

## Tujuan produk

* Memadukan NIB ↔ NOP **hanya bila meyakinkan** (1 NIB : 1 NOP, overlap, kesamaan luas, tak duplikat).
* Menyerahkan kasus ambigu ke manusia (Level 2 → studio) **tanpa** menganggapnya salah.
* Menggunakan AI sebagai **alat bantu prioritas verifikasi**, bukan penentu hukum.

## Nada dan kepribadian

Teliti, konservatif, transparan akan batasan, tidak membesar-besarkan. Rendah hati terhadap AI ("rekomendasi studio", "belum dapat dinilai"). Formal-teknis namun tidak birokratis-berat; kalimat pendek, aktif, bahasa Indonesia baku. Bukan: promosi, "dashboard startup", gamifikasi.

## Prinsip yang tidak boleh dilanggar oleh desain

1. **Jangan pernah menyajikan angka yang tidak sah sebagai valid.** Tanpa GOLD independen → "BELUM DAPAT DINILAI", bukan angka TRAIN. Tanpa data → empty state yang menjelaskan, bukan grafik kosong/dibuat-buat.
2. **Level 2 ≠ salah; "belum pasti" ≠ label 0.** Visual Level 2 tidak boleh bernada galat/gagal.
3. **Skor AI ≠ probabilitas ≠ bukti.** Peringatan "bukan bukti hukum" harus terlihat (bukan hanya catatan kaki).
4. **Peta PDF = visualisasi indikatif**, bukan peta pendaftaran resmi.
5. **Gap hasil delineasi bukan NIB baru**; overlap ditandai, bukan dikoreksi sepihak.
6. **Identitas (NIB/NOP) tidak boleh terpotong/ambigu** di laporan.
7. **Parameter & sumber input** harus bisa ditelusuri dari laporan (ambang overlap/kesamaan/deviasi, layer, kolom, CRS, versi).
8. Output harus layak **dicetak hitam-putih** dan terbaca oleh pengguna buta warna.

## Anti-referensi (hindari)

* Tampilan "BI dashboard" penuh kartu warna-warni dan gradasi.
* Merah/hijau semaphore sebagai satu-satunya penanda status.
* Grafik 3D, donut dekoratif, ikon emoji.
* Teks peringatan kecil abu-abu di ujung dokumen.
* Klaim presisi palsu (mis. "98,7 %" dari sampel kecil tanpa CI).

## Istilah domain (ringkas — lengkap di `DOMAIN_RULES.md`)

NIB = Nomor Identifikasi Bidang (BPN). NOP = Nomor Objek Pajak (PBB). BPN = Badan Pertanahan Nasional (kini Kementerian ATR/BPN). PBB = Pajak Bumi dan Bangunan. Level 1 = pasangan otomatis lolos semua gerbang. Level 2 = perlu verifikasi studio. GOLD = label terverifikasi manusia + bukti. SILVER = label tebakan aturan (lemah). Studio = proses verifikasi manual di peta.
