"""Fungsi murni untuk mengubah HTML/JSON halaman TikTok menjadi model.

Tidak ada akses jaringan di sini, jadi semuanya bisa dites dengan fixture.
Struktur halaman TikTok sering berubah; kalau hasil mulai kosong, perbaiki di file ini.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from datetime import datetime, timezone
from html import unescape
from typing import Any

from .models import Produk, Profil, Video

_SCRIPT_RE = re.compile(
    r"<script[^>]*\bid=\"(?P<id>[^\"]+)\"[^>]*>(?P<isi>.*?)</script>", re.DOTALL
)
_LD_JSON_RE = re.compile(
    r"<script[^>]*type=\"application/ld\+json\"[^>]*>(?P<isi>.*?)</script>", re.DOTALL
)
_ANGKA_RE = re.compile(r"[\d.,]+")
_PENGALI = {"jt": 1_000_000, "rb": 1_000, "k": 1_000, "m": 1_000_000, "b": 1_000_000_000}
_ANGKA_AKHIRAN_RE = re.compile(r"(?P<angka>\d[\d.,]*)(?P<akhiran>jt|rb|k|m|b)?")


class DataTidakDitemukan(ValueError):
    """Halaman tidak berisi data yang diharapkan (struktur berubah atau diblokir)."""


# ---------- utilitas ----------


def script_json(html: str, script_id: str) -> Any:
    """Ambil dan parse isi <script id="..."> yang berisi JSON."""
    for cocok in _SCRIPT_RE.finditer(html):
        if cocok.group("id") == script_id:
            return json.loads(unescape(cocok.group("isi")))
    raise DataTidakDitemukan(f"script #{script_id} tidak ada di halaman")


def semua_script_json(html: str) -> Iterator[Any]:
    """Semua <script> ber-id dan JSON-LD yang isinya JSON valid."""
    for cocok in _SCRIPT_RE.finditer(html):
        try:
            yield json.loads(unescape(cocok.group("isi")))
        except (json.JSONDecodeError, ValueError):
            continue
    for cocok in _LD_JSON_RE.finditer(html):
        try:
            yield json.loads(unescape(cocok.group("isi")))
        except (json.JSONDecodeError, ValueError):
            continue


def cari_kunci(data: Any, kunci: str) -> Iterator[Any]:
    """Telusuri dict/list bersarang, hasilkan semua nilai untuk `kunci`."""
    if isinstance(data, dict):
        for k, v in data.items():
            if k == kunci:
                yield v
            yield from cari_kunci(v, kunci)
    elif isinstance(data, list):
        for item in data:
            yield from cari_kunci(item, kunci)


def pertama(data: Any, *kunci: str) -> Any:
    """Nilai pertama yang tidak kosong dari salah satu kunci (dicari bersarang)."""
    for k in kunci:
        for nilai in cari_kunci(data, k):
            if nilai not in (None, "", [], {}):
                return nilai
    return None


def ke_int(nilai: Any) -> int | None:
    """Ubah 12345, "12345", "1,2K", "3.4M", "10rb", "1,5jt" menjadi int."""
    if nilai is None or isinstance(nilai, bool):
        return None
    if isinstance(nilai, (int, float)):
        return int(nilai)
    teks = str(nilai).strip().lower().replace(" ", "")
    cocok = _ANGKA_AKHIRAN_RE.search(teks)
    if not cocok:
        return None
    angka, akhiran = cocok.group("angka").strip(".,"), cocok.group("akhiran")
    if akhiran:
        # "1,2K" atau "1.2rb" -> desimal dikali pengali
        return int(float(angka.replace(",", ".")) * _PENGALI[akhiran])
    return int(re.sub(r"[.,]", "", angka) or 0)


def ke_float(nilai: Any) -> float | None:
    """Ubah harga/rating ke float. "Rp149.000" -> 149000.0, "4.8" -> 4.8."""
    if nilai is None or isinstance(nilai, bool):
        return None
    if isinstance(nilai, (int, float)):
        return float(nilai)
    cocok = _ANGKA_RE.search(str(nilai))
    if not cocok:
        return None
    angka = cocok.group().strip(".,")
    # Format Indonesia: titik ribuan, koma desimal ("149.000" / "12.500,50").
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", angka):
        angka = angka.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", angka):
        angka = angka.replace(",", "")
    else:
        angka = angka.replace(",", ".")
    try:
        return float(angka)
    except ValueError:
        return None


# ---------- profil & video ----------


def parse_profil(html: str) -> Profil:
    """Profil dari JSON __UNIVERSAL_DATA_FOR_REHYDRATION__ halaman tiktok.com/@username."""
    data = script_json(html, "__UNIVERSAL_DATA_FOR_REHYDRATION__")
    detail = data.get("__DEFAULT_SCOPE__", {}).get("webapp.user-detail")
    if not detail or "userInfo" not in detail:
        raise DataTidakDitemukan("webapp.user-detail kosong (akun tidak ada atau diblokir)")
    user = detail["userInfo"].get("user", {})
    stats = detail["userInfo"].get("statsV2") or detail["userInfo"].get("stats", {})
    username = user.get("uniqueId", "")
    return Profil(
        username=username,
        nama=user.get("nickname", ""),
        bio=user.get("signature", ""),
        verified=bool(user.get("verified")),
        followers=ke_int(stats.get("followerCount")) or 0,
        following=ke_int(stats.get("followingCount")) or 0,
        likes=ke_int(stats.get("heartCount") or stats.get("heart")) or 0,
        jumlah_video=ke_int(stats.get("videoCount")) or 0,
        link=f"https://www.tiktok.com/@{username}",
    )


def product_ids_dari_item(item: dict) -> list[str]:
    """ID produk keranjang kuning yang ditempel di sebuah video.

    TikTok menaruhnya di `anchors[].extra` (string JSON) atau di field produk lain.
    """
    ids: list[str] = []

    def tambah(nilai: Any) -> None:
        teks = str(nilai).strip()
        if teks.isdigit() and teks not in ids:
            ids.append(teks)

    for anchor in item.get("anchors") or []:
        extra = anchor.get("extra")
        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except json.JSONDecodeError:
                extra = None
        for kunci in ("product_id", "productId"):
            for nilai in cari_kunci(extra, kunci):
                tambah(nilai)
    for kunci in ("products", "productInfo", "shopProducts"):
        for blok in cari_kunci(item, kunci):
            for produk in blok if isinstance(blok, list) else [blok]:
                tambah(pertama(produk, "product_id", "productId") or "")
    return ids


def parse_video_item(item: dict, username: str = "") -> Video:
    """Satu item video dari itemList (API item_list) atau itemStruct (halaman video)."""
    stats = item.get("statsV2") or item.get("stats") or {}
    author = item.get("author")
    if isinstance(author, dict):
        username = author.get("uniqueId") or username
    elif isinstance(author, str) and author:
        username = author
    video_id = str(item.get("id", ""))
    dibuat = ""
    if item.get("createTime"):
        waktu = datetime.fromtimestamp(int(item["createTime"]), tz=timezone.utc)
        dibuat = waktu.isoformat()
    return Video(
        video_id=video_id,
        link=f"https://www.tiktok.com/@{username}/video/{video_id}" if username else "",
        deskripsi=item.get("desc", ""),
        dibuat=dibuat,
        views=ke_int(stats.get("playCount")) or 0,
        likes=ke_int(stats.get("diggCount")) or 0,
        komentar=ke_int(stats.get("commentCount")) or 0,
        share=ke_int(stats.get("shareCount")) or 0,
        simpan=ke_int(stats.get("collectCount")) or 0,
        product_ids=product_ids_dari_item(item),
    )


def parse_item_list(data: dict, username: str = "") -> tuple[list[Video], bool, str]:
    """Respons JSON /api/post/item_list/ -> (video, masih_ada, cursor)."""
    videos = [parse_video_item(item, username) for item in data.get("itemList") or []]
    return videos, bool(data.get("hasMore")), str(data.get("cursor", ""))


def parse_halaman_video(html: str) -> Video:
    """Halaman tiktok.com/@user/video/<id>."""
    data = script_json(html, "__UNIVERSAL_DATA_FOR_REHYDRATION__")
    detail = data.get("__DEFAULT_SCOPE__", {}).get("webapp.video-detail") or {}
    item = detail.get("itemInfo", {}).get("itemStruct")
    if not item:
        raise DataTidakDitemukan("webapp.video-detail kosong")
    return parse_video_item(item)


# ---------- produk ----------


def _produk_dari_ld(data: Any, produk: Produk) -> None:
    """Isi dari JSON-LD schema.org/Product kalau halaman menyediakannya."""
    for blok in data if isinstance(data, list) else [data]:
        if not isinstance(blok, dict) or blok.get("@type") != "Product":
            continue
        produk.nama = produk.nama or blok.get("name", "")
        offers = blok.get("offers") or {}
        if isinstance(offers, list):
            offers = offers[0] if offers else {}
        produk.harga = produk.harga if produk.harga is not None else ke_float(
            offers.get("price") or offers.get("lowPrice")
        )
        produk.mata_uang = produk.mata_uang or offers.get("priceCurrency", "")
        rating = blok.get("aggregateRating") or {}
        if produk.rating is None:
            produk.rating = ke_float(rating.get("ratingValue"))
        if produk.jumlah_ulasan is None:
            produk.jumlah_ulasan = ke_int(rating.get("reviewCount") or rating.get("ratingCount"))
        brand = blok.get("brand")
        if not produk.toko and isinstance(brand, dict):
            produk.toko = brand.get("name", "")


def parse_produk(html: str, product_id: str, link: str = "") -> Produk:
    """Halaman produk TikTok Shop publik.

    Urutan sumber: JSON-LD schema.org lalu JSON tertanam (router data) dengan
    pencarian kunci yang umum dipakai TikTok Shop.
    """
    produk = Produk(product_id=product_id, link=link)
    blok_json = list(semua_script_json(html))
    if not blok_json:
        raise DataTidakDitemukan(f"tidak ada data JSON di halaman produk {product_id}")

    for data in blok_json:
        _produk_dari_ld(data, produk)

    for data in blok_json:
        produk.nama = produk.nama or pertama(data, "product_name", "title") or ""
        if produk.harga is None:
            produk.harga = ke_float(
                pertama(data, "sale_price", "real_price", "min_price", "format_price")
            )
        if produk.harga_coret is None:
            produk.harga_coret = ke_float(
                pertama(data, "original_price", "origin_price", "format_original_price")
            )
        produk.mata_uang = produk.mata_uang or pertama(data, "currency") or ""
        produk.toko = produk.toko or pertama(data, "shop_name", "seller_name") or ""
        if produk.terjual is None:
            produk.terjual = ke_int(pertama(data, "sold_count", "sold", "format_sold_count"))
        if produk.rating is None:
            produk.rating = ke_float(pertama(data, "product_rating", "rating", "overall_score"))
        if produk.jumlah_ulasan is None:
            produk.jumlah_ulasan = ke_int(pertama(data, "review_count", "total_reviews"))
        if produk.komisi_persen is None:
            produk.komisi_persen = ke_float(pertama(data, "commission_rate", "commission"))

    if not produk.nama and produk.harga is None:
        raise DataTidakDitemukan(f"nama/harga produk {product_id} tidak ditemukan")
    return produk


def gabung_statistik_produk(produk: list[Produk], videos: list[Video]) -> None:
    """Isi jumlah_video & total_views_video tiap produk dari daftar video."""
    per_id = {p.product_id: p for p in produk}
    for p in produk:
        p.jumlah_video = 0
        p.total_views_video = 0
    for video in videos:
        for pid in video.product_ids:
            if pid in per_id:
                per_id[pid].jumlah_video += 1
                per_id[pid].total_views_video += video.views
