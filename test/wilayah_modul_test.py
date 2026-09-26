"""
Setiap modul yang levelnya terjangkau harus punya WILAYAH.

Izin ditentukan tiga hal berurutan: izin khusus per-pengguna, lalu WILAYAH
DIVISI, baru levelnya. Urutan itu yang menjebak — pemeriksaan wilayah berjalan
LEBIH DAHULU, sehingga modul yang tidak tercantum di divisi mana pun akan
ditolak untuk semua orang yang punya divisi, berapa pun levelnya, meski
matriksnya menetapkan akses 1.

Yang menolak tidak menyebutkan sebabnya: pengguna hanya membaca "Anda tidak
memiliki akses", dan yang memeriksa akan melihat matriks yang tampak sudah
benar. Lebih menyesatkan lagi, pengguna TANPA divisi justru lolos — sehingga
gejalanya tampak acak, dan sebagian orang bisa sementara sebagian tidak.

Sudah dua kali terjadi: `audit_log` (dicatat pada komentarnya di `UMUM`) dan
`reminder` — yang membuat siapa pun berdivisi tidak dapat membuat pengingat
agenda sama sekali.
"""

from constants.department_modules import DEPARTMENT_MODULES, UMUM
from constants.permission_matrix import MATRIX

# Batas level yang MELEWATI pemeriksaan wilayah divisi.
#
# Wilayah hanya ditegakkan di bawah level ini; general manager dan pemilik
# berwenang atas seluruh perusahaan. Modul yang seluruh aksinya menuntut level
# segini ke atas karena itu tidak perlu punya wilayah — tidak ada seorang pun
# yang dapat menjangkaunya sekaligus terkena batas wilayahnya.
LEVEL_LEWAT_WILAYAH = 4


def _berwilayah() -> set[str]:
    punya = set(UMUM)
    for modul in DEPARTMENT_MODULES.values():
        punya |= modul
    return punya


def _level_terendah(nilai) -> int | None:
    """
    Level terendah yang benar-benar dipakai modul ini.

    Nol berarti aksinya memang tidak berlaku (mis. `approve` pada modul yang
    tidak punya persetujuan), bukan "boleh untuk semua" — mengikutkannya
    membuat setiap modul tampak terjangkau akses nol.
    """
    dipakai = [int(v) for v in nilai if int(v) > 0]
    return min(dipakai) if dipakai else None


def test_modul_terjangkau_harus_punya_wilayah():
    """
    Modul yang dapat dicapai di bawah level 4 WAJIB ada di suatu wilayah.

    Kalau tidak, matriksnya berbohong: ia menjanjikan akses yang tidak pernah
    diberikan kepada siapa pun yang punya divisi.
    """
    punya = _berwilayah()
    yatim = []
    for modul, nilai in MATRIX.items():
        if modul in punya:
            continue
        terendah = _level_terendah(nilai)
        if terendah is not None and terendah < LEVEL_LEWAT_WILAYAH:
            yatim.append((modul, terendah, nilai))

    assert not yatim, (
        "Modul berikut terjangkau di bawah level "
        f"{LEVEL_LEWAT_WILAYAH} tetapi tidak tercantum di divisi mana pun, "
        "sehingga setiap pengguna yang punya divisi akan ditolak "
        '"Anda tidak memiliki akses":\n'
        + "\n".join(f"  {m} (level terendah {lv}, matriks {n})" for m, lv, n in yatim)
        + "\nTambahkan ke UMUM bila milik semua orang, atau ke divisi yang "
        "memilikinya."
    )


def test_pengingat_milik_semua_orang():
    """
    Pengingat agenda ada di UMUM, bukan di satu divisi.

    Kartu agenda tampil di dashboard SETIAP pengguna, dan matriksnya
    menetapkan buat/ubah/hapus di akses 1. Menaruhnya pada satu divisi berarti
    kartu itu terlihat oleh semua orang tetapi hanya dapat diisi sebagian.
    """
    assert "reminder" in UMUM


def test_batas_pengingat_adalah_kepemilikan_bukan_level():
    """
    Yang menjaga pengingat orang lain adalah kepemilikannya, bukan levelnya.

    Karena itu aman berada di UMUM: empat aksi pertama di akses 1, dan
    membuat pengingat bagi SELURUH pengguna dijaga terpisah di `approve`.
    """
    baca, buat, ubah, hapus, semua_pengguna = MATRIX["reminder"]
    assert (baca, buat, ubah, hapus) == (1, 1, 1, 1)
    assert semua_pengguna >= LEVEL_LEWAT_WILAYAH, (
        "membuat pengingat bagi seluruh pengguna harus tetap dibatasi"
    )


def test_modul_khusus_level_lima_boleh_tanpa_wilayah():
    """
    Kebalikannya tidak boleh ikut dipaksa.

    `user` hanya untuk pemilik, dan level 5 memang melewati pemeriksaan
    wilayah — memaksanya masuk ke suatu divisi justru menyiratkan divisi itu
    berwenang atasnya.
    """
    punya = _berwilayah()
    if "user" in MATRIX and "user" not in punya:
        assert _level_terendah(MATRIX["user"]) >= LEVEL_LEWAT_WILAYAH
