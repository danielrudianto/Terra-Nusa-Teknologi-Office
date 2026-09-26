"""
PERGANTIAN TANDA TANGAN — persetujuan level 5 dan deteksi kemiripan.

"kalau mau ganti tanda tangan harus ada persetujuan level 5 ya, takutnya
 pemalsuan"
"bisa ga ya kasih fungsi check tanda tangan yang terlalu mirip, bandingkan
 sama semua user di saat perubahan itu mau dilakukan"

Yang dijaga di sini:

  1. Tanda tangan PERTAMA berlaku seketika; PERGANTIAN tidak. Kalau yang
     pertama pun ditahan, orang baru terkunci di depan pintu yang wajib
     dilewati — dan tidak ada satu pun galat yang menjelaskan mengapa.
  2. Pergantian TIDAK mengubah tanda tangan yang berlaku sebelum disetujui.
     Ini kegagalan paling berbahaya: tanpa uji ini, penjagaannya dapat hilang
     sementara antreannya tetap terisi rapi — seolah bekerja.
  3. Yang mengajukan TIDAK BOLEH menyetujui permintaannya sendiri, berapa pun
     levelnya. Tanda tangan direktur justru yang paling berharga dipalsukan.
  4. Keputusan hanya sekali; permintaan yang sudah diputus tidak dapat
     diputus ulang.
  5. Kemiripan MENANDAI, bukan MENOLAK — dan bukti angkanya DIBEKUKAN pada
     permintaannya, bukan dihitung ulang saat dibaca.
  6. Sidik mengenali SALINAN, termasuk yang digeser tempatnya, dan tidak
     mengarang kemiripan pada tanda tangan yang tidak berhubungan.
"""

import base64
import io
import random
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image, ImageDraw

from controllers.user_signature_controller import UserSignatureController
from repository.user_signature_repository import UserSignatureRepository
from utils.sidik_ttd import (
    AMBANG_MIRIP,
    jarak,
    kemiripan,
    sidik,
    tingkat,
)


