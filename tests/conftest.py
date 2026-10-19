from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture_teks():
    def baca(nama: str) -> str:
        return (FIXTURES / nama).read_text(encoding="utf-8")

    return baca
