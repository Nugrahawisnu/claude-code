# Aturan kerja untuk Claude

Tujuan utama: perubahan kecil, teruji, dan mudah dibatalkan. Kode tidak boleh rusak.

## Alur kerja wajib
1. Jangan pernah mengedit di branch `main` atau `master`. Buat branch dulu: `git checkout -b nama-fitur`.
2. Untuk perubahan yang menyentuh lebih dari satu file, tulis rencana dulu dan tunggu persetujuan.
3. Kerjakan satu tugas kecil sampai selesai sebelum pindah ke tugas lain.
4. Setelah mengubah kode, jalankan `./scripts/cek.sh`. Perbaiki sampai lulus.
5. Commit kecil dengan pesan jelas setiap satu langkah selesai dan cek lulus.

## Larangan
- Jangan menghapus, melewati, atau melemahkan tes supaya cek lulus. Perbaiki kodenya.
- Jangan `git push --force`, `git reset --hard`, atau `rm -rf`.
- Jangan membaca atau menampilkan isi `.env`.
- Jangan mengubah file di luar lingkup tugas tanpa bertanya.
- Jangan menambah dependensi baru tanpa menyebutkannya dan alasannya.

## Kalau ragu
Tanya dulu. Lebih baik satu pertanyaan daripada satu perubahan yang merusak.

## Perintah proyek
<!-- Isi setelah stack dipilih. Contoh:
- Install: npm install
- Jalankan: npm run dev
- Tes: npm test
- Lint: npm run lint
-->
- Cek semua (lint + tes): `./scripts/cek.sh`
