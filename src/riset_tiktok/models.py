"""Model data hasil riset."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Produk:
    product_id: str
    nama: str = ""
    link: str = ""
    harga: float | None = None
    harga_coret: float | None = None
    mata_uang: str = ""
    toko: str = ""
    terjual: int | None = None
    rating: float | None = None
    jumlah_ulasan: int | None = None
    # Komisi afiliasi hampir tidak pernah tampil di halaman publik; biasanya kosong.
    komisi_persen: float | None = None
    jumlah_video: int = 0
    total_views_video: int = 0

    def ke_dict(self) -> dict:
        return asdict(self)


@dataclass
class Video:
    video_id: str
    link: str = ""
    deskripsi: str = ""
    dibuat: str = ""
    views: int = 0
    likes: int = 0
    komentar: int = 0
    share: int = 0
    simpan: int = 0
    product_ids: list[str] = field(default_factory=list)

    def ke_dict(self) -> dict:
        data = asdict(self)
        data["product_ids"] = ",".join(self.product_ids)
        return data


@dataclass
class Profil:
    username: str
    nama: str = ""
    bio: str = ""
    verified: bool = False
    followers: int = 0
    following: int = 0
    likes: int = 0
    jumlah_video: int = 0
    link: str = ""

    def ke_dict(self) -> dict:
        return asdict(self)
