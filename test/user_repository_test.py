"""
Pengujian repository pengguna.

Dua fungsi di berkas ini pernah rusak dengan cara yang sama: blok pencatatan
jejak disalin dari `update_user` beserta variabelnya, padahal variabel itu
tidak ada di fungsi tujuannya. Akibatnya membuat dan menghapus pengguna
selalu gagal — dan galatnya hanya muncul saat dijalankan, bukan saat kode
diperiksa.

Pengujian ini menjalankan keduanya sungguhan terhadap basis data tiruan,
sehingga kekeliruan seperti itu ketahuan tanpa perlu mencobanya di aplikasi.
"""

import pytest

from repository.user_repository import UserRepository


@pytest.fixture
def db(fake_db):
    return fake_db("repository.user_repository", "repository.audit_log_repository")


@pytest.mark.asyncio
async def test_membuat_pengguna_mengembalikan_barisnya(db):
    """
    Yang dikembalikan harus baris utuh, bukan sekadar id.

    Rutenya memakai `UserResponse` sebagai response_model, dan sebuah angka
    tidak dapat dipetakan ke sana.
    """
    db.queue("execute", 7)  # id hasil insert
    db.queue("fetch_one", {"id": 7, "name": "Ade", "email": "ade@akn.id"})

    hasil = await UserRepository.create_user(
        {"name": "Ade", "email": "ade@akn.id", "password": "rahasia"}
    )

    assert isinstance(hasil, dict)
    assert hasil["id"] == 7
    assert hasil["name"] == "Ade"


@pytest.mark.asyncio
async def test_membuat_pengguna_tidak_mencatat_kata_sandi(db):
    """Jejak aktivitas tidak boleh memuat kata sandi, walau sudah teracak."""
    db.queue("execute", 7)
    db.queue("fetch_one", {"id": 7, "name": "Ade"})

    await UserRepository.create_user(
        {"name": "Ade", "email": "ade@akn.id", "password": "rahasia"}
    )

    jejak = " ".join(str(q) for _, q in db.calls)
    assert "rahasia" not in jejak


@pytest.mark.asyncio
async def test_membuat_pengguna_tetap_berhasil_bila_baris_tak_terbaca(db):
    """Bila pembacaan ulang gagal, id-nya tetap dikembalikan."""
    db.queue("execute", 7)
    db.queue("fetch_one", None)

    hasil = await UserRepository.create_user({"name": "Ade"})

    assert hasil == {"id": 7}


@pytest.mark.asyncio
async def test_menghapus_pengguna_menandai_bukan_membuang(db):
    """
    Penghapusan bersifat menandai, bukan membuang barisnya.

    Pengguna yang dihapus masih dirujuk oleh dokumen lama sebagai pembuat;
    membuang barisnya memutus rujukan itu.
    """
    db.queue("fetch_one", {"id": 7, "name": "Ade", "isDeleted": False})
    db.queue("execute", 1)

    hasil = await UserRepository.soft_delete(7)

    assert "message" in hasil
    perintah = " ".join(str(q).lower() for _, q in db.calls)
    assert "update" in perintah
    assert "delete from" not in perintah


@pytest.mark.asyncio
async def test_menghapus_pengguna_membaca_keadaan_sebelumnya(db):
    """
    Keadaan sebelum harus dibaca lebih dulu.

    Setelah ditandai terhapus, nilai lamanya tidak bisa direkam lagi — dan
    jejak tanpa nilai sebelum tidak menjelaskan apa yang berubah.
    """
    db.queue("fetch_one", {"id": 7, "name": "Ade", "isDeleted": False})
    db.queue("execute", 1)

    await UserRepository.soft_delete(7)

    # Kueri pertama membaca, baru kemudian memperbarui.
    assert len(db.calls) >= 2
    assert db.calls[0][0] == "fetch_one"
