"""
Rencana kas disaring menurut REKENING — dan yang tanpa rekening tetap ikut.

KENAPA INI ADA

Proyeksi kas di kalender memakai dua angka: saldo rekening yang dicentang, dan
rencana kas. Sebelumnya `PaymentPlanRepository.rentang` tidak punya penyaring
rekening sama sekali, sehingga saldonya datang dari rekening yang dicentang
sementara rencananya dari SELURUH rekening — termasuk rekening yang sengaja
dikecualikan dari kalender (deposito, escrow, penampung uang muka).

Dua sisi dari satu perhitungan memakai kumpulan rekening yang berbeda. Tidak
ada galat, tidak ada angka yang tampak ganjil, garisnya tetap mulus — hanya
salah. Daniel menemukannya dari firasat, bukan dari pesan apa pun.

YANG TANPA REKENING TETAP IKUT

Rencana kerap dibuat sebelum diputuskan dibayar dari rekening mana; kolomnya
memang boleh kosong, dan itu disengaja. Membuangnya saat menyaring berarti
kewajiban sungguhan menghilang dari proyeksi — yang membuatnya terbaca lebih
sehat daripada keadaannya, persis pada bagian yang paling perlu diwaspadai.

Uji ini memeriksa KUERI yang disusun, bukan hasil basis data: yang mudah
salah adalah bentuk penyaringnya, dan bentuk itu terbaca dari kuerinya.
"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from repository.payment_plan_repository import PaymentPlanRepository

AWAL = date(2026, 9, 1)
AKHIR = date(2026, 11, 30)


async def _tangkap(**kwargs):
    """Jalankan `rentang` dengan DB tertambal; kembalikan objek kuerinya."""
    tangkap = AsyncMock(return_value=[])
    with patch(
        "repository.payment_plan_repository.database.fetch_all", new=tangkap
    ):
        await PaymentPlanRepository.rentang(AWAL, AKHIR, **kwargs)
    tangkap.assert_awaited_once()
    return tangkap.await_args.args[0]


def _bersih(teks: str) -> str:
    """
    Rapatkan spasi dan BUANG tanda kutip pengenal.

    SQLAlchemy mengutip nama kolom bergaya camelCase — `payment_plans."bankAccountID"`.
    Pemeriksaan teks tanpa membuangnya gagal karena alasan yang sama sekali
    tidak berhubungan dengan yang sedang diuji, dan uji yang merah karena
    sebab palsu adalah uji yang akhirnya dimatikan orang.
    """
    return " ".join(teks.replace('"', "").replace("`", "").split())


async def _kueri(**kwargs) -> str:
    return _bersih(str(await _tangkap(**kwargs)))


async def _kueri_nilai(**kwargs) -> str:
    """
    Kueri dengan NILAINYA ikut tercetak.

    `str(query)` menuliskan `IN (__[POSTCOMPILE_...])` — penanda, bukan
    nilainya — sehingga memeriksa id di sana tidak menguji apa pun.
    """
    q = await _tangkap(**kwargs)
    return _bersih(str(q.compile(compile_kwargs={"literal_binds": True})))


# ----------------------------------------------------------------------
# Penyaring rekening
# ----------------------------------------------------------------------


async def test_tanpa_penyaring_kuerinya_tidak_menyebut_rekening():
    """Perilaku lama dipertahankan bagi pemanggil yang memang ingin semuanya."""
    q = await _kueri()
    assert "bankAccountID IN" not in q
    assert "bankAccountID IS NULL" not in q


async def test_penyaring_rekening_terpasang():
    q = await _kueri(bank_account_ids=[3, 7])
    assert "payment_plans.bankAccountID IN" in q, (
        "tanpa penyaring ini, proyeksi kas memakai saldo rekening yang "
        "dicentang tetapi rencana dari SELURUH rekening"
    )


async def test_rencana_tanpa_rekening_TETAP_ikut():
    """
    Penjaga yang paling mudah hilang saat seseorang "merapikan" penyaringnya.

    Tanpa cabang `IS NULL`, seluruh rencana yang rekeningnya belum ditentukan
    lenyap dari proyeksi — dan proyeksinya terbaca lebih sehat, tanpa satu pun
    tanda bahwa ada yang hilang.
    """
    q = await _kueri(bank_account_ids=[3])
    assert "payment_plans.bankAccountID IS NULL" in q
    # Keduanya harus dihubungkan OR, bukan AND: `IN (...) AND IS NULL` tidak
    # pernah benar untuk baris mana pun, dan hasilnya selalu kosong.
    assert " OR " in q


async def test_daftar_kosong_tidak_menyaring_apa_apa():
    """
    Daftar kosong berarti "tidak disebut", bukan "tidak satu pun".

    Yang menjaga sisi layar terhadap hal ini adalah komponennya, yang berhenti
    lebih dulu saat tidak ada rekening tercentang — lihat `tanpaRekening`.
    Di lapis ini, daftar kosong sekadar dilewati.
    """
    q = await _kueri(bank_account_ids=[])
    assert "bankAccountID IN" not in q


# ----------------------------------------------------------------------
# Yang tidak boleh ikut berubah
# ----------------------------------------------------------------------


async def test_penyaring_lain_tetap_berlaku():
    q = await _kueri(bank_account_ids=[3], project_name="R501")
    assert "isDelete" in q
    assert "projectName" in q
    assert "status" in q, "yang BATAL harus tetap dikecualikan secara bawaan"


async def test_sertakan_batal_membuka_yang_batal():
    q = await _kueri(sertakan_batal=True)
    assert "payment_plans.status !=" not in q


@pytest.mark.parametrize("ids", [[3], [3, 7], [1, 2, 3, 4, 5]])
async def test_id_selalu_dicasting_ke_int(ids):
    """
    Nilai dari query string datang sebagai TEKS.

    Dibiarkan, penyaringnya membandingkan teks dengan angka — dan pada MySQL
    perbandingan itu diam-diam tetap jalan untuk sebagian nilai dan tidak
    untuk sebagian lain. Karena itu id-nya di-cast di repository, dan kueri
    yang tercetak harus memuat ANGKANYA, bukan teks berkutip.
    """
    q = await _kueri_nilai(bank_account_ids=[str(x) for x in ids])
    penggal = q[q.index("bankAccountID IN") :]
    for x in ids:
        assert f"'{x}'" not in penggal, "id masih berupa teks, belum di-cast"
        assert str(x) in penggal
