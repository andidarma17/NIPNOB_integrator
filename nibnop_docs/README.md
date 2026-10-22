# Dokumentasi NIB–NOP Integrator (v0.9.4)

Paket dokumen ini disusun dari pemeriksaan paket `NIBNOP_Integrator_QGIS3_QGIS4_v0.9.4_MACOS_PDF_FIX.zip`. Letakkan semua berkas di **root repo/plugin** (atau di `docs/`) sebelum menjalankan Impeccable.

| Berkas | Isi | Kapan dibaca |
|---|---|---|
| **[`DESIGN.md`](DESIGN.md)** | Desain laporan per modul: warna, tipografi, layout, komponen grafik, 22 temuan masalah, peran semantik, batasan renderer, opsi implementasi | **Desain ulang laporan** |
| [`REPORT_SPEC.md`](REPORT_SPEC.md) | Isi halaman-per-halaman tiap laporan, kontrak parameter fungsi, empty state | Desain ulang / implementasi |
| [`PRODUCT.md`](PRODUCT.md) | Pengguna, tujuan, nada, prinsip tak boleh dilanggar, anti-referensi | Konteks awal |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Struktur paket, lapisan, alur data antarmodul, kompatibilitas Qt5/Qt6 | Menyentuh kode |
| [`MODULES.md`](MODULES.md) | Enam tools: input, parameter, proses, keluaran | Memahami fitur |
| [`DOMAIN_RULES.md`](DOMAIN_RULES.md) | Aturan Level 1/2, GOLD/SILVER, fitur, metrik, glosarium | Logika/validasi |
| [`DATA_SCHEMA.md`](DATA_SCHEMA.md) | Berkas keluaran, skema CSV/JSON, kosakata status | Data & label UI |
| [`STATUS_AND_TESTING.md`](STATUS_AND_TESTING.md) | Status kematangan, hasil pemeriksaan, utang teknis, uji penerimaan | QA/rilis |
| [`CLAUDE.md`](CLAUDE.md) | Petunjuk ringkas untuk asisten AI | Otomatis oleh Claude Code |
| `reference/` | Gambar tata letak laporan **saat ini** (6 modul) + skrip render | Referensi "sebelum" |

Catatan nama: Impeccable umumnya membaca `PRODUCT.md` dan `DESIGN.md` (huruf kapital) di root proyek. Pada sistem berkas yang membedakan huruf besar/kecil, ganti nama menjadi `design.md` bila alat Anda mencarinya demikian.

Ringkasan temuan utama desain: tidak ada ringkasan eksekutif; status/peringatan tak punya bobot visual; satu grafik per halaman (banyak ruang kosong); pasangan warna hijau–merah tak terbedakan (kontras luminans 1,11:1); oranye < 3:1; peta tanpa skala/panah utara/CRS; ID dipotong di tabel; dua palet berbeda (Modul 4 vs lainnya); bug render plot Modul 4.
