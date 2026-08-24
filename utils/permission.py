import time
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import select

from constants.permission_matrix import (
    NOT_APPLICABLE,
    SPECIAL_ONLY,
    required_level,
)
from constants.department_modules import modules_for, read_only_for
from models.user_department_model import user_departments_table
from models.user_permission_model import user_permissions_table
from utils.auth_utils import get_current_user
from utils.database import database
from utils.logger_utils import log_error

"""
Pemeriksa izin.

Urutan penentuan:

    1. Izin khusus pengguna (bila ada) -> nilainya menang, izin maupun larangan
    2. Modul harus berada dalam wilayah departemen pengguna
    3. Level pengguna dibanding level minimum modul

Level dan departemen menjawab hal berbeda: level menentukan sejauh apa yang
boleh dilakukan, departemen menentukan modul mana yang menjadi urusannya.
Tanpa sumbu departemen, level 1 procurement dan level 1 accounting terpaksa
melihat hal yang sama padahal pekerjaannya berbeda.

Menyembunyikan tombol di layar bukan pengamanan; pemeriksaan di sinilah yang
menentukan. Setiap rute yang mengubah data harus melewatinya.
"""

# Izin khusus jarang berubah, sementara satu layar bisa memicu banyak
# permintaan. Hasilnya disimpan sebentar agar tidak menambah satu query pada
# setiap permintaan.
_CACHE: dict[int, tuple[float, dict[tuple[str, str], bool]]] = {}
_DEPT_CACHE: dict[int, tuple[float, set[str]]] = {}
_CACHE_TTL = 60.0

#: Modul yang batas divisinya berlaku untuk SEMUA level di bawah 5, termasuk
#: yang tidak punya departemen. Isinya data paling sensitif di sistem.
MODUL_WILAYAH_MUTLAK = frozenset(
    {
        "salary_slip",
        "employees",
        "employee_profile",
        "employee_form",
        # Ujian rekrutmen.
        #
        # Jawabannya menentukan seseorang diterima atau tidak, dan berkas
        # yang diunggah memuat karya yang belum tentu ingin dilihat orang
        # lain. Sama seperti gaji: tidak boleh terbuka hanya karena levelnya
        # tinggi.
        "hr_recruitment",
    }
)


def invalidate_permission_cache(user_id: int | None = None) -> None:
    """
    Dipanggil setelah izin diubah agar perubahannya langsung berlaku dan tidak
    menunggu masa simpan habis.
    """
    if user_id is None:
        _CACHE.clear()
        _DEPT_CACHE.clear()
    else:
        _CACHE.pop(user_id, None)
        _DEPT_CACHE.pop(user_id, None)


async def _overrides(user_id: int) -> dict[tuple[str, str], bool]:
    cached = _CACHE.get(user_id)
    if cached and (time.monotonic() - cached[0]) < _CACHE_TTL:
        return cached[1]

    try:
        rows = await database.fetch_all(
            select(user_permissions_table).where(
                user_permissions_table.c.userID == user_id
            )
        )
        data = {(r["module"], r["action"]): bool(r["allowed"]) for r in rows}
    except Exception as e:
        # Bila tabel izin tidak terbaca, jangan menganggap semuanya boleh:
        # kembalikan kosong sehingga penentuan jatuh ke level pengguna.
        log_error(f"Izin khusus tidak dapat dibaca: {str(e)}")
        return {}

    _CACHE[user_id] = (time.monotonic(), data)
    return data


async def _departments(user_id: int) -> set[str]:
    cached = _DEPT_CACHE.get(user_id)
    if cached and (time.monotonic() - cached[0]) < _CACHE_TTL:
        return cached[1]

    try:
        rows = await database.fetch_all(
            select(user_departments_table).where(
                user_departments_table.c.userID == user_id
            )
        )
        data = {r["department"] for r in rows}
    except Exception as e:
        # Tabel belum ada atau tidak terbaca. Dikembalikan kosong, yang
        # artinya penentuan jatuh sepenuhnya ke level — perilaku sebelum
        # departemen diperkenalkan.
        log_error(f"Departemen pengguna tidak dapat dibaca: {str(e)}")
        return set()

    _DEPT_CACHE[user_id] = (time.monotonic(), data)
    return data


