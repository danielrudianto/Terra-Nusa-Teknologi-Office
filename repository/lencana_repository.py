"""
Hitungan "menunggu SAYA" untuk lencana di menu samping.

MENGAPA "MENUNGGU SAYA", BUKAN "SEMUA YANG TERTUNDA"

Hitungan global tidak pernah nol pada perusahaan yang jalan. Dalam dua minggu
setiap orang berhenti melihat titik merahnya — dan itu kelas kegagalan yang
sama seperti pemeriksa yang selalu merah: keluaran yang selalu memuat sesuatu
yang selalu boleh diabaikan mengajari pembacanya mengabaikan seluruhnya,
termasuk yang berikutnya yang sungguhan.

Lencana yang BISA nol adalah lencana yang dilihat orang. Karena itu tiap
hitungan di sini mencerminkan aturan wewenang yang sama persis dengan yang
menjaga tombolnya — termasuk pembuat ≠ penyetuju.

DAN ADA ALASAN KEDUA YANG LEBIH SERIUS

Hitungan yang tidak menyaring wilayah departemen membocorkan keberadaan
dokumen yang tidak boleh dilihat penggunanya. Angka bukan isi, tetapi angka
tetap keterangan: "ada 3 slip gaji menunggu" pada layar orang yang tidak
berhak melihat slip gaji sudah menyatakan lebih daripada yang seharusnya.

SATU PERMINTAAN, BUKAN EMPAT

Seluruh hitungan dikembalikan sekaligus. Satu lencana per permintaan berarti
empat permintaan pada setiap perpindahan halaman, dan menu samping tampil di
SETIAP halaman.

YANG TIDAK BOLEH DILAKUKAN DI SINI

Gagal menghitung TIDAK BOLEH menjatuhkan halamannya. Menu samping ada di
setiap layar; satu kueri yang bermasalah tidak boleh membuat seluruh aplikasi
tidak dapat dibuka. Yang gagal dikembalikan sebagai `None` — dan layar
menampilkannya sebagai tanpa lencana, bukan sebagai nol. Nol berarti "tidak
ada yang menunggu"; itu pernyataan yang berbeda, dan menyamakannya membuat
pengguna mengira pekerjaannya sudah habis.
"""

from datetime import date
from typing import Any, Dict

from utils.database import database
from utils.logger_utils import log_error
from utils.permission import (
    boleh_memeriksa,
    boleh_memeriksa_sendiri,
    boleh_menyetujui_bap_cop,
    boleh_menyetujui_cop,
    boleh_menyetujui_sendiri,
    boleh_menyetujui_yang_diperiksanya,
    is_allowed,
)


async def _hitung(sql: str, nilai: Dict[str, Any]) -> int:
    baris = await database.fetch_one(sql, nilai)
    return int(baris["jumlah"]) if baris else 0


