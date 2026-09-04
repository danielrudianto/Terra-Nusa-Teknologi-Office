"""
Slip gaji: menghapus, dan rekening yang diisikan sendiri.

DUA hal dijaga di sini.

Pertama, slip yang PEMBAYARANNYA sudah ada tidak boleh dihapus. Pembayaran
menunjuk slipnya lewat `salarySlipID`; menghapus slipnya meninggalkan
pembayaran yang menunjuk dokumen yang tidak tampil di mana pun — uangnya tetap
keluar, asal-usulnya hilang, dan yang memeriksanya nanti tidak punya apa pun
untuk dibaca. Ini bukan galat yang muncul saat itu juga: ia baru terasa
berbulan-bulan kemudian, saat rekening koran dicocokkan.

Kedua, rekening karyawan diambil lewat rute yang HANYA mengembalikan
rekeningnya. Profil karyawan memuat nama ibu kandung, alamat, dan kontak
darurat — tidak satu pun ada urusannya dengan slip gaji, dan rute yang
mengembalikan seluruh profil membuat layar pembuatan slip membawa semuanya ke
peramban hanya untuk mengisi nomor rekening.
"""

import ast
import os

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTROLLER = os.path.join(AKAR, "controllers", "salary_slip_controller.py")
REPO = os.path.join(AKAR, "repository", "salary_slip_repository.py")
ROUTES = os.path.join(AKAR, "routes", "salary_slip_routes.py")


def _sumber(path: str) -> str:
    return open(path, encoding="utf-8").read()


def _blok(sumber: str, nama: str) -> str:
    i = sumber.index(f"async def {nama}(")
    j = sumber.find("\n    @staticmethod", i)
    return sumber[i:] if j == -1 else sumber[i:j]


# --------------------------------------------------------------------------
# Menghapus
# --------------------------------------------------------------------------


def test_hapus_ditolak_bila_pembayarannya_sudah_ada():
    b = _blok(_sumber(CONTROLLER), "delete")
    assert "punya_pembayaran" in b, "penghapusan tidak memeriksa pembayarannya"
    assert "SALARY_SLIP_HAS_PAYMENT" in b, (
        "penolakannya tanpa kode; layar tidak dapat menyebut sebabnya"
    )


def test_penolakan_tidak_berubah_menjadi_galat_server():
    """
    `except Exception` yang menyeluruh menelan penolakan yang disengaja.

    Tanpa `except HTTPException: raise` di depannya, penolakan 409 di atas
    tertangkap dan berubah menjadi 500 tanpa kode — dan layar menampilkan
    "galat server" untuk penolakan yang sebenarnya punya sebab dan jalan
    keluar.
    """
    b = _blok(_sumber(CONTROLLER), "delete")
    i = b.index("except HTTPException")
    j = b.index("except Exception")
    assert i < j, "HTTPException harus ditangkap SEBELUM Exception"


def test_pembayaran_yang_sudah_dihapus_tidak_menghalangi():
    """
    Yang menahan hanya pembayaran yang MASIH berlaku.

    Pembayaran yang sudah dibatalkan tidak menunjuk apa-apa lagi; membiarkannya
    menahan berarti slip yang keliru terkunci selamanya, dan satu-satunya jalan
    keluarnya lewat basis data.
    """
    b = _blok(_sumber(REPO), "punya_pembayaran")
    assert "isDelete == False" in b


def test_penghapusan_tetap_lunak_dan_tercatat():
    """Jejaknya tidak boleh hilang — slip gaji menyangkut uang orang."""
    b = _blok(_sumber(REPO), "delete_by_id")
    assert '"isDelete": True' in b
    assert "deletedBy" in b and "deletedAt" in b
    assert "AuditLogRepository" in b


# --------------------------------------------------------------------------
# Rekening karyawan
# --------------------------------------------------------------------------


def test_rute_bank_hanya_mengembalikan_rekening():
    """
    Tiga kolom, tidak lebih.

    Diperiksa lewat AST, bukan pencocokan teks: kolom yang ditambahkan belakangan
    bisa ditulis dengan gaya berbeda dan lolos dari pencarian teks.
    """
    b = _blok(_sumber(REPO), "bank_karyawan")
    pohon = ast.parse(b.replace("async def", "def", 1))

    # Yang diperiksa isi `select(...)` saja — `p.employeeID` di klausa WHERE
    # memang harus ada, dan menghitungnya sebagai kolom yang dikembalikan
    # membuat uji ini menuntut kueri yang tidak dapat ditulis.
    dipilih = set()
    for n in ast.walk(pohon):
        if (
            isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id == "select"
        ):
            for arg in n.args:
                if isinstance(arg, ast.Attribute):
                    dipilih.add(arg.attr)

    assert dipilih == {"bankName", "bankAccountName", "bankAccountNumber"}, dipilih


def test_rute_bank_dijaga_izin_slip_gaji_bukan_profil():
    """
    Yang membukanya sedang membuat slip gaji.

    Menuntut `employee_profile:read` berarti sebagian orang yang berhak
    membuat slip tidak dapat mengisi kolom yang ada di layarnya sendiri —
    modul profil punya wilayah divisinya sendiri yang lebih ketat.
    """
    s = _sumber(ROUTES)
    i = s.index('@router.get("/bank/{employee_id}")')
    blok = s[i : i + 600]
    assert 'require("salary_slip", "create")' in blok
    assert "employee_profile" not in blok.split('"""')[0]


def test_rute_bank_didaftarkan_sebelum_rute_berparameter():
    """
    FastAPI mencocokkan berurutan.

    Di bawah `/{salary_slip_id}`, permintaan ke `/bank/7` akan tertangkap
    sebagai id slip bernama "bank" — dan gagalnya berupa galat penguraian
    angka, bukan keterangan bahwa rutenya salah urutan.
    """
    s = _sumber(ROUTES)
    assert s.index('@router.get("/bank/{employee_id}")') < s.index(
        '@router.get("/{salary_slip_id}")'
    )


def test_profil_kosong_bukan_galat():
    """
    Karyawan yang sudah ada sebelum tabel profil dibuat memang belum punya
    profil. Layarnya harus tetap terbuka dengan kolom bank kosong, bukan
    menampilkan pesan galat.
    """
    b = _blok(_sumber(REPO), "bank_karyawan")
    assert "return dict(baris) if baris else None" in b