async def is_allowed(user, module: str, action: str) -> bool:
    """Apakah pengguna boleh melakukan aksi ini pada modul tersebut."""
    if user is None:
        return False

    user_id = user["id"]
    level = user["authenticationLevel"] or 1

    override = (await _overrides(user_id)).get((module, action))
    if override is not None:
        return override

    """
    Batas wilayah departemen.

    Level 5 tidak dibatasi: superadmin memang perlu melihat seluruh sistem.

    Level 4 juga tidak dibatasi. Jabatannya General Manager — wilayahnya
    seluruh perusahaan, bukan satu divisi, sehingga ia sengaja tidak diberi
    departemen. Ditulis sebagai `level < 4` agar aturannya tetap berlaku
    walaupun kelak ada level 4 yang kebetulan diberi departemen.

    Pengguna yang BELUM punya departemen sama sekali juga tidak dibatasi,
    sehingga penambahan tabel ini tidak mengunci siapa pun sebelum datanya
    diisi. Begitu seseorang diberi departemen, batas ini langsung berlaku
    baginya.
    """
    departments = await _departments(user_id)
    if level < 4 and departments and module not in modules_for(departments):
        return False

    """
    Modul yang bagi divisinya hanya boleh DIBACA.

    Satu modul dapat menjadi urusan dua divisi dengan kedalaman berbeda. Aset
    demikian: procurement perlu mengetahui perusahaan punya alat apa saja
    sebelum memutuskan menyewa atau membeli, sedangkan yang mencatat
    perolehan, menghitung penyusutan, dan menyesuaikan nilainya saat dilepas
    adalah accounting — dan angka itu masuk ke pembukuan.

    Peta wilayah tidak dapat menyatakan perbedaan ini; ia hanya mengenal
    "urusannya" atau "bukan urusannya". Daftarnya karena itu ada di
    `DEPARTMENT_READ_ONLY`.

    Diperiksa SESUDAH izin khusus, sehingga satu orang procurement yang memang
    perlu mencatat tetap dapat diberi haknya tanpa mengubah kebijakan bagi
    seluruh divisinya.
    """
    if (
        level < 4
        and departments
        and action != "read"
        and module in read_only_for(departments)
    ):
        return False

    """
    Modul yang batas divisinya BERLAKU MUTLAK.

    Slip gaji dan data karyawan hanya wilayah HRD dan FAT, dan itu tidak
    boleh terlewati hanya karena levelnya tinggi atau karena departemennya
    belum diisi. Tanpa penjagaan ini, seorang General Manager membaca gaji
    seluruh karyawan tanpa seorang pun pernah memutuskan bahwa ia boleh —
    dan daftar aktivitas sudah lebih dulu ditutup untuk level 4 justru
    supaya tidak menjadi pintu belakang ke angka yang sama.

    Bila kelak memang perlu, memberikannya cukup dengan memasukkan orangnya
    ke divisi HRD atau memberi izin khusus. Bedanya: cara itu meninggalkan
    keputusan yang tercatat, bukan akses yang diam-diam ada.
    """
    if level < 5 and module in MODUL_WILAYAH_MUTLAK:
        if not departments or module not in modules_for(departments):
            return False

    minimum = required_level(module, action)
    if minimum in (NOT_APPLICABLE, SPECIAL_ONLY):
        # Aksi yang tidak berlaku, atau yang sengaja hanya lewat izin khusus
        # (mis. slip gaji) — tidak pernah terbuka lewat level.
        return False

    return level >= minimum


def require(module: str, action: str):
    """
    Dependency FastAPI.

    Mengembalikan objek pengguna yang sama seperti `get_current_user`, sehingga
    isi rute tidak perlu diubah — cukup menukar isi `Depends`.

        async def approve(id: int, current_user = Depends(require("expenses", "approve"))):
    """

    async def _cek(current_user: Annotated[dict, Depends(get_current_user)]):
        if not await is_allowed(current_user, module, action):
            raise HTTPException(
                status_code=403,
                detail="Anda tidak memiliki akses untuk tindakan ini.",
            )
        return current_user

    return _cek

