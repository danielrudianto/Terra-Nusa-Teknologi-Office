"""
KPI perusahaan & papan antrean.

Yang dijaga di sini adalah kekeliruan yang TIDAK menghasilkan galat: ember
umur yang meleset satu hari di batasnya, marjin yang digambar nol padahal
datanya belum cukup, tahap antrean yang muncul kepada orang yang tidak
berhak, dan kegagalan kueri yang dijawab angka nol — yang terbaca sebagai
"tidak ada yang menunggu".
"""

import pytest

from controllers.kpi_controller import KpiController
from repository.kpi_repository import (
    EMBER_TERAKHIR,
    KpiRepository,
    _antre,
    _bulan_mundur,
    _ember,
)

MODUL = "repository.kpi_repository"


# ---------------------------------------------------------------------
# Ember umur — batasnya, dan kedua sisinya.
# ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "hari,harap",
    [
        (0, "0-2"), (1, "0-2"), (2, "0-2"),
        (3, "3-7"), (7, "3-7"),
        (8, "8-14"), (14, "8-14"),
        (15, EMBER_TERAKHIR), (400, EMBER_TERAKHIR),
    ],
)
def test_ember_umur_pada_batasnya(hari, harap):
    """
    Tiap batas diuji dari KEDUA sisinya.

    Meleset satu hari tidak menghasilkan galat apa pun — ia hanya memindahkan
    dokumen ke kolom sebelahnya, dan papannya tetap terlihat masuk akal.
    """
    assert _ember(hari) == harap


def test_umur_negatif_tidak_masuk_ember_terakhir():
    """
    Dokumen bertanggal masa depan (salah ketik tahun) berumur negatif.

    Tanpa penjagaan, angka negatif lolos seluruh batas dan jatuh ke ember
    "15+" — dokumen yang baru dibuat kemarin tampil sebagai yang paling
    lama tertahan, dan itu justru yang akan dikejar orang lebih dulu.
    """
    assert _ember(-5) == "0-2"


# ---------------------------------------------------------------------
# Kegagalan disebut, bukan dijawab nol.
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_kueri_gagal_menjawab_gagal_bukan_nol(fake_db):
    """
    Nol berarti "tidak ada yang menunggu". Itu pernyataan yang BERBEDA dari
    "angkanya tidak terbaca", dan yang keliru justru menenangkan: papan yang
    kosong karena rusak terlihat persis seperti papan yang kosong karena
    pekerjaannya sudah beres.
    """
    db = fake_db(MODUL)
    db.fail("fetch_all", RuntimeError("basis data mati"))

    hasil = await _antre("poPeriksa", "purchase_order", "SELECT 1", {})

    assert hasil["gagal"] is True
    assert hasil["jumlah"] is None
    assert hasil["tertuaHari"] is None


@pytest.mark.asyncio
async def test_antrean_kosong_bukan_gagal(fake_db):
    """Tahap yang memang kosong TIDAK boleh ditandai gagal."""
    db = fake_db(MODUL)
    db.queue("fetch_all", [])

    hasil = await _antre("poPeriksa", "purchase_order", "SELECT 1", {})

    assert "gagal" not in hasil
    assert hasil["jumlah"] == 0
    assert hasil["tertuaHari"] == 0


@pytest.mark.asyncio
async def test_umur_tertua_dan_sebarannya(fake_db):
    db = fake_db(MODUL)
    db.queue(
        "fetch_all",
        [{"umur": 0}, {"umur": 3}, {"umur": 9}, {"umur": 40}, {"umur": 2}],
    )

    hasil = await _antre("poPeriksa", "purchase_order", "SELECT 1", {})

    assert hasil["jumlah"] == 5
    assert hasil["tertuaHari"] == 40
    assert hasil["ember"] == {"0-2": 2, "3-7": 1, "8-14": 1, "15+": 1}


# ---------------------------------------------------------------------
# Syarat antrean HARUS sama dengan syarat lencana.
# ---------------------------------------------------------------------


def _normal(teks: str) -> str:
    return " ".join(teks.split()).lower()


