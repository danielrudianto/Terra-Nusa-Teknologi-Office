"""
TANDA TANGAN PENGGUNA — penyimpanan, pemeriksaan isi, dan batas aksesnya.

Yang dijaga di sini, berurutan dari yang paling berbahaya:

  1. TIDAK ADA endpoint yang mengembalikan tanda tangan ORANG LAIN. Gambar
     tanda tangan adalah stempel; sekali sampai di peramban seseorang ia
     dapat ditempelkan ke dokumen apa pun di luar sistem ini. Ini satu-
     satunya penjagaan yang, bila hilang, tidak menimbulkan gejala apa pun —
     fiturnya tetap bekerja, hanya saja tanda tangan direktur ikut terkirim
     ke setiap layar yang memintanya.

  2. Yang disimpan benar-benar PNG. Awalan `data:image/png` ditulis
     pengirim, jadi ia keterangan, bukan bukti.

  3. Ada batas ukuran — berkas dan piksel.

  4. Menyimpan dua kali MENGGANTI, bukan menumpuk. Kunci unik pada `userID`
     membuat cara "periksa dulu lalu sisip" gagal dengan galat mentah saat
     dua perangkat menyimpan bersamaan.

  5. `punya()` tidak menarik kolom gambarnya. Layar menanyakannya pada
     setiap login; menjawabnya dengan blob berarti mengirim puluhan kilobita
     untuk menghasilkan satu kata.
"""

import base64
import re
import struct
import zlib
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

import repository.user_signature_repository as usr
from controllers.user_signature_controller import (
    BATAS_BITA,
    UserSignatureController,
)
from repository.user_signature_repository import UserSignatureRepository

AKAR = Path(__file__).resolve().parents[1]