#: Level yang DIKECUALIKAN dari larangan menyetujui dokumen sendiri.
#
# General manager (4) dan pemilik (5). Keduanya memang berwenang atas seluruh
# dokumen, dan pada perusahaan sebesar ini kerap merekalah satu-satunya yang
# hadir untuk menyetujui — melarangnya berarti dokumen tertahan tanpa ada
# orang lain yang berwenang.
#
# Pengecualian ini BUKAN berarti tanpa catatan: persetujuan atas dokumen
# sendiri tetap tercatat pada jejak aktivitas, sehingga dapat ditelusuri.
# Dinaikkan ke 5 atas keputusan pemilik.
#
# Level 4 memang berwenang atas seluruh dokumen, tetapi menyetujui yang
# dibuatnya sendiri menghapus satu-satunya pemeriksaan yang tersisa: tidak ada
# mata kedua sama sekali pada dokumen itu, dari dibuat sampai terbit.
#
# Pemilik dikecualikan karena pada akhirnya ialah yang menanggung akibatnya —
# dan kerap ialah satu-satunya yang hadir.
LEVEL_BOLEH_SETUJU_SENDIRI = 5


# Pemeriksaan dokumen — tahap sebelum persetujuan.
#
# Dokumen melewati dua tangan: diperiksa dulu, baru disetujui. Pemeriksa
# membaca isinya — harga, volume, spesifikasi; penyetuju memutuskan dokumen
# itu boleh terbit.
LEVEL_PEMERIKSA = 3
DIVISI_PEMERIKSA = frozenset({"procurement"})

# Level yang boleh memeriksa tanpa memandang divisi.
#
# Keduanya berwenang atas seluruh dokumen, dan kerap merekalah satu-satunya
# yang hadir — memaksa mereka lewat divisi hanya menghentikan pekerjaan tanpa
# menambah satu pun pemeriksaan.
LEVEL_PEMERIKSA_BEBAS = 4


def boleh_memeriksa(level, departments=None) -> bool:
    """
    Pengguna ini boleh MEMERIKSA purchase order.

    Level 3 harus berada di divisi procurement — merekalah yang mengetahui
    harga wajar dan spesifikasi yang dipesan. Level 4 ke atas boleh tanpa
    memandang divisi.
    """
    try:
        lv = int(level or 1)
    except (TypeError, ValueError):
        return False

    if lv >= LEVEL_PEMERIKSA_BEBAS:
        return True
    if lv < LEVEL_PEMERIKSA:
        return False
    return bool(set(departments or ()) & DIVISI_PEMERIKSA)


# Mengubah purchase order.
#
# Level 4 ke atas boleh selalu (selama dokumennya belum disetujui). Pembuatnya
# juga boleh: yang salah ketik biasanya yang mengisi, dan memaksanya meminta
# tolong orang lain membuat orang menghindari koreksi.
#
# Level 3 — manajer — ada di antaranya, dan di situlah masalahnya selama ini.
# Pemeriksa menemukan harga yang keliru, memberi tahu manajernya, dan manajer
# itu tidak dapat membetulkannya sama sekali: dokumennya bukan buatannya.
# Yang tersisa hanya menunggu pembuatnya hadir.
LEVEL_UBAH_SEBELUM_DIPERIKSA = 3

# Level yang boleh mengubah tanpa memandang sudah diperiksa atau belum.
LEVEL_UBAH_BEBAS = 4


