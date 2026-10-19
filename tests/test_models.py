from riset_tiktok.models import Produk, Video


def test_video_ke_dict_menggabung_product_ids():
    video = Video(video_id="1", product_ids=["a", "b"])
    assert video.ke_dict()["product_ids"] == "a,b"


def test_produk_default_kosong():
    produk = Produk(product_id="9")
    assert produk.komisi_persen is None
    assert produk.jumlah_video == 0
