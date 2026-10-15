# tiktok-potong

Dua alat:
1. `tiktok_potong.py`: potong depan/belakang + format 9:16.
2. `tiktok_upload.py`: kirim ke inbox TikTok sebagai draf + lembar posting keranjang kuning.

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

## Upload ke TikTok + keranjang kuning (`tiktok_upload.py`)

API resmi TikTok **tidak bisa memasang keranjang kuning**. Jadi alurnya:
video dikirim ke **kotak masuk (inbox) TikTok sebagai draf**, lalu Anda
pasang produk dan posting di aplikasi. Tool ini juga membuat
`lembar_posting.md` berisi caption + nama produk tiap video supaya cepat.

### Persiapan (sekali saja)
1. Buka [developers.tiktok.com](https://developers.tiktok.com), login, buat app
   (platform **Desktop**).
2. Tambahkan produk **Login Kit** dan **Content Posting API**, aktifkan scope
   `video.upload`.
3. Di Login Kit, daftarkan Redirect URI: `http://localhost:8585/callback/`
4. Salin **Client key** dan **Client secret**, lalu set di terminal:
   ```bash
   export TIKTOK_CLIENT_KEY="..."      # Windows: set TIKTOK_CLIENT_KEY=...
   export TIKTOK_CLIENT_SECRET="..."
   ```
5. Login akun TikTok (browser akan terbuka):
   ```bash
   python3 tiktok_upload.py login
   ```
   Kalau browser tidak bisa kembali ke localhost, pakai `login --tempel` lalu
   tempel URL dari address bar.

Selama app belum lolos review TikTok, upload hanya berfungsi untuk akun yang
terdaftar sebagai tester/pemilik app. Itu cukup untuk akun sendiri.

### Pemakaian harian
```bash
# 1. Potong & format
python3 tiktok_potong.py mentah/ -o hasil/

# 2. (Opsional) buat daftar caption/produk, lalu isi di Excel/Sheets
python3 tiktok_upload.py templat hasil/

# 3. Kirim ke inbox TikTok
python3 tiktok_upload.py kirim hasil/
```

Isi `daftar_upload.csv`:

| video | caption | hashtag | produk |
|---|---|---|---|
| sepatu_tiktok.mp4 | Empuk banget buat lari! | #racuntiktok #fyp | Sepatu Lari X |

Lalu di HP: buka **notifikasi TikTok** → ketuk draf → Berikutnya →
**Tambah link → Produk** → pilih dari etalase → tempel caption dari
`lembar_posting.md` → **Posting**.

Catatan:
- Video yang sudah terkirim dicatat di `riwayat_upload.json` dan dilewati.
  Pakai `--ulang` untuk mengirim lagi.
- TikTok membatasi draf yang menunggu (sekitar 5 per 24 jam). Posting draf
  yang ada dulu sebelum mengirim lagi.
- `kirim --coba` untuk melihat rencana tanpa mengirim.
- Token login disimpan di `~/.config/tiktok_potong/token.json` (di luar repo).

## Pengembangan
```bash
./scripts/cek.sh   # ruff + pytest
```
