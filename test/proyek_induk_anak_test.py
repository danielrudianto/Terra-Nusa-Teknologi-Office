"""
Hubungan induk-anak antar proyek.

Sebagian pekerjaan dipecah menjadi beberapa kode: satu memegang kontraknya,
yang lain menampung biaya per paket. Dilihat sendiri-sendiri keduanya tampak
ganjil — ada penjualan tanpa pembelian, atau pembelian tanpa penjualan sama
sekali — dan margin masing-masing tidak berarti apa-apa.

Yang dijaga di sini BENTUK hubungannya. Tiga gabungan menghasilkan laporan
gabungan yang salah tanpa satu pun galat bila dibiarkan, dan yang ketiga
bahkan tidak pernah selesai dihitung.
"""

import pytest

from controllers.project_controller import _periksa_induk
from models.project_model import projects_table


class Palsu:
    """Pengganti repository; hanya tiga pertanyaan yang ditanyakan penjaganya."""

    def __init__(self, ada=True, induk_dari=None, anak=0):
        self._ada = ada
        self._induk_dari = induk_dari
        self._anak = anak

    async def get_by_id(self, pid):
        return {"id": pid} if self._ada else None

    async def induk_dari(self, pid):
        return self._induk_dari

    async def punya_anak(self, pid):
        return self._anak


@pytest.fixture
def repo(monkeypatch):
    def pasang(**kw):
        palsu = Palsu(**kw)
        import controllers.project_controller as modul

        monkeypatch.setattr(modul.ProjectRepository, "get_by_id", palsu.get_by_id)
        monkeypatch.setattr(modul.ProjectRepository, "induk_dari", palsu.induk_dari)
        monkeypatch.setattr(modul.ProjectRepository, "punya_anak", palsu.punya_anak)
        return palsu

    return pasang


def test_kolomnya_ada():
    assert "parentProjectID" in {c.name for c in projects_table.columns}


@pytest.mark.asyncio
async def test_induk_yang_wajar_diterima(repo):
    repo()
    assert await _periksa_induk(5, 9) is None


@pytest.mark.asyncio
async def test_mengosongkan_induk_selalu_boleh(repo):
    """
    Melepas hubungan tidak pernah merusak apa pun.

    Diperiksa lebih dahulu, sebelum pertanyaan lain: proyek yang punya anak
    tetap boleh MELEPAS induknya sendiri.
    """
    repo(anak=3)
    for kosong in (None, "", 0):
        assert await _periksa_induk(5, kosong) is None, kosong


@pytest.mark.asyncio
async def test_induk_diri_sendiri_ditolak(repo):
    """Laporan gabungan yang menelusurinya menjumlahkan biayanya dua kali."""
    repo()
    hasil = await _periksa_induk(5, 5)
    assert hasil and hasil["status"] == 400


@pytest.mark.asyncio
async def test_induk_yang_tidak_ada_ditolak(repo):
    repo(ada=False)
    hasil = await _periksa_induk(5, 9)
    assert hasil and hasil["status"] == 404


@pytest.mark.asyncio
async def test_induk_yang_sendirinya_anak_ditolak(repo):
    """
    Kedalamannya SATU tingkat.

    Rantai induk-anak-cucu membuat laporan gabungan harus menelusuri sedalam
    apa pun rantainya — dan rantai yang melingkar tidak pernah selesai
    dihitung.
    """
    repo(induk_dari=1)
    hasil = await _periksa_induk(5, 9)
    assert hasil and hasil["status"] == 409


@pytest.mark.asyncio
async def test_proyek_berANAK_tidak_boleh_dijadikan_anak(repo):
    """Sisi lain dari aturan yang sama, dan yang paling mudah terlewat."""
    repo(anak=2)
    hasil = await _periksa_induk(5, 9)
    assert hasil and hasil["status"] == 409
    assert "2" in hasil["error"]


@pytest.mark.asyncio
async def test_nilai_yang_tidak_terbaca_ditolak(repo):
    repo()
    for ngawur in ("ngawur", [], {}):
        hasil = await _periksa_induk(5, ngawur)
        assert hasil and hasil["status"] == 400, ngawur


@pytest.mark.asyncio
async def test_id_berupa_teks_angka_tetap_terbaca(repo):
    # Sebagian jalur meneruskan nilainya apa adanya dari muatan JSON.
    repo()
    assert await _periksa_induk(5, "9") is None
    hasil = await _periksa_induk(5, "5")
    assert hasil and hasil["status"] == 400
