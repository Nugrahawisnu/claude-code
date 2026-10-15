import hashlib

import pytest

from tiktok_upload import (
    MB,
    baca_daftar,
    buat_pkce,
    header_chunk,
    lembar_posting,
    rencana_chunk,
    rentang_chunk,
    tulis_templat,
)


def test_chunk_file_kecil_dikirim_utuh():
    assert rencana_chunk(3 * MB) == (3 * MB, 1)


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