def test_syarat_antrean_sama_dengan_lencana():
    """
    Dua tempat menghitung antrean yang sama.

    Kalau syaratnya menyimpang, lencana di menu dan papan antrean akan
    menyebut dua angka untuk tahap yang sama — dan yang membacanya tidak
    punya cara tahu mana yang benar. Yang dibandingkan potongan syaratnya,
    bukan seluruh SQL: papan ini sengaja TIDAK mengecualikan dokumen buatan
    pembacanya sendiri (lihat keterangan di `_Antrean`).
    """
    import os

    akar = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    lencana = _normal(
        open(
            os.path.join(akar, "repository", "lencana_repository.py"),
            encoding="utf-8",
        ).read()
    )
    from repository.kpi_repository import _Antrean

    # Potongan yang menentukan TAHAPNYA, bukan penyaring diri sendiri.
    WAJIB = {
        "poPeriksa": "isdelete = 0, ischecked = 0, status = 'draft'",
        "poSetujui": (
            "isdelete = 0, ischecked = 1, isapproved = 0, status = 'draft'"
        ),
    }
    for nama, gabungan in WAJIB.items():
        for potongan in gabungan.split(", "):
            assert potongan in lencana, (
                f"{nama}: syarat `{potongan}` tidak ada di lencana — "
                f"salah satu dari keduanya sudah berubah sendirian"
            )
            sql = _normal(
                _Antrean.PO_PERIKSA
                if nama == "poPeriksa"
                else _Antrean.PO_SETUJUI
            )
            assert potongan in sql, (
                f"{nama}: syarat `{potongan}` hilang dari papan antrean"
            )


def test_antrean_tidak_menghitung_dokumen_terhapus():
    from repository.kpi_repository import _Antrean

    for nama in (
        "PO_PERIKSA", "PO_SETUJUI", "REIMBURSEMENT", "COP_BAP",
        "COP_SETUJUI", "TENDER", "PEMBAYARAN", "FAKTUR",
    ):
        sql = _normal(getattr(_Antrean, nama))
        assert "isdelete = 0" in sql, (
            f"{nama} tidak menyaring `isDelete` — dokumen yang sudah dihapus "
            f"akan menumpuk di papan dan tidak dapat diturunkan siapa pun"
        )


# ---------------------------------------------------------------------
# Deret bulan.
# ---------------------------------------------------------------------


def test_bulan_mundur_menyeberang_tahun():
    from datetime import date as d

    assert _bulan_mundur(3, d(2026, 1, 15)) == [(2025, 11), (2025, 12), (2026, 1)]


def test_bulan_mundur_selalu_kronologis():
    from datetime import date as d

    deret = _bulan_mundur(14, d(2026, 3, 1))
    assert deret == sorted(deret)
    assert len(deret) == 14
    assert deret[-1] == (2026, 3)


# ---------------------------------------------------------------------
# Controller: jendela marjin, dan apa yang terjadi sebelum cukup panjang.
# ---------------------------------------------------------------------


def _deret(n: int, pendapatan=1000.0, laba_kotor=200.0, beban=50.0):
    """n bulan berurutan dengan angka yang sama, mulai 2025-01."""
    out = []
    t, b = 2025, 1
    for _ in range(n):
        out.append(
            {
                "tahun": t, "bulan": b,
                "pendapatan": pendapatan,
                "hpp": pendapatan - laba_kotor,
                "labaKotor": laba_kotor,
                "bebanUsaha": beban,
                "labaUsaha": laba_kotor - beban,
                "bebanLain": 0.0,
                "labaSebelumPajak": laba_kotor - beban,
            }
        )
        b += 1
        if b > 12:
            b = 1
            t += 1
    return out


@pytest.mark.asyncio
async def test_marjin_memakai_jendela_dua_belas_bulan(monkeypatch):
    async def _palsu(mundur, sampai=None):
        return {"bulan": _deret(mundur)}

    monkeypatch.setattr(
        KpiRepository, "laba_per_bulan", staticmethod(_palsu)
    )

    hasil = await KpiController.perusahaan(3)

    assert hasil["jendelaBulan"] == 12
    terakhir = hasil["bulan"][-1]["jendela"]
    assert terakhir["bulan"] == 12
    # 12 bulan x 1000 pendapatan, laba kotor 200 -> marjin 0,2
    assert terakhir["pendapatan"] == 12_000
    assert abs(terakhir["marjinKotor"] - 0.2) < 1e-9


@pytest.mark.asyncio
async def test_data_belum_cukup_ditandai_bukan_digambar_nol(monkeypatch):
    """
    Marjin 0% dan "datanya belum dua belas bulan" adalah dua keadaan.

    Tanpa penanda, titik pertama grafik akan digambar di nol dan terbaca
    sebagai bulan tanpa laba sama sekali.
    """
    async def _palsu(mundur, sampai=None):
        return {"bulan": _deret(4)}  # jauh lebih pendek dari yang diminta

    monkeypatch.setattr(
        KpiRepository, "laba_per_bulan", staticmethod(_palsu)
    )

    hasil = await KpiController.perusahaan(4)

    assert hasil["bulan"][0]["jendela"].get("belumCukup") is True
    assert "marjinKotor" not in hasil["bulan"][0]["jendela"]


