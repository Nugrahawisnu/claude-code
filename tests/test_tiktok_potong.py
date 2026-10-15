import pytest

from tiktok_potong import bangun_perintah_ffmpeg, hitung_potongan, parse_hening

CONTOH_STDERR = """\
[silencedetect @ 0x1] silence_start: -0.0213
[silencedetect @ 0x1] silence_end: 1.52 | silence_duration: 1.54
[silencedetect @ 0x1] silence_start: 4.1
[silencedetect @ 0x1] silence_end: 4.9 | silence_duration: 0.8
[silencedetect @ 0x1] silence_start: 8.75
"""


def test_parse_hening():
    assert parse_hening(CONTOH_STDERR) == [(0.0, 1.52), (4.1, 4.9), (8.75, None)]


def test_parse_hening_kosong():
    assert parse_hening("tidak ada apa-apa") == []


def test_potong_detik_tetap_saja():
    assert hitung_potongan(10.0, [], awal=2, akhir=3) == (2.0, 7.0)


def test_potong_hening_saja():
    assert hitung_potongan(10.0, [(0.0, 1.5), (8.0, None)]) == (1.5, 8.0)


def test_hening_di_tengah_diabaikan():
    assert hitung_potongan(10.0, [(4.0, 5.0)]) == (0.0, 10.0)


def test_gabungan_ambil_potongan_terbanyak():
    hening = [(0.0, 1.5), (8.0, 10.0)]
    # detik tetap lebih besar di depan, hening lebih besar di belakang
    assert hitung_potongan(10.0, hening, awal=3, akhir=1) == (3.0, 8.0)
    # hening lebih besar di depan, detik tetap lebih besar di belakang
    assert hitung_potongan(10.0, hening, awal=1, akhir=4) == (1.5, 6.0)


def test_sisa_terlalu_pendek():
    with pytest.raises(ValueError, match="terlalu pendek"):
        hitung_potongan(5.0, [], awal=2.5, akhir=2)


def test_nilai_negatif_ditolak():
    with pytest.raises(ValueError):
        hitung_potongan(5.0, [], awal=-1)


def test_perintah_format_tiktok():
    cmd = bangun_perintah_ffmpeg("a.mp4", "b.mp4", 1.5, 8.0)
    assert cmd[cmd.index("-ss") + 1] == "1.500"
    assert cmd[cmd.index("-t") + 1] == "6.500"
    filtergraph = cmd[cmd.index("-filter_complex") + 1]
    assert "1080:1920" in filtergraph and "boxblur" in filtergraph
    assert cmd[-1] == "b.mp4"


def test_perintah_tanpa_format():
    cmd = bangun_perintah_ffmpeg("a.mp4", "b.mp4", 0, 5, format_tiktok=False)
    assert "-filter_complex" not in cmd
