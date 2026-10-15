import hashlib
import json
import urllib.parse

import pytest

from tiktok_upload import (
    MB,
    GalatTikTok,
    KlienTikTok,
    ambil_kode,
    baca_daftar,
    buat_pkce,
    header_chunk,
    lembar_posting,
    main,
    rencana_chunk,
    rentang_chunk,
    tulis_templat,
    url_otorisasi,
)


def test_chunk_file_kecil_dikirim_utuh():
    assert rencana_chunk(3 * MB) == (3 * MB, 1)


def test_chunk_file_lebih_kecil_dari_satu_chunk():
    ukuran = 8 * MB + 7
    assert rencana_chunk(ukuran) == (ukuran, 1)
    assert rentang_chunk(ukuran, ukuran, 1) == [(0, ukuran - 1)]


def test_chunk_kelipatan_pas():
    assert rencana_chunk(30 * MB) == (10 * MB, 3)


def test_chunk_sisa_diserap_terakhir():
    ukuran = 25 * MB + 123
    size, total = rencana_chunk(ukuran)
    assert (size, total) == (10 * MB, 2)
    r = rentang_chunk(ukuran, size, total)
    assert r == [(0, 10 * MB - 1), (10 * MB, ukuran - 1)]


def test_chunk_ukuran_tidak_valid():
    with pytest.raises(ValueError):
        rencana_chunk(0)


def test_header_chunk():
    h = header_chunk(0, 99, 250)
    assert h["Content-Range"] == "bytes 0-99/250"
    assert h["Content-Length"] == "100"
    assert h["Content-Type"] == "video/mp4"


def test_pkce_hex_sha256():
    verifier, challenge = buat_pkce()
    assert 43 <= len(verifier) <= 128
    assert challenge == hashlib.sha256(verifier.encode()).hexdigest()


def test_templat_dan_baca_daftar(tmp_path):
    csv_path = tmp_path / "daftar.csv"
    tulis_templat(csv_path, [tmp_path / "a_tiktok.mp4", tmp_path / "b_tiktok.mp4"])
    isi = csv_path.read_text().replace(
        "a_tiktok.mp4,,,", "a_tiktok.mp4,Murah banget!,#fyp #racun,Sepatu Lari X"
    )
    csv_path.write_text(isi)
    daftar = baca_daftar(csv_path)
    assert daftar["a_tiktok.mp4"]["produk"] == "Sepatu Lari X"
    assert daftar["b_tiktok.mp4"]["caption"] == ""


def test_lembar_posting():
    teks = lembar_posting([
        {"video": "a.mp4", "caption": "Murah!", "hashtag": "#fyp", "produk": "Sepatu X"},
        {"video": "b.mp4"},
    ])
    assert "Tambah link → Produk" in teks
    assert "Murah! #fyp" in teks
    assert "**Sepatu X**" in teks
    assert "(isi sendiri)" in teks


# ------------------------------------------------------------ klien & CLI


class HttpPalsu:
    """Meniru TikTok: catat semua permintaan, balas sesuai skenario."""

    def __init__(self, status_list=("PROCESSING_UPLOAD", "SEND_TO_USER_INBOX"),
                 galat_init=None, put_gagal=0):
        self.catatan = []
        self.status_list = list(status_list)
        self.galat_init = galat_init
        self.put_gagal = put_gagal

    def __call__(self, metode, url, header, data):
        self.catatan.append((metode, url, header, data))
        if url.endswith("/oauth/token/"):
            return 200, json.dumps({
                "access_token": "akses-baru", "refresh_token": "segar",
                "expires_in": 86400, "refresh_expires_in": 31536000, "open_id": "u1",
            }).encode()
        if url.endswith("/inbox/video/init/"):
            if self.galat_init:
                return 403, json.dumps({"error": {"code": self.galat_init}}).encode()
            return 200, json.dumps({
                "data": {"publish_id": "pid-1", "upload_url": "https://upload.example/u"},
                "error": {"code": "ok"},
            }).encode()
        if metode == "PUT":
            if self.put_gagal:
                self.put_gagal -= 1
                return 500, b""
            return 206, b""
        if url.endswith("/status/fetch/"):
            return 200, json.dumps({
                "data": {"status": self.status_list.pop(0)}, "error": {"code": "ok"},
            }).encode()
        raise AssertionError(url)


def _klien(tmp_path, http, token=None):
    token_path = tmp_path / "token.json"
    token_path.write_text(json.dumps(token or {
        "access_token": "akses", "refresh_token": "r",
        "expires_at": 2000, "refresh_expires_at": 9_999_999,
    }))
    return KlienTikTok("key", "secret", token_path=token_path, http=http,
                       sekarang=lambda: 1000, tidur=lambda s: None)


