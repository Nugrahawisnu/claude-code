# Panduan singkat: Claude Code yang mudah dan aman

Repo ini sudah berisi pengaman otomatis. Anda cukup mengikuti alur di bawah.

## Alur harian

```bash
git checkout main && git pull
git checkout -b nama-fitur      # 1. selalu kerja di branch
claude                          # 2. buka Claude Code
```

Di dalam Claude Code:

1. **Tekan `Shift+Tab` dua kali** untuk masuk Plan mode. Claude hanya membaca dan membuat rencana, tanpa mengubah file.
2. **Minta satu tugas kecil.** Contoh: "Tambahkan validasi email di form login. Buat rencananya dulu."
3. **Baca rencananya, lalu setujui.** Claude mulai mengedit.
4. **Biarkan cek otomatis bekerja.** Sebelum Claude selesai, hook menjalankan `scripts/cek.sh`. Kalau gagal, Claude memperbaikinya sendiri.
5. **Minta review.** Ketik `/code-review` untuk memeriksa bug di perubahan.
6. **Minta commit**, lalu `git push -u origin nama-fitur` dan buat pull request.

Kalau sesi sudah panjang dan Claude mulai lupa konteks, ketik `/compact`. Untuk tugas baru yang tidak berhubungan, ketik `/clear`.

## Pengaman yang sudah terpasang

| File | Fungsinya |
|---|---|
| `CLAUDE.md` | Aturan yang dibaca Claude otomatis di setiap sesi. |
| `.claude/settings.json` | Memblokir perintah berbahaya dan pembacaan `.env`. Mengizinkan perintah baca-saja tanpa bertanya. |
| `.claude/hooks/tolak-edit-main.sh` | Menolak edit file saat Anda di branch `main` atau `master`. |
| `.claude/hooks/cek-sebelum-selesai.sh` | Menjalankan lint dan tes sebelum Claude berhenti. Gagal berarti Claude harus memperbaiki dulu. |
| `scripts/cek.sh` | Satu perintah untuk lint dan tes. Mendeteksi Node, Python, Go, Rust, dan PHP otomatis. |

Hook Stop hanya memaksa Claude lanjut satu kali per giliran, jadi tidak akan berputar tanpa akhir.

## Kalau hasilnya rusak

```bash
git diff                     # lihat apa yang berubah
git restore .                # buang semua perubahan yang belum di-commit
git checkout main            # kembali ke kode aman
git revert <hash-commit>     # batalkan commit tertentu yang sudah dibuat
```

Karena Anda selalu kerja di branch, `main` tidak pernah tersentuh.

## Setelah memilih stack

1. Isi bagian "Perintah proyek" di `CLAUDE.md`.
2. Pastikan ada skrip `test` (dan `lint` bila ada) supaya `scripts/cek.sh` punya sesuatu untuk dijalankan.
3. Kalau belum punya tes, minta Claude: "Buatkan tes dasar untuk fungsi X sebelum kita mengubahnya."

## Mematikan pengaman sementara

Buat `.claude/settings.local.json` (tidak ikut di-commit) untuk pengaturan pribadi. Untuk mematikan semua hook sementara:

```json
{ "disableAllHooks": true }
```

Hapus lagi setelah selesai.