def boleh_mengubah_purchase_order(
    level, adalah_pembuat: bool = False, sudah_diperiksa: bool = False
) -> bool:
    """
    Pengguna ini boleh MENGUBAH isi purchase order.

    Berlaku hanya untuk dokumen yang belum disetujui; yang sudah disetujui
    ditolak lebih dulu di repository, apa pun levelnya, dan jalurnya adendum.

    Batas level 3 bergantung pada PEMERIKSAAN, bukan pada persetujuan:

      - Belum diperiksa — belum ada yang menjaminkan namanya atas isinya,
        sehingga membetulkannya tidak menyalahi apa pun. Manajer boleh.

      - Sudah diperiksa — seseorang sudah membaca harga dan volumenya lalu
        menyatakan benar. Menyuntingnya MENCABUT pemeriksaan itu diam-diam
        (lihat `PurchaseOrderRepository.update`), dan pencabutan yang tidak
        disadari membuat dokumen kembali ke antrean tanpa ada yang tahu
        mengapa. Untuk itu diperlukan level 4, atau pemeriksaannya dicabut
        lebih dulu secara terang-terangan.

    Pembuatnya sendiri tetap boleh pada keduanya — haknya tidak dikurangi
    aturan ini.
    """
    try:
        lv = int(level or 1)
    except (TypeError, ValueError):
        return False

    if lv >= LEVEL_UBAH_BEBAS:
        return True
    if adalah_pembuat:
        return True
    return lv >= LEVEL_UBAH_SEBELUM_DIPERIKSA and not sudah_diperiksa


# Mencabut pemeriksaan.
#
# Level yang boleh mencabut pemeriksaan SIAPA PUN. Di bawahnya, hanya
# pemeriksanya sendiri yang boleh menarik kembali pernyataannya.
LEVEL_CABUT_BEBAS = 4


def boleh_mencabut_pemeriksaan(level, adalah_pemeriksa: bool = False) -> bool:
    """
    Pengguna ini boleh MENCABUT pemeriksaan sebuah purchase order.

    Aturannya sengaja TIDAK sama dengan aturan memeriksa, dan itu bukan
    kelalaian.

    Memberi centang adalah menyatakan "saya sudah membaca isinya dan isinya
    benar" — pernyataan atas nama sendiri, dan setiap pemeriksa berhak
    membuatnya. MENCABUT centang orang lain adalah hal yang berbeda: ia
    menghapus pernyataan orang lain, dan di sistem ini ia sekaligus
    MENGGUGURKAN PERSETUJUAN yang terlanjur terbit — dokumennya kembali
    menjadi draft (lihat `PurchaseOrderRepository.set_checked`).

    Artinya satu klik dari siapa pun yang berizin `purchase_order:update`
    dapat membatalkan tanda tangan seorang direktur, tanpa dokumen itu
    berubah satu huruf pun. Yang menandatanganinya tidak diberi tahu, dan
    dari layar mana pun tidak tampak apa yang terjadi — yang tersisa hanya
    dokumen yang tiba-tiba kembali ke antrean.

    Karena itu:

      - Pemeriksanya sendiri boleh. Ia menarik pernyataannya sendiri, dan
        orang yang menemukan kekeliruan sesudah mencentang harus punya jalan
        untuk membetulkannya — kalau tidak, ia akan diam saja.

      - Level 4 ke atas boleh atas siapa pun. Merekalah yang menanggung
        akibat dokumen yang beredar, dan kerap merekalah satu-satunya yang
        hadir ketika pemeriksanya cuti.

      - Selain keduanya, tidak.

    Dokumen yang MEMANG BELUM diperiksa tidak melewati aturan ini sama
    sekali: mencabut sesuatu yang tidak ada bukan pencabutan, dan menolaknya
    hanya menghasilkan galat pada tombol yang tidak melakukan apa-apa.
    """
    if adalah_pemeriksa:
        return True
    try:
        return int(level or 1) >= LEVEL_CABUT_BEBAS
    except (TypeError, ValueError):
        return False


def boleh_memeriksa_sendiri(level) -> bool:
    """
    Pengguna ini boleh memeriksa dokumen yang dibuatnya sendiri.

    Tidak ada seorang pun — termasuk pemilik. Pemeriksaan justru ADA untuk
    menghadirkan mata kedua; membiarkan pembuatnya memeriksa sendiri membuat
    tahap ini hanya menambah satu klik tanpa menambah apa pun.
    """
    return False