def test_kirim_draf_alur_lengkap(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x" * (12 * MB + 5))
    http = HttpPalsu()
    assert _klien(tmp_path, http).kirim_draf(video) == "pid-1"

    init = http.catatan[0]
    badan = json.loads(init[3])["source_info"]
    assert badan == {"source": "FILE_UPLOAD", "video_size": 12 * MB + 5,
                     "chunk_size": 10 * MB, "total_chunk_count": 1}
    assert init[2]["Authorization"] == "Bearer akses"
    puts = [c for c in http.catatan if c[0] == "PUT"]
    assert len(puts) == 1
    assert puts[0][2]["Content-Range"] == f"bytes 0-{12 * MB + 4}/{12 * MB + 5}"
    assert len(puts[0][3]) == 12 * MB + 5


def test_put_gagal_dicoba_ulang(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x" * 100)
    http = HttpPalsu(put_gagal=2)
    _klien(tmp_path, http).kirim_draf(video)
    assert len([c for c in http.catatan if c[0] == "PUT"]) == 3


def test_galat_terlalu_banyak_draf(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x" * 100)
    http = HttpPalsu(galat_init="spam_risk_too_many_pending_share")
    with pytest.raises(GalatTikTok, match="draf menunggu"):
        _klien(tmp_path, http).kirim_draf(video)


def test_status_gagal(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x" * 100)
    http = HttpPalsu(status_list=["FAILED"])
    with pytest.raises(GalatTikTok, match="menolak"):
        _klien(tmp_path, http).kirim_draf(video)


def test_token_kedaluwarsa_diperpanjang(tmp_path):
    http = HttpPalsu()
    klien = _klien(tmp_path, http, token={
        "access_token": "lama", "refresh_token": "r",
        "expires_at": 900, "refresh_expires_at": 9_999_999,
    })
    assert klien.access_token() == "akses-baru"
    form = urllib.parse.parse_qs(http.catatan[0][3].decode())
    assert form["grant_type"] == ["refresh_token"]
    assert json.loads(klien.token_path.read_text())["access_token"] == "akses-baru"


def test_url_otorisasi_dan_ambil_kode():
    url = url_otorisasi("key", "http://localhost:8585/callback/", "st", "abc")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert q["scope"] == ["video.upload"]
    assert q["code_challenge_method"] == ["S256"]
    assert ambil_kode("/callback/?code=K1&state=st", "st") == "K1"
    with pytest.raises(GalatTikTok, match="State"):
        ambil_kode("/callback/?code=K1&state=lain", "st")
    with pytest.raises(GalatTikTok, match="Login gagal"):
        ambil_kode("/callback/?error=access_denied&state=st", "st")


def test_cli_kirim_folder_dengan_riwayat_dan_lembar(tmp_path, monkeypatch):
    monkeypatch.setenv("TIKTOK_CLIENT_KEY", "key")
    monkeypatch.setenv("TIKTOK_CLIENT_SECRET", "secret")
    folder = tmp_path / "hasil"
    folder.mkdir()
    (folder / "a_tiktok.mp4").write_bytes(b"a" * 100)
    (folder / "b_tiktok.mp4").write_bytes(b"b" * 100)
    daftar = tmp_path / "daftar.csv"
    daftar.write_text("video,caption,hashtag,produk\n"
                      "a_tiktok.mp4,Murah!,#fyp,Sepatu X\n")
    token = tmp_path / "token.json"
    token.write_text(json.dumps({"access_token": "a", "refresh_token": "r",
                                 "expires_at": 9e12, "refresh_expires_at": 9e12}))
    riwayat, lembar = tmp_path / "riwayat.json", tmp_path / "lembar.md"
    argv = ["--token", str(token), "kirim", str(folder), "--daftar", str(daftar),
            "--riwayat", str(riwayat), "--lembar", str(lembar)]

    http = HttpPalsu(status_list=["SEND_TO_USER_INBOX"] * 2)
    assert main(argv, http=http) == 0
    assert len(json.loads(riwayat.read_text())) == 2
    isi = lembar.read_text()
    assert "**Sepatu X**" in isi and "b_tiktok.mp4" in isi

    # dijalankan lagi: semua dilewati, tidak ada permintaan baru
    http2 = HttpPalsu()
    assert main(argv, http=http2) == 0
    assert http2.catatan == []


def test_cli_coba_tanpa_kredensial(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TIKTOK_CLIENT_KEY", raising=False)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x" * 100)
    assert main(["kirim", str(video), "--coba", "--riwayat", str(tmp_path / "r.json")]) == 0
    assert "1 bagian" in capsys.readouterr().out


def test_cli_tanpa_kredensial_pesan_jelas(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("TIKTOK_CLIENT_KEY", raising=False)
    video = tmp_path / "v.mp4"
    video.write_bytes(b"x")
    assert main(["kirim", str(video)]) == 1
    assert "TIKTOK_CLIENT_KEY" in capsys.readouterr().err
