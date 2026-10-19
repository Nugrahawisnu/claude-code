"""Akses halaman publik TikTok lewat Playwright (Chromium).

Sengaja pelan dan sopan: jeda acak antar-halaman, tanpa login, dan berhenti kalau
TikTok menampilkan CAPTCHA atau memblokir. Tool ini tidak mencoba menembus blokir.
"""

from __future__ import annotations

import random
import time
from typing import Any, Protocol

URL_PROFIL = "https://www.tiktok.com/@{username}"
URL_PRODUK = "https://shop.tiktok.com/view/product/{product_id}?region={region}&locale=id-ID"

_PENANDA_BLOKIR = (
    'id="captcha',
    "captcha_verify",
    "secsdk-captcha",
    "verify-bar-close",
    "<title>access denied",
    "too many requests",
)


class GagalAkses(RuntimeError):
    """Halaman tidak bisa dibuka (jaringan, timeout, dsb.)."""


class Diblokir(GagalAkses):
    """TikTok meminta verifikasi/CAPTCHA atau menolak akses."""


def cek_diblokir(html: str, url: str = "") -> None:
    """Lempar `Diblokir` kalau halaman berupa CAPTCHA, login paksa, atau penolakan."""
    kecil = html.lower()
    for penanda in _PENANDA_BLOKIR:
        if penanda in kecil:
            raise Diblokir(f"TikTok meminta verifikasi/CAPTCHA di {url or 'halaman'}")
    if "/login" in url:
        raise Diblokir(f"TikTok mengalihkan ke halaman login ({url})")


class Sumber(Protocol):
    """Antarmuka sumber data; CLI hanya bergantung pada ini (mudah di-mock di tes)."""

    def riset_profil(self, username: str, maks_video: int) -> tuple[str, list[dict[str, Any]]]:
        """HTML profil + daftar respons JSON item_list yang tertangkap."""
        ...

    def produk_html(self, product_id: str) -> tuple[str, str]:
        """(HTML, URL) halaman produk."""
        ...


class PenjelajahTikTok:
    """Sumber data nyata berbasis Playwright. Pakai sebagai context manager."""

    def __init__(
        self,
        headless: bool = True,
        region: str = "ID",
        jeda: tuple[float, float] = (2.0, 5.0),
        timeout_ms: int = 30_000,
        maks_scroll: int = 30,
        chromium: str | None = None,
    ) -> None:
        self.headless = headless
        self.region = region
        self.jeda = jeda
        self.timeout_ms = timeout_ms
        self.maks_scroll = maks_scroll
        self.chromium = chromium
        self._pw = None
        self._browser = None
        self._context = None

    def __enter__(self) -> PenjelajahTikTok:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless, executable_path=self.chromium
        )
        self._context = self._browser.new_context(locale="id-ID", viewport={"width": 1280,
                                                                             "height": 900})
        self._context.set_default_timeout(self.timeout_ms)
        return self

    def __exit__(self, *_: object) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()

    def _buka(self, page, url: str) -> None:
        from playwright.sync_api import Error as PlaywrightError

        try:
            page.goto(url, wait_until="domcontentloaded")
        except PlaywrightError as e:
            raise GagalAkses(f"tidak bisa membuka {url}: {str(e).splitlines()[0]}") from e

    def _istirahat(self) -> None:
        time.sleep(random.uniform(*self.jeda))

    def riset_profil(self, username: str, maks_video: int) -> tuple[str, list[dict[str, Any]]]:
        page = self._context.new_page()
        tertangkap: list[dict[str, Any]] = []

        def tangkap(respons) -> None:
            if "/api/post/item_list" in respons.url and respons.ok:
                try:
                    tertangkap.append(respons.json())
                except Exception:  # respons kosong/bukan JSON: abaikan saja
                    pass

        page.on("response", tangkap)
        try:
            url = URL_PROFIL.format(username=username)
            self._buka(page, url)
            page.wait_for_timeout(3000)
            html = page.content()
            cek_diblokir(html, page.url)

            # Scroll sampai video cukup, TikTok bilang habis, atau batas scroll tercapai.
            for _ in range(self.maks_scroll):
                jumlah = sum(len(d.get("itemList") or []) for d in tertangkap)
                habis = bool(tertangkap) and not tertangkap[-1].get("hasMore")
                if jumlah >= maks_video or habis:
                    break
                page.mouse.wheel(0, 4000)
                page.wait_for_timeout(int(random.uniform(*self.jeda) * 1000))
                cek_diblokir(page.content(), page.url)
            return html, tertangkap
        finally:
            page.close()
            self._istirahat()

    def produk_html(self, product_id: str) -> tuple[str, str]:
        page = self._context.new_page()
        try:
            url = URL_PRODUK.format(product_id=product_id, region=self.region)
            self._buka(page, url)
            page.wait_for_timeout(2500)
            html = page.content()
            cek_diblokir(html, page.url)
            return html, page.url
        finally:
            page.close()
            self._istirahat()