@pytest.mark.asyncio
async def test_tanpa_pendapatan_marjin_none_bukan_nol(monkeypatch):
    async def _palsu(mundur, sampai=None):
        return {"bulan": _deret(mundur, pendapatan=0.0, laba_kotor=0.0)}

    monkeypatch.setattr(
        KpiRepository, "laba_per_bulan", staticmethod(_palsu)
    )

    hasil = await KpiController.perusahaan(2)
    jendela = hasil["bulan"][-1]["jendela"]

    assert jendela["marjinKotor"] is None, (
        "marjin 0% berarti pendapatan habis dimakan biaya; tidak ada "
        "pendapatan sama sekali adalah keadaan lain"
    )


@pytest.mark.asyncio
async def test_banding_bulan_lalu_dan_tahun_lalu(monkeypatch):
    deret = _deret(14)
    # Bulan terakhir dinaikkan supaya selisihnya dapat dibedakan.
    deret[-1]["pendapatan"] = 1500.0

    async def _palsu(mundur, sampai=None):
        return {"bulan": deret}

    monkeypatch.setattr(
        KpiRepository, "laba_per_bulan", staticmethod(_palsu)
    )

    hasil = await KpiController.perusahaan(2)
    banding = hasil["bulan"][-1]["banding"]

    assert banding["bulanLalu"]["pendapatan"] == 500.0
    assert banding["tahunLalu"]["pendapatan"] == 500.0


@pytest.mark.asyncio
async def test_kegagalan_repository_diteruskan(monkeypatch):
    async def _palsu(mundur, sampai=None):
        return {"bulan": [], "gagal": True}

    monkeypatch.setattr(
        KpiRepository, "laba_per_bulan", staticmethod(_palsu)
    )

    hasil = await KpiController.perusahaan(12)

    assert hasil["gagal"] is True, (
        "deret kosong tanpa penanda akan digambar sebagai perusahaan tanpa "
        "pendapatan sama sekali — grafik rata di nol, tanpa satu pun galat"
    )


# ---------------------------------------------------------------------
# Izin: tahap yang tidak boleh dikerjakan TIDAK muncul sama sekali.
# ---------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tahap_tanpa_izin_tidak_muncul(fake_db, monkeypatch):
    """
    Tidak muncul SAMA SEKALI, bukan muncul sebagai nol.

    Nol berarti "tidak ada yang menunggu di tahap itu". Menampilkannya
    kepada orang yang tidak berhak melihatnya menyatakan sesuatu tentang
    keadaan dokumen perusahaan yang tidak berhak ia ketahui — dan pada saat
    antreannya panjang, nol itu juga kebohongan.
    """
    db = fake_db(MODUL)
    db.queue("fetch_all", [], [], [], [], [], [], [], [])

    import utils.permission as izin

    async def _tolak_semua(user, modul, aksi):
        return False

    monkeypatch.setattr(izin, "is_allowed", _tolak_semua)
    monkeypatch.setattr(izin, "boleh_memeriksa", lambda *a, **k: False)
    monkeypatch.setattr(izin, "boleh_menyetujui_bap_cop", lambda *a: False)
    monkeypatch.setattr(izin, "boleh_menyetujui_cop", lambda *a: False)

    hasil = await KpiRepository.antrean({"id": 1}, 1, set())

    assert hasil["tahap"] == []
    assert db.executed("fetch_all") == 0, (
        "kueri tetap dijalankan untuk tahap yang tidak boleh dilihat — "
        "penyaringannya terjadi SESUDAH membaca, bukan sebelum"
    )


@pytest.mark.asyncio
async def test_hanya_tahap_yang_berizin_yang_dibaca(fake_db, monkeypatch):
    db = fake_db(MODUL)
    db.queue("fetch_all", [{"umur": 4}])

    import utils.permission as izin

    async def _hanya_po_setujui(user, modul, aksi):
        return modul == "purchase_order" and aksi == "approve"

    monkeypatch.setattr(izin, "is_allowed", _hanya_po_setujui)
    monkeypatch.setattr(izin, "boleh_memeriksa", lambda *a, **k: False)
    monkeypatch.setattr(izin, "boleh_menyetujui_bap_cop", lambda *a: False)
    monkeypatch.setattr(izin, "boleh_menyetujui_cop", lambda *a: False)

    hasil = await KpiRepository.antrean({"id": 1}, 3, set())

    assert [t["kode"] for t in hasil["tahap"]] == ["poSetujui"]
    assert hasil["tahap"][0]["jumlah"] == 1
    assert db.executed("fetch_all") == 1
