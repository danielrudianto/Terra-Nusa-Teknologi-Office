"""
Rencana pengeluaran.

Kalender sudah menampilkan pembayaran yang SUDAH terjadi; yang belum ada
adalah yang AKAN terjadi — dan itu yang menentukan apakah kasnya cukup.

Yang dijaga di sini adalah keadaan-keadaan yang membuat perbandingan antara
rencana dan kenyataan tidak lagi dapat dipercaya.
"""

import os
import re

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CTRL = os.path.join(AKAR, 'controllers', 'payment_plan_controller.py')
REPO = os.path.join(AKAR, 'repository', 'payment_plan_repository.py')
RUTE = os.path.join(AKAR, 'routes', 'payment_plan_routes.py')


def _blok(berkas: str, nama: str) -> str:
    s = open(berkas).read()
    m = re.search(
        rf'\n    async def {nama}\([\s\S]*?'
        r'(?=\n    @staticmethod|\n    async def |\Z)', s)
    assert m, nama
    return m.group(0)


def test_terpakai_tidak_dapat_diubah_nilainya():
    """
    Ia sudah dipakai membandingkan rencana dengan kenyataan; mengubahnya
    membuat selisihnya menyusut sendiri, dan yang meninjau menyimpulkan
    perencanaannya lebih tepat daripada yang sebenarnya.
    """
    b = _blok(CTRL, 'ubah')
    assert 'terpakai' in b and 'hanya_status' in b


def test_terpakai_dibatalkan_bukan_dihapus():
    """
    Selisih antara yang direncanakan dan yang terjadi menjelaskan mengapa
    kasnya meleset; itu hilang bila barisnya lenyap.
    """
    b = _blok(CTRL, 'hapus')
    assert 'terpakai' in b


def test_yang_batal_dikecualikan_dari_perhitungan():
    """
    Memasukkannya membuat angka yang ditampilkan lebih besar daripada yang
    benar-benar akan keluar.
    """
    b = _blok(REPO, 'rentang')
    assert "status != \"batal\"" in b or "!= 'batal'" in b


def test_ringkasan_hanya_yang_masih_rencana():
    b = _blok(REPO, 'ringkasan')
    assert '"rencana"' in b


def test_rentang_wajib_pada_rute():
    """
    Tanpa batas, kalender yang membuka bulan mana pun menarik seluruh riwayat
    perencanaan — dan itu tumbuh terus tanpa pernah menyusut.
    """
    s = open(RUTE).read()
    m = re.search(r'@router\.get\("/"\)[\s\S]{0,700}', s)
    assert 'awal: date = Query(...)' in m.group(0)
    assert 'akhir: date = Query(...)' in m.group(0)


def test_hapus_lunak_bukan_keras():
    b = _blok(REPO, 'hapus')
    assert 'isDelete=True' in b
    assert 'delete()' not in b


def test_terdaftar_di_matriks_izin():
    s = open(os.path.join(AKAR, 'constants', 'permission_matrix.py')).read()
    assert '"payment_plan":' in s


def test_masuk_wilayah_fat():
    """Perencanaan kas adalah pekerjaan FAT."""
    s = open(os.path.join(AKAR, 'constants', 'department_modules.py')).read()
    m = re.search(r'"fat": UMUM[\s\S]*?\n    \}', s)
    assert '"payment_plan"' in m.group(0)


# ---------------------------------------------------------------------------
# Arah kas dan rencana yang terlewat
# ---------------------------------------------------------------------------


def test_arah_kas_masuk_dan_keluar():
    """
    Satu tabel untuk keduanya: bidangnya persis sama, dan yang dilihat orang
    justru SELISIHNYA.
    """
    s = open(os.path.join(AKAR, 'models', 'payment_plan_model.py')).read()
    assert '"planType"' in s
    b = _blok(REPO, 'ringkasan')
    assert '"masuk"' in b and '"keluar"' in b and '"selisih"' in b


def test_yang_lewat_tidak_dihitung():
    """
    Rencana yang tanggalnya terlewat tanpa pernah ditandai terpakai praktis
    tidak terjadi — membiarkannya ikut membuat posisi kas menunjukkan uang
    yang tidak akan bergerak ke mana pun.
    """
    b = _blok(REPO, 'ringkasan')
    assert 'date.today()' in b
    assert 'batas' in b


def test_yang_lewat_tidak_dihapus():
    """
    Selisih antara yang direncanakan dan yang terjadi menjelaskan mengapa
    kasnya meleset; itu hilang bila barisnya lenyap. Ia hanya berhenti
    dihitung.
    """
    b = _blok(REPO, 'ringkasan')
    # Ringkasan hanya MEMBACA; ia tidak boleh menghapus apa pun.
    #
    # `isDelete` sengaja tidak dicari sebagai kata "delete" — kolom itu memang
    # disebut pada penyaringnya, dan mencarinya membuat uji ini gagal terhadap
    # kode yang benar.
    assert 'payment_plans_table.delete()' not in b
    assert 'update(' not in b
    # Dan tetap dikembalikan pada daftar, dengan penanda.
    assert '"lewat"' in _blok(REPO, 'rentang')


def test_batas_tidak_memotong_rentang_masa_depan():
    """
    Bila rentang yang diminta seluruhnya di masa depan, batasnya tetap awal
    rentang — bukan hari ini, yang akan menarik baris di luar yang diminta.
    """
    b = _blok(REPO, 'ringkasan')
    assert 'awal if awal > hari_ini else hari_ini' in b


# ---------------------------------------------------------------------------
# Kategori mengikuti arah kasnya
# ---------------------------------------------------------------------------


def test_kategori_keluar_dan_masuk_berbeda():
    """
    Uang masuk tidak dibelanjakan untuk material atau gaji — ia DATANG dari
    tagihan proyek, uang muka, atau retensi. Satu daftar untuk keduanya
    membuat layar menawarkan "gaji" sebagai sumber pemasukan.
    """
    from schemas.payment_plan_schema import KATEGORI_KELUAR, KATEGORI_MASUK
    assert 'gaji' in KATEGORI_KELUAR and 'gaji' not in KATEGORI_MASUK
    assert 'tagihan' in KATEGORI_MASUK and 'tagihan' not in KATEGORI_KELUAR


def test_kategori_salah_arah_ditolak():
    """
    Diperiksa di SERVER: muatan permintaan dapat disusun sendiri, dan kategori
    yang tidak cocok membuat ringkasan menampilkan hal yang mustahil.
    """
    from datetime import date as _d

    import pytest

    from schemas.payment_plan_schema import PaymentPlanCreate

    # Yang cocok diterima.
    PaymentPlanCreate(
        planType='masuk', date=_d(2026, 9, 1), amount=1000,
        description='uji', category='tagihan',
    )

    # Yang tidak cocok ditolak.
    with pytest.raises(Exception):
        PaymentPlanCreate(
            planType='masuk', date=_d(2026, 9, 1), amount=1000,
            description='uji', category='gaji',
        )
    with pytest.raises(Exception):
        PaymentPlanCreate(
            planType='keluar', date=_d(2026, 9, 1), amount=1000,
            description='uji', category='tagihan',
        )


def test_kategori_boleh_kosong():
    """Sebagian rencana memang belum jelas kelompoknya saat dicatat."""
    from datetime import date as _d

    from schemas.payment_plan_schema import PaymentPlanCreate

    PaymentPlanCreate(
        planType='masuk', date=_d(2026, 9, 1), amount=1000,
        description='uji', category=None,
    )
