"""
Menghapus beban ikut menghapus pembayarannya.

Pembayaran yang ditinggalkan hidup adalah uang keluar tanpa dokumen: ia tetap
terhitung pada saldo bank dan pada kalender kas, tetapi tidak dapat ditelusuri
ke beban mana pun. Yang mencocokkan rekening koran menemukan selisih yang
tidak ada penjelasannya, dan penjelasannya memang sudah dihapus.

Sebaliknya, membatalkan pembayaran adalah tindakan yang di pintu lain hanya
boleh dilakukan level 5. Karena penghapusan beban melakukannya secara tidak
langsung, ia harus punya penjaganya sendiri — sama seperti pada pembelian.

Diperiksa dari sumbernya, bukan dengan menjalankan basis data: seluruh yang
dijaga di sini adalah urutan dan syarat di dalam kode, bukan hasil kueri.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _blok(relatif: str, nama: str) -> str:
    """Badan sebuah fungsi, tanpa komentar."""
    s = open(os.path.join(AKAR, relatif), encoding="utf-8").read()
    i = s.index(f"async def {nama}(")
    j = s.find("async def ", i + 10)
    blok = s[i:] if j == -1 else s[i:j]
    # Komentar dibuang: keterangan yang MENYEBUT sesuatu bukan kodenya.
    return "\n".join(
        b for b in blok.splitlines() if not b.lstrip().startswith("#")
    )


# ----------------------------------------------------------------------
# Controller
# ----------------------------------------------------------------------

def test_menghapus_beban_ikut_menghapus_pembayarannya():
    b = _blok("controllers/expense_controller.py", "delete_expense")
    assert "delete_payment_by_expense_id" in b, (
        "delete_expense tidak menghapus pembayaran yang melekat"
    )


def test_pembayaran_dihapus_SESUDAH_dokumennya():
    """
    Urutannya menentukan keadaan bila langkah kedua gagal.

    Dokumen dulu, pembayaran menyusul: beban yang terhapus dengan pembayaran
    tersisa masih dapat dibereskan. Terbalik — pembayaran hilang lebih dulu
    lalu penghapusan bebannya gagal — meninggalkan beban yang tampak belum
    dibayar padahal uangnya sudah keluar.
    """
    b = _blok("controllers/expense_controller.py", "delete_expense")
    i_dokumen = b.index("ExpenseRepository.delete(")
    i_bayar = b.index("delete_payment_by_expense_id")
    assert i_dokumen < i_bayar, (
        "pembayaran dihapus sebelum dokumennya; bila penghapusan dokumen "
        "gagal, bebannya terbaca belum dibayar padahal uangnya sudah keluar"
    )


def test_beban_berpembayaran_hanya_boleh_dihapus_level_4():
    b = _blok("controllers/expense_controller.py", "delete_expense")

    assert "hitung_pembayaran_aktif_beban" in b, (
        "delete_expense tidak memeriksa apakah ada pembayaran yang melekat"
    )
    assert "EXPENSE_HAS_PAYMENTS" in b, (
        "penolakannya tidak memakai kode tetap, sehingga layar tidak dapat "
        "menerjemahkannya menjadi kalimat yang berguna"
    )
    assert re.search(r"userLevel\s*or\s*0\)\s*<\s*4", b), (
        "batas levelnya bukan 4; menghapus pembayaran adalah tindakan level "
        "tinggi walaupun modul beban mengizinkan hapus di level 2"
    )


def test_beban_yang_sudah_dihapus_ditolak():
    """
    Tanpa ini, menghapus dua kali akan menghapus pembayaran DUA kali dan
    meninggalkan dua jejak audit untuk satu peristiwa.
    """
    b = _blok("controllers/expense_controller.py", "delete_expense")
    assert "isDelete" in b, "delete_expense tidak menolak beban yang sudah dihapus"


def test_rute_meneruskan_level_pemakai():
    """Penjaga di controller tidak berarti apa-apa bila levelnya tidak sampai."""
    s = open(
        os.path.join(AKAR, "routes", "expenses_routes.py"), encoding="utf-8"
    ).read()
    i = s.index('@router.delete("/{expense_id}")')
    blok = s[i : s.find("@router.", i + 10)]

    assert "authenticationLevel" in blok, (
        "rute DELETE beban tidak meneruskan level pemakai ke controller"
    )


# ----------------------------------------------------------------------
# Repository
# ----------------------------------------------------------------------

def test_persetujuan_ikut_dicabut():
    """
    Status lunas dihitung dari pembayaran yang DISETUJUI dan belum dihapus.

    Menyisakan `isApprove` pada baris yang sudah dihapus membuat dokumen
    terbaca lunas oleh sebagian kueri dan belum lunas oleh sebagian yang lain.
    """
    b = _blok(
        "repository/payment_outgoing_repository.py", "delete_payment_by_expense_id"
    )
    assert "isDelete=True" in b
    assert "isApprove=False" in b, (
        "persetujuan tidak dicabut; pembayaran terhapus masih terhitung lunas"
    )


def test_jejak_audit_memakai_id_pembayaran_bukan_id_beban():
    """
    Ini kekeliruan yang ada pada versi pembelian-nya.

    Mencatat id dokumen induk pada entitas `payment_outgoing` membuat jejaknya
    tidak dapat ditelusuri balik: yang membukanya mencari pembayaran bernomor
    itu dan menemukan pembayaran milik dokumen lain.
    """
    b = _blok(
        "repository/payment_outgoing_repository.py", "delete_payment_by_expense_id"
    )
    assert 'entity="payment_outgoing"' in b
    assert "entityID=expenseID" not in b, (
        "jejak audit pembayaran memakai id beban"
    )
    assert re.search(r"entityID=int\(paymentID\)", b), (
        "jejak audit tidak memakai id pembayarannya sendiri"
    )


def test_id_diambil_sebelum_diperbarui():
    """
    Sesudah diperbarui, baris yang terkena tidak dapat dibedakan lagi dari
    yang memang sudah terhapus sebelumnya — dan jejaknya akan menyebut
    pembayaran yang tidak disentuh operasi ini.
    """
    b = _blok(
        "repository/payment_outgoing_repository.py", "delete_payment_by_expense_id"
    )
    i_baca = b.index("fetch_all(")
    i_tulis = b.index(".update()")
    assert i_baca < i_tulis, "id pembayaran diambil setelah barisnya diperbarui"


def test_gagal_menghitung_dianggap_ada_pembayaran():
    """
    Menolak penghapusan yang mungkin sah lebih ringan akibatnya daripada
    meloloskan penghapusan yang ikut membatalkan pembayaran.
    """
    b = _blok(
        "repository/payment_outgoing_repository.py", "hitung_pembayaran_aktif_beban"
    )
    assert "return -1" in b, (
        "kegagalan menghitung mengembalikan 0, sehingga beban berpembayaran "
        "lolos dihapus oleh level rendah"
    )
