import json

import pytest

from riset_tiktok.models import Produk, Video
from riset_tiktok.parser import (
    DataTidakDitemukan,
    gabung_statistik_produk,
    ke_float,
    ke_int,
    parse_item_list,
    parse_produk,
    parse_profil,
)


@pytest.mark.parametrize(
    ("masuk", "hasil"),
    [(12345, 12345), ("12345", 12345), ("1,2K", 1200), ("3.4M", 3_400_000),
     ("10rb", 10_000), ("1,5jt", 1_500_000), ("1,2rb terjual", 1200), ("12.500", 12500),
     (None, None), ("", None)],
)
def test_ke_int(masuk, hasil):
    assert ke_int(masuk) == hasil


@pytest.mark.parametrize(
    ("masuk", "hasil"),
    [("Rp149.000", 149000.0), ("Rp12.500,50", 12500.5), ("$1,299.99", 1299.99),
     ("4.8", 4.8), ("4,6", 4.6), (89000, 89000.0), ("gratis", None)],
)
def test_ke_float(masuk, hasil):
    assert ke_float(masuk) == hasil


def test_parse_profil(fixture_teks):
    profil = parse_profil(fixture_teks("profil.html"))
    assert profil.username == "tokocontoh"
    assert profil.nama == "Toko Contoh"
    assert profil.verified is True
    assert profil.followers == 125000
    assert profil.likes == 3400000
    assert profil.jumlah_video == 210
    assert profil.link == "https://www.tiktok.com/@tokocontoh"


def test_parse_profil_kosong_error():
    html = '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">{"__DEFAULT_SCOPE__": {}}</script>'
    with pytest.raises(DataTidakDitemukan):
        parse_profil(html)


def test_parse_profil_tanpa_script_error():
    with pytest.raises(DataTidakDitemukan):
        parse_profil("<html></html>")


def test_parse_item_list(fixture_teks):
    data = json.loads(fixture_teks("item_list.json"))
    videos, masih_ada, cursor = parse_item_list(data)
    assert masih_ada is True
    assert cursor == "1700000000000"
    assert [v.video_id for v in videos] == [
        "7300000000000000001", "7300000000000000002", "7300000000000000003",
    ]
    pertama = videos[0]
    assert pertama.views == 150000
    assert pertama.simpan == 300
    assert pertama.product_ids == ["1729384756"]
    assert pertama.link == "https://www.tiktok.com/@tokocontoh/video/7300000000000000001"
    assert pertama.dibuat.startswith("2023-11-14")
    assert videos[1].product_ids == []
    assert videos[1].link.endswith("/@tokocontoh/video/7300000000000000002")
    assert videos[2].views == 20000
    assert videos[2].product_ids == ["1729384756", "1729000001"]


def test_parse_produk_dengan_json_ld(fixture_teks):
    produk = parse_produk(fixture_teks("produk.html"), "1729384756", "https://x/1729384756")
    assert produk.nama == "Serum Wajah Glowing 30ml"
    assert produk.harga == 89000.0
    assert produk.harga_coret == 149000.0
    assert produk.mata_uang == "IDR"
    assert produk.toko == "Toko Contoh Official"
    assert produk.terjual == 12500
    assert produk.rating == 4.8
    assert produk.jumlah_ulasan == 1520
    assert produk.komisi_persen is None
    assert produk.link == "https://x/1729384756"


def test_parse_produk_tanpa_json_ld(fixture_teks):
    produk = parse_produk(fixture_teks("produk_tanpa_ld.html"), "1")
    assert produk.nama == "Masker Tidur"
    assert produk.harga == 45500.0
    assert produk.harga_coret == 60000.0
    assert produk.terjual == 1200
    assert produk.rating == 4.6
    assert produk.jumlah_ulasan == 312
    assert produk.toko == "Toko Lain"


def test_parse_produk_halaman_kosong_error():
    with pytest.raises(DataTidakDitemukan):
        parse_produk("<html><body>captcha</body></html>", "1")


def test_gabung_statistik_produk():
    produk = [Produk(product_id="a"), Produk(product_id="b")]
    videos = [
        Video(video_id="1", views=100, product_ids=["a"]),
        Video(video_id="2", views=50, product_ids=["a", "b"]),
        Video(video_id="3", views=999),
    ]
    gabung_statistik_produk(produk, videos)
    assert (produk[0].jumlah_video, produk[0].total_views_video) == (2, 150)
    assert (produk[1].jumlah_video, produk[1].total_views_video) == (1, 50)
