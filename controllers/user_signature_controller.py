import base64
import binascii
import struct

from repository.user_signature_repository import UserSignatureRepository

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


class UserSignatureController:
    @staticmethod
    async def status(user_id: int):
        return {"hasSignature": await UserSignatureRepository.punya(user_id)}

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
    async def simpan(user_id: int, data_uri: str):
        hasil = UserSignatureController._bongkar(data_uri)
        if "error" in hasil:
            return hasil
        simpan = await UserSignatureRepository.simpan(
            user_id, hasil["data"], hasil["width"], hasil["height"]
        )
        if isinstance(simpan, dict) and "error" in simpan:
            return simpan
        return {"hasSignature": True, "width": hasil["width"], "height": hasil["height"]}
