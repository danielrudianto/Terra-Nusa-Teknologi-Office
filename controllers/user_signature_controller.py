import base64
import binascii
import struct

from repository.audit_log_repository import AuditLogRepository
from utils.transaksi import atomik
from repository.user_signature_repository import UserSignatureRepository
from utils.sidik_ttd import kemiripan as hitung_kemiripan, sidik, tingkat

#: Batas ukuran berkas tanda tangan.
#:
#: Papan tanda tangan menghasilkan PNG 720x240 bertinta hitam — biasanya di
#: bawah 30 KB. 256 KB memberi ruang lebar untuk layar beresolusi tinggi dan
#: tetap menutup pengunggahan foto sebagai "tanda tangan".
BATAS_BITA = 256 * 1024

#: Ukuran piksel yang masuk akal untuk sebuah tanda tangan.
BATAS_SISI = 4000

#: Delapan bita pembuka setiap berkas PNG.
PNG_AJAIB = b"\x89PNG\r\n\x1a\n"

AWALAN = "data:image/png;base64,"


def _ukuran_png(data: bytes) -> tuple[int, int] | None:
    """
    Lebar x tinggi dari kepala IHDR, tanpa pustaka gambar.

    PNG menaruh IHDR sebagai bongkah pertama, selalu pada offset yang sama.
    Membaca dua bilangan 32-bit di sana jauh lebih murah daripada memasang
    Pillow di server hanya untuk mengetahui ukuran.
    """
    if len(data) < 24 or data[12:16] != b"IHDR":
        return None
    lebar, tinggi = struct.unpack(">II", data[16:24])
    return lebar, tinggi


#: Entitas jejak audit untuk tanda tangan.
ENTITAS = "user_signatures"


def _heksa(nilai: int | None) -> str | None:
    return None if nilai is None else format(int(nilai), "016x")


def _dari_heksa(teks) -> int | None:
    try:
        return int(str(teks), 16)
    except (TypeError, ValueError):
        return None


