# tiktok-potong

Potong otomatis bagian depan & belakang video, lalu ubah ke format TikTok
(1080x1920, 9:16, latar blur). Tidak perlu library Python tambahan, hanya
**Python 3.9+** dan **ffmpeg**.

## Pasang ffmpeg
- Windows: `winget install ffmpeg`
- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt install ffmpeg`

## Cara pakai

```bash
# Buang hening di awal & akhir secara otomatis (default)
python3 tiktok_potong.py video.mp4

# Tambah potongan tetap: buang 2 dtk depan dan 3 dtk belakang
python3 tiktok_potong.py video.mp4 --awal 2 --akhir 3

# Proses semua video dalam satu folder, simpan ke folder lain
python3 tiktok_potong.py folder_video/ -o siap_upload/

# Lihat dulu rencana potongannya tanpa membuat file
python3 tiktok_potong.py video.mp4 --awal 2 --coba
```

Hasil disimpan di folder `hasil/` dengan nama `<nama>_tiktok.mp4`.

## Opsi

| Opsi | Arti | Default |
|---|---|---|
| `--awal DETIK` | detik yang dibuang di depan | 0 |
| `--akhir DETIK` | detik yang dibuang di belakang | 0 |
| `--no-hening` | matikan deteksi hening | aktif |
| `--ambang-db` | suara di bawah ini dianggap hening (makin kecil makin ketat) | -35 |
| `--min-hening` | panjang hening minimal (detik) | 0.5 |
| `--tanpa-format` | hanya potong, rasio asli dipertahankan | – |
| `-o, --keluar` | folder hasil | `hasil/` |
| `--coba` | pratinjau tanpa membuat file | – |

Kalau detik tetap dan hening sama-sama dipakai, diambil potongan yang
**paling banyak** di masing-masing sisi. Hening di tengah video tidak disentuh.

Tips: kalau suara latar (kipas, AC) membuat hening tidak terdeteksi, naikkan
ambangnya, misal `--ambang-db -30`.

## Pengembangan
```bash
./scripts/cek.sh   # ruff + pytest
```