def coret(benih: int, geser: int = 0) -> bytes:
    """Tanda tangan buatan yang dapat diulang persis."""
    img = Image.new("RGBA", (720, 240), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rnd = random.Random(benih)
    titik = [(100 + geser, 150)]
    for _ in range(40):
        titik.append(
            (titik[-1][0] + rnd.randint(4, 14), 150 + rnd.randint(-40, 40))
        )
    d.line([(int(x), int(y)) for x, y in titik], fill=(17, 24, 39, 255), width=4)
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()


def uri(data: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(data).decode("ascii")


# ---------------------------------------------------------------------------
# 6. Sidiknya sendiri
# ---------------------------------------------------------------------------


def test_salinan_persis_terdeteksi():
    a = coret(1)
    assert kemiripan(sidik(a), sidik(a)) == 1.0
    assert tingkat(kemiripan(sidik(a), sidik(a))) == "sangat_mirip"


def test_salinan_yang_DIGESER_tempatnya_tetap_terdeteksi():
    # Tanpa pemotongan ke kotak tinta, yang paling menentukan sidiknya adalah
    # DI MANA orang membubuhkan tanda tangannya di papan.
    a = coret(1)
    b = coret(1, geser=250)
    assert kemiripan(sidik(a), sidik(b)) >= AMBANG_MIRIP


def test_tanda_tangan_yang_TIDAK_berhubungan_tidak_ditandai():
    # Penjaga arah sebaliknya: ambang yang terlalu longgar menandai semua
    # orang, dan penanda yang selalu menyala berhenti dibaca.
    ditandai = 0
    pasangan = 0
    sidik_semua = [sidik(coret(i)) for i in range(25)]
    for i in range(len(sidik_semua)):
        for j in range(i + 1, len(sidik_semua)):
            pasangan += 1
            if tingkat(kemiripan(sidik_semua[i], sidik_semua[j])):
                ditandai += 1
    assert ditandai == 0, f"{ditandai} dari {pasangan} pasangan acak ditandai"


def test_gambar_kosong_tidak_bersidik():
    # None, bukan 0: nol adalah sidik yang sah, dan menyamakan keduanya
    # membuat setiap gambar kosong "sangat mirip" dengan gambar kosong lain.
    kosong = Image.new("RGBA", (720, 240), (0, 0, 0, 0))
    b = io.BytesIO()
    kosong.save(b, "PNG")
    assert sidik(b.getvalue()) is None
    assert kemiripan(None, 123) is None
    assert tingkat(None) is None


def test_jarak_tidak_pernah_melebihi_64_bit():
    assert jarak(0, (1 << 64) - 1) == 64
    assert jarak(5, 5) == 0


# ---------------------------------------------------------------------------
# 1-2. Pertama vs pergantian
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tanda_tangan_pertama_BERLAKU_seketika():
    with patch.object(UserSignatureRepository, "punya", AsyncMock(return_value=False)), \
         patch.object(
             UserSignatureRepository, "sidik_orang_lain", AsyncMock(return_value=[])
         ), \
         patch.object(
             UserSignatureRepository, "simpan", AsyncMock(return_value={"ok": True})
         ) as simpan, \
         patch.object(
             UserSignatureRepository,
             "buat_permintaan",
             AsyncMock(return_value={"id": 1}),
         ) as permintaan:
        hasil = await UserSignatureController.simpan(7, uri(coret(1)))

    assert hasil["state"] == "active"
    simpan.assert_awaited()
    # Tetap dicatat sebagai versi pertama: riwayatnyalah yang kelak menjawab
    # penyangkalan "itu bukan tanda tangan saya".
    assert permintaan.await_args.kwargs["status"] == "approved"


@pytest.mark.asyncio
async def test_PERGANTIAN_tidak_menyentuh_tanda_tangan_yang_berlaku():
    with patch.object(UserSignatureRepository, "punya", AsyncMock(return_value=True)), \
         patch.object(
             UserSignatureRepository, "sidik_orang_lain", AsyncMock(return_value=[])
         ), \
         patch.object(UserSignatureRepository, "batalkan_tertunda", AsyncMock()), \
         patch.object(
             UserSignatureRepository, "simpan", AsyncMock(return_value={"ok": True})
         ) as simpan, \
         patch.object(
             UserSignatureRepository,
             "buat_permintaan",
             AsyncMock(return_value={"id": 9}),
         ):
        hasil = await UserSignatureController.simpan(7, uri(coret(2)))

    assert hasil["state"] == "pending"
    simpan.assert_not_awaited()


@pytest.mark.asyncio
async def test_mengajukan_dua_kali_menutup_yang_lama():
    # Tanpa ini, antreannya berisi dua permintaan dari orang yang sama dan
    # penyetuju harus menebak mana yang terakhir.
    with patch.object(UserSignatureRepository, "punya", AsyncMock(return_value=True)), \
         patch.object(
             UserSignatureRepository, "sidik_orang_lain", AsyncMock(return_value=[])
         ), \
         patch.object(
             UserSignatureRepository, "batalkan_tertunda", AsyncMock()
         ) as batal, \
         patch.object(
             UserSignatureRepository,
             "buat_permintaan",
             AsyncMock(return_value={"id": 9}),
         ):
        await UserSignatureController.simpan(7, uri(coret(2)))

    batal.assert_awaited_once_with(7)


# ---------------------------------------------------------------------------
# 3-4. Persetujuan
# ---------------------------------------------------------------------------


def _permintaan(user_id=7, status="pending"):
    return {
        "id": 9,
        "userID": user_id,
        "status": status,
        "image": coret(1),
        "width": 720,
        "height": 240,
        "fingerprint": "abcdef0123456789",
    }


@pytest.mark.asyncio
async def test_disetujui_direktur_lain_menjadikannya_berlaku():
    with patch.object(
        UserSignatureRepository, "permintaan", AsyncMock(return_value=_permintaan())
    ), patch.object(
        UserSignatureRepository, "putuskan", AsyncMock(return_value=1)
    ), patch.object(
        UserSignatureRepository, "simpan", AsyncMock(return_value={"ok": True})
    ) as simpan:
        hasil = await UserSignatureController.putuskan(9, True, oleh=3)

    assert hasil["state"] == "active"
    assert simpan.await_args.args[0] == 7
    assert simpan.await_args.kwargs["disetujui_oleh"] == 3


@pytest.mark.asyncio
async def test_TIDAK_BOLEH_menyetujui_permintaan_sendiri():
    with patch.object(
        UserSignatureRepository, "permintaan", AsyncMock(return_value=_permintaan(7))
    ), patch.object(
        UserSignatureRepository, "putuskan", AsyncMock()
    ) as putuskan, patch.object(
        UserSignatureRepository, "simpan", AsyncMock()
    ) as simpan:
        hasil = await UserSignatureController.putuskan(9, True, oleh=7)

    assert hasil["status"] == 403
    assert hasil["error"] == "SIGNATURE_SELF_APPROVAL"
    putuskan.assert_not_awaited()
    simpan.assert_not_awaited()


@pytest.mark.asyncio
async def test_penolakan_tidak_mengubah_tanda_tangan_yang_berlaku():
    with patch.object(
        UserSignatureRepository, "permintaan", AsyncMock(return_value=_permintaan())
    ), patch.object(
        UserSignatureRepository, "putuskan", AsyncMock(return_value=1)
    ), patch.object(
        UserSignatureRepository, "simpan", AsyncMock()
    ) as simpan:
        hasil = await UserSignatureController.putuskan(9, False, oleh=3, catatan="bukan dia")

    assert hasil["state"] == "rejected"
    simpan.assert_not_awaited()


@pytest.mark.asyncio
async def test_permintaan_yang_sudah_diputus_tidak_dapat_diputus_lagi():
    with patch.object(
        UserSignatureRepository,
        "permintaan",
        AsyncMock(return_value=_permintaan(status="approved")),
    ), patch.object(UserSignatureRepository, "simpan", AsyncMock()) as simpan:
        hasil = await UserSignatureController.putuskan(9, True, oleh=3)

    assert hasil["status"] == 400
    simpan.assert_not_awaited()


@pytest.mark.asyncio
async def test_permintaan_yang_tidak_ada_menjawab_404():
    with patch.object(
        UserSignatureRepository, "permintaan", AsyncMock(return_value=None)
    ):
        hasil = await UserSignatureController.putuskan(9, True, oleh=3)
    assert hasil["status"] == 404


# ---------------------------------------------------------------------------
# 5. Kemiripan: menandai, tidak menolak
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tanda_tangan_yang_MIRIP_tetap_tersimpan_tetapi_DITANDAI():
    sama = coret(1)
    lain = [{"userID": 3, "name": "Budi", "fingerprint": format(sidik(sama), "016x")}]

    with patch.object(UserSignatureRepository, "punya", AsyncMock(return_value=True)), \
         patch.object(
             UserSignatureRepository, "sidik_orang_lain", AsyncMock(return_value=lain)
         ), \
         patch.object(UserSignatureRepository, "batalkan_tertunda", AsyncMock()), \
         patch.object(
             UserSignatureRepository,
             "buat_permintaan",
             AsyncMock(return_value={"id": 9}),
         ) as permintaan:
        hasil = await UserSignatureController.simpan(7, uri(sama))

    # Ditandai...
    assert hasil["similarLevel"] == "sangat_mirip"
    assert hasil["similarName"] == "Budi"
    # ...tetapi TIDAK ditolak.
    assert hasil["state"] == "pending"
    permintaan.assert_awaited()
    # Buktinya dibekukan pada permintaannya.
    assert permintaan.await_args.args[5] == 1.0
    assert permintaan.await_args.args[6] == 3


@pytest.mark.asyncio
async def test_yang_paling_mirip_yang_dilaporkan_bukan_yang_pertama_ditemukan():
    dekat = coret(1)
    lain = [
        {"userID": 2, "name": "Jauh", "fingerprint": format(sidik(coret(5)), "016x")},
        {"userID": 3, "name": "Dekat", "fingerprint": format(sidik(dekat), "016x")},
        {"userID": 4, "name": "Jauh2", "fingerprint": format(sidik(coret(9)), "016x")},
    ]
    with patch.object(UserSignatureRepository, "punya", AsyncMock(return_value=False)), \
         patch.object(
             UserSignatureRepository, "sidik_orang_lain", AsyncMock(return_value=lain)
         ), \
         patch.object(
             UserSignatureRepository, "simpan", AsyncMock(return_value={"ok": True})
         ), \
         patch.object(
             UserSignatureRepository,
             "buat_permintaan",
             AsyncMock(return_value={"id": 1}),
         ):
        hasil = await UserSignatureController.simpan(7, uri(dekat))

    assert hasil["similarName"] == "Dekat"


@pytest.mark.asyncio
async def test_sidik_orang_lain_TIDAK_menarik_kolom_gambar():
    # Membandingkan sidik tidak perlu blob. Menariknya berarti puluhan
    # tanda tangan berpindah dari basis data untuk tiap penyimpanan.
    import repository.user_signature_repository as usr

    tangkap = []

    async def fetch_all(q, *a, **k):
        tangkap.append(str(q).lower())
        return []

    with patch.object(usr.database, "fetch_all", AsyncMock(side_effect=fetch_all)):
        await UserSignatureRepository.sidik_orang_lain(7)

    assert tangkap, "tidak ada kueri dijalankan"
    for sql in tangkap:
        assert ".image" not in sql, sql
        assert "fingerprint" in sql