def png(lebar: int = 720, tinggi: int = 240) -> bytes:
    """PNG sah sekecil mungkin, berukuran yang diminta."""

    def bongkah(jenis: bytes, isi: bytes) -> bytes:
        return (
            struct.pack(">I", len(isi))
            + jenis
            + isi
            + struct.pack(">I", zlib.crc32(jenis + isi) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", lebar, tinggi, 8, 6, 0, 0, 0)
    baris = b"\x00" + b"\x00\x00\x00\x00" * lebar
    idat = zlib.compress(baris * tinggi)
    return (
        b"\x89PNG\r\n\x1a\n"
        + bongkah(b"IHDR", ihdr)
        + bongkah(b"IDAT", idat)
        + bongkah(b"IEND", b"")
    )


def uri(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


# ---------------------------------------------------------------------------
# 1. Batas akses — dijaga pada BERKAS RUTENYA
# ---------------------------------------------------------------------------


def test_tidak_ada_rute_yang_membaca_tanda_tangan_orang_lain():
    """
    Tidak boleh ada rute berparameter id pada berkas ini.

    Diperiksa sebagai teks, bukan lewat permintaan HTTP, karena yang dijaga
    adalah KETIADAAN sesuatu — dan yang tidak ada tidak dapat dipanggil untuk
    diuji. Satu `@router.get("/{user_id}")` yang ditambahkan kelak akan
    langsung tertangkap di sini.
    """
    isi = (AKAR / "routes" / "user_signature_routes.py").read_text(encoding="utf-8")
    berparameter = re.findall(r'@router\.\w+\(\s*"([^"]*\{[^"]*)"', isi)
    assert not berparameter, f"rute berparameter id: {berparameter}"


def test_setiap_rute_dijaga_izin():
    isi = (AKAR / "routes" / "user_signature_routes.py").read_text(encoding="utf-8")
    jumlah_rute = len(re.findall(r"@router\.(get|put|post|delete)\(", isi))
    jumlah_jaga = len(re.findall(r'require\(\s*"user_signature"', isi))
    assert jumlah_rute > 0
    assert jumlah_jaga == jumlah_rute


def test_modulnya_ada_di_matriks_izin():
    from constants.permission_matrix import MATRIX

    assert "user_signature" in MATRIX
    # read dan update harus terbuka untuk level 1: SETIAP pengguna wajib
    # punya tanda tangan, termasuk yang paling junior.
    assert MATRIX["user_signature"][0] == 1
    assert MATRIX["user_signature"][2] == 1


# ---------------------------------------------------------------------------
# 2-3. Pemeriksaan isi berkas
# ---------------------------------------------------------------------------


def test_png_sah_diterima_beserta_ukurannya():
    hasil = UserSignatureController._bongkar(uri(png(720, 240)))
    assert "error" not in hasil
    assert hasil["width"] == 720
    assert hasil["height"] == 240


def test_berkas_yang_MENGAKU_png_ditolak():
    # Awalannya benar, isinya bukan PNG sama sekali.
    palsu = "data:image/png;base64," + base64.b64encode(b"%PDF-1.7 bukan png").decode()
    hasil = UserSignatureController._bongkar(palsu)
    assert hasil.get("error") == "SIGNATURE_MUST_BE_PNG"


def test_jpeg_ditolak():
    # JPEG tidak punya kanal alfa: yang tertempel di dokumen akan berupa
    # kotak putih menutupi garis tanda tangan tercetak di bawahnya.
    jpeg = b"\xff\xd8\xff\xe0" + b"\x00" * 64
    hasil = UserSignatureController._bongkar(
        "data:image/png;base64," + base64.b64encode(jpeg).decode()
    )
    assert hasil.get("error") == "SIGNATURE_MUST_BE_PNG"


def test_awalan_lain_ditolak():
    for buruk in (
        "data:image/jpeg;base64,AAAA",
        "data:text/html;base64,AAAA",
        "https://contoh.id/ttd.png",
        "",
        None,
    ):
        assert "error" in UserSignatureController._bongkar(buruk)


def test_base64_rusak_ditolak_tanpa_melempar():
    hasil = UserSignatureController._bongkar("data:image/png;base64,@@@bukan-base64")
    assert hasil.get("error") == "SIGNATURE_INVALID_ENCODING"


def test_berkas_kebesaran_ditolak():
    besar = b"\x89PNG\r\n\x1a\n" + b"\x00" * (BATAS_BITA + 1)
    hasil = UserSignatureController._bongkar(uri(besar))
    assert hasil.get("error") == "SIGNATURE_TOO_LARGE"


def test_gambar_berpiksel_tak_masuk_akal_ditolak():
    hasil = UserSignatureController._bongkar(uri(png(9000, 10)))
    assert hasil.get("error") == "SIGNATURE_BAD_SIZE"


@pytest.mark.asyncio
async def test_muatan_buruk_TIDAK_menyentuh_basis_data():
    # Penolakan yang tetap menulis adalah penolakan yang tidak menolak apa
    # pun.
    with patch.object(UserSignatureRepository, "simpan", AsyncMock()) as simpan:
        hasil = await UserSignatureController.simpan(7, "data:image/png;base64,@@")
    assert "error" in hasil
    simpan.assert_not_awaited()


# ---------------------------------------------------------------------------
# 4-5. Penyimpanan
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_menyimpan_dua_kali_MENGGANTI_bukan_menumpuk():
    dijalankan = []

    async def execute(q, *a, **k):
        dijalankan.append(str(q))

    with patch.object(usr.database, "execute", AsyncMock(side_effect=execute)):
        await UserSignatureRepository.simpan(7, png(), 720, 240)

    sql = dijalankan[0].lower()
    assert "on duplicate key update" in sql, sql


@pytest.mark.asyncio
async def test_punya_tidak_menarik_kolom_gambar():
    tangkap = {}

    async def fetch_val(q, *a, **k):
        tangkap["q"] = str(q)
        return None

    with patch.object(usr.database, "fetch_val", AsyncMock(side_effect=fetch_val)):
        await UserSignatureRepository.punya(7)

    sql = tangkap["q"].lower()
    assert "image" not in sql, sql
    assert "user_signatures.id" in sql, sql


@pytest.mark.asyncio
async def test_status_menjawab_ada_atau_tidak():
    with patch.object(UserSignatureRepository, "punya", AsyncMock(return_value=True)):
        assert await UserSignatureController.status(7) == {"hasSignature": True}
    with patch.object(UserSignatureRepository, "punya", AsyncMock(return_value=False)):
        assert await UserSignatureController.status(7) == {"hasSignature": False}


@pytest.mark.asyncio
async def test_milik_sendiri_mengembalikan_data_uri_yang_dapat_dipakai_kembali():
    asli = png(100, 40)
    with patch.object(
        UserSignatureRepository,
        "ambil",
        AsyncMock(return_value={"image": asli, "width": 100, "height": 40}),
    ):
        hasil = await UserSignatureController.milik_sendiri(7)

    assert hasil["image"].startswith("data:image/png;base64,")
    # Bolak-balik harus menghasilkan bita yang SAMA PERSIS: tanda tangan yang
    # berubah sebita pun sudah bukan tanda tangan yang sama.
    kembali = UserSignatureController._bongkar(hasil["image"])
    assert kembali["data"] == asli


@pytest.mark.asyncio
async def test_belum_punya_menjawab_404_bukan_gambar_kosong():
    with patch.object(UserSignatureRepository, "ambil", AsyncMock(return_value=None)):
        hasil = await UserSignatureController.milik_sendiri(7)
    assert hasil["status"] == 404
