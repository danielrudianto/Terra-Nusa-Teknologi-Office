"""
Pencarian global (Ctrl+K): izin diperiksa SEBELUM kueri, satu kelompok yang
gagal tidak menjatuhkan yang lain, dan ketikan pendek tidak dikueri.
"""

import asyncio

import pytest

from controllers import search_controller as sc


def _jalankan(coro):
    return asyncio.run(coro)


@pytest.fixture
def palsu(monkeypatch):
    dipanggil = []

    def pengambil(jenis, baris=None, gagal=False):
        async def f(q, batas):
            dipanggil.append(jenis)
            if gagal:
                raise RuntimeError("kolom hilang")
            return baris or []
        return f

    kelompok = [
        ("klien", "client", pengambil("klien", [{"id": 1, "prefix": "PT", "name": "Maju", "city": "Bekasi"}]),
         sc.KELOMPOK[1][3]),
        ("karyawan", "employees", pengambil("karyawan", [{"id": 2, "name": "Budi", "position": "Staf"}]),
         sc.KELOMPOK[-1][3]),
        ("proyek", "project", pengambil("proyek", gagal=True), sc.KELOMPOK[0][3]),
    ]
    monkeypatch.setattr(sc, "KELOMPOK", kelompok)
    return dipanggil


def test_modul_tanpa_izin_tidak_pernah_dikueri(palsu, monkeypatch):
    async def boleh(user, modul, aksi):
        return modul != "employees"
    monkeypatch.setattr(sc, "is_allowed", boleh)

    hasil = asyncio.run(sc.SearchController.cari({"id": 1}, "ma"))
    jenis = [k["jenis"] for k in hasil["kelompok"]]
    assert "karyawan" not in jenis
    assert "karyawan" not in palsu          # bahkan tidak disentuh
    assert hasil["kelompok"][0]["hasil"][0]["judul"] == "PT Maju"


def test_kelompok_gagal_dilewati_yang_lain_tetap(palsu, monkeypatch):
    async def boleh(user, modul, aksi):
        return True
    monkeypatch.setattr(sc, "is_allowed", boleh)
    hasil = asyncio.run(sc.SearchController.cari({"id": 1}, "ma"))
    assert [k["jenis"] for k in hasil["kelompok"]] == ["klien", "karyawan"]


def test_ketikan_pendek_tidak_dikueri(palsu, monkeypatch):
    async def boleh(user, modul, aksi):
        return True
    monkeypatch.setattr(sc, "is_allowed", boleh)
    hasil = asyncio.run(sc.SearchController.cari({"id": 1}, " m "))
    assert hasil["kelompok"] == [] and palsu == []
