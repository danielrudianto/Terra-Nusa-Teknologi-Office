"""
Keluaran `deploy.sh` harus tetap BERSIH.

Selama berbulan-bulan setiap deploy mencetak delapan blok peringatan usang.
Tidak satu pun merusak apa pun saat itu, dan justru itulah masalahnya:
keluaran yang selalu memuat peringatan yang selalu boleh diabaikan mengajari
pembacanya mengabaikan seluruh keluarannya — termasuk peringatan berikutnya
yang mungkin sungguhan.

Keempat sebabnya sudah dibereskan; uji ini yang menjaga agar tidak merayap
kembali. Yang diperiksa SUMBERNYA, bukan keluaran pytest-nya: peringatan baru
muncul pada saat modulnya diimpor, dan pada saat itu sudah terlambat untuk
menolaknya dengan cara lain.

Perhatikan bahwa dua di antaranya BUKAN sekadar kerapian:

  * `passlib` 1.7.4 mengimpor modul `crypt`, yang SUDAH DIHAPUS pada Python
    3.13 — menaikkan Python akan menjatuhkan aplikasi sejak startup;
  * bawaan `dt.utcnow().date()` dihitung SEKALI saat impor, sehingga
    nilainya membeku pada tanggal server dinyalakan.
"""

import os
import re
from glob import glob

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _berkas_python():
    """Seluruh berkas .py milik aplikasi; `env/` dan uji tidak ikut."""
    for akar, direktori, berkas in os.walk(AKAR):
        direktori[:] = [
            d
            for d in direktori
            if d not in {"env", "__pycache__", ".git", "test", "node_modules"}
        ]
        for b in berkas:
            if b.endswith(".py"):
                yield os.path.join(akar, b)


def _isi(jalur: str) -> str:
    return open(jalur, encoding="utf-8").read()


# ----------------------------------------------------------------------


def test_passlib_tidak_dipakai_dan_tidak_terpasang():
    """
    `passlib` membawa Python 3.13 sebagai bom waktu.

    Ia mengimpor modul `crypt` yang sudah dihapus dari pustaka standar pada
    3.13. Selama paketnya terpasang, menaikkan Python menjatuhkan seluruh
    aplikasi pada saat impor — bukan satu halaman, melainkan sejak startup.

    Dan ia tidak pernah dipakai: penanganan sandi yang sebenarnya memakai
    `bcrypt` langsung di `user_controller` dan `user_repository`. Yang ada
    di `auth_utils` dulu adalah kode mati yang NAMANYA menyesatkan —
    `verify_password()` dan `get_password_hash()` terbaca persis seperti
    jalur sandi sungguhan.
    """
    # Baris KETERANGAN tidak dihitung: `auth_utils` menerangkan panjang-lebar
    # mengapa paket itu dibuang, dan penjelasan itu justru yang menahan orang
    # memasangnya kembali. Menghukumnya berarti menghapus alasannya.
    def menyebut(jalur: str) -> bool:
        for baris in _isi(jalur).split("\n"):
            if baris.lstrip().startswith("#"):
                continue
            if re.search(r"\bpasslib\b", baris):
                return True
        return False

    pemakai = [
        os.path.relpath(p, AKAR) for p in _berkas_python() if menyebut(p)
    ]
    assert not pemakai, (
        f"`passlib` diimpor kembali di {pemakai}; ia akan menjatuhkan "
        "aplikasi pada Python 3.13. Pakai `bcrypt` langsung."
    )

    req = _isi(os.path.join(AKAR, "requirements.txt"))
    assert "passlib" not in req, (
        "`passlib` masih terdaftar di requirements.txt"
    )


def test_tidak_ada_fungsi_sandi_palsu_di_auth_utils():
    """
    Nama yang menyesatkan lebih berbahaya daripada nama yang tidak ada.

    Yang menambah fitur dan memanggil `get_password_hash()` akan memperoleh
    hash bcrypt yang sah — lalu menyimpannya lewat jalur yang tidak pernah
    diuji siapa pun, berdampingan dengan jalur yang sebenarnya.
    """
    s = _isi(os.path.join(AKAR, "utils", "auth_utils.py"))
    for nama in ("def verify_password", "def get_password_hash", "def authenticate_user"):
        assert nama not in s, (
            f"`{nama}` hidup kembali di auth_utils; penanganan sandi ada di "
            "`controllers/user_controller.py`, memakai bcrypt langsung"
        )