# Mengubah bukti potong PPh yang SUDAH terisi.
#
# Mengisi PERTAMA kali bebas dilakukan bagian keuangan seperti biasa. Tetapi
# MENGUBAH yang sudah terisi berbeda: nomor bukti potong yang tertukar antar
# invoice (kerap karena nominalnya sama) baru ketahuan belakangan, dan
# menimpanya menyentuh dokumen pajak yang sudah dicatat. Karena itu koreksinya
# dibatasi pada level 5 — satu tangan yang bertanggung jawab, bukan siapa pun
# yang kebetulan membuka layarnya.
LEVEL_EDIT_BUKTI_POTONG = 5


def boleh_edit_bukti_potong(level) -> bool:
    """Pengguna ini boleh MENGUBAH bukti potong PPh yang sudah terisi."""
    try:
        return int(level or 1) >= LEVEL_EDIT_BUKTI_POTONG
    except (TypeError, ValueError):
        return False


def boleh_menghapus_yang_disetujui(level) -> bool:
    """
    Pengguna ini boleh MENGHAPUS purchase order yang SUDAH DISETUJUI.

    Hanya pemilik.

    Dokumen yang belum disetujui bebas dihapus siapa pun yang berhak
    menghapus — ia belum terbit dan belum dipegang siapa pun di luar kantor.
    Yang sudah disetujui berbeda: lembarnya sudah dicetak dan ada di tangan
    vendor, dan menghapusnya membuat lembar itu tidak punya padanan sama
    sekali di sistem. Jalan yang biasa ADENDUM.

    Tetapi kadang dokumen memang keliru sejak awal dan harus benar-benar
    hilang. Yang memutuskan itu pemiliknya — bukan karena ia lebih teliti,
    melainkan karena ialah yang menanggung akibatnya bila lembar yang
    beredar ternyata masih dipakai.
    """
    try:
        return int(level or 1) >= LEVEL_BOLEH_SETUJU_SENDIRI
    except (TypeError, ValueError):
        return False


def boleh_menyetujui_yang_diperiksanya(level) -> bool:
    """
    Pengguna ini boleh MENYETUJUI dokumen yang DIPERIKSANYA sendiri.

    Hanya pemilik.

    Pemeriksaan dan persetujuan dipisah menjadi dua tangan dengan sengaja:
    pemeriksa membaca isinya — harga, volume, spesifikasi — dan penyetuju
    memutuskan dokumen itu boleh terbit. Satu orang yang mengerjakan
    keduanya berturut-turut mengembalikan keduanya menjadi satu tangan, dan
    tahap pemeriksaan tinggal menjadi satu klik tambahan.

    Yang membuatnya sulit terlihat: dari kursi penggunanya tidak terasa
    seperti melanggar apa pun. Ia menekan "Periksa", menu itu langsung
    berganti menampilkan "Setujui", dan ia menekannya. Dua tahap, satu
    orang, dua detik.

    Dua penjagaan yang sudah ada tidak menangkapnya, dan keduanya karena
    sebab yang sama: `set_checked` melarang PEMBUAT memeriksa, dan
    `update_status` melarang PEMBUAT menyetujui. Keduanya membandingkan
    dengan pembuat dokumen — sehingga pemeriksa yang bukan pembuat lolos
    dari keduanya.

    Pemilik dikecualikan dengan alasan yang sama seperti pada persetujuan
    dokumen buatannya sendiri: pada akhirnya ialah yang menanggung
    akibatnya, dan kerap ialah satu-satunya yang hadir. Pengecualiannya
    tetap tercatat pada jejak aktivitas.
    """
    try:
        return int(level or 1) >= LEVEL_BOLEH_SETUJU_SENDIRI
    except (TypeError, ValueError):
        return False


def boleh_menyetujui_sendiri(level) -> bool:
    """
    Pengguna ini boleh menyetujui dokumen yang dibuatnya sendiri.

    Ditulis sekali di sini, bukan diulang di tiap controller: ambangnya
    pernah berbeda antar modul, dan yang tertinggal saat aturannya berubah
    tidak menimbulkan galat — hanya satu modul yang diam-diam lebih longgar.
    """
    try:
        return int(level or 1) >= LEVEL_BOLEH_SETUJU_SENDIRI
    except (TypeError, ValueError):
        return False
