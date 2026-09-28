# Arsitektur

Dokumen ini adalah peta resmi struktur kode. Claude dan manusia wajib mengikutinya.
Menambah file boleh, asal lokasinya sesuai pola di bawah. Pola yang dicek mesin ada di
`.claude/struktur-izin.txt`; dokumen ini menjelaskan maksudnya.

> Versi awal, netral-stack. Setelah stack dipilih, sesuaikan contoh nama file dan
> perbarui `.claude/struktur-izin.txt` bersamaan (oleh manusia).

## Peta folder

| Folder | Isi | Aturan |
|---|---|---|
| `src/agent/` | Loop agent: menerima tugas, memanggil model, memanggil tool, mengembalikan hasil. | Boleh subfolder. Tidak berisi logika tool. |
| `src/tools/` | Tool yang bisa dipanggil agent. | **Satu tool = satu file**, langsung di folder ini (tanpa subfolder). Nama file = nama tool, contoh `cuaca`, `cari_dokumen`. |
| `src/prompts/` | Teks system prompt dan template prompt. | Hanya teks/template, tanpa logika. |
| `src/config/` | Pembacaan konfigurasi dan variabel lingkungan. | Satu-satunya tempat yang membaca env. Rahasia tidak ditulis di sini. |
| `src/` (akar) | Titik masuk aplikasi (mis. `main`, `index`, `app`). | Hanya file titik masuk, bukan tempat logika. |
| `tests/` | Tes. | Mencerminkan `src/`: tes untuk `src/tools/cuaca` ada di `tests/tools/`. |
| `scripts/` | Skrip bantu (cek, runner agent). | Langsung di folder ini. |
| `deploy/` | Berkas deploy VPS (systemd, dsb). | Langsung di folder ini. |
| `.claude/` | Pengaturan dan hook Claude Code. | Diubah hanya atas izin manusia. |
| `.github/workflows/` | CI. | |

## Contoh: fitur baru masuk ke mana?

- Agent perlu bisa mengecek cuaca → file baru di `src/tools/`, tes di `tests/tools/`.
- Mengubah cara agent memilih tool → edit di `src/agent/`.
- Mengganti gaya bahasa agent → edit di `src/prompts/`.
- Butuh API key baru → baca di `src/config/`, nilai asli di env VPS, contoh di `.env.example`.

## Yang tidak boleh tanpa izin manusia

- Memindahkan, mengganti nama, atau menghapus file/folder yang sudah ada.
- Membuat folder tingkat atas baru.
- Mengubah `.claude/struktur-izin.txt`.

Kalau fitur tidak cocok ke folder mana pun, berhenti dan tanya. Jangan mengarang lokasi baru.