def test_skema_memakai_model_config_bukan_class_config():
    """
    `class Config:` adalah bentuk Pydantic v1.

    Masih berjalan di v2 dengan peringatan, dan akan berhenti berjalan di v3.
    Penggantinya `model_config = ConfigDict(...)`.
    """
    pelanggar = []
    for p in sorted(glob(os.path.join(AKAR, "schemas", "*.py"))):
        if re.search(r"^\s+class Config:", _isi(p), re.M):
            pelanggar.append(os.path.basename(p))
    assert not pelanggar, (
        f"`class Config:` gaya Pydantic v1 di {pelanggar}; "
        "pakai `model_config = ConfigDict(...)`"
    )


def test_tidak_ada_bawaan_kolom_yang_dihitung_saat_impor():
    """
    Bawaan kolom harus CALLABLE, bukan nilai yang sudah dihitung.

    `default=dt.utcnow().date()` dijalankan sekali saat modulnya diimpor,
    sehingga nilainya membeku pada tanggal server dinyalakan — bukan tanggal
    dokumennya dibuat. Layanan yang hidup tiga bulan memberi bawaan yang sama
    kepada seluruh dokumen selama tiga bulan itu.

    Bentuk yang benar `default=lambda: ...` atau `default=dt.now` (tanpa
    tanda kurung).
    """
    pelanggar = []
    for p in sorted(glob(os.path.join(AKAR, "models", "*.py"))):
        for n, baris in enumerate(_isi(p).split("\n"), 1):
            if baris.lstrip().startswith("#"):
                continue
            # `default=` yang diikuti PEMANGGILAN fungsi waktu.
            #
            # `server_default=func.now()` SENGAJA tidak dihitung: itu bawaan
            # sisi-BASIS DATA, dihitung MySQL untuk setiap baris — bukan
            # sekali saat impor. Bentuk itu justru yang paling benar di repo
            # ini, karena pustaka `databases` menjalankan kueri terkompilasi
            # dan mengabaikan bawaan sisi-Python sama sekali.
            if re.search(
                r"(?<!server_)default\s*=\s*(?!lambda)[\w.]*\b"
                r"(now|utcnow|today)\s*\(\s*\)",
                baris,
            ):
                pelanggar.append(f"{os.path.basename(p)}:{n}")
    assert not pelanggar, (
        f"bawaan kolom dihitung saat impor di {pelanggar}; "
        "nilainya akan membeku pada tanggal server dinyalakan"
    )


def test_tidak_ada_utcnow_yang_sudah_usang():
    """`datetime.utcnow()` mengembalikan waktu tanpa zona dan akan dihapus."""
    pelanggar = []
    for p in _berkas_python():
        for n, baris in enumerate(_isi(p).split("\n"), 1):
            if baris.lstrip().startswith("#"):
                continue
            if re.search(r"\butcnow\s*\(\s*\)", baris):
                pelanggar.append(f"{os.path.relpath(p, AKAR)}:{n}")
    assert not pelanggar, f"`utcnow()` yang sudah usang di {pelanggar}"


def test_kunci_uji_sepanjang_yang_dituntut_produksi():
    """
    Kunci uji harus 32 bita atau lebih, sama seperti produksi.

    PyJWT memperingatkan kunci HMAC di bawah 32 bita pada SETIAP deploy.
    Peringatan itu menyangkut kunci uji, bukan `SECRET_KEY` produksi —
    tetapi selama ia muncul, ia tidak dapat dibedakan dari peringatan yang
    menyangkut kunci sungguhan.

    Disamakan panjangnya, BUKAN dibungkam: bila suatu saat kunci produksi
    yang terbaca di sini, peringatannya akan muncul kembali, dan memang
    harus.
    """
    s = _isi(os.path.join(AKAR, "test", "conftest.py"))
    m = re.search(
        r'setdefault\(\s*\n?\s*"SECRET_KEY",\s*\n?\s*"([^"]*)"', s
    )
    assert m, "kunci uji tidak ditemukan di conftest"
    assert len(m.group(1).encode()) >= 32, (
        f"kunci uji hanya {len(m.group(1).encode())} bita; "
        "PyJWT akan memperingatkannya pada setiap deploy"
    )
