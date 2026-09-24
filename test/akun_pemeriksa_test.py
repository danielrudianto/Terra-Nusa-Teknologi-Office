"""
Akun PEMERIKSA — boleh membaca, tidak boleh mengubah apa pun.

Dipakai konsultan pajak dan akuntansi yang menelusuri pembukuan AKN
sendiri, tanpa didampingi.

Kenapa tanda tersendiri, bukan sekadar level rendah: laba rugi dan jejak
aktivitas dijaga LEVEL 5, dan level 5 sekaligus memberi hak MENULIS atas
rekening bank, pinjaman, dan pengguna. Tanpa tanda ini, memberi mereka akses
baca berarti memberi hak ubah atas data induk keuangan — dan yang pertama
menuliskannya sebagai temuan justru auditor itu sendiri.

Diuji lewat `is_allowed()` YANG SEBENARNYA, dengan tabel izin khusus dan
departemen ditiru: yang dijaga adalah penolakannya benar-benar terjadi, dan
pemeriksaan teks akan tetap lulus ketika penjaganya dipindah ke cabang yang
tidak pernah dijalankan.
"""

import pytest

import utils.permission as izin
from constants.permission_matrix import ACTIONS


class Baris(dict):
    """`Row` tiruan — mendukung `user["x"]` dan melempar untuk kolom asing."""

    def __getitem__(self, k):
        if k not in self:
            raise KeyError(k)
        return super().__getitem__(k)


def pengguna(level=5, hanya_baca=False, dengan_kolom=True):
    d = {"id": 1, "authenticationLevel": level}
    if dengan_kolom:
        d["isReadOnly"] = hanya_baca
    return Baris(d)


@pytest.fixture(autouse=True)
def tanpa_basis_data(monkeypatch):
    """Izin khusus dan departemen dikosongkan; yang diuji tandanya."""

    async def _kosong_overrides(_user_id):
        return {}

    async def _kosong_departemen(_user_id):
        return set()

    monkeypatch.setattr(izin, "_overrides", _kosong_overrides)
    monkeypatch.setattr(izin, "_departments", _kosong_departemen)


MODUL_TULIS = ["purchase", "bank", "loan", "user", "sales_invoice", "payment_incoming"]


@pytest.mark.asyncio
@pytest.mark.parametrize("modul", MODUL_TULIS)
@pytest.mark.parametrize("aksi", [a for a in ACTIONS if a != "read"])
async def test_pemeriksa_tidak_dapat_menulis(modul, aksi):
    # Level 5 sekalipun: tandanya di atas level.
    assert await izin.is_allowed(pengguna(5, True), modul, aksi) is False


@pytest.mark.asyncio
@pytest.mark.parametrize("modul", MODUL_TULIS)
async def test_pemeriksa_tetap_dapat_membaca(modul):
    assert await izin.is_allowed(pengguna(5, True), modul, "read") is True


@pytest.mark.asyncio
async def test_pemeriksa_dapat_membaca_laba_rugi_dan_jejak():
    # Inilah alasan tandanya ada: keduanya level 5, dan level 5 tanpa tanda
    # ini juga berarti dapat mengubah rekening bank.
    for modul in ("finance_status", "audit_log"):
        assert await izin.is_allowed(pengguna(5, True), modul, "read") is True
    assert await izin.is_allowed(pengguna(5, True), "bank", "update") is False
    assert await izin.is_allowed(pengguna(5, True), "bank", "delete") is False


@pytest.mark.asyncio
async def test_izin_khusus_tidak_membuka_kembali(monkeypatch):
    """
    Satu baris `allowed = 1` yang terlanjur ada TIDAK boleh menjadikannya
    dapat menulis.

    Inilah sebabnya tandanya diperiksa DI ATAS `_overrides`. Akun pemeriksa
    kerap dibuat dari akun lama, dan izin khusus yang tertinggal di tabelnya
    akan membuka pintu yang dikira sudah tertutup.
    """

    async def _override(_user_id):
        return {("purchase", "create"): True, ("bank", "delete"): True}

    monkeypatch.setattr(izin, "_overrides", _override)

    assert await izin.is_allowed(pengguna(5, True), "purchase", "create") is False
    assert await izin.is_allowed(pengguna(5, True), "bank", "delete") is False
    # Tanpa tanda, izin khusus tetap berlaku seperti sebelumnya.
    assert await izin.is_allowed(pengguna(1, False), "purchase", "create") is True


@pytest.mark.asyncio
async def test_akun_biasa_tidak_terpengaruh():
    assert await izin.is_allowed(pengguna(5, False), "bank", "update") is True
    assert await izin.is_allowed(pengguna(5, False), "purchase", "create") is True


@pytest.mark.asyncio
async def test_kolom_belum_ada_tidak_mengunci_siapa_pun():
    """
    SQL-nya belum dijalankan: `user["isReadOnly"]` melempar `KeyError`.

    Yang benar adalah "tidak ada akun pemeriksa", bukan "seluruh aplikasi
    berhenti bekerja" — dan bukan pula "semuanya hanya baca".
    """
    u = pengguna(5, dengan_kolom=False)
    assert await izin.is_allowed(u, "bank", "update") is True
    assert await izin.is_allowed(u, "purchase", "create") is True


@pytest.mark.asyncio
async def test_nilai_tersimpan_sebagai_angka_tetap_terbaca():
    # MySQL mengembalikan TINYINT(1) sebagai 0/1, bukan True/False.
    u = Baris({"id": 1, "authenticationLevel": 5, "isReadOnly": 1})
    assert await izin.is_allowed(u, "purchase", "create") is False
    u0 = Baris({"id": 1, "authenticationLevel": 5, "isReadOnly": 0})
    assert await izin.is_allowed(u0, "purchase", "create") is True


def test_tidak_ada_rute_tulis_berpenjaga_baca():
    """
    Penjagaannya utuh selama pemetaan "rute tulis -> aksi tulis" utuh.

    Satu POST yang benar-benar menulis tetapi dijaga `require(..., "read")`
    menembus seluruh peran ini, tanpa satu pun galat.
    """
    import sys, pathlib

    akar = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(akar / "scripts"))
    import bacatuliscek

    masalah = bacatuliscek.periksa(str(akar / "routes"))
    assert masalah == [], "\n".join(masalah)