class LencanaRepository:
    """Hitungan pekerjaan yang menunggu seorang pengguna."""

    @staticmethod
    async def purchase_order(user: dict, level: int, departemen: set) -> int:
        """
        SPK yang menunggu pengguna ini — memeriksa ATAU menyetujui.

        Dua tahap berbeda dengan dua wewenang berbeda, dijumlah menjadi satu
        angka karena yang membaca menu hanya perlu tahu "ada yang menunggu
        saya di sini". Rinciannya ada di layarnya.

        Dokumen BUATANNYA SENDIRI dikecualikan, kecuali bagi level yang
        memang boleh — sama seperti tombolnya. Tanpa itu, yang mencatat
        sepuluh SPK melihat angka sepuluh yang tidak dapat ia turunkan
        sendiri, dan lencananya berubah menjadi penghitung pekerjaan orang
        lain.
        """
        total = 0
        uid = user["id"]

        if boleh_memeriksa(level, departemen):
            syarat = [
                "isDelete = 0",
                "isChecked = 0",
                "status = 'draft'",
            ]
            nilai: Dict[str, Any] = {}
            if not boleh_memeriksa_sendiri(level):
                syarat.append("createdBy <> :uid")
                nilai["uid"] = uid
            total += await _hitung(
                f"SELECT COUNT(*) AS jumlah FROM purchase_orders "
                f"WHERE {' AND '.join(syarat)}",
                nilai,
            )

        if await is_allowed(user, "purchase_order", "approve"):
            syarat = [
                "isDelete = 0",
                "isChecked = 1",
                "isApproved = 0",
                "status = 'draft'",
            ]
            nilai = {}
            if not boleh_menyetujui_sendiri(level):
                syarat.append("createdBy <> :uid")
                nilai["uid"] = uid
            if not boleh_menyetujui_yang_diperiksanya(level):
                # Yang MEMERIKSA dokumen ini tidak boleh pula menyetujuinya.
                # Tanpa baris ini, lencananya menghitung dokumen yang tombol
                # setujuinya justru ditolak server saat ditekan — dan yang
                # membacanya menyimpulkan lencananya rusak.
                syarat.append("(checkedBy IS NULL OR checkedBy <> :uid2)")
                nilai["uid2"] = uid
            total += await _hitung(
                f"SELECT COUNT(*) AS jumlah FROM purchase_orders "
                f"WHERE {' AND '.join(syarat)}",
                nilai,
            )

        return total

    @staticmethod
    async def reimbursement(user: dict, level: int) -> int:
        """Reimbursement yang menunggu persetujuan pengguna ini."""
        if not await is_allowed(user, "reimbursement", "approve"):
            return 0

        syarat = ["isDelete = 0", "isApprove = 0"]
        nilai: Dict[str, Any] = {}
        if not boleh_menyetujui_sendiri(level):
            syarat.append("createdBy <> :uid")
            nilai["uid"] = user["id"]

        return await _hitung(
            f"SELECT COUNT(*) AS jumlah FROM reimbursements "
            f"WHERE {' AND '.join(syarat)}",
            nilai,
        )

    @staticmethod
    async def certificate_of_payment(user: dict, level: int) -> int:
        """
        CoP yang menunggu pengguna ini — gerbang 1 (BAP) atau gerbang 3 (CoP).

        Gerbang 2 (menyusun CoP, mengisi harga) sengaja TIDAK dihitung. Ia
        pekerjaan menyusun, bukan pekerjaan memutuskan — dan yang menyusun
        biasanya sudah tahu dokumen mana miliknya. Memasukkannya membuat
        angkanya membengkak oleh pekerjaan yang tidak menunggu keputusan
        siapa pun.
        """
        total = 0
        uid = user["id"]
        nilai: Dict[str, Any] = {"uid": uid}

        kecuali_diri = "" if boleh_menyetujui_sendiri(level) else " AND createdBy <> :uid"

        if boleh_menyetujui_bap_cop(level):
            total += await _hitung(
                "SELECT COUNT(*) AS jumlah FROM certificate_of_payments "
                "WHERE isDelete = 0 AND status <> 'cancelled' "
                f"  AND isBapApproved = 0{kecuali_diri}",
                nilai if kecuali_diri else {},
            )

        if boleh_menyetujui_cop(level):
            total += await _hitung(
                "SELECT COUNT(*) AS jumlah FROM certificate_of_payments "
                "WHERE isDelete = 0 AND status <> 'cancelled' "
                "  AND isBapApproved = 1 AND isCopCreated = 1 AND isApproved = 0"
                f"{kecuali_diri}",
                nilai if kecuali_diri else {},
            )

        return total

    @staticmethod
    async def pembayaran(user: dict) -> int:
        """
        Rencana pembayaran KELUAR yang jatuh tempo sampai HARI INI.

        Berbeda jenis dari tiga lainnya, dan perbedaannya perlu disadari: yang
        tiga menghitung KEPUTUSAN yang menunggu orang, yang ini menghitung
        TANGGAL yang sudah lewat. Ia tidak menunggu wewenang siapa pun — ia
        menunggu uang keluar.

        Yang sudah lewat IKUT dihitung, bukan hanya yang tepat hari ini.
        Rencana kemarin yang belum dibayar justru yang paling perlu terlihat,
        dan menyaringnya menjadi "hari ini saja" membuatnya hilang dari
        pandangan tepat pada hari ia menjadi terlambat.
        """
        if not await is_allowed(user, "payment_plan", "read"):
            return 0

        return await _hitung(
            "SELECT COUNT(*) AS jumlah FROM payment_plans "
            "WHERE isDelete = 0 "
            "  AND planType = 'keluar' "
            "  AND status = 'rencana' "
            "  AND date <= :hari_ini",
            {"hari_ini": date.today()},
        )

    @staticmethod
    async def semua(user: dict, level: int, departemen: set) -> Dict[str, Any]:
        """
        Seluruh hitungan sekaligus.

        Tiap modul dibungkus sendiri-sendiri: satu kueri yang bermasalah
        mengembalikan `None` untuk modulnya saja, dan tiga lainnya tetap
        terkirim. Menu samping tampil di SETIAP halaman — membiarkan satu
        hitungan menjatuhkan seluruh jawaban berarti satu kolom yang hilang
        membuat aplikasi tidak dapat dibuka.
        """
        hasil: Dict[str, Any] = {}

        async def coba(kunci: str, kerjakan):
            try:
                hasil[kunci] = await kerjakan
            except Exception as e:
                log_error(f"Lencana {kunci} gagal dihitung: {e}")
                # None, BUKAN 0 — lihat catatan di kepala berkas.
                hasil[kunci] = None

        await coba(
            "purchase_order",
            LencanaRepository.purchase_order(user, level, departemen),
        )
        await coba("reimbursement", LencanaRepository.reimbursement(user, level))
        await coba(
            "certificate_of_payment",
            LencanaRepository.certificate_of_payment(user, level),
        )
        await coba("payment_plan", LencanaRepository.pembayaran(user))

        return hasil
