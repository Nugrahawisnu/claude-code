"""Potong otomatis bagian depan & belakang video lalu siapkan untuk TikTok.

Pemotongan memakai dua cara sekaligus:
- detik tetap (--awal / --akhir), dan
- deteksi hening di awal & akhir video (ffmpeg silencedetect).

Hasilnya diubah ke 1080x1920 (9:16) dengan latar blur.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

LEBAR, TINGGI = 1080, 1920
DURASI_MINIMAL = 1.0
BATAS_TIKTOK = 10 * 60
EKSTENSI_VIDEO = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}

_POLA_MULAI = re.compile(r"silence_start:\s*(-?[\d.]+)")
_POLA_SELESAI = re.compile(r"silence_end:\s*(-?[\d.]+)")


def parse_hening(stderr: str) -> list[tuple[float, float | None]]:
    """Ambil pasangan (mulai, selesai) hening dari output silencedetect.

    Selesai bernilai None kalau hening berlanjut sampai akhir video.
    """
    hasil: list[tuple[float, float | None]] = []
    mulai: float | None = None
    for baris in stderr.splitlines():
        m = _POLA_MULAI.search(baris)
        if m:
            mulai = max(0.0, float(m.group(1)))
            continue
        m = _POLA_SELESAI.search(baris)
        if m and mulai is not None:
            hasil.append((mulai, float(m.group(1))))
            mulai = None
    if mulai is not None:
        hasil.append((mulai, None))
    return hasil


def hitung_potongan(
    durasi: float,
    hening: list[tuple[float, float | None]],
    awal: float = 0.0,
    akhir: float = 0.0,
    toleransi: float = 0.1,
) -> tuple[float, float]:
    """Tentukan titik mulai & selesai video hasil (dalam detik).

    Hening yang menyentuh awal video menggeser titik mulai; hening yang
    menyentuh akhir video memajukan titik selesai. Hening di tengah diabaikan.
    Detik tetap (awal/akhir) dan hening digabung: diambil potongan terbanyak.
    """
    if awal < 0 or akhir < 0:
        raise ValueError("--awal dan --akhir tidak boleh negatif")

    mulai = awal
    selesai = durasi - akhir
    for h_mulai, h_selesai in hening:
        ujung = durasi if h_selesai is None else h_selesai
        if h_mulai <= toleransi:
            mulai = max(mulai, ujung)
        if ujung >= durasi - toleransi:
            selesai = min(selesai, h_mulai)

    if selesai - mulai < DURASI_MINIMAL:
        raise ValueError(
            f"Sisa video terlalu pendek ({max(0.0, selesai - mulai):.2f} dtk). "
            "Kurangi --awal/--akhir atau ubah pengaturan hening."
        )
    return round(mulai, 3), round(selesai, 3)


def filter_tiktok() -> str:
    """Filter 9:16: video di tengah, latar video yang sama di-blur."""
    return (
        "[0:v]split=2[latar][depan];"
        f"[latar]scale={LEBAR}:{TINGGI}:force_original_aspect_ratio=increase,"
        f"crop={LEBAR}:{TINGGI},boxblur=20:2[blur];"
        f"[depan]scale={LEBAR}:{TINGGI}:force_original_aspect_ratio=decrease:"
        "force_divisible_by=2[atas];"
        "[blur][atas]overlay=(W-w)/2:(H-h)/2,setsar=1,fps=30,format=yuv420p[v]"
    )


def bangun_perintah_ffmpeg(
    masuk: str,
    keluar: str,
    mulai: float,
    selesai: float,
    format_tiktok: bool = True,
) -> list[str]:
    """Susun argumen ffmpeg untuk memotong (dan memformat) satu video."""
    perintah = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{mulai:.3f}", "-i", masuk, "-t", f"{selesai - mulai:.3f}",
    ]
    if format_tiktok:
        perintah += ["-filter_complex", filter_tiktok(), "-map", "[v]", "-map", "0:a?"]
    else:
        perintah += ["-map", "0:v:0", "-map", "0:a?", "-pix_fmt", "yuv420p"]
    perintah += [
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        keluar,
    ]
    return perintah


def durasi(path: Path) -> float:
    """Durasi video dalam detik (via ffprobe)."""
    hasil = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(hasil.stdout.strip())


def cari_hening(path: Path, ambang_db: float = -35, min_hening: float = 0.5):
    """Jalankan silencedetect; video tanpa audio menghasilkan daftar kosong."""
    hasil = subprocess.run(
        ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn",
         "-af", f"silencedetect=noise={ambang_db}dB:d={min_hening}", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    if hasil.returncode != 0:
        return []
    return parse_hening(hasil.stderr)


def kumpulkan_video(masukan: Path) -> list[Path]:
    if masukan.is_dir():
        return sorted(
            p for p in masukan.iterdir()
            if p.suffix.lower() in EKSTENSI_VIDEO and not p.stem.endswith("_tiktok")
        )
    return [masukan]


def proses(path: Path, folder_keluar: Path, args: argparse.Namespace) -> Path:
    total = durasi(path)
    hening = cari_hening(path, args.ambang_db, args.min_hening) if args.hening else []
    mulai, selesai = hitung_potongan(total, hening, args.awal, args.akhir)
    keluar = folder_keluar / f"{path.stem}_tiktok.mp4"
    perintah = bangun_perintah_ffmpeg(
        str(path), str(keluar), mulai, selesai, not args.tanpa_format
    )

    print(f"• {path.name}: {total:.2f} dtk → potong {mulai:.2f}–{selesai:.2f} "
          f"({selesai - mulai:.2f} dtk)")
    if selesai - mulai > BATAS_TIKTOK:
        print("  ⚠ Hasil lebih dari 10 menit, melebihi batas unggah TikTok.")
    if args.coba:
        print("  " + " ".join(perintah))
    else:
        subprocess.run(perintah, check=True)
        print(f"  ✔ {keluar}")
    return keluar


def buat_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Potong otomatis depan & belakang video lalu ubah ke format TikTok 9:16.",
    )
    p.add_argument("masukan", type=Path, help="file video atau folder berisi video")
    p.add_argument("-o", "--keluar", type=Path, default=Path("hasil"),
                   help="folder hasil (default: hasil/)")
    p.add_argument("--awal", type=float, default=0.0, help="detik yang dibuang di depan")
    p.add_argument("--akhir", type=float, default=0.0, help="detik yang dibuang di belakang")
    p.add_argument("--hening", action=argparse.BooleanOptionalAction, default=True,
                   help="buang hening di awal & akhir (default: aktif)")
    p.add_argument("--ambang-db", type=float, default=-35,
                   help="batas suara dianggap hening, dalam dB (default: -35)")
    p.add_argument("--min-hening", type=float, default=0.5,
                   help="panjang hening minimal, detik (default: 0.5)")
    p.add_argument("--tanpa-format", action="store_true",
                   help="hanya potong, jangan ubah ke 9:16")
    p.add_argument("--coba", action="store_true",
                   help="tampilkan rencana potongan tanpa membuat file")
    return p


def main(argv: list[str] | None = None) -> int:
    args = buat_parser().parse_args(argv)
    for alat in ("ffmpeg", "ffprobe"):
        if shutil.which(alat) is None:
            print(f"✘ {alat} tidak ditemukan. Pasang ffmpeg dulu.", file=sys.stderr)
            return 2
    if not args.masukan.exists():
        print(f"✘ {args.masukan} tidak ada.", file=sys.stderr)
        return 2

    daftar = kumpulkan_video(args.masukan)
    if not daftar:
        print(f"✘ Tidak ada video di {args.masukan}.", file=sys.stderr)
        return 2
    if not args.coba:
        args.keluar.mkdir(parents=True, exist_ok=True)

    gagal = 0
    for path in daftar:
        try:
            proses(path, args.keluar, args)
        except (ValueError, subprocess.CalledProcessError) as e:
            gagal += 1
            print(f"  ✘ {path.name}: {e}", file=sys.stderr)
    return 1 if gagal else 0


if __name__ == "__main__":
    sys.exit(main())
