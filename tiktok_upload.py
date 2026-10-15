"""Kirim video ke TikTok sebagai draf (inbox) lewat Content Posting API resmi.

API TikTok tidak bisa memasang keranjang kuning, jadi tool ini juga membuat
"lembar posting": caption, hashtag, dan produk per video untuk diselesaikan
di aplikasi TikTok.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import secrets
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Callable

API = "https://open.tiktokapis.com"
URL_OTORISASI = "https://www.tiktok.com/v2/auth/authorize/"
SCOPE = "video.upload"
REDIRECT_BAWAAN = "http://localhost:8585/callback/"
TOKEN_BAWAAN = Path.home() / ".config" / "tiktok_potong" / "token.json"
RIWAYAT_BAWAAN = Path("riwayat_upload.json")
LEMBAR_BAWAAN = Path("lembar_posting.md")
EKSTENSI_VIDEO = {".mp4", ".mov", ".webm"}

PESAN_GALAT = {
    "spam_risk_too_many_pending_share": (
        "Terlalu banyak draf menunggu di inbox TikTok (batas sekitar 5 per 24 jam). "
        "Selesaikan/posting draf yang ada dulu, lalu coba lagi."
    ),
    "spam_risk_too_many_posts": "Batas upload harian akun tercapai. Coba lagi besok.",
    "scope_not_authorized": (
        "Akun belum memberi izin 'video.upload'. Pastikan scope itu aktif di app "
        "TikTok Developers, lalu jalankan 'login' lagi."
    ),
    "access_token_invalid": "Sesi login tidak berlaku. Jalankan 'login' lagi.",
    "rate_limit_exceeded": "Terlalu banyak permintaan ke TikTok. Tunggu sebentar.",
    "file_format_check_failed": "Format video ditolak TikTok. Gunakan MP4 (H.264).",
}

Http = Callable[[str, str, dict, "bytes | None"], "tuple[int, bytes]"]

MB = 1024 * 1024
CHUNK_MIN = 5 * MB
CHUNK_STANDAR = 10 * MB
CHUNK_TERAKHIR_MAKS = 128 * MB
KOLOM_CSV = ["video", "caption", "hashtag", "produk"]


def rencana_chunk(ukuran: int, chunk: int = CHUNK_STANDAR) -> tuple[int, int]:
    """Kembalikan (chunk_size, total_chunk_count) sesuai aturan TikTok.

    File < 5 MB atau lebih kecil dari satu chunk dikirim utuh.
    Selain itu, sisa pembagian diserap chunk terakhir.
    """
    if ukuran <= 0:
        raise ValueError("Ukuran file tidak valid")
    if ukuran < CHUNK_MIN or ukuran < chunk:
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


# ---------------------------------------------------------------- jaringan


class GalatTikTok(Exception):
    pass


def http_bawaan(metode: str, url: str, header: dict, data: bytes | None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=data, headers=header, method=metode)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
    except urllib.error.URLError as e:
        raise GalatTikTok(f"Tidak bisa terhubung ke TikTok: {e.reason}") from e


def _json(isi: bytes) -> dict:
    try:
        return json.loads(isi or b"{}")
    except json.JSONDecodeError:
        return {}


class KlienTikTok:
    def __init__(
        self,
        client_key: str,
        client_secret: str,
        token_path: Path = TOKEN_BAWAAN,
        http: Http = http_bawaan,
        sekarang: Callable[[], float] = time.time,
        tidur: Callable[[float], None] = time.sleep,
    ):
        self.client_key = client_key
        self.client_secret = client_secret
        self.token_path = token_path
        self.http = http
        self.sekarang = sekarang
        self.tidur = tidur

    # ---- token
    def _minta_token(self, isian: dict[str, str]) -> dict:
        data = urllib.parse.urlencode(
            {"client_key": self.client_key, "client_secret": self.client_secret, **isian}
        ).encode()
        _, isi = self.http(
            "POST", f"{API}/v2/oauth/token/",
            {"Content-Type": "application/x-www-form-urlencoded"}, data,
        )
        hasil = _json(isi)
        if "access_token" not in hasil:
            raise GalatTikTok(
                f"Gagal mendapat token: {hasil.get('error_description') or hasil}"
            )
        now = self.sekarang()
        token = {
            "access_token": hasil["access_token"],
            "refresh_token": hasil["refresh_token"],
            "open_id": hasil.get("open_id", ""),
            "scope": hasil.get("scope", ""),
            "expires_at": now + int(hasil.get("expires_in", 0)),
            "refresh_expires_at": now + int(hasil.get("refresh_expires_in", 0)),
        }
        self.simpan_token(token)
        return token

    def tukar_kode(self, kode: str, verifier: str, redirect_uri: str) -> dict:
        return self._minta_token({
            "code": kode, "grant_type": "authorization_code",
            "redirect_uri": redirect_uri, "code_verifier": verifier,
        })

    def simpan_token(self, token: dict) -> None:
        self.token_path.parent.mkdir(parents=True, exist_ok=True)
        self.token_path.write_text(json.dumps(token, indent=2))
        os.chmod(self.token_path, 0o600)

    def access_token(self) -> str:
        if not self.token_path.exists():
            raise GalatTikTok("Belum login. Jalankan: python3 tiktok_upload.py login")
        token = json.loads(self.token_path.read_text())
        now = self.sekarang()
        if token["expires_at"] - 60 > now:
            return token["access_token"]
        if token["refresh_expires_at"] <= now:
            raise GalatTikTok("Sesi login kedaluwarsa. Jalankan 'login' lagi.")
        return self._minta_token(
            {"grant_type": "refresh_token", "refresh_token": token["refresh_token"]}
        )["access_token"]

    # ---- content posting
    def _api(self, jalur: str, badan: dict) -> dict:
        header = {
            "Authorization": f"Bearer {self.access_token()}",
            "Content-Type": "application/json; charset=UTF-8",
        }
        _, isi = self.http("POST", f"{API}{jalur}", header, json.dumps(badan).encode())
        hasil = _json(isi)
        galat = hasil.get("error", {})
        kode = galat.get("code", "tanpa_respon")
        if kode != "ok":
            pesan = PESAN_GALAT.get(kode, f"{kode}: {galat.get('message', '')}")
            raise GalatTikTok(pesan)
        return hasil.get("data", {})

    def init_draf(self, ukuran: int) -> tuple[dict, int, int]:
        chunk_size, total = rencana_chunk(ukuran)
        data = self._api("/v2/post/publish/inbox/video/init/", {"source_info": {
            "source": "FILE_UPLOAD", "video_size": ukuran,
            "chunk_size": chunk_size, "total_chunk_count": total,
        }})
        return data, chunk_size, total

    def unggah(self, path: Path, upload_url: str, chunk_size: int, total: int) -> None:
        ukuran = path.stat().st_size
        with path.open("rb") as f:
            for i, (awal, akhir) in enumerate(rentang_chunk(ukuran, chunk_size, total), 1):
                f.seek(awal)
                potongan = f.read(akhir - awal + 1)
                for coba in range(1, 4):
                    kode, _ = self.http("PUT", upload_url, header_chunk(awal, akhir, ukuran),
                                        potongan)
                    if 200 <= kode < 300:
                        break
                    if coba == 3:
                        raise GalatTikTok(f"Gagal mengirim bagian {i}/{total} (HTTP {kode})")
                    self.tidur(2 * coba)
                print(f"    bagian {i}/{total} terkirim")

    def tunggu_status(self, publish_id: str, maks_cek: int = 60, jeda: float = 3) -> str:
        for _ in range(maks_cek):
            data = self._api("/v2/post/publish/status/fetch/", {"publish_id": publish_id})
            status = data.get("status", "")
            if status in ("SEND_TO_USER_INBOX", "PUBLISH_COMPLETE"):
                return status
            if status == "FAILED":
                raise GalatTikTok(f"TikTok menolak video: {data.get('fail_reason', '-')}")
            self.tidur(jeda)
        return "MASIH_DIPROSES"

    def kirim_draf(self, path: Path) -> str:
        data, chunk_size, total = self.init_draf(path.stat().st_size)
        self.unggah(path, data["upload_url"], chunk_size, total)
        status = self.tunggu_status(data["publish_id"])
        print(f"    status: {status}")
        return data["publish_id"]


# ---------------------------------------------------------------- login


def url_otorisasi(client_key: str, redirect_uri: str, state: str, challenge: str) -> str:
    return URL_OTORISASI + "?" + urllib.parse.urlencode({
        "client_key": client_key, "scope": SCOPE, "response_type": "code",
        "redirect_uri": redirect_uri, "state": state,
        "code_challenge": challenge, "code_challenge_method": "S256",
    })


def ambil_kode(url_redirect: str, state: str) -> str:
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url_redirect).query)
    if q.get("state", [""])[0] != state:
        raise GalatTikTok("State tidak cocok. Ulangi login.")
    if "code" not in q:
        alasan = q.get("error_description", q.get("error", ["dibatalkan"]))[0]
        raise GalatTikTok(f"Login gagal: {alasan}")
    return q["code"][0]


def tunggu_redirect(redirect_uri: str) -> str:
    """Server lokal satu kali untuk menangkap redirect dari TikTok."""
    target = urllib.parse.urlparse(redirect_uri)
    tangkapan: dict[str, str] = {}

    class Penangan(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            tangkapan["url"] = self.path
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("<h2>Login berhasil. Tutup tab ini.</h2>".encode())

        def log_message(self, *a):
            pass

    with HTTPServer((target.hostname or "localhost", target.port or 80), Penangan) as srv:
        srv.timeout = 300
        srv.handle_request()
    if "url" not in tangkapan:
        raise GalatTikTok("Tidak ada balasan dari TikTok dalam 5 menit.")
    return tangkapan["url"]


# ---------------------------------------------------------------- CLI


def kumpulkan(masukan: Path) -> list[Path]:
    if masukan.is_dir():
        return sorted(p for p in masukan.iterdir() if p.suffix.lower() in EKSTENSI_VIDEO)
    return [masukan]


def kunci_riwayat(path: Path) -> str:
    return f"{path.name}:{path.stat().st_size}"


def _kredensial() -> tuple[str, str]:
    key = os.environ.get("TIKTOK_CLIENT_KEY", "")
    secret = os.environ.get("TIKTOK_CLIENT_SECRET", "")
    if not key or not secret:
        raise GalatTikTok(
            "Set dulu env var TIKTOK_CLIENT_KEY dan TIKTOK_CLIENT_SECRET "
            "(dari app di developers.tiktok.com)."
        )
    return key, secret


def perintah_login(args, klien: KlienTikTok) -> int:
    verifier, challenge = buat_pkce()
    state = secrets.token_urlsafe(16)
    url = url_otorisasi(klien.client_key, args.redirect_uri, state, challenge)
    print("Buka tautan ini untuk login TikTok:\n" + url + "\n")
    if args.tempel:
        balik = input("Tempel URL lengkap setelah redirect: ").strip()
    else:
        webbrowser.open(url)
        print(f"Menunggu redirect di {args.redirect_uri} ...")
        balik = tunggu_redirect(args.redirect_uri)
    klien.tukar_kode(ambil_kode(balik, state), verifier, args.redirect_uri)
    print(f"✔ Login berhasil. Token disimpan di {klien.token_path}")
    return 0


def perintah_templat(args) -> int:
    if args.daftar.exists():
        print(f"✘ {args.daftar} sudah ada, tidak ditimpa.", file=sys.stderr)
        return 1
    tulis_templat(args.daftar, kumpulkan(args.masukan))
    print(f"✔ Templat dibuat: {args.daftar}. Isi caption, hashtag, dan produk.")
    return 0


def perintah_kirim(args, klien: KlienTikTok | None) -> int:
    videos = kumpulkan(args.masukan)
    if not videos:
        print(f"✘ Tidak ada video di {args.masukan}.", file=sys.stderr)
        return 2
    daftar = baca_daftar(args.daftar) if args.daftar.exists() else {}
    riwayat = json.loads(args.riwayat.read_text()) if args.riwayat.exists() else {}

    terkirim, gagal = [], 0
    for v in videos:
        ukuran = v.stat().st_size
        chunk_size, total = rencana_chunk(ukuran)
        info = daftar.get(v.name, {})
        print(f"• {v.name} ({ukuran / MB:.1f} MB, {total} bagian)"
              + (f" → produk: {info['produk']}" if info.get("produk") else ""))
        if kunci_riwayat(v) in riwayat and not args.ulang:
            print("    dilewati: sudah pernah dikirim (pakai --ulang untuk kirim lagi)")
            continue
        if args.coba or klien is None:
            continue
        try:
            publish_id = klien.kirim_draf(v)
        except GalatTikTok as e:
            gagal += 1
            print(f"    ✘ {e}", file=sys.stderr)
            if "draf menunggu" in str(e) or "Batas upload" in str(e):
                break
            continue
        riwayat[kunci_riwayat(v)] = {"publish_id": publish_id, "waktu": time.time()}
        args.riwayat.write_text(json.dumps(riwayat, indent=2))
        terkirim.append({"video": v.name, **{k: info.get(k, "") for k in KOLOM_CSV[1:]}})
        print("    ✔ masuk ke inbox TikTok")

    if terkirim:
        args.lembar.write_text(lembar_posting(terkirim), encoding="utf-8")
        print(f"\n✔ {len(terkirim)} video terkirim. Buka notifikasi TikTok, pasang "
              f"keranjang kuning. Panduan & caption: {args.lembar}")
    return 1 if gagal else 0


def buat_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Kirim video ke inbox TikTok sebagai draf + lembar posting keranjang kuning.",
    )
    p.add_argument("--token", type=Path, default=TOKEN_BAWAAN, help=argparse.SUPPRESS)
    sub = p.add_subparsers(dest="perintah", required=True)

    s = sub.add_parser("login", help="login akun TikTok (sekali, berlaku ±1 tahun)")
    s.add_argument("--redirect-uri", default=REDIRECT_BAWAAN,
                   help=f"harus sama dengan di app TikTok (default: {REDIRECT_BAWAAN})")
    s.add_argument("--tempel", action="store_true",
                   help="tempel URL redirect manual, tanpa server lokal")

    s = sub.add_parser("templat", help="buat CSV caption/produk untuk diisi")
    s.add_argument("masukan", type=Path, help="folder video (mis. hasil/)")
    s.add_argument("--daftar", type=Path, default=Path("daftar_upload.csv"))

    s = sub.add_parser("kirim", help="kirim video ke inbox TikTok sebagai draf")
    s.add_argument("masukan", type=Path, help="file video atau folder (mis. hasil/)")
    s.add_argument("--daftar", type=Path, default=Path("daftar_upload.csv"),
                   help="CSV caption/hashtag/produk (opsional)")
    s.add_argument("--riwayat", type=Path, default=RIWAYAT_BAWAAN)
    s.add_argument("--lembar", type=Path, default=LEMBAR_BAWAAN)
    s.add_argument("--ulang", action="store_true", help="kirim lagi walau sudah pernah")
    s.add_argument("--coba", action="store_true", help="tampilkan rencana tanpa mengirim")
    return p


def main(argv: list[str] | None = None, http: Http = http_bawaan) -> int:
    args = buat_parser().parse_args(argv)
    try:
        if args.perintah == "templat":
            return perintah_templat(args)
        if args.perintah == "kirim" and not args.masukan.exists():
            print(f"✘ {args.masukan} tidak ada.", file=sys.stderr)
            return 2
        if args.perintah == "kirim" and args.coba:
            return perintah_kirim(args, None)
        key, secret = _kredensial()
        klien = KlienTikTok(key, secret, token_path=args.token, http=http)
        if args.perintah == "login":
            return perintah_login(args, klien)
        return perintah_kirim(args, klien)
    except GalatTikTok as e:
        print(f"✘ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
