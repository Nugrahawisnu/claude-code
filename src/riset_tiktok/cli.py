"""CLI: riset-tiktok @username [--maks-video N] [--keluar file.xlsx | --csv]."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

from .browser import Diblokir, GagalAkses, PenjelajahTikTok, Sumber
from .ekspor import tulis_csv, tulis_excel
from .models import Produk, Profil, Video
from .parser import (
    DataTidakDitemukan,
    gabung_statistik_produk,
    parse_item_list,
    parse_produk,
    parse_profil,
)


def _log(pesan: str) -> None:
    print(pesan, file=sys.stderr)


def jalankan_riset(
    sumber: Sumber, username: str, maks_video: int, maks_produk: int
) -> tuple[Profil, list[Video], list[Produk]]:
    _log(f"Membuka profil @{username} ...")
    html, halaman_video = sumber.riset_profil(username, maks_video)
    profil = parse_profil(html)
    _log(f"  {profil.nama} | {profil.followers} followers | {profil.jumlah_video} video")

    videos: list[Video] = []
    sudah: set[str] = set()
    for data in halaman_video:
        for video in parse_item_list(data, profil.username)[0]:
            if video.video_id not in sudah:
                sudah.add(video.video_id)
                videos.append(video)
    videos = videos[:maks_video]
    if not videos:
        _log("  Peringatan: daftar video tidak tertangkap (mungkin diblokir atau akun privat).")
    _log(f"  {len(videos)} video diambil")

    product_ids: list[str] = []
    for video in videos:
        for pid in video.product_ids:
            if pid not in product_ids:
                product_ids.append(pid)
    _log(f"  {len(product_ids)} produk keranjang kuning ditemukan di video")
    if len(product_ids) > maks_produk:
        _log(f"  Hanya {maks_produk} produk pertama yang dibuka (--maks-produk)")

    produk: list[Produk] = []
    diblokir = False
    for i, pid in enumerate(product_ids):
        if i >= maks_produk or diblokir:
            produk.append(Produk(product_id=pid))
            continue
        _log(f"  Produk {i + 1}/{min(len(product_ids), maks_produk)}: {pid}")
        try:
            halaman, url = sumber.produk_html(pid)
            produk.append(parse_produk(halaman, pid, url))
        except DataTidakDitemukan as e:
            _log(f"    Lewati detail: {e}")
            produk.append(Produk(product_id=pid))
        except Diblokir as e:
            _log(f"    Berhenti membuka produk: {e}")
            diblokir = True
            produk.append(Produk(product_id=pid))
        except GagalAkses as e:
            _log(f"    Lewati detail: {e}")
            produk.append(Produk(product_id=pid))

    gabung_statistik_produk(produk, videos)
    produk.sort(key=lambda p: p.total_views_video, reverse=True)
    return profil, videos, produk


def buat_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="riset-tiktok",
        description="Riset akun TikTok publik beserta produk keranjang kuning-nya.",
    )
    ap.add_argument("username", help="username TikTok, boleh pakai @")
    ap.add_argument("--maks-video", type=int, default=30, help="jumlah video (default 30)")
    ap.add_argument("--maks-produk", type=int, default=50,
                    help="jumlah halaman produk yang dibuka (default 50)")
    ap.add_argument("--keluar", type=Path,
                    help="file .xlsx, atau folder kalau --csv (default: hasil_<username>.xlsx)")
    ap.add_argument("--csv", action="store_true", help="tulis 3 file CSV, bukan Excel")
    ap.add_argument("--region", default="ID", help="region TikTok Shop (default ID)")
    ap.add_argument("--tampilkan-browser", action="store_true",
                    help="buka jendela browser (tidak headless)")
    ap.add_argument("--chromium", help="path Chromium kalau tidak pakai bawaan Playwright")
    return ap


def main(
    argv: list[str] | None = None,
    buat_sumber: Callable[[argparse.Namespace], AbstractContextManager[Sumber]] | None = None,
) -> int:
    args = buat_parser().parse_args(argv)
    username = args.username.strip().lstrip("@")
    if not username:
        _log("Username kosong.")
        return 2
    if args.maks_video < 1 or args.maks_produk < 0:
        _log("--maks-video minimal 1 dan --maks-produk tidak boleh negatif.")
        return 2

    if buat_sumber is None:
        def buat_sumber(a: argparse.Namespace) -> PenjelajahTikTok:
            return PenjelajahTikTok(headless=not a.tampilkan_browser, region=a.region,
                                    chromium=a.chromium)

    try:
        with buat_sumber(args) as sumber:
            profil, videos, produk = jalankan_riset(
                sumber, username, args.maks_video, args.maks_produk
            )
    except Diblokir as e:
        _log(f"Gagal: {e}. Coba lagi nanti, atau pakai --tampilkan-browser.")
        return 1
    except GagalAkses as e:
        _log(f"Gagal: {e}. Periksa koneksi internet.")
        return 1
    except DataTidakDitemukan as e:
        _log(f"Gagal membaca profil: {e}")
        return 1

    if args.csv:
        for path in tulis_csv(args.keluar or Path("."), f"hasil_{username}", profil, videos,
                              produk):
            print(path)
    else:
        print(tulis_excel(args.keluar or Path(f"hasil_{username}.xlsx"), profil, videos, produk))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