class UserSignatureController:
    @staticmethod
    async def status(user_id: int):
        """
        Keadaan tanda tangan seseorang, untuk layar.

        Tiga keadaan, bukan dua: belum punya, punya, dan punya-tetapi-sedang
        menunggu persetujuan penggantian. Tanpa yang ketiga, orang yang sudah
        mengajukan akan mengajukan lagi karena layarnya tidak menyebut apa pun
        sedang berjalan.
        """
        tertunda = await UserSignatureRepository.tertunda_milik(user_id)
        return {
            "hasSignature": await UserSignatureRepository.punya(user_id),
            "pending": bool(tertunda),
            "pendingSince": tertunda.get("createdAt") if tertunda else None,
        }

    @staticmethod
    async def _periksa_kemiripan(user_id: int, sidik_baru: int | None):
        """
        Bandingkan sidik baru dengan SELURUH pengguna lain.

        Hasilnya MENANDAI, tidak pernah MENOLAK — lihat `utils/sidik_ttd.py`.
        Dua orang yang sama-sama menandatangani dengan coretan sederhana dapat
        berkemiripan tinggi tanpa seorang pun berniat buruk, dan menolak tanda
        tangan orang jujur pada fitur yang WAJIB dimiliki adalah kegagalan
        yang lebih buruk daripada melewatkan satu kemiripan.
        """
        if sidik_baru is None:
            return {"similarity": None, "similarTo": None, "similarName": None,
                    "level": None}

        terdekat = {"similarity": None, "similarTo": None, "similarName": None,
                    "level": None}
        for lain in await UserSignatureRepository.sidik_orang_lain(user_id):
            nilai = hitung_kemiripan(sidik_baru, _dari_heksa(lain.get("fingerprint")))
            if nilai is None:
                continue
            if terdekat["similarity"] is None or nilai > terdekat["similarity"]:
                terdekat = {
                    "similarity": nilai,
                    "similarTo": lain.get("userID"),
                    "similarName": lain.get("name"),
                    "level": tingkat(nilai),
                }
        return terdekat

    @staticmethod
    async def milik_sendiri(user_id: int):
        """
        Tanda tangan MILIK PEMINTA, sebagai data-URI.

        Tidak ada endpoint yang mengembalikan tanda tangan orang lain, dan
        itu disengaja. Gambar tanda tangan adalah stempel: begitu ia sampai
        di peramban seseorang, ia dapat disimpan dan ditempelkan ke dokumen
        apa pun di luar sistem ini. Pencapan pada dokumen resmi karena itu
        dikerjakan SERVER saat persetujuan, bukan dengan mengirimkan
        gambarnya ke layar.
        """
        row = await UserSignatureRepository.ambil(user_id)
        if isinstance(row, dict) and "error" in row:
            return row
        if not row:
            return {"error": "Signature not found", "status": 404}
        return {
            "image": AWALAN + base64.b64encode(row["image"]).decode("ascii"),
            "width": row.get("width"),
            "height": row.get("height"),
            "updatedAt": row.get("updatedAt") or row.get("createdAt"),
        }

    @staticmethod
    def _bongkar(data_uri: str):
        """
        data-URI -> bita PNG yang sudah diperiksa, atau dict galat.

        Yang diperiksa ISI berkasnya, bukan namanya: awalan `data:image/png`
        ditulis pengirim, jadi ia keterangan, bukan bukti. Tanpa memeriksa
        bita ajaibnya, satu berkas apa pun — skrip, PDF, gambar berpenyusup —
        dapat disimpan sebagai "tanda tangan" dan kelak dilayani kembali.
        """
        teks = (data_uri or "").strip()
        if not teks.startswith(AWALAN):
            return {"error": "SIGNATURE_MUST_BE_PNG", "status": 400}

        try:
            data = base64.b64decode(teks[len(AWALAN):], validate=True)
        except (binascii.Error, ValueError):
            return {"error": "SIGNATURE_INVALID_ENCODING", "status": 400}

        if not data:
            return {"error": "SIGNATURE_EMPTY", "status": 400}
        if len(data) > BATAS_BITA:
            return {"error": "SIGNATURE_TOO_LARGE", "status": 400}
        if not data.startswith(PNG_AJAIB):
            return {"error": "SIGNATURE_MUST_BE_PNG", "status": 400}

        ukuran = _ukuran_png(data)
        if not ukuran:
            return {"error": "SIGNATURE_MUST_BE_PNG", "status": 400}
        lebar, tinggi = ukuran
        if lebar <= 0 or tinggi <= 0 or lebar > BATAS_SISI or tinggi > BATAS_SISI:
            return {"error": "SIGNATURE_BAD_SIZE", "status": 400}

        return {"data": data, "width": lebar, "height": tinggi}

    @staticmethod
    @atomik
    async def simpan(user_id: int, data_uri: str):
        """
        Simpan tanda tangan.

        YANG PERTAMA BERLAKU SEKETIKA; PERGANTIAN MENUNGGU PERSETUJUAN.

        Bedanya bukan kelonggaran. Yang pertama tidak menimpa apa pun, dan
        setiap pengguna WAJIB punya — menahannya berarti orang baru tidak
        dapat bekerja sampai ada direktur yang sempat menekan tombol.
        Pergantian MENGGANTI stempel yang sudah menempel pada dokumen yang
        beredar, dan di situlah pemalsuan dan penyangkalan bisa lewat.
        """
        hasil = UserSignatureController._bongkar(data_uri)
        if "error" in hasil:
            return hasil

        sidik_baru = sidik(hasil["data"])
        mirip = await UserSignatureController._periksa_kemiripan(user_id, sidik_baru)
        sudah_punya = await UserSignatureRepository.punya(user_id)

        if not sudah_punya:
            simpan = await UserSignatureRepository.simpan(
                user_id,
                hasil["data"],
                hasil["width"],
                hasil["height"],
                _heksa(sidik_baru),
            )
            if isinstance(simpan, dict) and "error" in simpan:
                return simpan
            # Dicatat sebagai versi pertama, bukan tidak dicatat sama sekali:
            # riwayatnyalah yang kelak menjawab penyangkalan.
            await UserSignatureRepository.buat_permintaan(
                user_id,
                hasil["data"],
                hasil["width"],
                hasil["height"],
                _heksa(sidik_baru),
                mirip["similarity"],
                mirip["similarTo"],
                status="approved",
                catatan="tanda tangan pertama",
            )
            await AuditLogRepository.record(
                ENTITAS, user_id, "create",
                note="tanda tangan pertama; berlaku tanpa persetujuan",
            )
            return {
                "state": "active",
                "hasSignature": True,
                "similarity": mirip["similarity"],
                "similarLevel": mirip["level"],
                "similarName": mirip["similarName"],
            }

        await UserSignatureRepository.batalkan_tertunda(user_id)
        buat = await UserSignatureRepository.buat_permintaan(
            user_id,
            hasil["data"],
            hasil["width"],
            hasil["height"],
            _heksa(sidik_baru),
            mirip["similarity"],
            mirip["similarTo"],
        )
        if isinstance(buat, dict) and "error" in buat:
            return buat
        await AuditLogRepository.record(
            ENTITAS, user_id, "update",
            note="pergantian tanda tangan diajukan; menunggu persetujuan",
        )
        return {
            "state": "pending",
            "hasSignature": True,
            "similarity": mirip["similarity"],
            "similarLevel": mirip["level"],
            "similarName": mirip["similarName"],
        }

    # ------------------------------------------------------------------
    # Persetujuan — level 5
    # ------------------------------------------------------------------

    @staticmethod
    async def daftar_tertunda():
        """
        Antrean permintaan, BESERTA gambarnya.

        Ini satu-satunya tempat gambar tanda tangan orang lain keluar dari
        server, dan itu tidak terhindarkan: yang menyetujui harus MELIHAT apa
        yang disetujuinya. Dijaga `user_signature:approve`, yaitu level 5.
        """
        baris = await UserSignatureRepository.daftar_tertunda()
        if isinstance(baris, dict) and "error" in baris:
            return baris
        hasil = []
        for b in baris:
            hasil.append(
                {
                    "id": b["id"],
                    "userID": b["userID"],
                    "userName": b.get("userName"),
                    "image": AWALAN + base64.b64encode(b["image"]).decode("ascii"),
                    "width": b.get("width"),
                    "height": b.get("height"),
                    "similarity": b.get("similarity"),
                    "similarLevel": tingkat(b.get("similarity")),
                    "similarTo": b.get("similarTo"),
                    "createdAt": b.get("createdAt"),
                }
            )
        return hasil

    @staticmethod
    @atomik
    async def putuskan(
        request_id: int, setuju: bool, oleh: int, catatan: str | None = None
    ):
        """
        Setujui atau tolak satu permintaan.

        YANG MENGAJUKAN TIDAK BOLEH MENYETUJUI PERMINTAANNYA SENDIRI, berapa
        pun levelnya. Tanpa itu, seorang direktur dapat mengganti tanda
        tangannya kapan saja tanpa seorang pun tahu — dan justru tanda tangan
        direktur yang paling berharga untuk dipalsukan.

        Aturan yang sama sudah berlaku pada pembayaran keluar; ditegakkan di
        sini, bukan lewat beda level, karena beda level tidak dapat
        menyatakannya.
        """
        permintaan = await UserSignatureRepository.permintaan(request_id)
        if isinstance(permintaan, dict) and "error" in permintaan:
            return permintaan
        if not permintaan:
            return {"error": "Signature request not found", "status": 404}
        if permintaan["status"] != "pending":
            return {"error": "SIGNATURE_REQUEST_ALREADY_DECIDED", "status": 400}
        if int(permintaan["userID"]) == int(oleh):
            return {"error": "SIGNATURE_SELF_APPROVAL", "status": 403}

        terputus = await UserSignatureRepository.putuskan(
            request_id, "approved" if setuju else "rejected", oleh, catatan
        )
        if isinstance(terputus, dict) and "error" in terputus:
            return terputus

        if setuju:
            simpan = await UserSignatureRepository.simpan(
                permintaan["userID"],
                permintaan["image"],
                permintaan.get("width"),
                permintaan.get("height"),
                permintaan.get("fingerprint"),
                disetujui_oleh=oleh,
            )
            if isinstance(simpan, dict) and "error" in simpan:
                return simpan

        await AuditLogRepository.record(
            ENTITAS,
            permintaan["userID"],
            "approve" if setuju else "reject",
            note=catatan
            or ("pergantian tanda tangan disetujui" if setuju else "pergantian ditolak"),
        )
        return {"ok": True, "state": "active" if setuju else "rejected"}

    @staticmethod
    async def riwayat(user_id: int):
        return await UserSignatureRepository.riwayat(user_id)
