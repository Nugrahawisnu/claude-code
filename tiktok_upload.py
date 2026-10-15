"""Kirim video ke TikTok sebagai draf (inbox) lewat Content Posting API resmi.

API TikTok tidak bisa memasang keranjang kuning, jadi tool ini juga membuat
"lembar posting": caption, hashtag, dan produk per video untuk diselesaikan
di aplikasi TikTok.
"""

from __future__ import annotations

import csv
import hashlib
import secrets
from pathlib import Path

MB = 1024 * 1024
CHUNK_MIN = 5 * MB
CHUNK_STANDAR = 10 * MB
CHUNK_TERAKHIR_MAKS = 128 * MB
KOLOM_CSV = ["video", "caption", "hashtag", "produk"]


def rencana_chunk(ukuran: int, chunk: int = CHUNK_STANDAR) -> tuple[int, int]:
    """Kembalikan (chunk_size, total_chunk_count) sesuai aturan TikTok.

    File < 5 MB dikirim utuh. Selain itu, sisa pembagian diserap chunk terakhir.
    """
    if ukuran <= 0:
        raise ValueError("Ukuran file tidak valid")
    if ukuran < CHUNK_MIN:
        return ukuran, 1
    return chunk, ukuran // chunk


def rentang_chunk(ukuran: int, chunk_size: int, total: int) -> list[tuple[int, int]]:
    """Daftar (awal, akhir) byte inklusif untuk tiap chunk."""
    rentang = []
    for i in range(total):
        awal = i * chunk_size
        akhir = ukuran - 1 if i == total - 1 else awal + chunk_size - 1
        rentang.append((awal, akhir))
    terakhir = rentang[-1][1] - rentang[-1][0] + 1
    if terakhir > CHUNK_TERAKHIR_MAKS:
        raise ValueError("Chunk terakhir melebihi 128 MB")
    return rentang


def header_chunk(awal: int, akhir: int, ukuran: int) -> dict[str, str]:
    return {
        "Content-Type": "video/mp4",
        "Content-Length": str(akhir - awal + 1),
        "Content-Range": f"bytes {awal}-{akhir}/{ukuran}",
    }


def buat_pkce() -> tuple[str, str]:
    """(verifier, challenge). TikTok desktop memakai SHA256 berformat hex."""
    verifier = secrets.token_urlsafe(48)[:64]
    return verifier, challenge_dari(verifier)


def challenge_dari(verifier: str) -> str:
    return hashlib.sha256(verifier.encode("ascii")).hexdigest()


def baca_daftar(path: Path) -> dict[str, dict[str, str]]:
    """Baca CSV daftar upload, dikunci berdasarkan nama file video."""
    with path.open(newline="", encoding="utf-8-sig") as f:
        baris = list(csv.DictReader(f))
    return {Path(b["video"].strip()).name: b for b in baris if b.get("video", "").strip()}


def tulis_templat(path: Path, videos: list[Path]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KOLOM_CSV)
        w.writeheader()
        for v in videos:
            w.writerow({"video": v.name, "caption": "", "hashtag": "", "produk": ""})


def lembar_posting(entri: list[dict[str, str]]) -> str:
    """Markdown panduan menyelesaikan posting + pasang keranjang kuning."""
    bagian = [
        "# Lembar posting TikTok",
        "",
        "Untuk tiap video: buka notifikasi TikTok (kotak masuk) → ketuk draf video → "
        "Berikutnya → **Tambah link → Produk** → pilih produk dari etalase → "
        "tempel caption → **Posting**.",
        "",
    ]
    for i, e in enumerate(entri, 1):
        teks = " ".join(t for t in (e.get("caption", ""), e.get("hashtag", "")) if t).strip()
        bagian += [
            f"## {i}. {e['video']}",
            "",
            f"- Produk keranjang kuning: **{e.get('produk') or '(isi sendiri)'}**",
            "- Caption:",
            "",
            "```",
            teks or "(kosong)",
            "```",
            "",
        ]
    return "\n".join(bagian)
