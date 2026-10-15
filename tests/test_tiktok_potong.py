import json
import shutil
import subprocess

import pytest

from tiktok_potong import (
    bangun_perintah_ffmpeg,
    hitung_potongan,
    kumpulkan_video,
    main,
    parse_hening,
)

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


butuh_ffmpeg = pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg tidak terpasang",
)


def _probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height:format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    ).stdout
    data = json.loads(out)
    s = data["streams"][0]
    return s["width"], s["height"], float(data["format"]["duration"])


@butuh_ffmpeg
def test_integrasi_hening_dan_format(tmp_path):
    # Video landscape 6 dtk: hening 1 dtk di awal & akhir, nada di tengah.
    sumber = tmp_path / "uji.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y",
         "-f", "lavfi", "-i", "testsrc=size=640x360:rate=30:duration=6",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
         "-af", "volume=enable='lt(t,1)+gt(t,5)':volume=0",
         "-c:v", "libx264", "-c:a", "aac", "-shortest", str(sumber)],
        check=True,
    )
    keluar = tmp_path / "hasil"
    assert main([str(sumber), "-o", str(keluar)]) == 0

    lebar, tinggi, dur = _probe(keluar / "uji_tiktok.mp4")
    assert (lebar, tinggi) == (1080, 1920)
    assert dur == pytest.approx(4.0, abs=0.25)


@butuh_ffmpeg
def test_integrasi_coba_tidak_membuat_file(tmp_path):
    sumber = tmp_path / "uji.mp4"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "testsrc=size=320x240:rate=30:duration=4", str(sumber)],
        check=True,
    )
    keluar = tmp_path / "hasil"
    assert main([str(sumber), "-o", str(keluar), "--awal", "1", "--coba"]) == 0
    assert not keluar.exists()


def test_kumpulkan_video_lewati_hasil(tmp_path):
    for nama in ["a.mp4", "b.MOV", "a_tiktok.mp4", "catatan.txt"]:
        (tmp_path / nama).touch()
    assert [p.name for p in kumpulkan_video(tmp_path)] == ["a.mp4", "b.MOV"]
