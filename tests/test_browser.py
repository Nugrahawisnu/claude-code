import pytest

from riset_tiktok.browser import Diblokir, cek_diblokir


def test_halaman_normal_lolos(fixture_teks):
    cek_diblokir(fixture_teks("profil.html"), "https://www.tiktok.com/@tokocontoh")


@pytest.mark.parametrize(
    "html",
    [
        '<div id="captcha-verify-image"></div>',
        '<div class="captcha_verify_container"></div>',
        "<html><head><title>Access Denied</title></head></html>",
    ],
)
def test_captcha_terdeteksi(html):
    with pytest.raises(Diblokir):
        cek_diblokir(html)


def test_alihkan_ke_login_terdeteksi():
    with pytest.raises(Diblokir):
        cek_diblokir("<html></html>", "https://www.tiktok.com/login?redirect=x")
