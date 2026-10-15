"""Potong otomatis bagian depan & belakang video lalu siapkan untuk TikTok.

Pemotongan memakai dua cara sekaligus:
- detik tetap (--awal / --akhir), dan
- deteksi hening di awal & akhir video (ffmpeg silencedetect).

Hasilnya diubah ke 1080x1920 (9:16) dengan latar blur.
"""

from __future__ import annotations

import re

LEBAR, TINGGI = 1080, 1920
DURASI_MINIMAL = 1.0

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
