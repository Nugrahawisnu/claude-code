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

## Menjaga struktur kode

Menambah file boleh, asal lokasinya sesuai `ARSITEKTUR.md`. Empat lapis pengaman:

| Lapis | File | Kapan bekerja |
|---|---|---|
| Aturan | `ARSITEKTUR.md`, `CLAUDE.md` | Dibaca Claude setiap sesi. |
| Hook | `.claude/hooks/tolak-file-luar-pola.sh` | Saat Claude membuat file baru di lokasi yang tidak sesuai pola: langsung ditolak. |
| Cek | `scripts/cek-struktur.sh` (dipanggil `scripts/cek.sh`) | Menolak file di luar pola, rename/hapus file, dan perubahan daftar pola. |
| Review | `.github/workflows/cek.yml` + proteksi `main` | Setiap PR. |

Pola lokasi ada di `.claude/struktur-izin.txt`. Hanya Anda yang mengubahnya. Kalau rename atau
hapus file memang disetujui: jalankan `IZINKAN_UBAH_STRUKTUR=1 ./scripts/cek.sh` secara lokal,
dan beri label `ubah-struktur` pada PR supaya CI mengizinkan.

## Menjalankan Claude Code di VPS

`scripts/agent-vps.sh` menjalankan Claude Code tanpa pengawasan dengan alur tetap: branch baru
`agent/...` dari `origin/main` → `claude -p` → `scripts/cek.sh` → commit → push → buka PR. Tidak
pernah push atau merge ke `main`. Kalau cek gagal, perubahan disimpan di branch lokal dan tidak
di-push. Log ada di `~/.claude-agent/log/`.

Persiapan sekali (sebagai root):

```bash
adduser --disabled-password claude-agent          # user khusus, bukan root
npm install -g @anthropic-ai/claude-code          # perlu Node.js
install -m 600 /dev/null /etc/claude-agent.env    # isi: ANTHROPIC_API_KEY=... (dan GH_TOKEN=... untuk gh)
```

Sebagai `claude-agent`:

```bash
git clone git@github.com:NAMA/REPO.git ~/repo     # pakai deploy key khusus repo ini
git -C ~/repo config user.name "claude-agent"
git -C ~/repo config user.email "claude-agent@localhost"
cd ~/repo && scripts/agent-vps.sh "Tambahkan tool cuaca beserta tesnya"
```

Untuk tugas berulang, pakai contoh `deploy/claude-agent.service` dan `deploy/claude-agent.timer`
(tugas dibaca dari `~/tugas.txt`).

Wajib di GitHub (Settings → Rules → Rulesets untuk `main`): wajib lewat PR, wajib CI `cek`
lulus, wajib 1 approval, blokir force-push. Ini pengaman terakhir kalau semua lapis lain lolos.

Catatan keamanan:
- Jangan pakai `--dangerously-skip-permissions`. Mode headless tetap memakai `.claude/settings.json`
  dan hook, jadi perintah di luar daftar izin otomatis ditolak.
- Aplikasi agent yang sudah jadi di-deploy dari `main` saja, di folder terpisah dari `~/repo`
  tempat Claude Code bekerja.
